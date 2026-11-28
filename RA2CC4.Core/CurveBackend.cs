using System.Globalization;
using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace RA2CC4.Core;

public static class CurveBackend
{
    private static readonly int[] PointOptions = [32,64,96,128,160,192,256,320,384,512,640,768,1024,2048,4096];
    private static readonly string[] Modes = ["noaccel","classic/linear","jump","natural","synchronous","motivity (1.6.1)","power","lut"];
    private static readonly string ConfigDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "CurveGen");
    private static readonly string ConfigPath = Path.Combine(ConfigDirectory, "config.json");
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static Task<JsonDocument> SendAsync(object request, IProgress<GenerationProgress>? progress = null)
    {
        var serializedRequest = JsonSerializer.Serialize(request);
        using var requestDocument = JsonDocument.Parse(serializedRequest);
        var action = Str(requestDocument.RootElement, "action", "fields");
        if (action is "generate" or "import_settings")
            return Task.Run(() => Execute(serializedRequest, progress));
        return Task.FromResult(Execute(serializedRequest));
    }

    private static JsonDocument Execute(string serializedRequest, IProgress<GenerationProgress>? progress = null)
    {
        try
        {
            using var doc = JsonDocument.Parse(serializedRequest);
            var result = Handle(doc.RootElement, progress);
            using var payload = JsonDocument.Parse(JsonSerializer.Serialize(result, JsonOptions));
            var response = new Dictionary<string, object?> { ["ok"] = true };
            if (payload.RootElement.ValueKind == JsonValueKind.Object)
                foreach (var property in payload.RootElement.EnumerateObject()) response[property.Name] = property.Value.Clone();
            else response["value"] = payload.RootElement.Clone();
            return JsonDocument.Parse(JsonSerializer.Serialize(response, JsonOptions));
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(ex.Message, ex);
        }
    }

    private static object Handle(JsonElement r, IProgress<GenerationProgress>? progress = null)
    {
        var action = Str(r, "action", "fields");
        return action switch
        {
            "state" => new { config = LoadConfig() },
            "settings" => SettingsState(),
            "update_settings" => UpdateSettings(r),
            "save_draft" => SaveDraft(r),
            "update_release_catalog" => UpdateReleaseCatalog(r),
            "mark_update_prompted" => MarkUpdatePrompted(r),
            "fields" => new { fields = Fields(r) },
            "generate" => Generate(r, progress),
            "inspect_settings" => Inspect(r),
            "load_settings_profile" => LoadProfile(r),
            "import_settings" => ImportSettings(r),
            _ => throw new InvalidOperationException($"Unknown action: {action}")
        };
    }

    private static Dictionary<string, object?> LoadConfig()
    {
        foreach (var path in new[] { ConfigPath, Path.Combine(ConfigDirectory, "last_config.json"), Path.Combine(Environment.CurrentDirectory, "config.json") })
        {
            try
            {
                if (!File.Exists(path)) continue;
                var loaded = JsonSerializer.Deserialize<Dictionary<string, object?>>(File.ReadAllText(path));
                if (loaded is not null)
                {
                    MigratePowerStartDefault(loaded);
                    return loaded;
                }
            }
            catch (JsonException) { }
            catch (IOException) { }
        }
        return Defaults();
    }
    private static Dictionary<string, object?> Defaults() => new() { ["profile_name"]="New Profile", ["mode"]="natural", ["curve_type"]="gain", ["cap_mode"]="out", ["point_count"]=128, ["precision"]=6, ["args"]=new Dictionary<string,object?>(), ["vertical_mode"]="natural", ["vertical_curve_type"]="gain", ["vertical_cap_mode"]="out", ["vertical_args"]=new Dictionary<string,object?>() };
    private static void MigratePowerStartDefault(Dictionary<string, object?> config)
    {
        var root = JsonSerializer.SerializeToElement(config);
        if (Bool(root, "power_start_default_migrated", false)) return;
        Migrate("mode", "args");
        Migrate("vertical_mode", "vertical_args");
        config["power_start_default_migrated"] = true;
        Save(config);

        void Migrate(string modeKey, string argsKey)
        {
            if (!string.Equals(Convert.ToString(config.GetValueOrDefault(modeKey)), "power", StringComparison.OrdinalIgnoreCase)) return;
            if (!config.TryGetValue(argsKey, out var raw)) return;
            var args = raw switch
            {
                Dictionary<string, object?> dictionary => dictionary,
                JsonElement element when element.ValueKind == JsonValueKind.Object =>
                    JsonSerializer.Deserialize<Dictionary<string, object?>>(element.GetRawText()),
                _ => null,
            };
            if (args is null || !args.ContainsKey("output_offset") || Number(args["output_offset"], 0) != 0) return;
            args["output_offset"] = 1d;
            config[argsKey] = args;
        }
    }

    private static object SettingsState()
    {
        var config = LoadConfig();
        var rawAccelPath = Convert.ToString(config.GetValueOrDefault("rawaccel_path")) ?? "";
        var customCurvePath = Convert.ToString(config.GetValueOrDefault("customcurve_path")) ?? "";
        return new { config, rawaccel_valid = File.Exists(Path.Combine(rawAccelPath, "settings.json")), customcurve_valid = File.Exists(customCurvePath) };
    }
    private static object UpdateSettings(JsonElement r)
    {
        var c=LoadConfig();
        if (r.TryGetProperty("rawaccel_path", out var rawPath))
        {
            var path = (rawPath.GetString() ?? "").Trim();
            if (path.Length > 0 && !File.Exists(Path.Combine(path, "settings.json")))
                throw new InvalidOperationException("The RawAccel folder must contain settings.json.");
            c["rawaccel_path"] = path.Length == 0 ? "" : Path.GetFullPath(path);
        }
        if (r.TryGetProperty("customcurve_path", out var ccPath))
        {
            var path = (ccPath.GetString() ?? "").Trim();
            if (path.Length > 0 && (!File.Exists(path) || !Path.GetFileName(path).Equals("CustomCurve.exe", StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("Select the CustomCurve.exe application file.");
            c["customcurve_path"] = path.Length == 0 ? "" : Path.GetFullPath(path);
        }
        if(r.TryGetProperty("point_count",out var p)) { var n=p.GetInt32(); if(!PointOptions.Contains(n)) throw new InvalidOperationException("Select a supported output point count."); c["point_count"]=n; }
        if(r.TryGetProperty("precision",out var q)) { var n=q.GetInt32(); if(n<1||n>10) throw new InvalidOperationException("Select a precision from 1 to 10."); c["precision"]=n; }
        Save(c); return new { config=c };
    }

    private static object SaveDraft(JsonElement r)
    {
        var config = LoadConfig();
        var mode = MapMode(Str(r, "mode", "natural"));
        var curveType = Str(r, "curve_type", "gain");
        var capMode = MapCapMode(Str(r, "cap_mode", "out"));
        var vertical = Prop(r, "vertical");
        var verticalMode = MapMode(Str(vertical, "mode", mode));
        var verticalType = Str(vertical, "curve_type", curveType);
        var verticalCap = MapCapMode(Str(vertical, "cap_mode", capMode));
        var pointCount = Int(r, "point_count", 128);
        var precision = Int(r, "precision", 6);
        if (!PointOptions.Contains(pointCount)) pointCount = 128;
        if (precision is < 1 or > 10) precision = 6;
        config["profile_name"] = Str(r, "profile_name", "New Profile");
        config["mode"] = mode;
        config["curve_type"] = curveType;
        config["cap_mode"] = capMode;
        config["args"] = ReadArgs(mode, capMode, Prop(r, "args"));
        config["vertical_mode"] = verticalMode;
        config["vertical_curve_type"] = verticalType;
        config["vertical_cap_mode"] = verticalCap;
        config["vertical_args"] = ReadArgs(verticalMode, verticalCap, Prop(vertical, "args"));
        config["separate_vertical_curve"] = Bool(r, "separate_vertical_curve", false);
        config["point_count"] = pointCount;
        config["precision"] = precision;
        config["sensitivity_multiplier"] = Num(r, "sensitivity_multiplier", 1);
        config["yx_ratio"] = Num(r, "yx_ratio", 1);
        config["left_right_ratio"] = Num(r, "left_right_ratio", 1);
        config["up_down_ratio"] = Num(r, "up_down_ratio", 1);
        config["rotation"] = Num(r, "rotation", 0);
        config["angle_snap"] = Num(r, "angle_snap", 0);
        config["lp_norm"] = Num(r, "lp_norm", 2);
        config["output_dpi_enabled"] = Bool(r, "output_dpi_enabled", false);
        config["output_dpi"] = Num(r, "output_dpi", 1000);
        config["input_smoothing_ms"] = Num(r, "input_smoothing_ms", 0);
        config["output_smoothing_ms"] = Num(r, "output_smoothing_ms", 0);
        config["anisotropy_enabled"] = Bool(r, "anisotropy_enabled", false);
        config["domain_x"] = Num(r, "domain_x", 1);
        config["domain_y"] = Num(r, "domain_y", 1);
        config["range_x"] = Num(r, "range_x", 1);
        config["range_y"] = Num(r, "range_y", 1);
        config["rawaccel_path"] = Str(r, "rawaccel_path", Convert.ToString(config.GetValueOrDefault("rawaccel_path")) ?? "");
        config["customcurve_path"] = Str(r, "customcurve_path", Convert.ToString(config.GetValueOrDefault("customcurve_path")) ?? "");
        config.Remove("lp_norm_infinite");
        Save(config);
        return new { saved = true };
    }

    private static object UpdateReleaseCatalog(JsonElement r)
    {
        var catalog = Prop(r, "catalog");
        if (catalog.ValueKind != JsonValueKind.Object || !catalog.EnumerateObject().Any())
            throw new InvalidOperationException("The release catalog is empty or invalid.");
        var config = LoadConfig();
        config["release_catalog"] = catalog.Clone();
        config["latest_release"] = Str(r, "latest_release", "");
        config["release_checked_utc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture);
        Save(config);
        return new { saved = true };
    }

    private static object MarkUpdatePrompted(JsonElement r)
    {
        var config = LoadConfig();
        config["prompted_release"] = Str(r, "release", "");
        Save(config);
        return new { saved = true };
    }

    private static Dictionary<string,object?> DefaultsFor(string mode,string cap)
    {
        var d=new Dictionary<string,object?>();
        void Put(string k,double v)=>d[k]=v;
        switch(mode) {
            case "noaccel": break;
            case "natural": Put("input_offset",0); Put("decay_rate",.1); Put("limit",1.5); break;
            case "jump": Put("input_offset",0); Put("cap_x",15); Put("cap_y",1.5); Put("smooth",.5); break;
            case "synchronous": Put("input_offset",0); Put("gamma",1); Put("motivity",1.5); Put("sync_speed",5); Put("smooth",.5); break;
            case "motivity (1.6.1)": Put("growth_rate",1); Put("motivity",1.5); Put("midpoint",5); break;
            case "lut": d["lut_velocity"]=true; d["lookup_points"]=new[]{new[]{1.505035,0.85549892},new[]{4.375,3.30972978},new[]{13.51,15.17478447},new[]{140d,354.7026875}}; break;
            case "power": Put("output_offset",1); Put("scale",1); Put("exponent_power",.05); Put("cap_x",cap=="out"?0:15); Put("cap_y",cap=="in"?0:1.5); break;
            default: Put("input_offset",0); Put("acceleration",.005); Put("exponent",2); Put("cap_x",cap=="out"?0:15); Put("cap_y",cap=="in"?0:1.5); break;
        }
        return d;
    }
    private static object[] Fields(JsonElement r)
    {
        var mode=Str(r,"mode","natural"); var cap=Str(r,"cap_mode","out"); var a=DefaultsFor(mode,cap);
        if(r.TryGetProperty("args",out var old)&&old.ValueKind==JsonValueKind.Object) foreach(var p in old.EnumerateObject()) if(a.ContainsKey(p.Name)) a[p.Name]=p.Value.ValueKind==JsonValueKind.String?p.Value.GetString():p.Value.ToString();
        if (mode == "lut" && IsPreviousDefaultLookup(Lookup(a)))
            a["lookup_points"] = DefaultsFor(mode, cap)["lookup_points"];
        if(mode=="noaccel") return [];
        var labels=new Dictionary<string,string>{{"acceleration","Acceleration"},{"cap_x","Cap: Input"},{"cap_y","Cap: Output"},{"input_offset","Input Offset"},{"exponent","Power"},{"smooth","Smooth"},{"decay_rate","Decay Rate"},{"limit","Limit"},{"gamma","Gamma"},{"growth_rate","Growth Rate"},{"motivity","Motivity"},{"sync_speed","Sync Speed"},{"midpoint","Midpoint"},{"scale","Scale"},{"exponent_power","Exponent"},{"output_offset","Output Offset"},{"lookup_points","Lookup table"}};
        var orderedKeys = mode switch
        {
            "classic/linear" => cap == "io"
                ? new[] { "cap_type", "cap_x", "cap_y", "input_offset", "exponent" }
                : cap == "in"
                    ? new[] { "acceleration", "cap_type", "cap_x", "input_offset", "exponent" }
                    : new[] { "acceleration", "cap_type", "cap_y", "input_offset", "exponent" },
            "jump" => new[] { "smooth", "cap_x", "cap_y" },
            "natural" => new[] { "decay_rate", "input_offset", "limit" },
            "synchronous" => new[] { "gamma", "smooth", "motivity", "sync_speed" },
            "motivity (1.6.1)" => new[] { "growth_rate", "motivity", "midpoint" },
            "power" => cap == "io"
                ? new[] { "cap_type", "cap_x", "cap_y", "exponent_power", "output_offset" }
                : cap == "in"
                    ? new[] { "scale", "cap_type", "cap_x", "exponent_power", "output_offset" }
                    : new[] { "scale", "cap_type", "cap_y", "exponent_power", "output_offset" },
            "lut" => new[] { "lut_velocity", "lookup_points" },
            _ => a.Keys.ToArray(),
        };
        var list=new List<object>();
        foreach(var key in orderedKeys) {
            if (key == "cap_type")
            {
                list.Add(new { key, label = "Cap type", kind = "choice", choices = new[] { "Output", "Input", "Both" },
                    value = cap == "in" ? "Input" : cap == "io" ? "Both" : "Output" });
                continue;
            }
            if (!a.TryGetValue(key, out var val)) continue;
            if (mode == "classic/linear" && cap == "io" && key == "acceleration") continue;
            if (mode == "power" && cap == "io" && key == "scale") continue;
            if(key=="lut_velocity") { list.Add(new{key,label="Lookup mode",kind="choice",choices=new[]{"Velocity","Sensitivity"},value=Bool(val,true)?"Velocity":"Sensitivity"}); continue; }
            var number=Number(val,0); var min=key switch {"motivity"=>1.000000000001,"smooth"=>0,"sync_speed"=>1e-12,"midpoint"=>1e-6,"scale" or "exponent_power" or "growth_rate" or "gamma" or "acceleration" or "decay_rate" or "limit"=>1e-12,"exponent"=>1.000000000001,_=>0};
            var fieldValue = key == "lookup_points"
                ? string.Join("; ", Lookup(a).Select(point => $"{point.X.ToString("G17", CultureInfo.InvariantCulture)},{point.Y.ToString("G17", CultureInfo.InvariantCulture)}"))
                : number.ToString("G17",CultureInfo.InvariantCulture);
            var label = mode == "jump" && key == "cap_x" ? "Input"
                : mode == "jump" && key == "cap_y" ? "Output"
                : labels.GetValueOrDefault(key,key);
            list.Add(new{key,label,kind=key=="lookup_points"?"text":"number",value=fieldValue,minimum=min,maximum=(double?)null});
        }
        return list.ToArray();
    }

    private static object Generate(JsonElement r, IProgress<GenerationProgress>? progress)
    {
        var mode=MapMode(Str(r,"mode","natural")); var cap=MapCapMode(Str(r,"cap_mode","out")); var type=Str(r,"curve_type","gain"); var count=Int(r,"point_count",128); var precision=Int(r,"precision",6);
        if(!PointOptions.Contains(count)||precision<1||precision>10) throw new InvalidOperationException("Output point count or precision is not supported.");
        var name=Str(r,"profile_name","New Profile").Trim(); if(name=="") name="New Profile";
        var args=ReadArgs(mode,cap,Prop(r,"args"));
        var destination = Str(r, "destination", "file");
        var openCustomCurve = destination == "app" && Bool(r, "open_customcurve", false);
        var outputDpiEnabled = Bool(r, "output_dpi_enabled", false);
        if (destination == "app" || outputDpiEnabled) EnsureCustomCurveClosed();
        var max=EstimateMaxInput(mode,type,cap,args,precision);
        progress?.Report(new GenerationProgress("Preparing curve", $"Formula: {mode} · {type} · cap {cap}; input range 0–{max:G6}"));
        var curve=MakeCurve(mode,type,cap,args,max,count,precision,progress,"Horizontal curve");
        var lr = Num(r,"left_right_ratio",1); var ud = Num(r,"up_down_ratio",1);
        var lpNorm = Num(r,"lp_norm",2);
        var outputDpi = Num(r, "output_dpi", 1000);
        if (lr < 0 || ud < 0 || lpNorm <= 0 || lpNorm > 16) throw new InvalidOperationException("Directional multipliers must be nonnegative and LP norm must be between 0 and 16.");
        if (outputDpiEnabled && (!double.IsFinite(outputDpi) || outputDpi < 1 || outputDpi > int.MaxValue || outputDpi != Math.Truncate(outputDpi)))
            throw new InvalidOperationException("Output DPI must be a positive whole number supported by CustomCurve.");
        var profile=NewProfile(name, curve, lr, ud, lpNorm,
            Num(r,"rotation",0), Num(r,"angle_snap",0), Num(r,"input_smoothing_ms",0), Num(r,"output_smoothing_ms",0));
        profile["UseMouseDpi"] = outputDpiEnabled;
        if (outputDpiEnabled) profile["MouseDpi"] = (int)outputDpi;
        var dx=Num(r,"domain_x",1);var dy=Num(r,"domain_y",1);var rx=Num(r,"range_x",1);var ry=Num(r,"range_y",1);var sens=Num(r,"sensitivity_multiplier",1);var ratio=Num(r,"yx_ratio",1);
        if (dx <= 0 || dy <= 0 || rx < 0 || ry < 0 || sens < 0 || ratio < 0 || !double.IsFinite(sens * ratio))
            throw new InvalidOperationException("Curve weights and sensitivity multipliers must be finite and nonnegative, with domain weights above zero.");
        if (outputDpiEnabled) ApplyCustomCurveOutputDpi((int)outputDpi);
        Transform(curve,dx,rx,sens);
        var separate=Bool(r,"separate_vertical_curve",false)||Math.Abs(dx-dy)>1e-12||Math.Abs(dx-rx)>1e-12||Math.Abs(dx-ry)>1e-12||Math.Abs(ratio-1)>1e-12;
        if(separate)
        {
            var vertical=Prop(r,"vertical");
            var vm=Bool(r,"separate_vertical_curve",false)?MapMode(Str(vertical,"mode",mode)):mode;
            var vt=Bool(r,"separate_vertical_curve",false)?Str(vertical,"curve_type",type):type;
            var vc=Bool(r,"separate_vertical_curve",false)?MapCapMode(Str(vertical,"cap_mode",cap)):cap;
            var va=Bool(r,"separate_vertical_curve",false)?ReadArgs(vm,vc,Prop(vertical,"args")):args;
            var vmax=EstimateMaxInput(vm,vt,vc,va,precision);
            var yc=MakeCurve(vm,vt,vc,va,vmax,count,precision,progress,"Vertical curve");Transform(yc,dy,ry,sens*ratio);profile["YCurve"]=yc;
        }
        progress?.Report(new GenerationProgress("Building profile", "Applying curve weights and profile settings"));
        string? outputPath = null;
        var opened = false;
        if(r.TryGetProperty("output_path",out var pathEl)&&pathEl.ValueKind==JsonValueKind.String&&!string.IsNullOrWhiteSpace(pathEl.GetString()))
        {
            outputPath = pathEl.GetString();
            File.WriteAllText(outputPath!,JsonSerializer.Serialize(profile,JsonOptions));
        }
        else if (destination == "app")
        {
            outputPath = LoadProfilesDirectly([profile]);
            if (openCustomCurve)
            {
                var executable = Convert.ToString(LoadConfig().GetValueOrDefault("customcurve_path")) ?? "";
                if (File.Exists(executable))
                {
                    Process.Start(new ProcessStartInfo(executable) { UseShellExecute = true, WorkingDirectory = Path.GetDirectoryName(executable)! });
                    opened = true;
                }
            }
        }
        var config=LoadConfig();
        config["profile_name"]=name; config["mode"]=mode; config["curve_type"]=type; config["cap_mode"]=cap; config["args"]=args;
        config["point_count"]=count; config["precision"]=precision; config["domain_x"]=dx; config["domain_y"]=dy;
        config["range_x"]=rx; config["range_y"]=ry; config["anisotropy_enabled"]=Bool(r,"anisotropy_enabled",false);
        config["sensitivity_multiplier"]=sens; config["yx_ratio"]=ratio; config["left_right_ratio"]=Num(r,"left_right_ratio",1);
        config["up_down_ratio"]=ud; config["rotation"]=Num(r,"rotation",0); config["angle_snap"]=Num(r,"angle_snap",0);
        config["lp_norm"] = lpNorm;
        config["output_dpi_enabled"] = outputDpiEnabled;
        config["output_dpi"] = outputDpi;
        config.Remove("lp_norm_infinite");
        config["input_smoothing_ms"]=Num(r,"input_smoothing_ms",0);
        config["output_smoothing_ms"]=Num(r,"output_smoothing_ms",0); config["vertical_mode"]=Str(Prop(r,"vertical"),"mode",mode);
        config["vertical_curve_type"]=Str(Prop(r,"vertical"),"curve_type",type); config["vertical_cap_mode"]=Str(Prop(r,"vertical"),"cap_mode",cap);
        config["vertical_args"]=ReadArgs(MapMode(Str(Prop(r,"vertical"),"mode",mode)),MapCapMode(Str(Prop(r,"vertical"),"cap_mode",cap)),Prop(Prop(r,"vertical"),"args"));
        config["separate_vertical_curve"]=Bool(r,"separate_vertical_curve",false); config["filename"]=outputPath ?? Str(r,"output_path","profile.cc4");
        progress?.Report(new GenerationProgress("Saving profile", "Writing generated CC4 data"));
        Save(config);
        var actualPointCount = ((List<string>)curve["Points"]!).Count;
        if (profile.TryGetValue("YCurve", out var verticalCurve) && verticalCurve is Dictionary<string, object?> verticalData &&
            verticalData.TryGetValue("Points", out var verticalPoints) && verticalPoints is List<string> verticalList)
            actualPointCount += verticalList.Count;
        progress?.Report(new GenerationProgress("Complete", $"Generated {actualPointCount} control points across { (separate ? "both curves" : "the curve") }",
            actualPointCount, count, Fraction: 1));
        return new {saved=outputPath is not null,destination,path=outputPath ?? "",opened,point_count=count,actual_point_count=actualPointCount,max_input=max,samples=Array.Empty<object>(),separate_curves=separate};
    }
    private static Dictionary<string, object?> ReadArgs(string mode, string cap, JsonElement input)
    {
        var args = DefaultsFor(mode, cap);
        if (input.ValueKind != JsonValueKind.Object) return args;
        foreach (var property in input.EnumerateObject())
        {
            if (!args.ContainsKey(property.Name)) continue;
            if (property.Name == "lookup_points") { args[property.Name] = property.Value.Clone(); continue; }
            if (property.Name == "lut_velocity") { args[property.Name] = Bool(property.Value, true); continue; }
            var fallback = Number(args[property.Name], 0);
            var value = Num(property.Value, fallback);
            if (!double.IsFinite(value) || value < 0) throw new InvalidOperationException($"{property.Name} must be a nonnegative finite number.");
            args[property.Name] = value;
        }
        if (mode == "lut" && Lookup(args, false).Count < 2)
            throw new InvalidOperationException("Enter at least two lookup points as x,y; x,y.");
        return args;
    }
    private static Dictionary<string, object?> NewProfile(string name, Dictionary<string, object?> xCurve,
        double lr = 1, double ud = 1, double lpNorm = 2, double rotation = 0, double angleSnap = 0,
        double inputSmoothing = 0, double outputSmoothing = 0) => new()
    {
        ["Id"] = Guid.NewGuid().ToString(), ["Name"] = name, ["Description"] = null,
        ["EditingVerticalCurve"] = false, ["XCurve"] = xCurve,
        ["RotationMode"] = "Both", ["RotationHorizontal"] = rotation, ["RotationVertical"] = 0,
        ["AngleSnappingMode"] = "Legacy", ["AngleSnappingHorizontal"] = angleSnap, ["AngleSnappingVertical"] = angleSnap,
        ["InputSpeedMetric"] = "Euclidean", ["InputSmoothingTimeMs"] = inputSmoothing,
        ["HandAccelScaleOn"] = "Acceleration", ["HandAccelTarget"] = "Velocity",
        ["HandAccelDetectionSmoothing"] = "Normal", ["HandAccelScale"] = 0, ["HandAccelLimit"] = 2,
        ["BiasMode"] = 0, ["BiasCurve"] = new { Points = new[] { "0|0|0.5", "90|1|0.5" } },
        ["Dimension"] = new { Points = CreateDimensionPoints(lr, ud, lpNorm), Mode = "Norm", Shape = 0, Weights = new int[8] },
        ["DimensionTarget"] = "Sensitivity", ["OutputSmoothingTimeMs"] = outputSmoothing,
        ["InvertHorizontal"] = false, ["InvertVertical"] = false, ["UseFixedTiming"] = false,
        ["MousePollingRate"] = "Auto", ["UseMouseDpi"] = false, ["MouseDpi"] = 800,
        ["NormalizeOutput"] = false, ["IsNew"] = false,
    };
    private static double[] CreateDimensionPoints(double lr, double ud, double p)
    {
        var result = new double[16];
        for (var i = 0; i < 8; i++)
        {
            var theta = i * Math.PI / 4;
            var cosine = Math.Cos(theta); var sine = Math.Sin(theta);
            if (Math.Abs(cosine) < 1e-15) cosine = 0;
            if (Math.Abs(sine) < 1e-15) sine = 0;
            var radius = 1 / Math.Pow(Math.Pow(Math.Abs(cosine), p) + Math.Pow(Math.Abs(sine), p), 1 / p);
            result[i * 2] = cosine * radius * (cosine < 0 ? lr : 1);
            result[i * 2 + 1] = sine * radius * (sine > 0 ? ud : 1);
        }
        return result;
    }
    private static Dictionary<string,object?> MakeCurve(string mode,string type,string cap,Dictionary<string,object?> a,
        double max,int count,int precision,IProgress<GenerationProgress>? progress = null,string curveName = "Curve")
    {
        var value = BuildEvaluator(mode, type, cap, a);
        if (mode == "noaccel")
            return new() { ["LeftSlopeMode"] = "Flat", ["CustomLeftSlope"] = 0d, ["RightSlopeMode"] = "Flat", ["CustomRightSlope"] = 0d,
                ["Points"] = new List<string> { "0|1|0.5", $"{max.ToString("G15", CultureInfo.InvariantCulture)}|1|0.5" } };
        max = Math.Max(0, max);
        precision = Math.Max(1, precision);
        count = Math.Max(2, count);
        var generated = FormulaPointGenerator.GeneratePoints(value, max, Math.Clamp(count, 2, 4096),
            Math.Max(Math.Pow(10, -precision), 1e-5), SplineEdges(mode, type, cap, a, max, precision), progress, curveName);
        var points = generated.Select(point => FormatGeneratedPoint(point.X, point.Y, precision, point.Edge, point.Weight)).ToList();
        var leftSlopeMode = mode is "power" or "lut" ? "Flat" : "Linear";
        if (points.Count > 2)
        {
            var first = Cc4Spline.ParsePoint(points[0]);
            var second = Cc4Spline.ParsePoint(points[1]);
            if (Math.Abs(first.X) <= 1e-12 && Math.Abs(first.Y - second.Y) <= Math.Max(Math.Pow(10, -(precision + 1)), 1e-12))
            {
                leftSlopeMode = "Flat";
                if (!second.Edge)
                {
                    points.RemoveAt(0);
                    points[0] = FormatGeneratedPoint(second.X, second.Y, precision, false, second.Weight);
                }
            }
        }
        var slopeDelta = Math.Max(1e-6, max * 1e-6);
        var slope = (SafeCurveValue(value, max + slopeDelta) - SafeCurveValue(value, max)) / slopeDelta;
        var hasLimit = TryGetAsymptoticLimit(mode, type, cap, a, value, out var asymptoticLimit);
        var limitTolerance = Math.Max(Math.Pow(10, -precision), 1e-5) * Math.Max(1, Math.Abs(asymptoticLimit));
        var flatRight = hasLimit
            ? Math.Abs(SafeCurveValue(value, max) - asymptoticLimit) <= limitTolerance
            : Math.Abs(slope) < 1e-9 || ((mode is "classic/linear" or "power") && HasCap(cap, a));
        return new()
        {
            ["LeftSlopeMode"] = leftSlopeMode,
            ["CustomLeftSlope"] = 0d,
            ["RightSlopeMode"] = flatRight ? "Flat" : "Custom",
            ["CustomRightSlope"] = flatRight ? 0d : slope,
            ["Points"] = points,
        };
    }

    private static double SafeCurveValue(Func<double, double> curve, double x)
    {
        try { var y = curve(x); return double.IsFinite(y) ? y : 0; }
        catch { return 0; }
    }

    private static string FormatGeneratedPoint(double x, double y, int precision, bool edge, double weight = 0.5)
    {
        static string FormatY(double value, int digits) => value.ToString($"F{digits}", CultureInfo.InvariantCulture).TrimEnd('0').TrimEnd('.');
        return $"{x.ToString("G15", CultureInfo.InvariantCulture)}|{FormatY(y, precision)}|{weight.ToString("G15", CultureInfo.InvariantCulture)}{(edge ? "|e" : "")}";
    }
    private static bool HasCap(string cap, Dictionary<string, object?> args) => cap switch
    {
        "in" => Number(args.GetValueOrDefault("cap_x"), 0) > 0,
        "io" => Number(args.GetValueOrDefault("cap_x"), 0) > 0 || Number(args.GetValueOrDefault("cap_y"), 0) > 0,
        _ => Number(args.GetValueOrDefault("cap_y"), 0) > 0,
    };
    private static Func<double, double> BuildEvaluator(string mode,string type,string cap,Dictionary<string,object?> a)
    {
        double A(string key, double fallback) => Number(a.GetValueOrDefault(key), fallback);
        var lookupPoints = mode == "lut" ? Lookup(a).ToArray() : [];
        var lookupX = lookupPoints.Select(point => point.X).ToArray();
        var lookupY = lookupPoints.Select(point => point.Y).ToArray();
        var lookupVelocity = Bool(a.GetValueOrDefault("lut_velocity"), true);
        if (mode == "classic/linear")
            return x => EvaluateClassic(x, type, cap, A("input_offset", 0), A("acceleration", .005), A("exponent", 2), A("cap_x", 0), A("cap_y", 0));
        if (mode == "power")
            return x => EvaluatePower(x, type, cap, A("output_offset", 0), A("scale", 1), A("exponent_power", .05), A("cap_x", 0), A("cap_y", 0));
        if (type == "gain" && mode is "synchronous" or "motivity (1.6.1)")
            return BuildSampledGainCurve(mode, BuildEvaluator(mode, "legacy", cap, a), a);
        double Value(double x) {
            double Arg(string key, double fallback) => Number(a.GetValueOrDefault(key), fallback);
            var offset = Arg("input_offset", 0);
            var capX = Arg("cap_x", 0);
            var capY = Arg("cap_y", 0);
            var smooth = Arg("smooth", .5);
            var jumpX = Arg("cap_x", 15);
            var jumpDelta = Arg("cap_y", 1.5) - 1;

            double Legacy(double input)
            {
                input = Math.Max(0, input);
                if (mode == "noaccel") return 1;
                if (mode == "natural")
                {
                    var delta = Arg("limit", 1.5) - 1;
                    var rate = Arg("decay_rate", .1);
                    if (input <= offset || Math.Abs(delta) <= 1e-10 || rate <= 1e-12) return 1;
                    var accel = rate / Math.Abs(delta);
                    var shifted = offset - input;
                    var decay = SafeExp(accel * shifted);
                    if (type == "gain")
                        return (delta * (decay / accel - shifted) - delta / accel) / input + 1;
                    return delta * (1 - (offset - decay * shifted) / input) + 1;
                }
                if (mode == "jump")
                {
                    var rateInverse = smooth * jumpX;
                    var rate = rateInverse < 1 ? 0 : 2 * Math.PI / rateInverse;
                    if (type == "gain")
                    {
                        if (input <= 0) return 1;
                        if (rate == 0) return input < jumpX ? 1 : 1 + jumpDelta * (input - jumpX) / input;
                        var antiderivative = jumpDelta * (input + Math.Log(1 + SafeExp(rate * (jumpX - input))) / rate);
                        var initial = jumpDelta * Math.Log(1 + SafeExp(rate * jumpX)) / rate;
                        return 1 + (antiderivative - initial) / input;
                    }
                    if (rate == 0) return input < jumpX ? 1 : 1 + jumpDelta;
                    return jumpDelta / (1 + SafeExp(rate * (jumpX - input))) + 1;
                }
                if (mode == "motivity (1.6.1)")
                {
                    var motivity = Math.Max(1.000000000001, Arg("motivity", 1.5));
                    if (input <= 0) return 1 / motivity;
                    var accel = Math.Min(SafeExp(Arg("growth_rate", 1)), 1e12);
                    var exponent = accel * (Math.Log(Math.Max(Arg("midpoint", 5), 1e-12)) - Math.Log(input));
                    if (exponent >= 60) return 1 / motivity;
                    if (exponent <= -60) return motivity;
                    var term = 2 * Math.Log(motivity);
                    return SafeExp(term / (SafeExp(exponent) + 1) - term / 2);
                }
                if (mode == "synchronous")
                {
                    var motivity = Math.Max(1.000000000001, Arg("motivity", 1.5));
                    var gamma = Math.Max(1e-12, Arg("gamma", 1));
                    var sync = Math.Max(1e-12, Arg("sync_speed", 5));
                    var sharp = smooth <= 0 ? 16 : .5 / smooth;
                    var logM = Math.Log(motivity);
                    var gammaConst = gamma / logM;
                    if (input <= 0) return 1 / motivity;
                    var diff = Math.Log(input / sync);
                    if (sharp >= 16)
                    {
                        var shaped = gammaConst * diff;
                        return shaped < -1 ? 1 / motivity : shaped > 1 ? motivity : SafeExp(shaped * logM);
                    }
                    if (Math.Abs(diff) < 1e-15) return 1;
                    var shapedMagnitude = Math.Pow(Math.Abs(gammaConst * diff), sharp);
                    var tanh = shapedMagnitude > 700 ? 1 : Math.Tanh(shapedMagnitude);
                    var exponent = Math.Pow(tanh, 1 / sharp) * Math.Sign(diff);
                    return SafeExp(exponent * logM);
                }
                if (mode == "classic/linear")
                {
                    var accel = Arg("acceleration", .005);
                    var power = Math.Max(1.000000000001, Arg("exponent", 2));
                    if (input <= offset) return 1;
                    var relative = accel * Math.Pow(input - offset, power - 1);
                    var result = relative * (input - offset) / input + 1;
                    if (cap == "in" && capX > 0) result = Math.Min(result, accel * Math.Pow(Math.Max(0, Math.Min(input, capX) - offset), power - 1) * Math.Max(0, Math.Min(input, capX) - offset) / Math.Max(input, 1e-12) + 1);
                    if (cap is "out" or "io" && capY > 0) result = Math.Min(result, capY);
                    return result;
                }
                if (mode == "power")
                {
                    var power = Math.Max(1e-12, Arg("exponent_power", .05));
                    var outputOffset = Arg("output_offset", 0);
                    var scale = Math.Max(1e-12, Arg("scale", 1));
                    var result = input <= 0 ? outputOffset : Math.Pow(scale * input, power) + outputOffset;
                    if (cap == "in" && capX > 0) result = Math.Min(result, Math.Pow(scale * capX, power) + outputOffset);
                    if (cap is "out" or "io" && capY > 0) result = Math.Min(result, capY);
                    return result;
                }
                return 1;
            }

            double y;
            if (mode == "lut")
                y = RawAccelLookup.Evaluate(lookupX, lookupY, x, lookupVelocity);
            else y = Legacy(x);
            return double.IsFinite(y) ? y : 1;
        }
        return Value;
    }

    private static Func<double, double> BuildSampledGainCurve(string mode, Func<double, double> legacy,
        Dictionary<string, object?> args)
    {
        double A(string key, double fallback) => Number(args.GetValueOrDefault(key), fallback);
        const int rangeStart = -3;
        const int rangeStop = 9;
        const int rangeCount = 8;
        var xStart = Math.Pow(2, rangeStart);
        var motivity = Math.Max(A("motivity", 1.5), 1.000000000001);
        var minSensitivity = 1 / motivity;
        double? lowerClamp = null;
        if (mode == "synchronous")
        {
            var gamma = Math.Max(A("gamma", 1), 1e-12);
            var smooth = Math.Max(A("smooth", .5), 0);
            if ((smooth == 0 ? 16 : .5 / smooth) >= 16)
            {
                var gammaConst = gamma / Math.Log(motivity);
                if (Math.Abs(gammaConst) > 1e-12)
                    lowerClamp = Math.Max(A("sync_speed", 5), 1e-12) / SafeExp(1 / gammaConst);
            }
        }

        var data = new List<double>(rangeCount * (rangeStop - rangeStart) + 1);
        var accumulatedArea = 0d;
        var previousX = 0d;
        void AccumulateTo(double nextX)
        {
            const int partitions = 2;
            var interval = (nextX - previousX) / partitions;
            for (var i = 1; i <= partitions; i++) accumulatedArea += legacy(previousX + i * interval) * interval;
            previousX = nextX;
            data.Add(accumulatedArea);
        }
        for (var exponent = 0; exponent < rangeStop - rangeStart; exponent++)
        {
            var step = Math.Pow(2, exponent + rangeStart) / rangeCount;
            for (var i = 0; i < rangeCount; i++) AccumulateTo((i + rangeCount) * step);
        }
        var tableEnd = Math.Pow(2, rangeStop);
        AccumulateTo(tableEnd);
        var endVelocity = legacy(tableEnd);

        return x =>
        {
            if (x <= 0) return data[0] / xStart;
            if (lowerClamp.HasValue && x <= lowerClamp.Value) return minSensitivity;
            if (x > tableEnd)
            {
                var logRatio = Math.Log(x / tableEnd);
                var intervals = Math.Max(1, (int)Math.Ceiling(logRatio / Math.Log(2) * rangeCount));
                var area = data[^1];
                var previous = tableEnd;
                var previousValue = endVelocity;
                for (var i = 1; i <= intervals; i++)
                {
                    var next = tableEnd * Math.Exp(logRatio * i / intervals);
                    var middle = previous + (next - previous) * 0.5;
                    var nextValue = legacy(next);
                    area += (next - previous) * (previousValue + 4 * legacy(middle) + nextValue) / 6;
                    previous = next;
                    previousValue = nextValue;
                }
                return area / x;
            }
            var exponent = Math.Min(Math.ILogB(x), rangeStop - 1);
            if (exponent >= rangeStart)
            {
                var integerPart = exponent - rangeStart;
                var fractionalPart = x / Math.Pow(2, exponent) - 1;
                var indexFloat = rangeCount * (integerPart + fractionalPart);
                var index = Math.Min((int)indexFloat, data.Count - 2);
                var t = indexFloat - index;
                return LerpGainTable(data[index], data[index + 1], t) / x;
            }
            return data[0] / xStart;
        };
    }

    private static double LerpGainTable(double a, double b, double t)
    {
        var value = a + t * (b - a);
        return (t > 1) == (a < b) ? Math.Max(value, b) : Math.Min(value, b);
    }

    private static double SafeExp(double value) => value >= 700 ? 1e300 : value <= -745 ? 0 : Math.Exp(value);
    private static double SafePow(double value, double exponent)
    {
        try
        {
            var result = Math.Pow(value, exponent);
            return double.IsFinite(result) ? Math.Clamp(result, -1e300, 1e300) : 1e300;
        }
        catch { return 1e300; }
    }

    private static double EvaluateClassic(double x, string type, string capMode, double offset, double acceleration,
        double exponent, double capX, double capY)
    {
        x = Math.Max(0, x); exponent = Math.Max(exponent, 1.000000000001);
        var accelRaised = SafePow(acceleration, exponent - 1);
        double Base(double input, double coefficient) => input <= offset ? 0 : coefficient * SafePow(input - offset, exponent) / Math.Max(input, 1e-300);
        if (type != "gain")
        {
            var sign = 1d; var cap = double.PositiveInfinity;
            if (capMode == "io")
            {
                cap = capY - 1;
                if (cap < 0) { cap = -cap; sign = -sign; }
                if (capX > offset && cap > 0)
                {
                    var a = SafePow(capX * cap * SafePow(capX - offset, -exponent), 1 / (exponent - 1));
                    accelRaised = SafePow(a, exponent - 1);
                }
            }
            else if (capMode == "in" && capX > 0) cap = Base(capX, accelRaised);
            else if (capY > 0)
            {
                cap = capY - 1;
                if (cap < 0) { cap = -cap; sign = -sign; }
            }
            return x <= offset ? 1 : sign * Math.Min(Base(x, accelRaised), cap) + 1;
        }

        var capInput = double.PositiveInfinity; var capOutput = double.PositiveInfinity; var constant = 0d; var outputSign = 1d;
        if (capMode == "io")
        {
            capInput = capX; capOutput = capY - 1;
            if (capOutput < 0) { capOutput = -capOutput; outputSign = -outputSign; }
            if (capInput > offset && capOutput > 0)
            {
                var baseAccel = -SafePow(capOutput / exponent, 1 / (exponent - 1)) / (offset - capInput);
                accelRaised = SafePow(baseAccel, exponent - 1);
                constant = (Base(capInput, accelRaised) - capOutput) * capInput;
            }
        }
        else if (capMode == "in" && capX > 0)
        {
            capInput = capX;
            capOutput = capInput <= offset ? 0 : exponent * SafePow(acceleration * (capInput - offset), exponent - 1);
            constant = (Base(capInput, accelRaised) - capOutput) * capInput;
        }
        else if (capY > 0)
        {
            capOutput = capY - 1;
            if (capOutput == 0) capInput = 0;
            else
            {
                if (capOutput < 0) { capOutput = -capOutput; outputSign = -outputSign; }
                capInput = acceleration <= 0 ? double.PositiveInfinity :
                    (acceleration * offset + SafePow(capOutput / exponent, 1 / (exponent - 1))) / acceleration;
                constant = (Base(capInput, accelRaised) - capOutput) * capInput;
            }
        }
        if (x <= offset) return 1;
        var value = x < capInput ? Base(x, accelRaised) : constant / x + capOutput;
        return outputSign * value + 1;
    }

    private static double EvaluatePower(double x, string type, string capMode, double outputOffset,
        double scale, double exponent, double capX, double capY)
    {
        x = Math.Max(0, x); exponent = Math.Max(exponent, 1e-12); scale = Math.Max(scale, 1e-12);
        var offsetX = 0d; var offsetY = outputOffset; var constant = 0d;
        if (capMode == "io")
        {
            if (type == "gain") scale = capX <= 0 ? 1 : SafePow(capY / (exponent + 1), 1 / exponent) / capX;
            else
            {
                offsetY = 0; constant = 0;
                scale = capX <= 0 ? 1 : SafePow(capY, 1 / exponent) / capX;
            }
            if (type == "gain")
            {
                offsetX = outputOffset <= 0 ? 0 : SafePow(outputOffset / (exponent + 1), 1 / exponent) / scale;
                constant = offsetX * outputOffset * exponent / (exponent + 1);
            }
        }
        else
        {
            offsetX = outputOffset <= 0 ? 0 : SafePow(outputOffset / (exponent + 1), 1 / exponent) / scale;
            constant = offsetX * outputOffset * exponent / (exponent + 1);
        }
        double Base(double input) => input <= offsetX ? offsetY : SafePow(scale * input, exponent) + constant / Math.Max(input, 1e-300);

        if (type != "gain")
        {
            var cap = double.PositiveInfinity;
            if (capMode == "io") cap = capY;
            else if (capMode == "in" && capX > 0) cap = Base(capX);
            else if (capY > 0) cap = capY;
            return Math.Min(Base(x), cap);
        }

        var capInput = double.PositiveInfinity; var capOutput = double.PositiveInfinity;
        if (capMode == "io") { capInput = capX; capOutput = capY; }
        else if (capMode == "in" && capX > 0)
        {
            if (capX <= offsetX) { capInput = 0; capOutput = offsetY; }
            else { capInput = capX; capOutput = (exponent + 1) * SafePow(scale * capX, exponent); }
        }
        else if (capY > 0)
        {
            capInput = SafePow(capY / (exponent + 1), 1 / exponent) / scale;
            capOutput = capY;
        }
        var constantTail = (Base(capInput) - capOutput) * capInput;
        if (x <= 0 && capInput <= 0) return capOutput;
        return x < capInput ? Base(x) : capOutput + constantTail / Math.Max(x, 1e-300);
    }
    private record XY(double X,double Y);
    private static List<XY> Lookup(Dictionary<string,object?> a, bool useFallback = true)
    {
        if (!a.TryGetValue("lookup_points", out var raw) || raw is null)
            return useFallback ? DefaultLookupPoints() : [];
        if (raw is string text)
        {
            try { return ValidateLookupPoints(ParseLookupText(text)); }
            catch { if (useFallback) return DefaultLookupPoints(); throw; }
        }
        try
        {
            var element = raw is JsonElement json ? json : JsonSerializer.SerializeToElement(raw);
            if (element.ValueKind == JsonValueKind.String)
                return Lookup(new Dictionary<string, object?> { ["lookup_points"] = element.GetString() }, useFallback);
            var points = new List<XY>();
            if (element.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in element.EnumerateArray())
                {
                    if (item.ValueKind == JsonValueKind.Array && item.GetArrayLength() >= 2)
                        points.Add(new(Num(item[0], 0), Num(item[1], 0)));
                    else if (item.ValueKind == JsonValueKind.Object)
                        points.Add(new(Num(item, "x", 0), Num(item, "y", 0)));
                }
            }
            return ValidateLookupPoints(points);
        }
        catch { if (useFallback) return DefaultLookupPoints(); throw; }
    }
    private static List<XY> DefaultLookupPoints() =>
        [new(1.505035, 0.85549892), new(4.375, 3.30972978), new(13.51, 15.17478447), new(140, 354.7026875)];
    private static bool IsPreviousDefaultLookup(List<XY> points) => points.Count == 3 &&
        points[0].X == 0.01 && points[0].Y == 1 && points[1].X == 5 && points[1].Y == 1 &&
        points[2].X == 15 && points[2].Y == 1;
    private static void Transform(Dictionary<string,object?> c,double domain,double range,double sensitivity)
    {
        var pts=(List<string>)c["Points"]!;
        for(int i=0;i<pts.Count;i++)
        {
            var p=pts[i].Split('|');
            var x=double.Parse(p[0],CultureInfo.InvariantCulture)/Math.Max(domain,1e-12);
            var y=(1+(double.Parse(p[1],CultureInfo.InvariantCulture)-1)*range)*sensitivity;
            p[0]=x.ToString("G15",CultureInfo.InvariantCulture);
            p[1]=y.ToString("G15",CultureInfo.InvariantCulture);
            pts[i]=string.Join('|',p);
        }
        var slopeFactor=domain*range*sensitivity;
        foreach(var key in new[]{"CustomLeftSlope","CustomRightSlope"})
            if(c.TryGetValue(key,out var slope)) c[key]=Number(slope,0)*slopeFactor;
    }

    private static JsonDocument ReadSettings(JsonElement r,out JsonElement profiles){var path=Str(r,"settings_path","");if(!File.Exists(path))throw new InvalidOperationException("Select a valid RawAccel settings.json file.");var doc=JsonDocument.Parse(File.ReadAllText(path));if(!doc.RootElement.TryGetProperty("profiles",out profiles)||profiles.ValueKind!=JsonValueKind.Array||profiles.GetArrayLength()==0)throw new InvalidOperationException("No profiles were found in settings.json.");return doc;}
    private static object Inspect(JsonElement r){using var d=ReadSettings(r,out var p);return new{profiles=p.EnumerateArray().Select((x,i)=>new{index=i,name=Str(x,"name",$"Profile {i+1}")}).ToArray()};}

    private static object ImportSettings(JsonElement request)
    {
        using var document = ReadSettings(request, out var sources);
        var pointCount = Int(request, "point_count", 128);
        var precision = Int(request, "precision", 6);
        if (!PointOptions.Contains(pointCount) || precision is < 1 or > 10)
            throw new InvalidOperationException("Output point count or precision is not supported.");
        var prefix = Str(request, "profile_name", "Imported Profile").Trim();
        if (prefix.Length == 0) prefix = "Imported Profile";
        var destination = Str(request, "destination", "file");
        var openCustomCurve = destination == "app" && Bool(request, "open_customcurve", false);
        var outputDpiEnabled = Bool(request, "output_dpi_enabled", false);
        if (destination == "app" || outputDpiEnabled) EnsureCustomCurveClosed();
        var profiles = new List<Dictionary<string, object?>>();
        foreach (var source in sources.EnumerateArray())
        {
            var sourceName = Str(source, "name", "profile").Trim();
            if (sourceName.Length == 0) sourceName = "profile";
            var name = sources.GetArrayLength() == 1 ? prefix : $"{prefix} - {sourceName}";
            profiles.Add(BuildRawAccelProfile(source, name, pointCount, precision));
        }
        var outputDpi = Num(request, "output_dpi", 1000);
        if (outputDpiEnabled && (!double.IsFinite(outputDpi) || outputDpi < 1 || outputDpi > int.MaxValue || outputDpi != Math.Truncate(outputDpi)))
            throw new InvalidOperationException("Output DPI must be a positive whole number supported by CustomCurve.");
        if (outputDpiEnabled)
        {
            ApplyCustomCurveOutputDpi((int)outputDpi);
            foreach (var profile in profiles)
            {
                profile["UseMouseDpi"] = true;
                profile["MouseDpi"] = (int)outputDpi;
            }
        }
        string? outputPath = null;
        var opened = false;
        if (destination == "app")
        {
            outputPath = LoadProfilesDirectly(profiles);
            if (openCustomCurve)
            {
                var executable = Convert.ToString(LoadConfig().GetValueOrDefault("customcurve_path")) ?? "";
                if (File.Exists(executable))
                {
                    Process.Start(new ProcessStartInfo(executable) { UseShellExecute = true, WorkingDirectory = Path.GetDirectoryName(executable)! });
                    opened = true;
                }
            }
        }
        else
        {
            var folder = Str(request, "output_dir", "");
            if (!Directory.Exists(folder)) throw new InvalidOperationException("Select an existing output folder for the converted profiles.");
            var used = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var profile in profiles)
            {
                var baseName = NormalizeFilename(Convert.ToString(profile["Name"]) ?? "profile");
                var candidate = baseName; var suffix = 2;
                while (!used.Add(candidate) || File.Exists(Path.Combine(folder, candidate)))
                    candidate = NormalizeFilename(Path.GetFileNameWithoutExtension(baseName) + "_" + suffix++);
                outputPath = Path.Combine(folder, candidate);
                File.WriteAllText(outputPath, JsonSerializer.Serialize(profile, JsonOptions));
            }
        }
        var first = sources[0]; var paramsX = FindAccelParams(first, false)!.Value;
        var state = CurveState(paramsX);
        var config = LoadConfig();
        config["profile_name"] = profiles[0]["Name"]; config["mode"] = state.mode;
        config["curve_type"] = state.curve_type; config["cap_mode"] = state.cap_mode; config["args"] = state.args;
        config["point_count"] = pointCount; config["precision"] = precision; config["filename"] = outputPath ?? "profile.cc4";
        Save(config);
        return new { count = profiles.Count, destination, path = outputPath, opened,
            separate_curve_count = profiles.Count(p => p.ContainsKey("YCurve")) };
    }

    private static Dictionary<string, object?> BuildRawAccelProfile(JsonElement source, string name, int pointCount, int precision)
    {
        var paramsX = FindAccelParams(source, false);
        if (!paramsX.HasValue) throw new InvalidOperationException("The RawAccel profile has no horizontal acceleration parameters.");
        var stateX = CurveState(paramsX.Value); var paramsY = FindAccelParams(source, true);
        if (stateX.mode == "lut" && Lookup(stateX.args, false).Count < 2)
            throw new InvalidOperationException("A lookup-table profile must have at least two valid points.");
        var (domainX, domainY) = AxisWeights(source, "Stretches domain for horizontal vs vertical inputs", 1e-12);
        var (rangeX, rangeY) = AxisWeights(source, "Stretches accel range for horizontal vs vertical inputs", 0);
        var speed = Prop(source, "Input speed calculation parameters");
        var byComponent = !Bool(Prop(speed, "Whole/combined accel (set false for 'by component' mode)"), true);
        var useVertical = byComponent && paramsY.HasValue;
        var sensitivity = Num(source, "Output DPI", 1000) / 1000d;
        var yxRatio = Num(source, "Y/X output DPI ratio (vertical sens multiplier)", 1);
        if (sensitivity < 0 || yxRatio < 0 || !double.IsFinite(sensitivity * yxRatio))
            throw new InvalidOperationException("RawAccel output sensitivity values must be finite and nonnegative.");
        var xCurve = BuildImportedAxis(stateX, pointCount, precision);
        Transform(xCurve, domainX, rangeX, sensitivity);
        var lrRatio = Num(source, "L/R output DPI ratio (left sens multiplier)", 1);
        var udRatio = Num(source, "U/D output DPI ratio (up sens multiplier)", 1);
        var lpNorm = Num(speed, "lpNorm", 2);
        if (lrRatio < 0 || udRatio < 0 || lpNorm <= 0)
            throw new InvalidOperationException("RawAccel directional multipliers must be nonnegative and LP norm must be positive.");
        var profile = NewProfile(name, xCurve, lrRatio, udRatio, lpNorm,
            Num(source, "Degrees of rotation", 0), Num(source, "Degrees of angle snapping", 0),
            Num(speed, "Time in ms after which an input is weighted at half its original value.", 0),
            Num(speed, "Time in ms after which an output is weighted at half its original value.", 0));
        var anisotropic = new[] { domainX, domainY, rangeX, rangeY }.Any(v => Math.Abs(v - 1) > 1e-12);
        if (useVertical || anisotropic || Math.Abs(yxRatio - 1) > 1e-12)
        {
            var stateY = useVertical ? CurveState(paramsY!.Value) : stateX;
            var yCurve = BuildImportedAxis(stateY, pointCount, precision);
            Transform(yCurve, domainY, rangeY, sensitivity * yxRatio);
            profile["YCurve"] = yCurve;
        }
        return profile;
    }

    private static Dictionary<string, object?> BuildImportedAxis(
        (string mode, string curve_type, string cap_mode, Dictionary<string, object?> args) state, int pointCount, int precision)
    {
        if (state.mode == "noaccel")
            return new() { ["LeftSlopeMode"] = "Flat", ["CustomLeftSlope"] = 0d, ["RightSlopeMode"] = "Flat", ["CustomRightSlope"] = 0d,
                ["Points"] = new List<string> { "0|1|0.5", "200|1|0.5" } };
        var maxInput = EstimateMaxInput(state.mode, state.curve_type, state.cap_mode, state.args, precision);
        var evaluator = BuildEvaluator(state.mode, state.curve_type, state.cap_mode, state.args);
        var points = FormulaPointGenerator.Generate(evaluator, maxInput, Math.Clamp(pointCount, 2, 4096),
            Math.Max(Math.Pow(10, -precision), 1e-5), SplineEdges(state.mode, state.curve_type, state.cap_mode, state.args, maxInput, precision));
        var delta = Math.Max(1e-5, maxInput * 1e-5);
        var slope = (evaluator(maxInput + delta) - evaluator(maxInput)) / delta;
        return new()
        {
            ["LeftSlopeMode"] = state.mode is "power" or "lut" ? "Flat" : "Linear",
            ["CustomLeftSlope"] = 0d, ["RightSlopeMode"] = "Custom",
            ["CustomRightSlope"] = double.IsFinite(slope) ? slope : 0d, ["Points"] = points,
        };
    }

    private static double EstimateMaxInput(string mode, string type, string cap, Dictionary<string, object?> args, int precision = 6)
    {
        var fallback = HeuristicMaxInput(mode, type, cap, args);
        Func<double, double> curve;
        try { curve = BuildEvaluator(mode, type, cap, args); }
        catch { return fallback; }
        var anchors = CoverageAnchors(mode, type, cap, args);
        var anchorMax = Math.Max(RequiredCoverageMaxInput(mode, cap, args), anchors.DefaultIfEmpty(0).Max());
        if (TryGetAsymptoticLimit(mode, type, cap, args, curve, out var limit))
        {
            var requiredEnd = FindLimitCoverageEnd(curve, limit, Math.Max(fallback, anchorMax), anchorMax, precision);
            var practicalEnd = Math.Max(Math.Max(fallback * 4, anchorMax * 1.1), 200);
            return Math.Min(requiredEnd, practicalEnd);
        }
        if (mode == "lut") return Math.Max(fallback, anchorMax);
        var ceiling = Math.Max(Math.Max(fallback * 4, anchorMax * 1.1), 200);
        var ceilingSamples = SampleCoverage(curve, ceiling, anchors, 256);
        if (CoverageSpan(ceilingSamples) <= CoverageTolerance(ceilingSamples))
            return Math.Clamp(fallback, anchorMax, ceiling);
        var tailStart = FindPracticalTailStart(curve, anchors, ceiling, anchorMax);
        if (tailStart.HasValue) return Math.Clamp(tailStart.Value, anchorMax, ceiling);

        var previous = 0d;
        var current = Math.Min(Math.Max(anchorMax * 1.05, 1), ceiling);
        double? stable = null;
        for (var i = 0; i < 28; i++)
        {
            var samples = SampleCoverage(curve, current, anchors);
            if (CoverageCanHandoff(curve, samples, current, anchors) && current >= anchorMax)
            { stable = current; break; }
            previous = current;
            if (current >= ceiling) break;
            current = Math.Min(current * 2, ceiling);
        }
        if (!stable.HasValue) return type == "gain" ? Math.Max(ceiling, anchorMax) : fallback;
        return Math.Clamp(RefineCoverageEnd(curve, anchors, previous, stable.Value) * 1.04, anchorMax, ceiling);
    }

    private static double FindLimitCoverageEnd(Func<double, double> curve, double limit, double initial,
        double anchorMax, int precision)
    {
        var scale = Math.Max(1, Math.Abs(limit));
        var tolerance = Math.Max(Math.Pow(10, -Math.Clamp(precision, 1, 10)), 1e-5) * scale;
        var low = Math.Max(0, anchorMax);
        if (Math.Abs(SafeCurveValue(curve, low) - limit) <= tolerance) return low;

        var high = Math.Max(initial, Math.Max(1, low));
        while (Math.Abs(SafeCurveValue(curve, high) - limit) > tolerance)
        {
            low = high;
            var next = high * 2;
            if (!double.IsFinite(next) || next <= high) return high;
            high = next;
        }

        while (true)
        {
            var middle = low + (high - low) * 0.5;
            if (middle == low || middle == high) return high;
            if (Math.Abs(SafeCurveValue(curve, middle) - limit) <= tolerance) high = middle;
            else low = middle;
        }
    }

    private static bool TryGetAsymptoticLimit(string mode, string type, string cap,
        Dictionary<string, object?> args, Func<double, double> curve, out double limit)
    {
        double A(string key, double fallback = 0) => Number(args.GetValueOrDefault(key), fallback);
        limit = 0;
        if (mode == "natural")
        {
            limit = Math.Abs(A("limit", 1.5) - 1) <= 1e-10 ? 1 : A("limit", 1.5);
            return true;
        }
        if (mode == "jump") { limit = A("cap_y", 1.5); return true; }
        if (mode is "synchronous" or "motivity (1.6.1)")
        {
            limit = Math.Max(A("motivity", 1.5), 1.000000000001);
            return true;
        }
        if (mode == "lut")
        {
            var points = Lookup(args);
            if (points.Count < 2) return false;
            var last = points[^1]; var previous = points[^2];
            var slope = (last.Y - previous.Y) / (last.X - previous.X);
            if (Bool(args.GetValueOrDefault("lut_velocity"), true))
            {
                limit = slope;
                return double.IsFinite(limit);
            }
            if (slope == 0)
            {
                limit = last.Y;
                return true;
            }
            return false;
        }
        if (mode == "classic/linear")
        {
            if (cap is "out" or "io" && A("cap_y") > 0)
            {
                limit = A("cap_y");
                return true;
            }
            if (cap == "in" && A("cap_x") > 0)
            {
                if (type != "gain") limit = SafeCurveValue(curve, A("cap_x"));
                else
                {
                    var exponent = Math.Max(A("exponent", 2), 1.000000000001);
                    var offset = A("input_offset");
                    var input = A("cap_x");
                    var acceleration = Math.Max(A("acceleration", .005), 0);
                    var capGain = input <= offset ? 0 : exponent * SafePow(acceleration * (input - offset), exponent - 1);
                    limit = 1 + capGain;
                }
                return double.IsFinite(limit);
            }
            return false;
        }
        if (mode == "power")
        {
            if (cap is "out" or "io" && A("cap_y") > 0)
            {
                limit = A("cap_y");
                return true;
            }
            if (cap == "in" && A("cap_x") > 0)
            {
                if (type != "gain") limit = SafeCurveValue(curve, A("cap_x"));
                else
                {
                    var offset = Math.Max(0, A("output_offset"));
                    var power = Math.Max(A("exponent_power", .05), 1e-12);
                    var scale = Math.Max(A("scale", 1), 1e-12);
                    var offsetX = offset > 0 ? SafePow(offset / (power + 1), 1 / power) / scale : 0;
                    limit = A("cap_x") <= offsetX ? offset : (power + 1) * SafePow(scale * A("cap_x"), power);
                }
                return double.IsFinite(limit);
            }
        }
        return false;
    }

    private static double HeuristicMaxInput(string mode, string type, string cap, Dictionary<string, object?> args)
    {
        double A(string key, double fallback = 0) => Number(args.GetValueOrDefault(key), fallback);
        double BoundTail(double capX, double constant, double reference)
        {
            capX = Math.Max(capX, 1e-9); reference = Math.Max(reference, 1e-9);
            var lower = Math.Min(capX * 2, 600); var upper = Math.Max(lower, Math.Min(capX * 6, 600));
            return Math.Clamp(Math.Abs(constant) / (reference * .01), lower, upper);
        }
        var offset = A("input_offset"); var baseRange = Math.Max(30, offset * 20);
        if (mode == "natural") return Math.Max(baseRange, Math.Max(200, 120 + A("decay_rate", .1) * 400 + offset * 20));
        if (mode == "jump") return Math.Max(baseRange, Math.Max(200, A("cap_x", 15) * 6));
        if (mode == "synchronous") return Math.Max(baseRange, Math.Max(200, A("sync_speed", 5) * 20));
        if (mode == "motivity (1.6.1)") return Math.Max(baseRange, Math.Max(200, A("midpoint", 5) * 20));
        if (mode == "lut") return Math.Max(baseRange, Math.Max(200, Lookup(args).DefaultIfEmpty(new XY(0, 1)).Max(p => p.X) * 2));
        if (mode == "classic/linear")
        {
            var capX = A("cap_x", 15); if (capX <= 0) capX = 15;
            if (cap is "in" or "io" && capX > 0) return Math.Max(baseRange, Math.Max(200, capX * 2));
            var accel = A("acceleration", .005); var exponent = Math.Max(A("exponent", 2), 1e-12); var capDelta = A("cap_y") - 1;
            if (cap == "out" && type == "gain" && accel > 0 && exponent != 1 && Math.Abs(capDelta) > 1e-12)
            {
                capX = (accel * offset + SafePow(Math.Abs(capDelta) / exponent, 1 / (exponent - 1))) / accel;
                var baseAtCap = SafePow(accel, exponent - 1) * SafePow(Math.Max(capX - offset, 1e-12), exponent) / Math.Max(capX, 1e-12);
                return Math.Max(Math.Max(baseRange, Math.Max(Math.Min(capX * 2, 600), BoundTail(capX, (baseAtCap - Math.Abs(capDelta)) * capX, Math.Abs(capDelta)))), 200);
            }
            return Math.Max(baseRange, 200);
        }
        if (mode == "power")
        {
            var outputOffset = Math.Max(0, A("output_offset")); var capX = A("cap_x"); var capY = A("cap_y");
            var power = Math.Max(A("exponent_power", .05), 1e-12); var scale = Math.Max(A("scale", 1), 1e-12);
            if (cap == "io" && type == "legacy") outputOffset = 0;
            if (cap == "io" && type == "gain" && capX > 0) scale = SafePow(capY / (power + 1), 1 / power) / capX;
            var offsetX = outputOffset > 0 ? SafePow(outputOffset / (power + 1), 1 / power) / scale : 0;
            var powerBase = Math.Max(120, offsetX * 2.5);
            if (cap is "in" or "io" && capX > 0) return Math.Min(Math.Max(Math.Max(powerBase, capX * 2.5), 200), 1000);
            if (cap == "out" && type == "gain" && capY > 0)
            {
                capX = SafePow(capY / (power + 1), 1 / power) / scale;
                var constant = (SafePow(scale * capX, power) - capY) * capX;
                return Math.Min(Math.Max(Math.Max(Math.Max(powerBase, capX * 2.5), BoundTail(capX, constant, capY)), 200), 1000);
            }
            return Math.Min(Math.Max(powerBase, 200), 1000);
        }
        return baseRange;
    }

    private static double RequiredCoverageMaxInput(string mode, string cap, Dictionary<string, object?> args)
    {
        double A(string key, double fallback = 0) => Number(args.GetValueOrDefault(key), fallback);
        var anchors = new List<double> { 0 };
        if (mode is "classic/linear" or "natural") anchors.Add(A("input_offset"));
        if (mode == "jump") anchors.Add(A("cap_x", 15));
        if (mode == "synchronous") anchors.Add(A("sync_speed", 5));
        if (mode == "motivity (1.6.1)") anchors.Add(A("midpoint", 5));
        if (mode == "power")
        {
            var offset = A("output_offset"); var p = Math.Max(A("exponent_power", .05), 1e-12); var scale = Math.Max(A("scale", 1), 1e-12);
            if (offset > 0) anchors.Add(SafePow(offset / (p + 1), 1 / p) / scale);
        }
        if (mode is "classic/linear" or "power" && cap is "in" or "io") anchors.Add(A("cap_x"));
        if (mode == "lut") anchors.AddRange(Lookup(args).Select(p => p.X));
        return anchors.Where(double.IsFinite).Where(x => x >= 0).DefaultIfEmpty(0).Max();
    }

    private static HashSet<double> CoverageAnchors(string mode, string type, string cap, Dictionary<string, object?> args)
    {
        var anchors = KnownEdges(mode, cap, args, double.MaxValue).ToHashSet();
        anchors.Add(RequiredCoverageMaxInput(mode, cap, args));
        if (mode == "power")
        {
            var output = Number(args.GetValueOrDefault("output_offset"), 0); var p = Math.Max(Number(args.GetValueOrDefault("exponent_power"), .05), 1e-12);
            var scale = Math.Max(Number(args.GetValueOrDefault("scale"), 1), 1e-12);
            if (cap == "io" && type == "gain" && Number(args.GetValueOrDefault("cap_x"), 0) > 0)
                scale = SafePow(Number(args.GetValueOrDefault("cap_y"), 0) / (p + 1), 1 / p) / Number(args.GetValueOrDefault("cap_x"), 1);
            if (output > 0) anchors.Add(SafePow(output / (p + 1), 1 / p) / Math.Max(scale, 1e-12));
        }
        return anchors.Where(double.IsFinite).Where(x => x >= 0).ToHashSet();
    }

    private static List<XY> SampleCoverage(Func<double, double> curve, double maxInput, IEnumerable<double> anchors, int sampleCount = 192)
    {
        maxInput = Math.Max(maxInput, 0);
        var xs = new SortedSet<double> { 0, maxInput };
        foreach (var anchor in anchors.Where(double.IsFinite)) xs.Add(Math.Clamp(anchor, 0, maxInput));
        if (maxInput > 0)
        {
            for (var i = 0; i < sampleCount; i++)
            {
                var t = i / (sampleCount - 1d);
                xs.Add(maxInput * t); xs.Add(maxInput * t * t);
            }
            var positive = xs.Where(x => x > 0).ToArray();
            var logStart = Math.Max(positive.Length == 0 ? maxInput / sampleCount : positive.Min(), maxInput / SafePow(2, 18));
            var logMin = Math.Log(logStart); var logMax = Math.Log(Math.Max(maxInput, logStart));
            for (var i = 0; i < sampleCount; i++)
            {
                var t = i / (sampleCount - 1d); xs.Add(Math.Exp(logMin + (logMax - logMin) * t));
            }
        }
        return xs.Select(x => new XY(x, SafeCurveValue(curve, x))).Where(p => double.IsFinite(p.Y)).ToList();
    }

    private static double CoverageSpan(IReadOnlyList<XY> samples) => samples.Count == 0 ? 0 : samples.Max(p => p.Y) - samples.Min(p => p.Y);
    private static double CoverageTolerance(IReadOnlyList<XY> samples)
    {
        if (samples.Count == 0) return 1e-8;
        var span = CoverageSpan(samples); var scale = Math.Max(1, Math.Max(span, samples.Max(p => Math.Abs(p.Y))));
        return Math.Max(Math.Max(span * .006, scale * 1e-5), 1e-8);
    }

    private static bool CoverageCanHandoff(Func<double, double> curve, IReadOnlyList<XY> samples, double maxInput, HashSet<double> anchors)
    {
        if (!CoverageStable(samples, maxInput) || !TailDirectionCovered(samples, maxInput)) return false;
        var future = SampleCoverage(curve, maxInput * 2, anchors);
        if (future.Count < 8) return true;
        var span = CoverageSpan(samples); var scale = Math.Max(1, Math.Max(span, samples.Max(p => Math.Abs(p.Y))));
        return Math.Abs(future[^1].Y - samples[^1].Y) <= Math.Max(Math.Max(span * .025, scale * 1e-5), 1e-8);
    }

    private static bool CoverageStable(IReadOnlyList<XY> samples, double maxInput)
    {
        if (samples.Count < 8 || maxInput <= 0) return false;
        var values = samples.Select(p => p.Y).ToArray(); var span = values.Max() - values.Min();
        var scale = Math.Max(1, Math.Max(span, values.Max(Math.Abs))); var tolerance = Math.Max(Math.Max(span * .006, scale * 1e-5), 1e-8);
        if (span <= tolerance) return true;
        var tail = samples.Where(p => p.X >= maxInput * .78).ToArray();
        if (tail.Length < 6) return false;
        var tailSpan = tail.Max(p => p.Y) - tail.Min(p => p.Y);
        if (tailSpan <= tolerance) return true;
        var dx = tail[^1].X - tail[0].X; if (dx <= 0) return false;
        var tailSlope = Math.Abs(tail[^1].Y - tail[0].Y) / dx; var avgSlope = span / Math.Max(maxInput, 1e-12);
        if (avgSlope <= 0) return true;
        var direction = tail[^1].Y >= values[0] ? 1 : -1;
        var covered = direction > 0 ? (tail[0].Y - values.Min()) / Math.Max(span, 1e-12) : (values.Max() - tail[0].Y) / Math.Max(span, 1e-12);
        if (tailSpan > Math.Max(span * .05, tolerance) || tailSlope > avgSlope * .22 || covered < .95) return false;
        var lineDx = dx; var maxDeviation = tail.Skip(1).SkipLast(1).Select(p => Math.Abs(p.Y - (tail[0].Y + (tail[^1].Y - tail[0].Y) * ((p.X - tail[0].X) / lineDx)))).DefaultIfEmpty(0).Max();
        return maxDeviation <= Math.Max(tailSpan * .2, tolerance);
    }

    private static bool TailDirectionCovered(IReadOnlyList<XY> samples, double maxInput)
    {
        if (samples.Count < 8) return true;
        var values = samples.Select(p => p.Y).ToArray(); var span = values.Max() - values.Min();
        var scale = Math.Max(1, Math.Max(span, values.Max(Math.Abs)));
        if (span <= Math.Max(scale * 1e-6, 1e-8)) return true;
        var tail = samples.Skip(Math.Max(0, (int)(samples.Count * .72))).ToArray(); var dx = tail[^1].X - tail[0].X;
        if (dx <= 0) return true;
        var terminal = samples.TakeLast(4).ToArray(); var terminalDx = terminal[^1].X - terminal[0].X;
        if (terminalDx <= 0) return true;
        var terminalSlope = Math.Abs(terminal[^1].Y - terminal[0].Y) / terminalDx;
        var floor = Math.Max(scale * 1e-7 / Math.Max(maxInput, 1e-12), 1e-10);
        if (terminalSlope <= floor) return true;
        var average = span / Math.Max(maxInput, 1e-12); var tailSlope = Math.Abs(tail[^1].Y - tail[0].Y) / dx;
        return terminalSlope <= average * .005 && (tailSlope <= floor || terminalSlope <= tailSlope * .1);
    }

    private static double? FindPracticalTailStart(Func<double, double> curve, HashSet<double> anchors, double maxInput, double anchorMax)
    {
        var samples = SampleCoverage(curve, maxInput, anchors, 256);
        if (samples.Count < 12) return null;
        var yMin = samples.Min(p => p.Y); var yMax = samples.Max(p => p.Y); var span = yMax - yMin;
        var scale = Math.Max(1, Math.Max(span, samples.Max(p => Math.Abs(p.Y))));
        var tolerance = Math.Max(Math.Max(span * .006, scale * 1e-5), 1e-7);
        if (span <= tolerance) return anchorMax > 0 ? anchorMax : null;
        for (var i = 0; i < samples.Count - 6; i++)
        {
            var start = samples[i]; if (start.X < anchorMax) continue;
            var tail = samples.Skip(i).ToArray(); var tailDx = tail[^1].X - tail[0].X; if (tailDx <= 0) continue;
            var tailSpan = tail.Max(p => p.Y) - tail.Min(p => p.Y);
            var tailSlope = Math.Abs(tail[^1].Y - tail[0].Y) / tailDx;
            var averageSlope = span / Math.Max(maxInput, 1e-12);
            var coverage = samples[^1].Y >= samples[0].Y ? (start.Y - yMin) / Math.Max(span, 1e-12) : (yMax - start.Y) / Math.Max(span, 1e-12);
            var future = SafeCurveValue(curve, start.X * 2);
            if (tailSpan > Math.Max(span * .01, tolerance) || tailSlope > averageSlope * .05 || coverage < .992 ||
                Math.Abs(future - start.Y) > Math.Max(Math.Max(span * .003, tolerance), 1e-8) || !TailDirectionCovered(samples, maxInput)) continue;
            var low = Math.Max(anchorMax, i > 0 ? samples[i - 1].X : start.X); var high = start.X;
            if (high <= low) return high;
            for (var iteration = 0; iteration < 20; iteration++)
            {
                var mid = (low + high) * .5; var refined = SampleCoverage(curve, maxInput, anchors.Append(mid).ToHashSet(), 256);
                var index = refined.FindIndex(p => p.X >= mid);
                if (index >= 0 && TailPredicate(curve, refined, index, maxInput, yMin, yMax, scale)) high = mid; else low = mid;
            }
            return high;
        }
        return null;
    }

    private static bool TailPredicate(Func<double, double> curve, IReadOnlyList<XY> samples, int index, double maxInput, double yMin, double yMax, double yScale)
    {
        if (index < 0 || index >= samples.Count - 6) return false;
        var tail = samples.Skip(index).ToArray(); var span = yMax - yMin; var tolerance = Math.Max(Math.Max(span * .006, yScale * 1e-5), 1e-8);
        var tailSpan = tail.Max(p => p.Y) - tail.Min(p => p.Y); var dx = tail[^1].X - tail[0].X;
        if (dx <= 0) return false;
        var slope = Math.Abs(tail[^1].Y - tail[0].Y) / dx; var avg = span / Math.Max(maxInput, 1e-12);
        var start = samples[index]; var covered = samples[^1].Y >= samples[0].Y ? (start.Y - yMin) / Math.Max(span, 1e-12) : (yMax - start.Y) / Math.Max(span, 1e-12);
        return tailSpan <= Math.Max(span * .01, tolerance) && (avg <= 0 || slope <= avg * .05) && covered >= .992 &&
            Math.Abs(SafeCurveValue(curve, start.X * 2) - start.Y) <= Math.Max(Math.Max(span * .003, tolerance), 1e-8) && TailDirectionCovered(samples, maxInput);
    }

    private static double RefineCoverageEnd(Func<double, double> curve, HashSet<double> anchors, double low, double high)
    {
        for (var i = 0; i < 18; i++)
        {
            var mid = (low + high) * .5;
            if (CoverageCanHandoff(curve, SampleCoverage(curve, mid, anchors), mid, anchors)) high = mid; else low = mid;
        }
        return high;
    }

    private static List<double> KnownEdges(string mode, string cap, Dictionary<string, object?> args, double max,
        string type = "gain")
    {
        double A(string key, double fallback = 0) => Number(args.GetValueOrDefault(key), fallback);
        var edges = new List<double>();
        void Add(double x) { if (double.IsFinite(x) && x > 0 && x < max) edges.Add(x); }
        if (mode is "classic/linear" or "natural") Add(A("input_offset"));
        if (mode == "jump" || (cap is "in" or "io")) Add(A("cap_x"));
        if (mode == "synchronous") Add(A("sync_speed"));
        if (mode == "motivity (1.6.1)") Add(A("midpoint"));
        if (mode == "lut") edges.AddRange(Lookup(args).Select(p => p.X));
        if (mode == "classic/linear" && cap == "out" && A("cap_y") > 0)
        {
            var offset = A("input_offset");
            var exponent = Math.Max(1.000000000001, A("exponent", 2));
            var acceleration = Math.Max(0, A("acceleration", .005));
            var capDelta = Math.Abs(A("cap_y") - 1);
            if (capDelta > 0 && acceleration > 0)
            {
                if (type == "gain")
                {
                    var root = Math.Pow(capDelta / exponent, 1 / (exponent - 1));
                    Add((acceleration * offset + root) / acceleration);
                }
                else
                {
                    double Uncapped(double x) => Math.Pow(acceleration, exponent - 1) *
                        Math.Pow(Math.Max(0, x - offset), exponent) / Math.Max(x, 1e-300);
                    var low = Math.Max(0, offset);
                    var high = Math.Max(1, low + 1);
                    while (Uncapped(high) < capDelta && double.IsFinite(high))
                    {
                        low = high;
                        high *= 2;
                    }
                    if (double.IsFinite(high) && Uncapped(high) >= capDelta)
                    {
                        while (true)
                        {
                            var middle = low + (high - low) * 0.5;
                            if (middle == low || middle == high) break;
                            if (Uncapped(middle) < capDelta) low = middle;
                            else high = middle;
                        }
                        Add(low + (high - low) * 0.5);
                    }
                }
            }
        }
        if (mode == "power" && cap == "out" && A("cap_y") > 0)
        {
            var power = Math.Max(1e-12, A("exponent_power", .05)); var scale = Math.Max(1e-12, A("scale", 1));
            Add(Math.Pow(A("cap_y") / (power + 1), 1 / power) / scale);
        }
        return edges.Where(x => x > 0 && x < max).Distinct().Order().ToList();
    }

    private static List<double> SplineEdges(string mode, string type, string cap,
        Dictionary<string, object?> args, double max, int precision = 6)
    {
        IEnumerable<double> landmarks = mode switch
        {
            "classic/linear" => KnownEdges(mode, cap, args, max, type),
            "natural" => KnownEdges(mode, cap, args, max, type).Where(x => x == Number(args.GetValueOrDefault("input_offset"), 0)),
            "jump" when Number(args.GetValueOrDefault("smooth"), 0.5) * Number(args.GetValueOrDefault("cap_x"), 15) < 1
                => KnownEdges(mode, cap, args, max, type),
            "lut" => Lookup(args).Select(point => point.X),
            "power" when type != "gain" => KnownEdges(mode, cap, args, max, type),
            _ => [],
        };
        if (mode == "motivity (1.6.1)" && type == "gain")
        {
            var legacy = BuildEvaluator(mode, "legacy", cap, args);
            if (TryGetAsymptoticLimit(mode, "legacy", cap, args, legacy, out var limit))
            {
                var midpoint = Number(args.GetValueOrDefault("midpoint"), 5);
                var tailStart = FindLimitCoverageEnd(legacy, limit, Math.Max(midpoint, 1), midpoint, precision);
                landmarks = landmarks.Append(tailStart);
            }
        }
        if (mode == "power" && !(cap == "io" && type != "gain"))
        {
            var outputOffset = Number(args.GetValueOrDefault("output_offset"), 0);
            if (outputOffset > 0)
            {
                var exponent = Math.Max(Number(args.GetValueOrDefault("exponent_power"), .05), 1e-12);
                var scale = Math.Max(Number(args.GetValueOrDefault("scale"), 1), 1e-12);
                landmarks = landmarks.Append(SafePow(outputOffset / (exponent + 1), 1 / exponent) / scale);
            }
        }
        return landmarks.Where(x => double.IsFinite(x) && x > 0 && x < max).Distinct().Order().ToList();
    }

    private static string NormalizeFilename(string name)
    {
        var invalid = Path.GetInvalidFileNameChars().ToHashSet();
        var clean = string.Concat(name.Select(c => invalid.Contains(c) ? '_' : c)).Trim().TrimEnd('.');
        if (clean.Length == 0) clean = "profile";
        if (clean.EndsWith(".json", StringComparison.OrdinalIgnoreCase)) clean = clean[..^5];
        if (clean.EndsWith(".cc4", StringComparison.OrdinalIgnoreCase)) clean = clean[..^4];
        return clean + ".cc4";
    }

    private static void EnsureCustomCurveClosed()
    {
        var running = Process.GetProcessesByName("CustomCurve");
        var isRunning = running.Length > 0;
        foreach (var process in running) process.Dispose();
        if (isRunning)
            throw new InvalidOperationException("CustomCurve is open. Close it before loading profiles or updating Output DPI. Nothing was generated.");
    }

    private static void ApplyCustomCurveOutputDpi(int dpi)
    {
        var path = Path.Combine(CustomCurveDataDirectory(), "settings.json");
        if (!File.Exists(path))
            throw new FileNotFoundException("CustomCurve settings.json was not found. Output DPI was not applied.", path);
        var root = JsonNode.Parse(File.ReadAllText(path)) ?? throw new InvalidOperationException("CustomCurve settings.json is invalid.");
        var updated = SetDpiValues(root, dpi);
        if (updated == 0) throw new InvalidOperationException("CustomCurve settings.json contains no DPI values to update.");
        File.WriteAllText(path, root.ToJsonString(JsonOptions));
    }

    private static int SetDpiValues(JsonNode node, int dpi)
    {
        var updated = 0;
        if (node is JsonObject obj)
        {
            foreach (var key in obj.Select(property => property.Key).ToArray())
            {
                if (key.Contains("dpi", StringComparison.OrdinalIgnoreCase))
                {
                    obj[key] = dpi;
                    updated++;
                }
                else if (obj[key] is { } child)
                {
                    updated += SetDpiValues(child, dpi);
                }
            }
        }
        else if (node is JsonArray array)
        {
            foreach (var child in array)
                if (child is not null) updated += SetDpiValues(child, dpi);
        }
        return updated;
    }

    private static string CustomCurveDataDirectory()
    {
        var roamingAppData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        if (string.IsNullOrWhiteSpace(roamingAppData))
            throw new InvalidOperationException("The current user's roaming AppData folder could not be resolved.");
        return Path.GetFullPath(Path.Combine(roamingAppData, "CustomCurve"));
    }

    private static string LoadProfilesDirectly(List<Dictionary<string, object?>> profiles)
    {
        var running = Process.GetProcessesByName("CustomCurve");
        var isRunning = running.Length > 0;
        foreach (var process in running) process.Dispose();
        if (isRunning)
        {
            throw new InvalidOperationException("CustomCurve is open. Close it before loading profiles directly into the app.");
        }
        var path = Path.Combine(CustomCurveDataDirectory(), "profiles.json");
        if (!Directory.Exists(Path.GetDirectoryName(path))) throw new DirectoryNotFoundException("CustomCurve folder was not found.");
        var root = File.Exists(path) ? JsonNode.Parse(File.ReadAllText(path)) as JsonObject : new JsonObject();
        if (root is null) throw new InvalidOperationException("CustomCurve profiles.json is invalid.");
        var stored = root["Profiles"] as JsonArray ?? new JsonArray();
        if (stored.Count + profiles.Count > 10)
            throw new InvalidOperationException($"CustomCurve supports 10 profiles. It currently has {stored.Count}; there is not enough room for {profiles.Count} more.");
        foreach (var profile in profiles)
        {
            var node = JsonNode.Parse(JsonSerializer.Serialize(profile))!.AsObject();
            node["IsNew"] = false;
            stored.Add(node);
        }
        root["Profiles"] = stored;
        File.WriteAllText(path, root.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
        return path;
    }
    private static object LoadProfile(JsonElement r)
    {
        using var d = ReadSettings(r, out var profiles);
        var index = Int(r, "profile_index", 0);
        if (index < 0 || index >= profiles.GetArrayLength())
            throw new InvalidOperationException("The selected profile does not exist in settings.json.");

        var profile = profiles[index];
        var horizontalParams = FindAccelParams(profile, false);
        var verticalParams = FindAccelParams(profile, true) ?? horizontalParams;
        if (!horizontalParams.HasValue || horizontalParams.Value.ValueKind != JsonValueKind.Object)
            throw new InvalidOperationException("The selected profile has no acceleration parameters.");

        var horizontal = CurveState(horizontalParams.Value);
        var vertical = CurveState(verticalParams ?? horizontalParams.Value);
        var (domainX, domainY) = AxisWeights(profile, "Stretches domain for horizontal vs vertical inputs", 1e-12);
        var (rangeX, rangeY) = AxisWeights(profile, "Stretches accel range for horizontal vs vertical inputs", 0);
        var speed = Prop(profile, "Input speed calculation parameters");
        var byComponent = !Bool(Prop(speed, "Whole/combined accel (set false for 'by component' mode)"), true);
        var hasVertical = verticalParams.HasValue;
        var sensitivity = Num(profile, "Output DPI", 1000) / 1000d;
        var yx = Num(profile, "Y/X output DPI ratio (vertical sens multiplier)", 1);
        var anisotropy = new[] { domainX, domainY, rangeX, rangeY }.Any(x => Math.Abs(x - 1) > 1e-12);
        var separate = (byComponent && hasVertical) || anisotropy || Math.Abs(yx - 1) > 1e-12;
        if (!byComponent || !hasVertical) vertical = horizontal;
        var horizontalState = new { mode = horizontal.mode, curve_type = horizontal.curve_type, cap_mode = horizontal.cap_mode, args = horizontal.args };
        var verticalState = new { mode = vertical.mode, curve_type = vertical.curve_type, cap_mode = vertical.cap_mode, args = vertical.args };

        var state = new Dictionary<string, object?>
        {
            ["profile_name"] = Str(profile, "name", "Imported Profile").Trim() is { Length: > 0 } n ? n : "Imported Profile",
            ["horizontal"] = horizontalState,
            ["vertical"] = verticalState,
            ["separate_curves"] = separate,
            ["by_component"] = byComponent,
            ["anisotropy_enabled"] = anisotropy,
            ["sensitivity_multiplier"] = sensitivity,
            ["yx_ratio"] = yx,
            ["domain_x"] = domainX, ["domain_y"] = domainY,
            ["range_x"] = rangeX, ["range_y"] = rangeY,
            ["left_right_ratio"] = Num(profile, "L/R output DPI ratio (left sens multiplier)", 1),
            ["up_down_ratio"] = Num(profile, "U/D output DPI ratio (up sens multiplier)", 1),
            ["rotation"] = Num(profile, "Degrees of rotation", 0),
            ["angle_snap"] = Num(profile, "Degrees of angle snapping", 0),
            ["lp_norm"] = Num(speed, "lpNorm", 2),
            ["input_smoothing_ms"] = Num(speed, "Time in ms after which an input is weighted at half its original value.", 0),
            ["output_smoothing_ms"] = Num(speed, "Time in ms after which an output is weighted at half its original value.", 0),
        };

        var config = LoadConfig();
        config["profile_name"] = state["profile_name"];
        config["mode"] = horizontal.mode;
        config["curve_type"] = horizontal.curve_type;
        config["cap_mode"] = horizontal.cap_mode;
        config["args"] = horizontal.args;
        config["vertical_mode"] = vertical.mode;
        config["vertical_curve_type"] = vertical.curve_type;
        config["vertical_cap_mode"] = vertical.cap_mode;
        config["vertical_args"] = vertical.args;
        config["separate_vertical_curve"] = byComponent;
        config["anisotropy_enabled"] = anisotropy;
        config["sensitivity_multiplier"] = sensitivity;
        config["yx_ratio"] = yx;
        config["domain_x"] = domainX; config["domain_y"] = domainY;
        config["range_x"] = rangeX; config["range_y"] = rangeY;
        Save(config);
        return new { profile_count = profiles.GetArrayLength(), generator_state = state };
    }

    private static JsonElement Prop(JsonElement value, string key) =>
        value.ValueKind == JsonValueKind.Object && value.TryGetProperty(key, out var result) ? result : default;

    private static JsonElement? FindAccelParams(JsonElement profile, bool vertical)
    {
        var keys = vertical
            ? new[] { "Vertical accel parameters", "Y accel parameters" }
            : new[] { "Whole or horizontal accel parameters", "Whole accel parameters", "Horizontal accel parameters" };
        foreach (var key in keys)
        {
            var value = Prop(profile, key);
            if (value.ValueKind == JsonValueKind.Object) return value;
        }
        return null;
    }

    private static (string mode, string curve_type, string cap_mode, Dictionary<string, object?> args) CurveState(JsonElement parameters)
    {
        var mode = MapMode(Str(parameters, "mode", "noaccel"));
        var cap = MapCapMode(Str(parameters, "Cap mode", "output"));
        var gain = Bool(Prop(parameters, "Gain / Velocity"), Bool(Prop(parameters, "Gain/Velocity"), true));
        var type = mode == "lut" ? "legacy" : gain ? "gain" : "legacy";
        var args = DefaultsFor(mode, cap);
        var capData = Prop(parameters, "Cap / Jump");
        var keys = new Dictionary<string, string>
        {
            ["input_offset"] = "inputOffset", ["output_offset"] = "outputOffset",
            ["decay_rate"] = "decayRate", ["growth_rate"] = "growthRate",
            ["exponent_power"] = "exponentPower", ["sync_speed"] = "syncSpeed",
            ["exponent"] = "exponentClassic",
        };
        foreach (var key in args.Keys.ToArray())
        {
            if (key == "lut_velocity") { args[key] = gain; continue; }
            if (key == "lookup_points") { args[key] = LookupFromRaw(parameters); continue; }
            var sourceKey = keys.GetValueOrDefault(key, key);
            var source = key is "cap_x" or "cap_y" ? Prop(capData, key == "cap_x" ? "x" : "y") : Prop(parameters, sourceKey);
            if (source.ValueKind != JsonValueKind.Undefined)
                args[key] = source.ValueKind == JsonValueKind.String ? source.GetString() : source.ToString();
        }
        return (mode, type, cap, args);
    }

    private static List<XY> LookupFromRaw(JsonElement parameters)
    {
        foreach (var key in new[] { "Lookup table", "lookupTable", "lookup", "LookUpTable", "points", "Points" })
        {
            var value = Prop(parameters, key);
            if (value.ValueKind == JsonValueKind.Array)
            {
                var points = new List<XY>();
                foreach (var item in value.EnumerateArray())
                {
                    if (item.ValueKind == JsonValueKind.Array && item.GetArrayLength() >= 2)
                        points.Add(new XY(Num(item[0], 0), Num(item[1], 1)));
                    else if (item.ValueKind == JsonValueKind.Object)
                        points.Add(new XY(Num(item, "x", 0), Num(item, "y", 1)));
                }
                if (points.Count > 0) return ValidateLookupPoints(points);
            }
            if (value.ValueKind == JsonValueKind.String)
            {
                var parsed = ParseLookupText(value.GetString() ?? "");
                if (parsed.Count > 0) return ValidateLookupPoints(parsed);
            }
        }
        var data = Prop(parameters, "data");
        if (data.ValueKind == JsonValueKind.Array && data.GetArrayLength() >= 4)
        {
            var values = data.EnumerateArray().ToArray();
            var points = new List<XY>();
            for (var i = 0; i + 1 < values.Length; i += 2)
            {
                var x = Num(values[i], double.NaN); var y = Num(values[i + 1], double.NaN);
                if (double.IsFinite(x) && double.IsFinite(y)) points.Add(new XY(x, y));
            }
            if (points.Count > 1) return ValidateLookupPoints(points);
        }
        return [];
    }

    private static List<XY> ParseLookupText(string text)
    {
        var points = new List<XY>();
        foreach (var pair in text.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var parts = pair.Split(',', StringSplitOptions.TrimEntries);
            if (parts.Length == 2 && double.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var x) &&
                double.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var y))
                points.Add(new XY(x, y));
            else throw new InvalidOperationException($"Lookup point '{pair}' must contain one numeric X,Y pair.");
        }
        return points;
    }

    private static List<XY> ValidateLookupPoints(List<XY> points)
    {
        const int maxPoints = 257;
        if (points.Count < 2) throw new InvalidOperationException("A lookup table requires at least two points.");
        if (points.Count > maxPoints) throw new InvalidOperationException($"A lookup table can contain at most {maxPoints} points.");
        var lastX = 0f;
        for (var index = 0; index < points.Count; index++)
        {
            var point = points[index];
            var x = (float)point.X; var y = (float)point.Y;
            if (!double.IsFinite(point.X) || !double.IsFinite(point.Y) || !float.IsFinite(x) || !float.IsFinite(y))
                throw new InvalidOperationException($"Lookup point {index + 1} must contain finite values representable by RawAccel.");
            if (x <= 0) throw new InvalidOperationException($"Lookup point {index + 1} X must be greater than zero; RawAccel already supplies the (0,0) point.");
            if (x <= lastX) throw new InvalidOperationException($"Lookup point {index + 1} X must be greater than the previous point's X.");
            if (y <= 0) throw new InvalidOperationException($"Lookup point {index + 1} Y must be greater than zero.");
            lastX = x;
        }
        return points;
    }

    private static (double x, double y) AxisWeights(JsonElement profile, string key, double minimum)
    {
        var weights = Prop(profile, key);
        return (Math.Max(minimum, Num(weights, "x", 1)), Math.Max(minimum, Num(weights, "y", 1)));
    }

    private static string MapMode(string m) => m.Trim().ToLowerInvariant() switch
    {
        "classic" or "linear" => "classic/linear", "motivity" => "motivity (1.6.1)",
        "lookup" or "lookuptable" => "lut", _ => m.Trim().ToLowerInvariant()
    };
    private static string MapCapMode(string cap) => cap.Trim().ToLowerInvariant() switch
    {
        "input" or "in" => "in", "in_out" or "both" or "io" => "io", _ => "out"
    };
    private static string Str(JsonElement e,string k,string d)=>e.ValueKind==JsonValueKind.Object&&e.TryGetProperty(k,out var v)?v.ValueKind==JsonValueKind.String?v.GetString()??d:v.ToString():d;
    private static int Int(JsonElement e,string k,int d)=>int.TryParse(Str(e,k,d.ToString()),out var n)?n:d;
    private static double Num(JsonElement e,string k,double d)=>double.TryParse(Str(e,k,d.ToString(CultureInfo.InvariantCulture)),NumberStyles.Float,CultureInfo.InvariantCulture,out var n)&&double.IsFinite(n)?n:d;
    private static double Num(JsonElement value,double d)=>double.TryParse(value.ValueKind==JsonValueKind.String?value.GetString():value.ToString(),NumberStyles.Float,CultureInfo.InvariantCulture,out var n)&&double.IsFinite(n)?n:d;
    private static double Number(object? x,double d)=>double.TryParse(Convert.ToString(x,CultureInfo.InvariantCulture),NumberStyles.Float,CultureInfo.InvariantCulture,out var n)&&double.IsFinite(n)?n:d;
    private static bool Bool(object? x,bool d)=>x is bool b?b:bool.TryParse(Convert.ToString(x),out var q)?q:d;
    private static bool Bool(JsonElement e,bool d)=>e.ValueKind switch
    {
        JsonValueKind.True=>true, JsonValueKind.False=>false,
        JsonValueKind.Number=>e.TryGetDouble(out var number)?number!=0:d,
        JsonValueKind.String=>e.GetString()?.Trim().ToLowerInvariant() switch
        {"true" or "1" or "yes" or "y" or "on"=>true,"false" or "0" or "no" or "n" or "off"=>false,_=>d},
        _=>d
    };
    private static bool Bool(JsonElement e,string k,bool d)=>Bool(Prop(e,k),d);
    private static void Save(Dictionary<string,object?> c)
    {
        Directory.CreateDirectory(ConfigDirectory);
        File.WriteAllText(ConfigPath, JsonSerializer.Serialize(c, JsonOptions));
    }
}





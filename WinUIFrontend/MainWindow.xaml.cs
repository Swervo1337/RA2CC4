using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml.Media;
using System.Globalization;
using System.Diagnostics;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Text.RegularExpressions;
using RA2CC4.Core;
using Windows.Graphics;
using Windows.Globalization.NumberFormatting;
using Windows.Storage;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace RA2CC4.WinUI;

public sealed partial class MainWindow : Window
{
    private const string InstalledRelease = "26.11";
    private const string ReleaseCatalogUrl = "https://raw.githubusercontent.com/Swervo1337/RA2CC4/refs/heads/ra2cc4/Latest";
    private const string ReleaseDownloadsUrl = "https://github.com/Swervo1337/RA2CC4/releases/latest";
    private static readonly HttpClient ReleaseClient = new() { Timeout = TimeSpan.FromSeconds(6) };
    private readonly Dictionary<string, Control> _fields = new();
    private readonly Dictionary<string, Control> _verticalFields = new();
    private readonly Dictionary<Control, LookupPointEditorModel> _lookupPointEditors = new();
    private Dictionary<string, object?> _lastArgs = new();
    private Dictionary<string, object?> _lastVerticalArgs = new();
    private bool _loading;
    private readonly DispatcherTimer _draftSaveTimer = new() { Interval = TimeSpan.FromMilliseconds(450) };

    public sealed class LookupPointEditorModel
    {
        public ObservableCollection<LookupPointRow> Points { get; } = new();
        public event Action? Changed;
        public LookupPointEditorModel() => Points.CollectionChanged += (_, _) => Changed?.Invoke();
        public void NotifyChanged() => Changed?.Invoke();
        public void InsertSorted(LookupPointRow point)
        {
            var index = 0;
            while (index < Points.Count && Points[index].X < point.X) index++;
            Points.Insert(index, point);
        }
        public void SortByX()
        {
            var sorted = Points.OrderBy(point => point.X).ToArray();
            for (var target = 0; target < sorted.Length; target++)
            {
                var current = Points.IndexOf(sorted[target]);
                if (current != target) Points.Move(current, target);
            }
        }
    }

    public sealed class LookupPointRow : INotifyPropertyChanged
    {
        private double _x;
        private double _y;
        public LookupPointEditorModel Editor { get; }
        public double X { get => _x; set { if (_x == value) return; _x = value; Changed(); Changed(nameof(DisplayX)); Editor.NotifyChanged(); } }
        public double Y { get => _y; set { if (_y == value) return; _y = value; Changed(); Changed(nameof(DisplayY)); Editor.NotifyChanged(); } }
        public string DisplayX => $"X  {X.ToString("G4", CultureInfo.InvariantCulture)}";
        public string DisplayY => $"Y  {Y.ToString("G4", CultureInfo.InvariantCulture)}";
        public LookupPointRow(LookupPointEditorModel editor, double x, double y) { Editor = editor; _x = x; _y = y; }
        public event PropertyChangedEventHandler? PropertyChanged;
        private void Changed([CallerMemberName] string? propertyName = null) => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }

    public MainWindow()
    {
        InitializeComponent();
        RawAccelPathBox.TextChanged += RawAccelPathChanged;
        foreach (var box in new[]
        {
            SensitivityMultiplierBox, YXRatioBox, DomainXBox, DomainYBox, RangeXBox, RangeYBox,
            RotationBox, AngleSnapBox, LeftRightRatioBox, UpDownRatioBox, LpNormBox,
            InputSmoothingBox, OutputSmoothingBox, OutputDpiBox,
        })
        {
            box.NumberFormatter = CreateNumberFormatter();
            NormalizeSpinSteps(box);
        }
        Title = "";
        var windowId = Win32Interop.GetWindowIdFromWindow(WindowNative.GetWindowHandle(this));
        var appWindow = AppWindow.GetFromWindowId(windowId);
        var iconPath = ExtractWindowIcon();
        if (iconPath is not null) appWindow.SetIcon(iconPath);
        appWindow.Resize(new SizeInt32(1080, 760));
        if (AppWindowTitleBar.IsCustomizationSupported())
        {
            var titleBar = appWindow.TitleBar;
            titleBar.IconShowOptions = IconShowOptions.ShowIconAndSystemMenu;
            var surface = (AppNavigation.Background as SolidColorBrush)?.Color ?? Colors.White;
            titleBar.BackgroundColor = surface;
            titleBar.ButtonBackgroundColor = surface;
            titleBar.InactiveBackgroundColor = surface;
            titleBar.ButtonInactiveBackgroundColor = surface;
        }
        if (appWindow.Presenter is OverlappedPresenter presenter)
        {
            presenter.IsResizable = false;
            presenter.IsMaximizable = false;
        }
        AppNavigation.SelectedItem = AppNavigation.MenuItems[0];
        for (var precision = 1; precision <= 10; precision++)
            SettingsPrecisionBox.Items.Add(precision.ToString());
        foreach (var point in new[] { 32, 64, 96, 128, 160, 192, 256, 320, 384, 512, 640, 768, 1024, 2048, 4096 })
            SettingsPointCountBox.Items.Add(point.ToString());
        DestinationBox.SelectedIndex = 0;
        _draftSaveTimer.Tick += async (_, _) =>
        {
            _draftSaveTimer.Stop();
            await SaveDraftAsync();
        };
        _ = InitializeAsync();
    }

    private static string? ExtractWindowIcon()
    {
        try
        {
            var iconDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "RA2CC4", "Assets");
            var iconPath = Path.Combine(iconDirectory, "icon.ico");
            using var source = typeof(MainWindow).Assembly.GetManifestResourceStream("RA2CC4.WinUI.Assets.icon.ico");
            if (source is null) return null;
            Directory.CreateDirectory(iconDirectory);
            using var destination = File.Create(iconPath);
            source.CopyTo(destination);
            return iconPath;
        }
        catch { return null; }
    }

    private void NavigationSelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        var tag = (args.SelectedItem as NavigationViewItem)?.Tag?.ToString();
        HomePage.Visibility = tag == "home" ? Visibility.Visible : Visibility.Collapsed;
        GeneratePage.Visibility = tag == "generate" ? Visibility.Visible : Visibility.Collapsed;
        ImportPage.Visibility = tag == "import" ? Visibility.Visible : Visibility.Collapsed;
        AdvancedPage.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
        AboutPage.Visibility = tag == "about" ? Visibility.Visible : Visibility.Collapsed;
    }

    private void OpenAdvancedSettingsClicked(object sender, RoutedEventArgs e)
    {
        foreach (var item in AppNavigation.MenuItems.OfType<NavigationViewItem>())
        {
            if (item.Tag?.ToString() != "settings") continue;
            AppNavigation.SelectedItem = item;
            break;
        }
    }

    private void UpdateSetupRecommendation()
    {
        var missing = new List<string>();
        if (string.IsNullOrWhiteSpace(RawAccelPathBox.Text) || !Directory.Exists(RawAccelPathBox.Text))
            missing.Add("the RawAccel folder");
        if (string.IsNullOrWhiteSpace(CustomCurvePathBox.Text) || !File.Exists(CustomCurvePathBox.Text))
            missing.Add("CustomCurve.exe");

        SetupRecommendation.Visibility = missing.Count == 0 ? Visibility.Collapsed : Visibility.Visible;
        SetupRecommendationText.Text = missing.Count switch
        {
            2 => "Set the RawAccel folder and CustomCurve.exe location in App Settings to make importing and loading profiles easier.",
            1 => $"Set {missing[0]} location in App Settings to make importing and loading profiles easier.",
            _ => "",
        };
    }

    private static string SelectedTag(ComboBox combo) =>
        (combo.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "";

    private NumberBox CreateNumberBox(JsonElement field, double minWidth)
    {
        var minimum = field.TryGetProperty("minimum", out var minValue) && minValue.ValueKind == JsonValueKind.Number
            ? minValue.GetDouble() : -double.MaxValue;
        var maximum = field.TryGetProperty("maximum", out var maxValue) && maxValue.ValueKind == JsonValueKind.Number
            ? maxValue.GetDouble() : double.MaxValue;
        var text = field.GetProperty("value").GetString() ?? "0";
        if (!double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out var value) || !double.IsFinite(value))
            value = Math.Max(minimum, 0.0);
        value = Math.Clamp(value, minimum, maximum);
        var numberBox = new NumberBox
        {
            Minimum = minimum,
            Maximum = maximum,
            Value = value,
            SmallChange = 0.1,
            NumberFormatter = CreateNumberFormatter(),
            MinWidth = minWidth,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Inline,
            ValidationMode = NumberBoxValidationMode.InvalidInputOverwritten,
        };
        NormalizeSpinSteps(numberBox);
        numberBox.ValueChanged += (_, _) => ScheduleDraftSave();
        return numberBox;
    }

    private static void NormalizeSpinSteps(NumberBox box)
    {
        box.ValueChanged += (_, e) =>
        {
            if (!double.IsFinite(e.OldValue) || !double.IsFinite(e.NewValue) || box.SmallChange <= 0) return;
            var difference = e.NewValue - e.OldValue;
            var stepCount = Math.Round(difference / box.SmallChange);
            var magnitude = Math.Abs(e.NewValue);
            var ulp = Math.BitIncrement(magnitude) - magnitude;
            if (stepCount == 0 || Math.Abs(difference - stepCount * box.SmallChange) > Math.Max(1e-12, ulp * 16)) return;
            try
            {
                var oldValue = (decimal)e.OldValue;
                var step = (decimal)box.SmallChange * (decimal)stepCount;
                var adjusted = (double)(oldValue + step);
                if (adjusted != e.NewValue)
                {
                    var textBox = FindNumberBoxTextBox(box);
                    var preserveCaret = textBox is not null && textBox.FocusState != FocusState.Unfocused;
                    var selectionStart = textBox?.SelectionStart ?? 0;
                    var selectionLength = textBox?.SelectionLength ?? 0;
                    box.Value = adjusted;
                    if (preserveCaret && textBox is not null)
                    {
                        box.DispatcherQueue.TryEnqueue(() =>
                        {
                            if (!textBox.IsLoaded || textBox.FocusState == FocusState.Unfocused) return;
                            var start = Math.Min(selectionStart, textBox.Text.Length);
                            textBox.Select(start, Math.Min(selectionLength, textBox.Text.Length - start));
                        });
                    }
                }
            }
            catch (OverflowException) { }
        };
    }

    private static TextBox? FindNumberBoxTextBox(DependencyObject parent)
    {
        for (var index = 0; index < VisualTreeHelper.GetChildrenCount(parent); index++)
        {
            var child = VisualTreeHelper.GetChild(parent, index);
            if (child is TextBox textBox) return textBox;
            var descendant = FindNumberBoxTextBox(child);
            if (descendant is not null) return descendant;
        }
        return null;
    }

    private static DecimalFormatter CreateNumberFormatter() => new()
    {
        IsGrouped = false,
        IntegerDigits = 1,
        FractionDigits = 0,
        NumberRounder = new SignificantDigitsNumberRounder
        {
            SignificantDigits = 10,
            RoundingAlgorithm = RoundingAlgorithm.RoundHalfUp,
        },
    };

    private static double ReadNumberBoxValue(NumberBox box, string label)
    {
        var value = box.Value;
        if (!double.IsFinite(value) || value < box.Minimum || value > box.Maximum)
            throw new InvalidOperationException($"{label} must be a valid number between {box.Minimum:G6} and {box.Maximum:G6}.");
        return value;
    }

    private object CurrentRequest(string action) => new
    {
        action,
        mode = SelectedTag(ModeBox),
        curve_type = SelectedTag(CurveTypeBox),
        cap_mode = SelectedTag(CapModeBox),
        args = _lastArgs,
    };

    private async Task InitializeAsync()
    {
        _loading = true;
        try
        {
            using var response = await CurveBackend.SendAsync(new { action = "settings" });
            var config = response.RootElement.GetProperty("config");
            ProfileNameBox.Text = config.TryGetProperty("profile_name", out var name) ? name.GetString() ?? "New Profile" : "New Profile";
            SelectTag(ModeBox, config, "mode", "natural");
            SelectTag(CurveTypeBox, config, "curve_type", "gain");
            GainCheck.IsChecked = SelectedTag(CurveTypeBox) == "gain";
            SelectTag(CapModeBox, config, "cap_mode", "out");
            SelectTag(VerticalModeBox, config, "vertical_mode", "natural");
            SelectTag(VerticalCurveTypeBox, config, "vertical_curve_type", "gain");
            VerticalGainCheck.IsChecked = SelectedTag(VerticalCurveTypeBox) == "gain";
            SelectTag(VerticalCapModeBox, config, "vertical_cap_mode", "out");
            SeparateVerticalCheck.IsChecked = config.TryGetProperty("separate_vertical_curve", out var separateValue) && separateValue.GetBoolean();
            var points = config.TryGetProperty("point_count", out var pointValue) ? pointValue.ToString() : "128";
            var precision = config.TryGetProperty("precision", out var precisionValue) ? precisionValue.ToString() : "6";
            SettingsPointCountBox.SelectedItem = points;
            SettingsPrecisionBox.SelectedItem = precision;
            SensitivityMultiplierBox.Value = config.TryGetProperty("sensitivity_multiplier", out var sensValue) ? sensValue.GetDouble() : 1;
            YXRatioBox.Value = config.TryGetProperty("yx_ratio", out var ratioValue) ? ratioValue.GetDouble() : 1;
            LeftRightRatioBox.Value = config.TryGetProperty("left_right_ratio", out var lrValue) ? lrValue.GetDouble() : 1;
            UpDownRatioBox.Value = config.TryGetProperty("up_down_ratio", out var udValue) ? udValue.GetDouble() : 1;
            RotationBox.Value = config.TryGetProperty("rotation", out var rotationValue) ? rotationValue.GetDouble() : 0;
            AngleSnapBox.Value = config.TryGetProperty("angle_snap", out var snapValue) ? snapValue.GetDouble() : 0;
            LpNormBox.Value = config.TryGetProperty("lp_norm", out var lpNormValue) ? lpNormValue.GetDouble() : 2;
            OutputDpiEnabledCheck.IsChecked = config.TryGetProperty("output_dpi_enabled", out var outputDpiEnabled) && outputDpiEnabled.GetBoolean();
            OutputDpiBox.Value = config.TryGetProperty("output_dpi", out var outputDpi) ? outputDpi.GetDouble() : 1000;
            OutputDpiBox.IsEnabled = OutputDpiEnabledCheck.IsChecked == true;
            InputSmoothingBox.Value = config.TryGetProperty("input_smoothing_ms", out var inputSmoothValue) ? inputSmoothValue.GetDouble() : 0;
            OutputSmoothingBox.Value = config.TryGetProperty("output_smoothing_ms", out var outputSmoothValue) ? outputSmoothValue.GetDouble() : 0;
            AnisotropyEnabledCheck.IsChecked = config.TryGetProperty("anisotropy_enabled", out var anisotropyValue) && anisotropyValue.GetBoolean();
            DomainXBox.Value = config.TryGetProperty("domain_x", out var domainX) ? domainX.GetDouble() : 1;
            DomainYBox.Value = config.TryGetProperty("domain_y", out var domainY) ? domainY.GetDouble() : 1;
            RangeXBox.Value = config.TryGetProperty("range_x", out var rangeX) ? rangeX.GetDouble() : 1;
            RangeYBox.Value = config.TryGetProperty("range_y", out var rangeY) ? rangeY.GetDouble() : 1;
            RawAccelPathBox.Text = config.TryGetProperty("rawaccel_path", out var rawPath) ? rawPath.GetString() ?? "" : "";
            CustomCurvePathBox.Text = config.TryGetProperty("customcurve_path", out var appPath) ? appPath.GetString() ?? "" : "";
            UpdateSetupRecommendation();
            if (string.IsNullOrWhiteSpace(ImportPathBox.Text) && !string.IsNullOrWhiteSpace(RawAccelPathBox.Text))
                ImportPathBox.Text = Path.Combine(RawAccelPathBox.Text, "settings.json");
            if (config.TryGetProperty("args", out var args) && args.ValueKind == JsonValueKind.Object)
                _lastArgs = JsonSerializer.Deserialize<Dictionary<string, object?>>(args.GetRawText()) ?? new();
            if (config.TryGetProperty("vertical_args", out var verticalArgs) && verticalArgs.ValueKind == JsonValueKind.Object)
                _lastVerticalArgs = JsonSerializer.Deserialize<Dictionary<string, object?>>(verticalArgs.GetRawText()) ?? new();
        }
        catch (Exception ex)
        {
            ModeBox.SelectedIndex = 0;
            CurveTypeBox.SelectedIndex = 1;
            CapModeBox.SelectedIndex = 0;
            SettingsPointCountBox.SelectedItem = "128";
            SettingsPrecisionBox.SelectedItem = "6";
            StatusText.Text = "Using default settings";
            ShowError("Could not load saved settings", ex.Message);
        }
        finally
        {
            _loading = false;
        }
        _loading = true;
        AnisotropyContent.IsEnabled = AnisotropyEnabledCheck.IsChecked == true;
        SeparateVerticalCheck.IsEnabled = true;
        _loading = false;
        UpdateModeOptionVisibility();
        UpdateVerticalModeOptionVisibility();
        await RefreshFieldsAsync();
        await RefreshVerticalFieldsAsync();
        UpdateSeparateCurveVisibility();
        AttachAutoSaveHandlers();
        _ = InitializeReleaseCatalogAsync();
    }

    private async Task InitializeReleaseCatalogAsync()
    {
        try
        {
            using var response = await CurveBackend.SendAsync(new { action = "settings" });
            var config = response.RootElement.GetProperty("config");
            if (config.TryGetProperty("release_catalog", out var cached) && cached.ValueKind == JsonValueKind.Object)
                ApplyReleaseCatalog(ReadReleaseCatalog(cached),
                    config.TryGetProperty("latest_release", out var latest) ? latest.GetString() ?? "" : "",
                    config.TryGetProperty("prompted_release", out var prompted) ? prompted.GetString() ?? "" : "");
        }
        catch { }
        await CheckReleaseCatalogAsync();
    }

    private async Task CheckReleaseCatalogAsync()
    {
        try
        {
            var text = await ReleaseClient.GetStringAsync(ReleaseCatalogUrl);
            var catalog = ParseReleaseCatalog(text);
            if (catalog.Count == 0) return;
            var latestRelease = catalog.Keys.OrderByDescending(ParseReleaseVersion).First();
            using (await CurveBackend.SendAsync(new { action = "update_release_catalog", catalog, latest_release = latestRelease })) { }
            var promptedRelease = "";
            using (var response = await CurveBackend.SendAsync(new { action = "settings" }))
            {
                var config = response.RootElement.GetProperty("config");
                if (config.TryGetProperty("prompted_release", out var prompted)) promptedRelease = prompted.GetString() ?? "";
            }
            ApplyReleaseCatalog(catalog, latestRelease, promptedRelease);
        }
        catch { }
    }

    private void ApplyReleaseCatalog(Dictionary<string, string> catalog, string latestRelease, string promptedRelease)
    {
        CurrentUpdateText.Text = $"Update {InstalledRelease}";
        CompatibleVersionText.Text = catalog.TryGetValue(InstalledRelease, out var compatible) ? compatible : "Unavailable offline";
        if (string.IsNullOrWhiteSpace(latestRelease) || promptedRelease == latestRelease ||
            ParseReleaseVersion(latestRelease) <= ParseReleaseVersion(InstalledRelease)) return;
        _ = PromptForUpdateAsync(latestRelease);
    }

    private async Task PromptForUpdateAsync(string release)
    {
        try
        {
            using var _ = await CurveBackend.SendAsync(new { action = "mark_update_prompted", release });
            var dialog = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "Update available",
                Content = $"RA2CC4 update {release} is available. Open the GitHub release page to download and install it.",
                PrimaryButtonText = "Open release downloads",
                CloseButtonText = "Later",
                DefaultButton = ContentDialogButton.Primary,
            };
            if (await dialog.ShowAsync() == ContentDialogResult.Primary)
                Process.Start(new ProcessStartInfo(ReleaseDownloadsUrl) { UseShellExecute = true });
        }
        catch { }
    }

    private static Dictionary<string, string> ParseReleaseCatalog(string text)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (Match match in Regex.Matches(text, @"(?m)^\s*\[(?<release>\d+(?:\.\d+)*)\]\s*\r?\n\s*(?<compat>\d+(?:\.\d+)+)\s*$"))
            result[match.Groups["release"].Value] = match.Groups["compat"].Value;
        return result;
    }

    private static Dictionary<string, string> ReadReleaseCatalog(JsonElement element)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in element.EnumerateObject())
            if (entry.Value.ValueKind == JsonValueKind.String && Version.TryParse(entry.Name, out _) && Version.TryParse(entry.Value.GetString(), out _))
                result[entry.Name] = entry.Value.GetString()!;
        return result;
    }

    private static Version ParseReleaseVersion(string release) => Version.TryParse(release, out var version) ? version : new Version(0, 0);

    private void AttachAutoSaveHandlers()
    {
        foreach (var combo in new[] { ModeBox, CurveTypeBox, CapModeBox, VerticalModeBox, VerticalCurveTypeBox,
                     VerticalCapModeBox, SettingsPointCountBox, SettingsPrecisionBox })
            combo.SelectionChanged += (_, _) => ScheduleDraftSave();
        foreach (var box in new[] { SensitivityMultiplierBox, YXRatioBox, DomainXBox, DomainYBox, RangeXBox,
                     RangeYBox, RotationBox, AngleSnapBox, LeftRightRatioBox, UpDownRatioBox, LpNormBox,
                     InputSmoothingBox, OutputSmoothingBox, OutputDpiBox })
            box.ValueChanged += (_, _) => ScheduleDraftSave();
        foreach (var check in new[] { GainCheck, VerticalGainCheck, AnisotropyEnabledCheck, SeparateVerticalCheck, OutputDpiEnabledCheck })
        {
            check.Checked += (_, _) => ScheduleDraftSave();
            check.Unchecked += (_, _) => ScheduleDraftSave();
        }
        foreach (var box in new[] { ProfileNameBox, RawAccelPathBox, CustomCurvePathBox })
            box.TextChanged += (_, _) => ScheduleDraftSave();
    }

    private void ScheduleDraftSave()
    {
        if (_loading || ModeBox is null) return;
        _draftSaveTimer.Stop();
        _draftSaveTimer.Start();
    }

    private async Task SaveDraftAsync()
    {
        if (_loading) return;
        try
        {
            var verticalArgs = _verticalFields.Count == 0 ? _lastVerticalArgs : ReadVerticalArguments();
            var args = _fields.Count == 0 ? _lastArgs : ReadArguments();
            using var response = await CurveBackend.SendAsync(new Dictionary<string, object?>
            {
                ["action"] = "save_draft",
                ["profile_name"] = ProfileNameBox.Text,
                ["mode"] = SelectedTag(ModeBox),
                ["curve_type"] = SelectedTag(CurveTypeBox),
                ["cap_mode"] = SelectedTag(CapModeBox),
                ["args"] = args,
                ["vertical"] = new { mode = SelectedTag(VerticalModeBox), curve_type = SelectedTag(VerticalCurveTypeBox), cap_mode = SelectedTag(VerticalCapModeBox), args = verticalArgs },
                ["separate_vertical_curve"] = SeparateVerticalCheck.IsChecked == true,
                ["point_count"] = int.Parse(SettingsPointCountBox.SelectedItem?.ToString() ?? "128", CultureInfo.InvariantCulture),
                ["precision"] = int.Parse(SettingsPrecisionBox.SelectedItem?.ToString() ?? "6", CultureInfo.InvariantCulture),
                ["sensitivity_multiplier"] = ReadNumberBoxValue(SensitivityMultiplierBox, "Sens Multiplier"),
                ["yx_ratio"] = ReadNumberBoxValue(YXRatioBox, "Y/X Ratio"),
                ["left_right_ratio"] = ReadNumberBoxValue(LeftRightRatioBox, "L/R output ratio"),
                ["up_down_ratio"] = ReadNumberBoxValue(UpDownRatioBox, "U/D output ratio"),
                ["rotation"] = ReadNumberBoxValue(RotationBox, "Rotation"),
                ["angle_snap"] = ReadNumberBoxValue(AngleSnapBox, "Angle snap"),
                ["lp_norm"] = ReadNumberBoxValue(LpNormBox, "Lp Norm"),
                ["output_dpi_enabled"] = OutputDpiEnabledCheck.IsChecked == true,
                ["output_dpi"] = ReadNumberBoxValue(OutputDpiBox, "Output DPI"),
                ["input_smoothing_ms"] = ReadNumberBoxValue(InputSmoothingBox, "Input smoothing"),
                ["output_smoothing_ms"] = ReadNumberBoxValue(OutputSmoothingBox, "Output smoothing"),
                ["anisotropy_enabled"] = AnisotropyEnabledCheck.IsChecked == true,
                ["domain_x"] = ReadNumberBoxValue(DomainXBox, "Domain X"),
                ["domain_y"] = ReadNumberBoxValue(DomainYBox, "Domain Y"),
                ["range_x"] = ReadNumberBoxValue(RangeXBox, "Range X"),
                ["range_y"] = ReadNumberBoxValue(RangeYBox, "Range Y"),
                ["rawaccel_path"] = RawAccelPathBox.Text,
                ["customcurve_path"] = CustomCurvePathBox.Text,
            });
            SettingsStatusText.Text = "Changes saved automatically.";
            StatusText.Text = "Settings saved automatically.";
        }
        catch (Exception ex)
        {
            SettingsStatusText.Text = $"Changes not saved: {ex.Message}";
            StatusText.Text = "Some settings could not be saved. Check App settings.";
        }
    }

    private static void SelectTag(ComboBox combo, JsonElement config, string key, string fallback)
    {
        var wanted = config.TryGetProperty(key, out var value) ? value.GetString() : fallback;
        for (var index = 0; index < combo.Items.Count; index++)
        {
            if (combo.Items[index] is ComboBoxItem item && item.Tag?.ToString() == wanted)
            {
                combo.SelectedIndex = index;
                return;
            }
        }
        combo.SelectedIndex = 0;
    }

    private async void SettingsChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateModeOptionVisibility();
        if (!_loading && !string.IsNullOrEmpty(SelectedTag(ModeBox)))
            await RefreshFieldsAsync();
        ScheduleDraftSave();
    }

    private void UpdateModeOptionVisibility()
    {
        if (ModeBox is null || GainCheck is null) return;
        var mode = SelectedTag(ModeBox);
        GainCheck.Visibility = mode is "noaccel" or "lut" ? Visibility.Collapsed : Visibility.Visible;
    }

    private void UpdateVerticalModeOptionVisibility()
    {
        if (VerticalModeBox is null || VerticalGainCheck is null) return;
        var mode = SelectedTag(VerticalModeBox);
        VerticalGainCheck.Visibility = mode is "noaccel" or "lut" ? Visibility.Collapsed : Visibility.Visible;
    }

    private void GainChanged(object sender, RoutedEventArgs e)
    {
        if (CurveTypeBox is null || GainCheck is null) return;
        SetTag(CurveTypeBox, GainCheck.IsChecked == true ? "gain" : "legacy");
        ScheduleDraftSave();
    }

    private void VerticalGainChanged(object sender, RoutedEventArgs e)
    {
        if (VerticalCurveTypeBox is null || VerticalGainCheck is null) return;
        SetTag(VerticalCurveTypeBox, VerticalGainCheck.IsChecked == true ? "gain" : "legacy");
        ScheduleDraftSave();
    }

    private async Task RefreshFieldsAsync()
    {
        if (string.IsNullOrEmpty(SelectedTag(ModeBox))) return;
        _loading = true;
        try
        {
            if (_fields.Count > 0)
                _lastArgs = ReadArguments();
            ForgetLookupPointEditors(_fields);
            FieldsList.Items.Clear();
            _fields.Clear();
            StatusText.Text = "Loading curve settings...";
            using var response = await CurveBackend.SendAsync(CurrentRequest("fields"));
            foreach (var field in response.RootElement.GetProperty("fields").EnumerateArray())
            {
                var key = field.GetProperty("key").GetString()!;
                var labelText = field.GetProperty("label").GetString() ?? key;
                Control input;
                if (key == "lookup_points")
                {
                    input = CreateLookupPointsEditor(field.GetProperty("value").GetString() ?? "");
                }
                else if (key == "cap_type")
                {
                    input = CreateCapModeEditor(field, CapModeBox);
                }
                else if (field.GetProperty("kind").GetString() == "choice")
                {
                    var combo = new ComboBox { MinWidth = 120, HorizontalAlignment = HorizontalAlignment.Stretch };
                    foreach (var item in field.GetProperty("choices").EnumerateArray())
                        combo.Items.Add(item.GetString());
                    combo.SelectedItem = field.GetProperty("value").GetString();
                    combo.SelectionChanged += (_, _) => ScheduleDraftSave();
                    input = combo;
                }
                else if (field.GetProperty("kind").GetString() == "number")
                {
                    input = CreateNumberBox(field, 120);
                }
                else
                {
                    var box = new TextBox { MinWidth = 100, HorizontalAlignment = HorizontalAlignment.Stretch,
                        Text = field.GetProperty("value").GetString() ?? "" };
                    box.TextChanged += (_, _) => ScheduleDraftSave();
                    input = box;
                }
                if (key != "cap_type") _fields[key] = input;
                var row = new Grid { ColumnSpacing = 8, VerticalAlignment = VerticalAlignment.Center };
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(145) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                var label = new TextBlock { Text = labelText, VerticalAlignment = VerticalAlignment.Center, TextWrapping = TextWrapping.Wrap };
                row.Children.Add(label);
                Grid.SetColumn(input, 1);
                row.Children.Add(input);
                FieldsList.Items.Add(row);
            }
            StatusText.Text = "Ready";
        }
        catch (Exception ex)
        {
            StatusText.Text = "Curve backend unavailable";
            ShowError("Could not load curve settings", ex.Message);
        }
        finally
        {
            _loading = false;
        }
    }

    private Dictionary<string, object?> ReadArguments()
    {
        var values = new Dictionary<string, object?>();
        foreach (var (key, control) in _fields)
            values[key] = control switch
            {
                TextBox textBox => textBox.Text,
                NumberBox numberBox => ReadNumberBoxValue(numberBox, key),
                ComboBox combo => combo.SelectedItem?.ToString() == "Velocity",
                UserControl userControl when _lookupPointEditors.TryGetValue(userControl, out var points) => SerializeLookupPoints(points.Points),
                _ => null,
            };
        return values;
    }

    private ComboBox CreateCapModeEditor(JsonElement field, ComboBox target)
    {
        var combo = new ComboBox { MinWidth = 120, HorizontalAlignment = HorizontalAlignment.Stretch };
        foreach (var choice in field.GetProperty("choices").EnumerateArray())
        {
            var label = choice.GetString() ?? "Output";
            var tag = label switch { "Input" => "in", "Both" => "io", _ => "out" };
            combo.Items.Add(new ComboBoxItem { Content = label, Tag = tag });
        }
        var selected = field.GetProperty("value").GetString() switch { "Input" => "in", "Both" => "io", _ => "out" };
        SetTag(combo, selected);
        combo.SelectionChanged += (_, _) =>
        {
            if (!_loading && !string.IsNullOrEmpty(SelectedTag(combo))) SetTag(target, SelectedTag(combo));
            ScheduleDraftSave();
        };
        return combo;
    }

    private Control CreateLookupPointsEditor(string initialValue)
    {
        var model = new LookupPointEditorModel();
        model.Changed += ScheduleDraftSave;
        foreach (var point in ParseLookupPoints(initialValue))
            model.Points.Add(new LookupPointRow(model, point.X, point.Y));
        var pointList = new ListView
        {
            ItemsSource = model.Points,
            ItemTemplate = (DataTemplate)AppNavigation.Resources["LookupPointTemplate"],
            Background = new SolidColorBrush(Colors.Transparent),
            CanDragItems = false,
            CanReorderItems = false,
            AllowDrop = false,
            ReorderMode = ListViewReorderMode.Disabled,
            SelectionMode = ListViewSelectionMode.None,
            Height = 260,
        };
        pointList.ItemContainerStyle = new Style(typeof(ListViewItem));
        pointList.ItemContainerStyle.Setters.Add(new Setter(Control.PaddingProperty, new Thickness(0)));
        pointList.ItemContainerStyle.Setters.Add(new Setter(Control.HorizontalContentAlignmentProperty, HorizontalAlignment.Stretch));
        pointList.ItemContainerStyle.Setters.Add(new Setter(FrameworkElement.MinHeightProperty, 0d));
        var pointListFrame = new Border
        {
            Background = new SolidColorBrush(Colors.Transparent),
            BorderThickness = new Thickness(0),
            Padding = new Thickness(0),
            Child = pointList,
        };
        var pasteBox = new TextBox
        {
            PlaceholderText = "Paste x1,y1;x2,y2;...;",
            AcceptsReturn = true,
            TextWrapping = TextWrapping.Wrap,
            MinHeight = 54,
        };
        var addButton = new Button { Content = "Add point", HorizontalAlignment = HorizontalAlignment.Left };
        addButton.Click += async (_, _) => await EditLookupPointAsync(model, null);
        var importButton = new Button { Content = "Import points" };
        importButton.Click += (_, _) =>
        {
            try
            {
                var imported = ParseLookupPoints(pasteBox.Text);
                if (imported.Count < 2) throw new InvalidOperationException("RawAccel requires at least 2 points.");
                model.Points.Clear();
                foreach (var point in imported) model.Points.Add(new LookupPointRow(model, point.X, point.Y));
                pasteBox.Text = "";
            }
            catch (Exception ex) { ShowError("Invalid lookup points", ex.Message); }
        };
        var importRow = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        importRow.Children.Add(importButton);
        var editor = new StackPanel { Spacing = 8 };
        editor.Children.Add(pointListFrame);
        editor.Children.Add(addButton);
        editor.Children.Add(pasteBox);
        editor.Children.Add(importRow);
        var control = new UserControl { Content = editor };
        _lookupPointEditors[control] = model;
        return control;
    }

    private async void LookupPointEditClicked(object sender, RoutedEventArgs e)
    {
        if ((sender as FrameworkElement)?.DataContext is LookupPointRow point)
            await EditLookupPointAsync(point.Editor, point);
    }

    private void LookupPointRemoveClicked(object sender, RoutedEventArgs e)
    {
        if ((sender as FrameworkElement)?.DataContext is LookupPointRow point)
        {
            if (point.Editor.Points.Count <= 2)
            {
                ShowError("Cannot remove point", "RawAccel requires at least 2 lookup points.");
                return;
            }
            point.Editor.Points.Remove(point);
        }
    }

    private async Task EditLookupPointAsync(LookupPointEditorModel model, LookupPointRow? existing)
    {
        if (existing is null && model.Points.Count >= 257)
        {
            ShowError("Lookup table is full", "RawAccel allows up to 257 points.");
            return;
        }
        var xBox = CreateLookupNumberBox(existing?.X ?? (model.Points.Count == 0 ? 1 : model.Points[^1].X + 1));
        var yBox = CreateLookupNumberBox(existing?.Y ?? (model.Points.Count == 0 ? 1 : model.Points[^1].Y));
        var error = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = new SolidColorBrush(Colors.Red) };
        var grid = new Grid { ColumnSpacing = 12, RowSpacing = 10 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(70) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.Children.Add(new TextBlock { Text = "X", VerticalAlignment = VerticalAlignment.Center });
        Grid.SetColumn(xBox, 1); grid.Children.Add(xBox);
        var yLabel = new TextBlock { Text = "Y", VerticalAlignment = VerticalAlignment.Center };
        Grid.SetRow(yLabel, 1); grid.Children.Add(yLabel);
        Grid.SetRow(yBox, 1); Grid.SetColumn(yBox, 1); grid.Children.Add(yBox);
        Grid.SetRow(error, 2); Grid.SetColumnSpan(error, 2); grid.Children.Add(error);
        var dialog = new ContentDialog
        {
            XamlRoot = Content.XamlRoot,
            Title = existing is null ? "Add lookup point" : "Edit lookup point",
            Content = grid,
            PrimaryButtonText = existing is null ? "Add" : "Save",
            CloseButtonText = "Cancel",
            DefaultButton = ContentDialogButton.Primary,
        };
        dialog.PrimaryButtonClick += (_, args) =>
        {
            try
            {
                ValidateLookupPointChange(model, existing, xBox.Value, yBox.Value);
                if (existing is null) model.InsertSorted(new LookupPointRow(model, xBox.Value, yBox.Value));
                else { existing.X = xBox.Value; existing.Y = yBox.Value; model.SortByX(); }
            }
            catch (Exception ex) { args.Cancel = true; error.Text = ex.Message; }
        };
        await dialog.ShowAsync();
    }

    private static NumberBox CreateLookupNumberBox(double value)
    {
        var box = new NumberBox
        {
            Value = value,
            Minimum = 0,
            Maximum = float.MaxValue,
            SmallChange = 0.1,
            NumberFormatter = CreateNumberFormatter(),
            SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Inline,
            ValidationMode = NumberBoxValidationMode.InvalidInputOverwritten,
            MinWidth = 150,
        };
        NormalizeSpinSteps(box);
        return box;
    }

    private static void ValidateLookupPointChange(LookupPointEditorModel model, LookupPointRow? existing, double x, double y)
    {
        var rawX = (float)x; var rawY = (float)y;
        if (!double.IsFinite(x) || !double.IsFinite(y) || !float.IsFinite(rawX) || !float.IsFinite(rawY) || rawX <= 0 || rawY <= 0)
            throw new InvalidOperationException("RawAccel requires finite, positive X and Y values that fit in a 32-bit float.");
        if (existing is not null && !model.Points.Contains(existing))
            throw new InvalidOperationException("The selected point is no longer in the table.");
        if (model.Points.Any(point => point != existing && (float)point.X == rawX))
            throw new InvalidOperationException("Each lookup point must have a unique X value.");
    }

    private static List<(double X, double Y)> ParseLookupPoints(string text)
    {
        var points = new List<(double X, double Y)>();
        foreach (var entry in text.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var pair = entry.Split(',', StringSplitOptions.TrimEntries);
            if (pair.Length != 2 ||
                !double.TryParse(pair[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var x) ||
                !double.TryParse(pair[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var y))
                throw new InvalidOperationException($"'{entry}' is invalid. Enter numeric X,Y pairs separated by semicolons.");
            var rawX = (float)x; var rawY = (float)y;
            if (!double.IsFinite(x) || !double.IsFinite(y) || !float.IsFinite(rawX) || !float.IsFinite(rawY) || rawX <= 0 || rawY <= 0)
                throw new InvalidOperationException($"Point {points.Count + 1} must have positive finite X and Y values supported by RawAccel.");
            if (points.Any(point => (float)point.X == rawX))
                throw new InvalidOperationException($"Point {points.Count + 1} has an X value that duplicates another point.");
            points.Add((x, y));
            if (points.Count > 257) throw new InvalidOperationException("RawAccel allows up to 257 points.");
        }
        return points.OrderBy(point => point.X).ToList();
    }

    private static string SerializeLookupPoints(IEnumerable<LookupPointRow> points)
    {
        var values = points.ToArray();
        if (values.Length < 2) throw new InvalidOperationException("RawAccel requires at least 2 lookup points.");
        var validated = ParseLookupPoints(string.Join(';', values.Select(p =>
            $"{p.X.ToString("G17", CultureInfo.InvariantCulture)},{p.Y.ToString("G17", CultureInfo.InvariantCulture)}")));
        return string.Join(';', validated.Select(p =>
            $"{p.X.ToString("G17", CultureInfo.InvariantCulture)},{p.Y.ToString("G17", CultureInfo.InvariantCulture)}"));
    }

    private void ForgetLookupPointEditors(Dictionary<string, Control> fields)
    {
        foreach (var control in fields.Values)
            if (control is UserControl && _lookupPointEditors.ContainsKey(control))
                _lookupPointEditors.Remove(control);
    }

    private async void VerticalSettingsChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateVerticalModeOptionVisibility();
        if (_loading || string.IsNullOrEmpty(SelectedTag(VerticalModeBox))) return;
        try
        {
            if (_verticalFields.Count > 0) _lastVerticalArgs = ReadVerticalArguments();
        }
        catch (Exception ex)
        {
            ShowError("Invalid vertical curve value", ex.Message);
            return;
        }
        await RefreshVerticalFieldsAsync();
        ScheduleDraftSave();
    }

    private async Task RefreshVerticalFieldsAsync()
    {
        if (string.IsNullOrEmpty(SelectedTag(VerticalModeBox))) return;
        _loading = true;
        try
        {
            if (_verticalFields.Count > 0) _lastVerticalArgs = ReadVerticalArguments();
            ForgetLookupPointEditors(_verticalFields);
            VerticalFieldsList.Items.Clear();
            _verticalFields.Clear();
            using var response = await CurveBackend.SendAsync(new
            {
                action = "fields",
                mode = SelectedTag(VerticalModeBox),
                curve_type = SelectedTag(VerticalCurveTypeBox),
                cap_mode = SelectedTag(VerticalCapModeBox),
                args = _lastVerticalArgs,
            });
            foreach (var field in response.RootElement.GetProperty("fields").EnumerateArray())
            {
                var key = field.GetProperty("key").GetString()!;
                var labelText = field.GetProperty("label").GetString() ?? key;
                Control input;
                if (key == "lookup_points")
                {
                    input = CreateLookupPointsEditor(field.GetProperty("value").GetString() ?? "");
                }
                else if (key == "cap_type")
                {
                    input = CreateCapModeEditor(field, VerticalCapModeBox);
                }
                else if (field.GetProperty("kind").GetString() == "choice")
                {
                    var combo = new ComboBox { MinWidth = 110, HorizontalAlignment = HorizontalAlignment.Stretch };
                    foreach (var item in field.GetProperty("choices").EnumerateArray()) combo.Items.Add(item.GetString());
                    combo.SelectedItem = field.GetProperty("value").GetString();
                    combo.SelectionChanged += (_, _) => ScheduleDraftSave();
                    input = combo;
                }
                else if (field.GetProperty("kind").GetString() == "number")
                {
                    input = CreateNumberBox(field, 110);
                }
                else
                {
                    var textBox = new TextBox { MinWidth = 100, HorizontalAlignment = HorizontalAlignment.Stretch,
                        Text = field.GetProperty("value").GetString() ?? "" };
                    textBox.TextChanged += (_, _) => ScheduleDraftSave();
                    input = textBox;
                }
                if (key != "cap_type") _verticalFields[key] = input;
                var row = new Grid { ColumnSpacing = 8, VerticalAlignment = VerticalAlignment.Center };
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
                row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                row.Children.Add(new TextBlock { Text = labelText, VerticalAlignment = VerticalAlignment.Center, TextWrapping = TextWrapping.Wrap });
                Grid.SetColumn(input, 1);
                row.Children.Add(input);
                VerticalFieldsList.Items.Add(row);
            }
        }
        catch (Exception ex)
        {
            ShowError("Could not load vertical curve settings", ex.Message);
        }
        finally
        {
            _loading = false;
        }
    }

    private Dictionary<string, object?> ReadVerticalArguments()
    {
        var values = new Dictionary<string, object?>();
        foreach (var (key, control) in _verticalFields)
            values[key] = control switch
            {
                TextBox textBox => textBox.Text,
                NumberBox numberBox => ReadNumberBoxValue(numberBox, key),
                ComboBox combo => combo.SelectedItem?.ToString() == "Velocity",
                UserControl userControl when _lookupPointEditors.TryGetValue(userControl, out var points) => SerializeLookupPoints(points.Points),
                _ => null,
            };
        return values;
    }

    private void AnisotropyChanged(NumberBox sender, NumberBoxValueChangedEventArgs args)
    {
        if (_loading || AnisotropyEnabledCheck.IsChecked != true) return;
        UpdateSeparateCurveVisibility();
        ScheduleDraftSave();
    }

    private void AnisotropyEnabledChanged(object sender, RoutedEventArgs e)
    {
        if (AnisotropyContent is null) return;
        AnisotropyContent.IsEnabled = AnisotropyEnabledCheck.IsChecked == true;
        if (_loading) return;
        UpdateSeparateCurveVisibility();
        ScheduleDraftSave();
    }

    private void OutputDpiEnabledChanged(object sender, RoutedEventArgs e)
    {
        if (OutputDpiBox is not null) OutputDpiBox.IsEnabled = OutputDpiEnabledCheck.IsChecked == true;
        ScheduleDraftSave();
    }

    private async void SeparateVerticalChanged(object sender, RoutedEventArgs e)
    {
        UpdateSeparateCurveVisibility();
        ScheduleDraftSave();
        if (!_loading && SeparateVerticalCheck.IsChecked == true)
        {
            try { await CopyHorizontalToVerticalAsync(); }
            catch (Exception ex) { ShowError("Invalid curve value", ex.Message); }
        }
    }

    private async Task CopyHorizontalToVerticalAsync()
    {
        if (_fields.Count > 0) _lastArgs = ReadArguments();
        _loading = true;
        SetTag(VerticalModeBox, SelectedTag(ModeBox));
        SetTag(VerticalCurveTypeBox, SelectedTag(CurveTypeBox));
        VerticalGainCheck.IsChecked = GainCheck.IsChecked;
        SetTag(VerticalCapModeBox, SelectedTag(CapModeBox));
        _lastVerticalArgs = new Dictionary<string, object?>(_lastArgs);
        ForgetLookupPointEditors(_verticalFields);
        _verticalFields.Clear();
        VerticalFieldsList.Items.Clear();
        _loading = false;
        UpdateVerticalModeOptionVisibility();
        await RefreshVerticalFieldsAsync();
    }

    private static void SetTag(ComboBox combo, string tag)
    {
        for (var index = 0; index < combo.Items.Count; index++)
            if (combo.Items[index] is ComboBoxItem item && item.Tag?.ToString() == tag)
            {
                combo.SelectedIndex = index;
                return;
            }
    }

    private void SelectPage(string tag)
    {
        foreach (var item in AppNavigation.MenuItems.OfType<NavigationViewItem>())
            if (item.Tag?.ToString() == tag) { AppNavigation.SelectedItem = item; return; }
    }

    private void UpdateSeparateCurveVisibility()
    {
        if (VerticalCurvePanel is null || SeparateVerticalCheck is null) return;
        VerticalCurvePanel.Visibility = SeparateVerticalCheck.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        Grid.SetColumnSpan(HorizontalCurvePanel, VerticalCurvePanel.Visibility == Visibility.Visible ? 1 : 2);
    }

    private async void GenerateClicked(object sender, RoutedEventArgs e) => await GenerateProfileAsync();

    private async Task GenerateProfileAsync()
    {
        ContentDialog? progressDialog = null;
        Task<ContentDialogResult>? progressDialogTask = null;
        string? outputPath = null;
        if (SelectedTag(DestinationBox) == "file")
        {
            var picker = new FileSavePicker();
            picker.SuggestedStartLocation = PickerLocationId.DocumentsLibrary;
            picker.SuggestedFileName = MakeFileName(ProfileNameBox.Text);
            picker.FileTypeChoices.Add("CustomCurve profile", new List<string> { ".cc4" });
            picker.FileTypeChoices.Add("JSON file", new List<string> { ".json" });
            InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
            var file = await picker.PickSaveFileAsync();
            if (file is null) return;
            outputPath = file.Path;
        }

        try
        {
            StatusText.Text = "Generating curve...";
            var request = new Dictionary<string, object?>
            {
                ["action"] = "generate",
                ["mode"] = SelectedTag(ModeBox),
                ["curve_type"] = SelectedTag(CurveTypeBox),
                ["cap_mode"] = SelectedTag(CapModeBox),
                ["profile_name"] = ProfileNameBox.Text,
                ["point_count"] = int.Parse(SettingsPointCountBox.SelectedItem?.ToString() ?? "128"),
                ["precision"] = int.Parse(SettingsPrecisionBox.SelectedItem?.ToString() ?? "6"),
                ["sensitivity_multiplier"] = ReadNumberBoxValue(SensitivityMultiplierBox, "Sens Multiplier"),
                ["yx_ratio"] = ReadNumberBoxValue(YXRatioBox, "Y/X Ratio"),
                ["left_right_ratio"] = ReadNumberBoxValue(LeftRightRatioBox, "L/R output ratio"),
                ["up_down_ratio"] = ReadNumberBoxValue(UpDownRatioBox, "U/D output ratio"),
                ["rotation"] = ReadNumberBoxValue(RotationBox, "Rotation"),
                ["angle_snap"] = ReadNumberBoxValue(AngleSnapBox, "Angle snap"),
                ["lp_norm"] = ReadNumberBoxValue(LpNormBox, "Lp Norm"),
                ["output_dpi_enabled"] = OutputDpiEnabledCheck.IsChecked == true,
                ["output_dpi"] = ReadNumberBoxValue(OutputDpiBox, "Output DPI"),
                ["input_smoothing_ms"] = ReadNumberBoxValue(InputSmoothingBox, "Input smoothing"),
                ["output_smoothing_ms"] = ReadNumberBoxValue(OutputSmoothingBox, "Output smoothing"),
                ["anisotropy_enabled"] = AnisotropyEnabledCheck.IsChecked == true,
                ["domain_x"] = AnisotropyEnabledCheck.IsChecked == true ? ReadNumberBoxValue(DomainXBox, "Domain X") : 1.0,
                ["domain_y"] = AnisotropyEnabledCheck.IsChecked == true ? ReadNumberBoxValue(DomainYBox, "Domain Y") : 1.0,
                ["range_x"] = AnisotropyEnabledCheck.IsChecked == true ? ReadNumberBoxValue(RangeXBox, "Range X") : 1.0,
                ["range_y"] = AnisotropyEnabledCheck.IsChecked == true ? ReadNumberBoxValue(RangeYBox, "Range Y") : 1.0,
                ["separate_vertical_curve"] = SeparateVerticalCheck.IsChecked == true,
                ["vertical"] = new
                {
                    mode = SelectedTag(VerticalModeBox),
                    curve_type = SelectedTag(VerticalCurveTypeBox),
                    cap_mode = SelectedTag(VerticalCapModeBox),
                    args = ReadVerticalArguments(),
                },
                ["args"] = ReadArguments(),
                ["output_path"] = outputPath,
                ["destination"] = SelectedTag(DestinationBox),
                ["open_customcurve"] = OpenCustomCurveCheck.IsChecked == true,
            };
            var pointLimit = (int)request["point_count"]!;
            var progressRing = new ProgressRing { IsActive = true, Width = 28, Height = 28, VerticalAlignment = VerticalAlignment.Center };
            var stageText = new TextBlock { Text = "Starting generation…", FontSize = 16, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap };
            var detailText = new TextBlock { Text = "Preparing formula and input range", TextWrapping = TextWrapping.Wrap };
            var pointText = new TextBlock { Text = $"0 controls selected · limit {pointLimit}", FontSize = 13 };
            var pointBar = new ProgressBar { Minimum = 0, Maximum = pointLimit, Value = 0, Height = 8 };
            var errorText = new TextBlock { Text = "Fit error will appear during spline fitting", FontSize = 12, TextWrapping = TextWrapping.Wrap };
            var progressContent = new StackPanel { Spacing = 12, MinWidth = 400 };
            var heading = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 12 };
            heading.Children.Add(progressRing);
            heading.Children.Add(stageText);
            progressContent.Children.Add(heading);
            progressContent.Children.Add(detailText);
            progressContent.Children.Add(pointText);
            progressContent.Children.Add(pointBar);
            progressContent.Children.Add(errorText);
            progressContent.Children.Add(new TextBlock
            {
                Text = "The point setting is a ceiling. Controls are added only when they improve the spline fit.",
                FontSize = 12,
                TextWrapping = TextWrapping.Wrap,
            });
            progressDialog = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = "Generating CC4 profile",
                Content = progressContent,
                CloseButtonText = "Hide",
            };
            var reporter = new Progress<GenerationProgress>(update =>
            {
                stageText.Text = update.Stage;
                detailText.Text = update.Detail;
                if (update.Points is int points)
                {
                    var limit = update.PointLimit ?? pointLimit;
                    pointBar.Maximum = Math.Max(1, limit);
                    pointBar.Value = Math.Clamp(points, 0, pointBar.Maximum);
                    pointText.Text = update.Stage == "Complete"
                        ? $"{points} total generated controls"
                        : $"{points} controls in the current fit · per-curve limit {limit}";
                }
                if (update.Error is double error)
                    errorText.Text = $"Worst sampled fit error: {error:G7}";
                if (update.Stage == "Complete") progressRing.IsActive = false;
            });
            progressDialogTask = progressDialog.ShowAsync().AsTask();
            using var response = await CurveBackend.SendAsync(request, reporter);
            if (!progressDialogTask.IsCompleted) progressDialog.Hide();
            await progressDialogTask;
            var root = response.RootElement;
            var count = root.TryGetProperty("actual_point_count", out var actualCount)
                ? actualCount.GetInt32()
                : root.GetProperty("point_count").GetInt32();
            var maxInput = root.GetProperty("max_input").GetDouble();
            var path = root.TryGetProperty("path", out var pathElement) ? pathElement.GetString() : null;
            StatusText.Text = SelectedTag(DestinationBox) == "app"
                ? $"Loaded {count} points into CustomCurve | max input {maxInput:G6} | {path}"
                : $"Saved {count} points | max input {maxInput:G6} | {path}";
            var dialog = new ContentDialog
            {
                XamlRoot = Content.XamlRoot,
                Title = SelectedTag(DestinationBox) == "app" ? "Loaded into CustomCurve" : "Profile saved",
                Content = SelectedTag(DestinationBox) == "app"
                    ? $"Loaded the generated profile into CustomCurve.\n\n{path}"
                    : $"Generated and saved {count} points.\n\n{path}",
                CloseButtonText = "Done",
            };
            await dialog.ShowAsync();
        }
        catch (Exception ex)
        {
            if (progressDialog is not null && progressDialogTask is { IsCompleted: false })
            {
                progressDialog.Hide();
                try { await progressDialogTask; } catch { }
            }
            StatusText.Text = "Generation failed";
            ShowError("Could not generate profile", ex.Message);
        }
    }

    private void DestinationChanged(object sender, SelectionChangedEventArgs e)
    {
        OpenCustomCurveCheck.IsEnabled = SelectedTag(DestinationBox) == "app";
    }

    private async Task<StorageFolder?> PickFolderAsync(string title)
    {
        var picker = new FolderPicker { SuggestedStartLocation = PickerLocationId.DocumentsLibrary };
        picker.FileTypeFilter.Add("*");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        return await picker.PickSingleFolderAsync();
    }

    private async void BrowseImportClicked(object sender, RoutedEventArgs e)
    {
        var picker = new FileOpenPicker { SuggestedStartLocation = PickerLocationId.DocumentsLibrary };
        picker.FileTypeFilter.Add(".json");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        var file = await picker.PickSingleFileAsync();
        if (file is not null)
        {
            ImportPathBox.Text = file.Path;
            ImportStatusText.Text = "Using the selected settings.json for this session.";
        }
    }

    private void RawAccelPathChanged(object sender, TextChangedEventArgs e)
    {
        if (ImportPathBox is null) return;
        ImportPathBox.Text = string.IsNullOrWhiteSpace(RawAccelPathBox.Text)
            ? ""
            : Path.Combine(RawAccelPathBox.Text, "settings.json");
    }

    private async void BrowseRawAccelClicked(object sender, RoutedEventArgs e)
    {
        var folder = await PickFolderAsync("Select the RawAccel folder");
        if (folder is not null) RawAccelPathBox.Text = folder.Path;
    }

    private async void BrowseCustomCurveClicked(object sender, RoutedEventArgs e)
    {
        var picker = new FileOpenPicker { SuggestedStartLocation = PickerLocationId.ComputerFolder };
        picker.FileTypeFilter.Add(".exe");
        InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
        var file = await picker.PickSingleFileAsync();
        if (file is not null && Path.GetFileName(file.Path).Equals("CustomCurve.exe", StringComparison.OrdinalIgnoreCase))
            CustomCurvePathBox.Text = file.Path;
        else if (file is not null)
            ShowError("Invalid CustomCurve path", "Select the CustomCurve.exe application file.");
    }

    private async void SaveSettingsClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            var request = new Dictionary<string, object?>
            {
                ["action"] = "update_settings",
                ["rawaccel_path"] = RawAccelPathBox.Text,
                ["customcurve_path"] = CustomCurvePathBox.Text,
                ["point_count"] = int.Parse(SettingsPointCountBox.SelectedItem?.ToString() ?? "128"),
                ["precision"] = int.Parse(SettingsPrecisionBox.SelectedItem?.ToString() ?? "6"),
            };
            using var response = await CurveBackend.SendAsync(request);
            SettingsStatusText.Text = "Settings saved.";
            UpdateSetupRecommendation();
        }
        catch (Exception ex)
        {
            SettingsStatusText.Text = "Settings were not saved.";
            ShowError("Could not save settings", ex.Message);
        }
    }

    private async void ImportAllToAppClicked(object sender, RoutedEventArgs e) =>
        await ImportAllProfilesAsync();

    private async Task ImportAllProfilesAsync()
    {
        try
        {
            if (string.IsNullOrWhiteSpace(ImportPathBox.Text))
                throw new InvalidOperationException("Set the RawAccel folder in App Settings or browse to a settings.json file.");
            ImportStatusText.Text = "Loading RawAccel profiles into CustomCurve...";
            using var response = await CurveBackend.SendAsync(new
            {
                action = "import_settings",
                settings_path = ImportPathBox.Text,
                point_count = int.Parse(SettingsPointCountBox.SelectedItem?.ToString() ?? "128"),
                precision = int.Parse(SettingsPrecisionBox.SelectedItem?.ToString() ?? "6"),
                profile_name = "Imported Profile",
                destination = "app",
                output_dir = "",
                open_customcurve = true,
                output_dpi_enabled = OutputDpiEnabledCheck.IsChecked == true,
                output_dpi = ReadNumberBoxValue(OutputDpiBox, "Output DPI"),
            });
            var root = response.RootElement;
            var count = root.GetProperty("count").GetInt32();
            var path = root.TryGetProperty("path", out var pathElement) ? pathElement.GetString() : null;
            ImportStatusText.Text = $"Loaded {count} profile(s) into CustomCurve. {path}";
        }
        catch (Exception ex)
        {
            ImportStatusText.Text = "Profiles were not loaded.";
            ShowError("Could not load RawAccel profiles", ex.Message);
        }
    }

    private static string MakeFileName(string name)
    {
        var clean = string.Concat((string.IsNullOrWhiteSpace(name) ? "New Profile" : name)
            .Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch)).Trim();
        if (clean.EndsWith(".cc4", StringComparison.OrdinalIgnoreCase)) return clean;
        return clean + ".cc4";
    }

    private async void ShowError(string title, string message)
    {
        var dialog = new ContentDialog { XamlRoot = Content.XamlRoot, Title = title,
            Content = message, CloseButtonText = "Close" };
        await dialog.ShowAsync();
    }
}


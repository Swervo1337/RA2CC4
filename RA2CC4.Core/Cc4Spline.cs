using System.Globalization;

namespace RA2CC4.Core;

public readonly record struct SplinePoint(double X, double Y, double Weight = 0.5, bool Edge = false);
public readonly record struct SplineSample(double X, double Y);

public static class Cc4Spline
{
    public static SplinePoint ParsePoint(string point)
    {
        var parts = point.Split('|');
        if (parts.Length < 2 || !double.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var x) ||
            !double.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var y))
            throw new FormatException($"Invalid CC4 point: {point}");
        var weight = parts.Length > 2 && double.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out var parsedWeight) ? parsedWeight : 0.5;
        return new SplinePoint(x, y, Math.Clamp(weight, 0, 1), parts.Length > 3 && parts[^1].Trim().Equals("e", StringComparison.OrdinalIgnoreCase));
    }

    public static string FormatPoint(SplinePoint point, bool? edge = null) =>
        $"{point.X.ToString("G15", CultureInfo.InvariantCulture)}|{point.Y.ToString("G15", CultureInfo.InvariantCulture)}|{Math.Clamp(point.Weight, 0, 1).ToString("G15", CultureInfo.InvariantCulture)}{((edge ?? point.Edge) ? "|e" : "")}";

    public static double InternalWeight(double uiWeight, int pointCount) =>
        (pointCount == 3 ? 1.5 : Math.Sqrt(3)) * Math.Clamp(uiWeight, 0, 1);

    public static IReadOnlyList<SplineSample> Bake(IReadOnlyList<string> points, int count = 500) =>
        Bake(points.Select(ParsePoint).ToArray(), count);

    public static IReadOnlyList<SplineSample> Bake(IReadOnlyList<SplinePoint> points, int count = 500)
    {
        count = Math.Max(2, count);
        if (points.Count == 0) return [];
        var normalized = points.OrderBy(p => p.X).ToArray();
        var bounds = new List<int> { 0 };
        for (var i = 1; i < normalized.Length - 1; i++) if (normalized[i].Edge) bounds.Add(i);
        bounds.Add(normalized.Length - 1);
        var segments = new List<List<SplinePoint>>();
        for (var i = 0; i + 1 < bounds.Count; i++)
        {
            var start = bounds[i]; var end = bounds[i + 1];
            var segment = normalized[start..(end + 1)].ToList();
            if (normalized[start].Edge) segment.InsertRange(0, [normalized[start], normalized[start]]);
            if (normalized[end].Edge) segment.AddRange([normalized[end], normalized[end]]);
            segments.Add(segment);
        }
        if (segments.Count == 1) return BakeNormal(segments[0], count);

        var spans = segments.Select(s => Math.Max(0, s[^1].X - s[0].X)).ToArray();
        var total = spans.Sum(); var targetCount = count + segments.Count - 1; var assigned = 0;
        var output = new List<SplineSample>();
        for (var i = 0; i < segments.Count; i++)
        {
            var remaining = segments.Count - i;
            int n;
            if (i == segments.Count - 1) n = targetCount - assigned;
            else if (total > 1e-15)
            {
                n = Math.Max(2, (int)Math.Round(targetCount * spans[i] / total, MidpointRounding.ToEven));
                n = Math.Min(n, Math.Max(2, targetCount - assigned - 2 * (remaining - 1)));
            }
            else n = Math.Max(2, (targetCount - assigned) / remaining);
            assigned += n;
            var baked = BakeNormal(segments[i], n);
            if (output.Count > 0 && baked.Count > 0) baked = baked.Skip(1).ToList();
            output.AddRange(baked);
        }
        return output;
    }

    public static double InterpolateY(IReadOnlyList<SplineSample> samples, double x)
    {
        if (samples.Count == 0) return 0;
        if (x <= samples[0].X) return samples[0].Y;
        if (x >= samples[^1].X) return samples[^1].Y;
        var lo = 0; var hi = samples.Count - 1;
        while (hi - lo > 1)
        {
            var mid = (lo + hi) / 2;
            if (samples[mid].X < x) lo = mid; else hi = mid;
        }
        var a = samples[lo]; var b = samples[hi];
        if (Math.Abs(b.X - a.X) <= 1e-15) return b.Y;
        var t = (x - a.X) / (b.X - a.X);
        return a.Y + (b.Y - a.Y) * t;
    }

    private static List<SplineSample> BakeNormal(IReadOnlyList<SplinePoint> points, int count)
    {
        count = Math.Max(2, count);
        if (points.Count == 1) return [new(points[0].X, points[0].Y)];
        if (points.Count >= 4)
        {
            var knots = Knots(points.Count, 3);
            var table = BasisTable(points.Count, count, 3, knots);
            return table.Select(basis => WeightedPoint(points, basis)).ToList();
        }
        return Enumerable.Range(0, count).Select(i => RationalQuadratic(i / (count - 1d), points)).ToList();
    }

    private static double[] Knots(int n, int degree)
    {
        degree = Math.Min(degree, Math.Max(0, n - 1));
        var m = n + degree;
        var knots = new double[m + 1];
        for (var i = 0; i <= m; i++)
        {
            if (i <= degree) knots[i] = 0;
            else if (i >= m - degree) knots[i] = 1;
            else knots[i] = (double)(i - degree) / (m - 2 * degree);
        }
        return knots;
    }

    private static double[][] BasisTable(int n, int count, int degree, double[] knots) =>
        Enumerable.Range(0, count).Select(i => Basis(i / (count - 1d), n, degree, knots)).ToArray();

    public static double[] Basis(double t, int n, int degree, double[] knots)
    {
        t = Math.Clamp(t, 0, 1); degree = Math.Min(degree, Math.Max(0, n - 1));
        var basis = new double[n];
        for (var i = 0; i < n; i++) if (knots[i] <= t && t < knots[i + 1]) basis[i] = 1;
        if (t >= 1 && n > 0) basis[^1] = 1;
        for (var p = 1; p <= degree; p++)
        {
            var next = new double[n];
            for (var i = 0; i < n; i++)
            {
                var d1 = knots[i + p] - knots[i];
                var left = Math.Abs(d1) > 1e-12 ? (t - knots[i]) / d1 * basis[i] : 0;
                var right = 0d;
                if (i + 1 < n)
                {
                    var d2 = knots[i + p + 1] - knots[i + 1];
                    if (Math.Abs(d2) > 1e-12) right = (knots[i + p + 1] - t) / d2 * basis[i + 1];
                }
                next[i] = left + right;
            }
            basis = next;
        }
        return basis;
    }

    public readonly struct BasisWindow
    {
        public int Offset { get; }
        public double W0 { get; }
        public double W1 { get; }
        public double W2 { get; }
        public double W3 { get; }

        public BasisWindow(int offset, double w0, double w1 = 0, double w2 = 0, double w3 = 0)
        {
            Offset = offset;
            W0 = w0;
            W1 = w1;
            W2 = w2;
            W3 = w3;
        }

        public double this[int index] => index switch { 0 => W0, 1 => W1, 2 => W2, 3 => W3, _ => 0 };
    }

    public static BasisWindow PolynomialBasis(int pointCount, double t)
    {
        if (pointCount <= 1) return new BasisWindow(0, 1);
        t = Math.Clamp(t, 0, 1);
        if (t <= 0) return new BasisWindow(0, 1);
        if (t >= 1) return new BasisWindow(pointCount - 1, 1);
        var degree = Math.Min(3, pointCount - 1);
        if (degree == 1)
        {
            var u = 1 - t;
            return new BasisWindow(0, u, t);
        }
        if (degree == 2)
        {
            var u = 1 - t;
            return new BasisWindow(0, u * u, 2 * u * t, t * t);
        }

        var spans = pointCount - degree;
        var span = Math.Min((int)Math.Floor(t * spans), spans - 1);
        var knotIndex = span + degree;
        Span<double> basis = stackalloc double[4];
        Span<double> left = stackalloc double[4];
        Span<double> right = stackalloc double[4];
        basis[0] = 1;
        for (var j = 1; j <= degree; j++)
        {
            left[j] = t - KnotValue(knotIndex + 1 - j, pointCount, degree);
            right[j] = KnotValue(knotIndex + j, pointCount, degree) - t;
            var saved = 0d;
            for (var r = 0; r < j; r++)
            {
                var denominator = right[r + 1] + left[j - r];
                var temp = Math.Abs(denominator) > 1e-12 ? basis[r] / denominator : 0;
                basis[r] = saved + right[r + 1] * temp;
                saved = left[j - r] * temp;
            }
            basis[j] = saved;
        }
        return new BasisWindow(knotIndex - degree, basis[0], basis[1], basis[2], basis[3]);
    }

    private static double KnotValue(int index, int pointCount, int degree)
    {
        var m = pointCount + degree;
        if (index <= degree) return 0;
        if (index >= m - degree) return 1;
        return (double)(index - degree) / (m - 2 * degree);
    }

    private static SplineSample WeightedPoint(IReadOnlyList<SplinePoint> points, IReadOnlyList<double> basis)
    {
        var sx = 0d; var sy = 0d; var sw = 0d;
        for (var i = 0; i < points.Count; i++)
        {
            var weight = basis[i] * InternalWeight(points[i].Weight, points.Count);
            sx += weight * points[i].X; sy += weight * points[i].Y; sw += weight;
        }
        return Math.Abs(sw) <= 1e-15 ? new(points[^1].X, points[^1].Y) : new(sx / sw, sy / sw);
    }

    private static SplineSample RationalQuadratic(double t, IReadOnlyList<SplinePoint> points)
    {
        if (points.Count < 3)
        {
            var u = 1 - t;
            return new(u * points[0].X + t * points[^1].X, u * points[0].Y + t * points[^1].Y);
        }
        t = Math.Clamp(t, 0, 1); var u2 = 1 - t;
        var w0 = InternalWeight(points[0].Weight, 3); var w1 = InternalWeight(points[1].Weight, 3); var w2 = InternalWeight(points[2].Weight, 3);
        var b0 = u2 * u2 * w0; var b1 = 2 * u2 * t * w1; var b2 = t * t * w2; var denominator = b0 + b1 + b2;
        return Math.Abs(denominator) <= 1e-15
            ? new(points[2].X, points[2].Y)
            : new((b0 * points[0].X + b1 * points[1].X + b2 * points[2].X) / denominator,
                  (b0 * points[0].Y + b1 * points[1].Y + b2 * points[2].Y) / denominator);
    }
}

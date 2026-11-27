namespace RA2CC4.Core;

public static class FormulaPointGenerator
{
    private readonly record struct Leaf(double X0, double Y0, double X1, double Y1, double MidY, double Error);
    private readonly record struct Jump(double X0, double Y0, double X1, double Y1);
    private readonly record struct Span(double X0, double Y0, double X1, double Y1, bool Edge0, bool Edge1, Leaf[] Leaves);
    private readonly record struct Fit(SplinePoint[] Points, double Error);

    public static List<string> Generate(Func<double, double> formula, double maxSpeed, int maxPoints) =>
        GeneratePoints(formula, maxSpeed, maxPoints).Select(point => Cc4Spline.FormatPoint(point)).ToList();

    public static List<string> Generate(Func<double, double> formula, double maxSpeed, int maxPoints, double tolerance) =>
        GeneratePoints(formula, maxSpeed, maxPoints, tolerance).Select(point => Cc4Spline.FormatPoint(point)).ToList();

    public static List<string> Generate(Func<double, double> formula, double maxSpeed, int maxPoints,
        double tolerance, IEnumerable<double> edgePoints) =>
        GeneratePoints(formula, maxSpeed, maxPoints, tolerance, edgePoints)
            .Select(point => Cc4Spline.FormatPoint(point)).ToList();

    public static List<SplinePoint> GeneratePoints(Func<double, double> formula, double maxSpeed,
        int maxPoints, double tolerance = 1e-3, IEnumerable<double>? edgePoints = null,
        IProgress<GenerationProgress>? progress = null, string curveName = "Curve")
    {
        ArgumentNullException.ThrowIfNull(formula);
        if (!double.IsFinite(maxSpeed) || maxSpeed < 0) throw new ArgumentOutOfRangeException(nameof(maxSpeed));
        if (maxPoints is < 2 or > 4096) throw new ArgumentOutOfRangeException(nameof(maxPoints));
        if (!double.IsFinite(tolerance) || tolerance <= 0) throw new ArgumentOutOfRangeException(nameof(tolerance));
        if (maxSpeed == 0) return [new SplinePoint(0, Evaluate(formula, 0))];

        var leaves = new List<Leaf>();
        var jumps = new List<Jump>();
        progress?.Report(new GenerationProgress("Sampling formula", $"{curveName}: adaptively checking curvature and breakpoints"));
        Sample(formula, maxSpeed, maxPoints, tolerance, leaves, jumps, progress, curveName);
        var linearEdges = FindLinearRunEdges(leaves, maxSpeed);
        var allEdges = edgePoints is null ? linearEdges : edgePoints.Concat(linearEdges);
        var spans = BuildSpans(formula, maxSpeed, leaves, jumps, allEdges);
        progress?.Report(new GenerationProgress("Fitting CC4 spline", $"{curveName}: {leaves.Count} sampled intervals · {spans.Count} spline spans"));
        var points = FitSpans(formula, spans, maxPoints, tolerance, progress, curveName);
        progress?.Report(new GenerationProgress("Curve fitted", $"{curveName}: {points.Count} controls selected from a limit of {maxPoints}",
            points.Count, maxPoints, Fraction: 0.9));
        return points;
    }

    private static void Sample(Func<double, double> formula, double maxSpeed, int maxPoints, double tolerance,
        List<Leaf> leaves, List<Jump> jumps, IProgress<GenerationProgress>? progress, string curveName)
    {
        var cap = Math.Max(8, maxPoints * 8);
        var queue = new PriorityQueue<Leaf, double>();
        Enqueue(queue, formula, 0, Evaluate(formula, 0), maxSpeed, Evaluate(formula, maxSpeed));

        var checkedIntervals = 0;
        while (queue.Count > 0)
        {
            checkedIntervals++;
            var leaf = queue.Dequeue();
            var width = leaf.X1 - leaf.X0;
            var room = leaves.Count + queue.Count + 1 < cap;
            var midX = leaf.X0 + width * 0.5;
            if (leaf.Error <= tolerance || midX <= leaf.X0 || midX >= leaf.X1 || !room)
            {
                if (leaf.Error > tolerance && (midX <= leaf.X0 || midX >= leaf.X1) && IsStep(leaf, tolerance)) jumps.Add(new Jump(leaf.X0, leaf.Y0, leaf.X1, leaf.Y1));
                else leaves.Add(leaf);
                continue;
            }

            if (checkedIntervals % 64 == 0)
                progress?.Report(new GenerationProgress("Sampling formula",
                    $"{curveName}: {checkedIntervals:N0} intervals checked · {queue.Count:N0} remain"));

            Enqueue(queue, formula, leaf.X0, leaf.Y0, midX, leaf.MidY);
            Enqueue(queue, formula, midX, leaf.MidY, leaf.X1, leaf.Y1);
        }

        leaves.Sort((a, b) => a.X0.CompareTo(b.X0));
        jumps.Sort((a, b) => a.X0.CompareTo(b.X0));
        progress?.Report(new GenerationProgress("Formula sampled",
            $"{curveName}: {checkedIntervals:N0} intervals · {leaves.Count:N0} retained · {jumps.Count:N0} discontinuities"));
    }

    private static void Enqueue(PriorityQueue<Leaf, double> queue, Func<double, double> formula,
        double x0, double y0, double x1, double y1)
    {
        var midX = (x0 + x1) * 0.5;
        var midY = Evaluate(formula, midX);
        var error = Math.Abs(midY - (y0 + y1) * 0.5);
        if (error == 0)
        {
            var left = Evaluate(formula, (x0 + midX) * 0.5);
            var right = Evaluate(formula, (midX + x1) * 0.5);
            var leftLine = (y0 + midY) * 0.5;
            var rightLine = (midY + y1) * 0.5;
            error = Math.Max(Math.Abs(left - leftLine), Math.Abs(right - rightLine));
        }
        queue.Enqueue(new Leaf(x0, y0, x1, y1, midY, error), -error);
    }

    private static bool IsStep(Leaf leaf, double tolerance) =>
        Math.Abs(leaf.MidY - leaf.Y0) <= tolerance || Math.Abs(leaf.MidY - leaf.Y1) <= tolerance;

    private static List<double> FindLinearRunEdges(IReadOnlyList<Leaf> leaves, double maxSpeed)
    {
        var edges = new List<double>();
        var index = 0;
        while (index < leaves.Count)
        {
            if (!IsNumericallyLinear(leaves[index])) { index++; continue; }
            var start = index;
            var slope = (leaves[index].Y1 - leaves[index].Y0) / (leaves[index].X1 - leaves[index].X0);
            index++;
            while (index < leaves.Count && IsNumericallyLinear(leaves[index]))
            {
                var nextSlope = (leaves[index].Y1 - leaves[index].Y0) / (leaves[index].X1 - leaves[index].X0);
                var previous = leaves[index - 1];
                var next = leaves[index];
                var width = Math.Min(previous.X1 - previous.X0, next.X1 - next.X0);
                var scale = Math.Max(Math.Max(Math.Abs(previous.Y0), Math.Abs(previous.Y1)),
                    Math.Max(Math.Abs(next.Y0), Math.Abs(next.Y1)));
                if (!NearlyEqual(slope, nextSlope, width, scale)) break;
                index++;
                slope = (leaves[index - 1].Y1 - leaves[start].Y0) /
                    (leaves[index - 1].X1 - leaves[start].X0);
            }

            if (index - start >= 2)
            {
                var left = leaves[start].X0;
                var right = leaves[index - 1].X1;
                if (left > 0 && left < maxSpeed) edges.Add(left);
                if (right > 0 && right < maxSpeed) edges.Add(right);
            }

        }
        return edges;
    }

    private static bool IsNumericallyLinear(Leaf leaf)
    {
        var scale = Math.Max(Math.Abs(leaf.Y0), Math.Max(Math.Abs(leaf.MidY), Math.Abs(leaf.Y1)));
        var ulp = Math.BitIncrement(scale) - scale;
        return leaf.Error <= ulp * 16;
    }

    private static bool NearlyEqual(double a, double b, double width, double valueScale)
    {
        var ulp = Math.BitIncrement(valueScale) - valueScale;
        return Math.Abs(a - b) * width <= ulp * 16;
    }

    private static List<Span> BuildSpans(Func<double, double> formula, double maxSpeed,
        List<Leaf> leaves, List<Jump> jumps, IEnumerable<double>? edgePoints)
    {
        var cuts = new SortedDictionary<double, Cut>();
        cuts[0] = new Cut(Evaluate(formula, 0), false, false);
        cuts[maxSpeed] = new Cut(Evaluate(formula, maxSpeed), false, false);
        foreach (var jump in jumps)
        {
            cuts[jump.X0] = new Cut(jump.Y0, false, true);
            var right = jump.X1 > jump.X0 ? jump.X1 : NextAfter(jump.X0);
            cuts[right] = new Cut(jump.Y1, true, false);
        }
        if (edgePoints is not null)
        {
            foreach (var x in edgePoints.Where(x => double.IsFinite(x) && x > 0 && x < maxSpeed).Distinct().Order())
            {
                if (!cuts.ContainsKey(x)) cuts[x] = new Cut(Evaluate(formula, x), true, true);
            }
        }

        var keys = cuts.Keys.ToArray();
        var spans = new List<Span>(keys.Length - 1);
        for (var i = 0; i + 1 < keys.Length; i++)
        {
            var x0 = keys[i];
            var x1 = keys[i + 1];
            if (x1 <= x0) continue;
            var start = cuts[x0];
            var end = cuts[x1];
            var inside = leaves.Where(leaf => leaf.X0 >= x0 - x0 * 1e-12 && leaf.X1 <= x1 + x1 * 1e-12).ToArray();
            spans.Add(new Span(x0, start.Y, x1, end.Y, start.EdgeRight, end.EdgeLeft, inside));
        }
        if (spans.Count == 0)
            spans.Add(new Span(0, cuts[0].Y, maxSpeed, cuts[maxSpeed].Y, false, false, leaves.ToArray()));
        return spans;
    }

    private readonly record struct Cut(double Y, bool EdgeLeft, bool EdgeRight);
    private static List<SplinePoint> FitSpans(Func<double, double> formula, List<Span> spans, int maxPoints, double tolerance,
        IProgress<GenerationProgress>? progress, string curveName)
    {
        var fits = new Fit[spans.Count];
        for (var i = 0; i < spans.Count; i++)
            fits[i] = FitSpan(formula, spans[i], maxPoints, tolerance, progress,
                $"{curveName}: span {i + 1}/{spans.Count}", maxPoints);
        if (MergedCount(fits) <= maxPoints) return Merge(fits);

        var spare = Math.Max(0, maxPoints - (spans.Count + 1));
        var wanted = fits.Select(fit => Math.Max(0, fit.Points.Length - 2)).ToArray();
        var wantedTotal = Math.Max(1, wanted.Sum());
        for (var i = 0; i < spans.Count; i++)
        {
            var budget = 2 + (int)Math.Floor(spare * (wanted[i] / (double)wantedTotal));
            fits[i] = FitSpan(formula, spans[i], Math.Clamp(budget, 2, maxPoints), tolerance, progress,
                $"{curveName}: allocating controls to span {i + 1}/{spans.Count}", maxPoints);
        }
        while (MergedCount(fits) > maxPoints)
        {
            var index = 0;
            for (var i = 1; i < fits.Length; i++)
                if (fits[i].Points.Length > fits[index].Points.Length) index = i;
            if (fits[index].Points.Length <= 2) break;
            fits[index] = FitSpan(formula, spans[index], fits[index].Points.Length - 1, tolerance, progress,
                $"{curveName}: enforcing the {maxPoints}-point limit", maxPoints);
        }
        return Merge(fits);
    }

    private static int MergedCount(Fit[] fits)
    {
        var count = 0;
        foreach (var fit in fits) count += Math.Max(0, fit.Points.Length - 1);
        return count + (fits.Length == 0 ? 0 : 1);
    }

    private static List<SplinePoint> Merge(Fit[] fits)
    {
        var merged = new List<SplinePoint>();
        foreach (var fit in fits)
        {
            if (fit.Points.Length == 0) continue;
            var start = merged.Count > 0 && Math.Abs(merged[^1].X - fit.Points[0].X) <= Math.Max(1e-12, Math.Abs(fit.Points[0].X) * 1e-9) ? 1 : 0;
            for (var i = start; i < fit.Points.Length; i++) merged.Add(fit.Points[i]);
        }
        return merged;
    }

    private static Fit FitSpan(Func<double, double> formula, Span span, int maxPoints, double tolerance,
        IProgress<GenerationProgress>? progress, string context, int pointLimit)
    {
        maxPoints = Math.Max(2, maxPoints);
        var x = new[] { span.X0, span.X1 };
        var controlWeights = new[] { 0.5, 0.5 };
        var best = Solve(formula, span, x, controlWeights, tolerance);
        progress?.Report(new GenerationProgress("Fitting CC4 spline",
            $"{context} · {x.Length} controls · worst sampled error {best.Error:G4}", x.Length, pointLimit, best.Error));

        while (best.Error > tolerance && x.Length < maxPoints)
        {
            var candidates = ResidualCandidates(formula, span, best.Points, tolerance);
            Fit? improved = null;
            double[]? improvedX = null;
            double[]? improvedWeights = null;

            foreach (var candidateX in candidates)
            {
                var insertion = Array.BinarySearch(x, candidateX);
                if (insertion >= 0) continue;
                insertion = ~insertion;
                if (insertion == 0 || insertion == x.Length) continue;
                var left = x[insertion - 1];
                var right = x[insertion];
                var gap = right - left;
                if (gap <= 0 || candidateX - left <= gap * 1e-6 || right - candidateX <= gap * 1e-6) continue;

                var trialX = new double[x.Length + 1];
                var trialWeights = new double[controlWeights.Length + 1];
                Array.Copy(x, 0, trialX, 0, insertion);
                trialX[insertion] = candidateX;
                Array.Copy(x, insertion, trialX, insertion + 1, x.Length - insertion);
                Array.Copy(controlWeights, 0, trialWeights, 0, insertion);
                trialWeights[insertion] = 0.5;
                Array.Copy(controlWeights, insertion, trialWeights, insertion + 1, controlWeights.Length - insertion);
                var trial = Solve(formula, span, trialX, trialWeights, tolerance);
                if (trial.Error < (improved?.Error ?? double.PositiveInfinity))
                {
                    improved = trial;
                    improvedX = trialX;
                    improvedWeights = trialWeights;
                }
            }

            if (improved is null || improvedX is null || improvedWeights is null) break;
            x = improvedX;
            controlWeights = improvedWeights;
            best = improved.Value;
            if (x.Length == 3 && span.X0 == 0)
                (best, controlWeights) = OptimizeInitialControlWeight(formula, span, x, controlWeights, tolerance);
            progress?.Report(new GenerationProgress("Fitting CC4 spline",
                $"{context} · {x.Length} controls · worst sampled error {best.Error:G4}", x.Length, pointLimit, best.Error));
        }

        var allowedError = Math.Max(best.Error, tolerance);
        var simplified = true;
        while (simplified && x.Length > 2)
        {
            simplified = false;
            for (var remove = 1; remove < x.Length - 1; remove++)
            {
                var trialX = x.Where((_, index) => index != remove).ToArray();
                var trialWeights = controlWeights.Where((_, index) => index != remove).ToArray();
                var trial = Solve(formula, span, trialX, trialWeights, tolerance);
                if (trial.Error > allowedError) continue;
                x = trialX;
                controlWeights = trialWeights;
                best = trial;
                simplified = true;
                break;
            }
        }

        return best;
    }

    private static (Fit fit, double[] weights) OptimizeInitialControlWeight(Func<double, double> formula,
        Span span, double[] x, double[] weights, double tolerance)
    {
        var bestWeights = (double[])weights.Clone();
        var best = Solve(formula, span, x, bestWeights, tolerance);
        var left = 0d;
        var right = 1d;
        var ratio = (Math.Sqrt(5) - 1) * 0.5;
        var c = right - ratio * (right - left);
        var d = left + ratio * (right - left);
        var cWeights = (double[])weights.Clone(); cWeights[1] = c;
        var dWeights = (double[])weights.Clone(); dWeights[1] = d;
        var cFit = Solve(formula, span, x, cWeights, tolerance);
        var dFit = Solve(formula, span, x, dWeights, tolerance);
        if (cFit.Error < best.Error) { best = cFit; bestWeights = cWeights; }
        if (dFit.Error < best.Error) { best = dFit; bestWeights = dWeights; }

        var precisionLimit = Math.Sqrt(2.2204460492503131e-16);
        while (right - left > precisionLimit)
        {
            if (cFit.Error <= dFit.Error)
            {
                right = d;
                d = c;
                dFit = cFit;
                dWeights = cWeights;
                c = right - ratio * (right - left);
                cWeights = (double[])weights.Clone(); cWeights[1] = c;
                cFit = Solve(formula, span, x, cWeights, tolerance);
                if (cFit.Error < best.Error) { best = cFit; bestWeights = cWeights; }
            }
            else
            {
                left = c;
                c = d;
                cFit = dFit;
                cWeights = dWeights;
                d = left + ratio * (right - left);
                dWeights = (double[])weights.Clone(); dWeights[1] = d;
                dFit = Solve(formula, span, x, dWeights, tolerance);
                if (dFit.Error < best.Error) { best = dFit; bestWeights = dWeights; }
            }
        }
        return (best, bestWeights);
    }

    private static double[] ResidualCandidates(Func<double, double> formula, Span span,
        SplinePoint[] points, double tolerance)
    {
        var residuals = new List<(double X, double Error)>();
        var baked = BakeForFit(points);
        foreach (var x in ValidationXs(span, baked))
        {
            if (x > span.X0 && x < span.X1)
                residuals.Add((x, Math.Abs(Cc4Spline.InterpolateY(baked, x) - Evaluate(formula, x))));
        }
        if (residuals.Count == 0) return [];

        residuals.Sort((a, b) => b.Error.CompareTo(a.Error));
        var candidates = new List<double>(5);
        var minimumSeparation = (span.X1 - span.X0) / Math.Max(32, points.Length * 8);
        var selectedResiduals = new List<double>();
        foreach (var residual in residuals)
        {
            if (residual.Error <= tolerance) break;
            if (selectedResiduals.Any(x => Math.Abs(x - residual.X) <= minimumSeparation)) continue;
            selectedResiduals.Add(residual.X);
            candidates.Add(residual.X);
            if (candidates.Count == 5) break;
        }
        return candidates.ToArray();
    }

    private static Fit Solve(Func<double, double> formula, Span span, double[] x, double[] controlWeights, double tolerance)
    {
        var count = x.Length;
        var y = new double[count];
        y[0] = span.Y0;
        y[^1] = span.Y1;
        if (count > 2 && !SolveInterior(formula, span, x, controlWeights, y))
        {
            for (var i = 1; i < count - 1; i++) y[i] = Evaluate(formula, x[i]);
        }
        ConstrainMonotonicControls(span, y);
        var points = new SplinePoint[count];
        for (var i = 0; i < count; i++)
        {
            var edge = (i == 0 && span.Edge0) || (i == count - 1 && span.Edge1);
            points[i] = new SplinePoint(x[i], y[i], controlWeights[i], edge);
        }
        return new Fit(points, MaxError(formula, span, points, tolerance));
    }

    private static void ConstrainMonotonicControls(Span span, double[] y)
    {
        if (y.Length < 3 || span.Leaves.Length == 0) return;

        var increasing = span.Y1 >= span.Y0;
        var decreasing = span.Y1 <= span.Y0;
        var scale = Math.Max(1, Math.Max(Math.Abs(span.Y0), Math.Abs(span.Y1)));
        var epsilon = (Math.BitIncrement(scale) - scale) * 16;
        foreach (var leaf in span.Leaves)
        {
            increasing &= leaf.Y1 + epsilon >= leaf.Y0 && leaf.MidY + epsilon >= leaf.Y0 && leaf.Y1 + epsilon >= leaf.MidY;
            decreasing &= leaf.Y1 <= leaf.Y0 + epsilon && leaf.MidY <= leaf.Y0 + epsilon && leaf.Y1 <= leaf.MidY + epsilon;
        }

        if (increasing)
            ProjectMonotonicControls(y, span.Y0, span.Y1, increasing: true);
        else if (decreasing)
            ProjectMonotonicControls(y, span.Y0, span.Y1, increasing: false);
    }

    private static void ProjectMonotonicControls(double[] y, double first, double last, bool increasing)
    {
        var count = y.Length - 2;
        if (count <= 0) return;

        var direction = increasing ? 1d : -1d;
        var lower = Math.Min(direction * first, direction * last);
        var upper = Math.Max(direction * first, direction * last);
        var means = new double[count];
        var sizes = new int[count];
        var starts = new int[count];
        var blocks = 0;
        for (var i = 0; i < count; i++)
        {
            means[blocks] = Math.Clamp(direction * y[i + 1], lower, upper);
            sizes[blocks] = 1;
            starts[blocks] = i;
            blocks++;
            while (blocks > 1 && means[blocks - 2] > means[blocks - 1])
            {
                var totalSize = sizes[blocks - 2] + sizes[blocks - 1];
                means[blocks - 2] = (means[blocks - 2] * sizes[blocks - 2] + means[blocks - 1] * sizes[blocks - 1]) / totalSize;
                sizes[blocks - 2] = totalSize;
                blocks--;
            }
        }

        for (var block = 0; block < blocks; block++)
        {
            var value = direction * means[block];
            var end = starts[block] + sizes[block];
            for (var i = starts[block]; i < end; i++) y[i + 1] = value;
        }
    }

    private static bool SolveInterior(Func<double, double> formula, Span span, double[] x, double[] controlWeights, double[] y)
    {
        var unknown = x.Length - 2;
        if (unknown <= 0) return true;
        var bandwidth = Math.Min(3, unknown - 1);
        var normal = new double[bandwidth + 1][];
        for (var band = 0; band <= bandwidth; band++) normal[band] = new double[unknown - band];
        var rhs = new double[unknown];
        var probes = Math.Max(8, unknown * 6);
        for (var probe = 1; probe < probes; probe++)
        {
            var t = probe / (double)probes;
            WriteUserBasis(controlWeights, span.Edge0, span.Edge1, t, out var offset, out var w0, out var w1, out var w2, out var w3);
            var sampleX = 0d;
            Accumulate(x, offset, w0, w1, w2, w3, ref sampleX);
            var target = Evaluate(formula, sampleX);
            target -= EndpointContribution(y, x.Length, offset, w0, w1, w2, w3);
            AddNormal(normal, rhs, unknown, offset, w0, w1, w2, w3, target);
        }
        return BandSolver.TrySolve(normal, rhs) && CopyInterior(rhs, y);
    }

    private static double EndpointContribution(double[] y, int count, int offset, double w0, double w1, double w2, double w3)
    {
        var value = 0d;
        void Take(int index, double weight)
        {
            if (weight == 0 || index < 0 || index >= count) return;
            if (index == 0 || index == count - 1) value += weight * y[index];
        }
        Take(offset, w0);
        Take(offset + 1, w1);
        Take(offset + 2, w2);
        Take(offset + 3, w3);
        return value;
    }

    private static void AddNormal(double[][] normal, double[] rhs, int unknown, int offset,
        double w0, double w1, double w2, double w3, double target)
    {
        var columns = new int[4];
        var weights = new double[4];
        var used = 0;
        void Take(int index, double weight)
        {
            var column = index - 1;
            if (weight == 0 || column < 0 || column >= unknown) return;
            columns[used] = column;
            weights[used] = weight;
            used++;
        }
        Take(offset, w0);
        Take(offset + 1, w1);
        Take(offset + 2, w2);
        Take(offset + 3, w3);
        for (var a = 0; a < used; a++)
        {
            rhs[columns[a]] += weights[a] * target;
            for (var b = a; b < used; b++)
            {
                var row = columns[a];
                var column = columns[b];
                if (column < row) (row, column) = (column, row);
                var band = column - row;
                if (band < normal.Length && row < normal[band].Length) normal[band][row] += weights[a] * weights[b];
            }
        }
    }

    private static bool CopyInterior(double[] solved, double[] y)
    {
        for (var i = 0; i < solved.Length; i++)
        {
            if (!double.IsFinite(solved[i])) return false;
            y[i + 1] = solved[i];
        }
        return true;
    }

    private static double MaxError(Func<double, double> formula, Span span, SplinePoint[] points, double tolerance)
    {
        var worst = 0d;
        var baked = BakeForFit(points);
        foreach (var x in ValidationXs(span, baked))
        {
            if (x >= span.X0 && x <= span.X1)
                worst = Math.Max(worst, Math.Abs(Cc4Spline.InterpolateY(baked, x) - Evaluate(formula, x)));
        }
        return worst;
    }

    private static SortedSet<double> ValidationXs(Span span, IReadOnlyList<SplineSample> baked)
    {
        var xs = new SortedSet<double>(baked.Where(sample => sample.X >= span.X0 && sample.X <= span.X1).Select(sample => sample.X));
        foreach (var leaf in span.Leaves)
        {
            var width = leaf.X1 - leaf.X0;
            xs.Add(leaf.X0);
            xs.Add(leaf.X0 + width * 0.25);
            xs.Add(leaf.X0 + width * 0.5);
            xs.Add(leaf.X0 + width * 0.75);
            xs.Add(leaf.X1);
        }
        xs.RemoveWhere(x => !double.IsFinite(x));
        return xs;
    }

    private static IReadOnlyList<SplineSample> BakeForFit(SplinePoint[] points) =>
        Cc4Spline.Bake(points, Math.Max(256, points.Length * 16));

    private static void Accumulate(double[] values, int offset, double w0, double w1, double w2, double w3, ref double sum)
    {
        var accumulated = sum;
        void Take(int index, double weight)
        {
            if (weight != 0 && (uint)index < (uint)values.Length) accumulated += weight * values[index];
        }
        Take(offset, w0);
        Take(offset + 1, w1);
        Take(offset + 2, w2);
        Take(offset + 3, w3);
        sum = accumulated;
    }

    private static void WriteUserBasis(double[] controlWeights, bool edgeStart, bool edgeEnd, double t,
        out int offset, out double w0, out double w1, out double w2, out double w3)
    {
        var userCount = controlWeights.Length;
        var extraStart = edgeStart ? 2 : 0;
        var extraEnd = edgeEnd ? 2 : 0;
        var expanded = userCount + extraStart + extraEnd;
        var basis = Cc4Spline.PolynomialBasis(expanded, t);
        Span<int> indices = stackalloc int[4];
        Span<double> weights = stackalloc double[4];
        var used = 0;
        for (var j = 0; j < 4; j++)
        {
            var index = basis.Offset + j;
            var weight = basis[j];
            if (weight == 0 || (uint)index >= (uint)expanded) continue;
            var user = index < extraStart ? 0 : index >= extraStart + userCount ? userCount - 1 : index - extraStart;
            weight *= Cc4Spline.InternalWeight(controlWeights[user], expanded);
            var slot = -1;
            for (var s = 0; s < used; s++)
                if (indices[s] == user) { slot = s; break; }
            if (slot >= 0) weights[slot] += weight;
            else
            {
                indices[used] = user;
                weights[used] = weight;
                used++;
            }
        }
        var total = weights[0] + weights[1] + weights[2] + weights[3];
        if (total > 0)
            for (var i = 0; i < used; i++) weights[i] /= total;
        while (used < 4)
        {
            indices[used] = -1;
            weights[used] = 0;
            used++;
        }
        offset = indices[0];
        w0 = weights[0];
        w1 = weights[1];
        w2 = weights[2];
        w3 = weights[3];
    }

    private static double NextAfter(double value) => Math.BitIncrement(value);

    private static double Evaluate(Func<double, double> formula, double x)
    {
        var value = formula(x);
        if (!double.IsFinite(value)) throw new InvalidOperationException("The curve formula returned a non-finite value.");
        return value;
    }

    private static class BandSolver
    {
        public static bool TrySolve(double[][] upper, double[] rhs)
        {
            var n = rhs.Length;
            if (n == 0) return true;
            var bandwidth = upper.Length - 1;
            var factor = new double[n][];
            for (var i = 0; i < n; i++) factor[i] = new double[bandwidth + 1];
            for (var i = 0; i < n; i++)
            {
                for (var j = Math.Max(0, i - bandwidth); j <= i; j++)
                {
                    var sum = Band(upper, j, i);
                    for (var k = Math.Max(0, i - bandwidth); k < j; k++)
                        sum -= factor[i][i - k] * factor[j][j - k];
                    if (i == j)
                    {
                        if (sum <= 1e-18 * (1 + Math.Abs(Band(upper, i, i)))) return false;
                        factor[i][0] = Math.Sqrt(sum);
                    }
                    else factor[i][i - j] = sum / factor[j][0];
                }
            }

            var forward = new double[n];
            for (var i = 0; i < n; i++)
            {
                var sum = rhs[i];
                for (var k = Math.Max(0, i - bandwidth); k < i; k++) sum -= factor[i][i - k] * forward[k];
                forward[i] = sum / factor[i][0];
            }
            for (var i = n - 1; i >= 0; i--)
            {
                var sum = forward[i];
                for (var k = i + 1; k <= Math.Min(n - 1, i + bandwidth); k++) sum -= factor[k][k - i] * rhs[k];
                rhs[i] = sum / factor[i][0];
            }
            return rhs.All(double.IsFinite);
        }

        private static double Band(double[][] upper, int row, int column)
        {
            if (column < row) (row, column) = (column, row);
            var band = column - row;
            if (band >= upper.Length || row >= upper[band].Length) return 0;
            return upper[band][row];
        }
    }
}

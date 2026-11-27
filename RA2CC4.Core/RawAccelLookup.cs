namespace RA2CC4.Core;

public static class RawAccelLookup
{
    public static double Evaluate(IReadOnlyList<double> xValues, IReadOnlyList<double> yValues, double x, bool velocity)
    {
        if (xValues.Count != yValues.Count || xValues.Count < 2)
            throw new ArgumentException("Lookup tables need matching X and Y arrays with at least two points.");
        if (x <= 0) return velocity ? yValues[0] / xValues[0] : yValues[0];
        if (x < xValues[0]) return velocity ? yValues[0] / Math.Max(xValues[0], 1e-12) : yValues[0];

        var low = 0;
        var high = xValues.Count - 1;
        while (high - low > 1)
        {
            var middle = low + (high - low) / 2;
            if (x <= xValues[middle]) high = middle;
            else low = middle;
        }

        var x0 = xValues[low];
        var x1 = xValues[high];
        var t = x1 == x0 ? 1 : (x - x0) / (x1 - x0);
        var value = yValues[low] + (yValues[high] - yValues[low]) * t;
        return velocity ? value / x : value;
    }
}

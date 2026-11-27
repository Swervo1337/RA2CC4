namespace RA2CC4.Core;

public sealed record GenerationProgress(
    string Stage,
    string Detail,
    int? Points = null,
    int? PointLimit = null,
    double? Error = null,
    double? Fraction = null);

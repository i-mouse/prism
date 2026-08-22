using Microsoft.EntityFrameworkCore.Storage.ValueConversion;
using Prism.ApiService.Data.Schemas;

namespace Prism.ApiService.Data.Converters;

/// <summary>
/// Maps GroundingStatus enum ↔ Postgres title-case strings written by the Python worker.
/// </summary>
public sealed class GroundingStatusConverter : ValueConverter<GroundingStatus, string>
{
    private static readonly Dictionary<GroundingStatus, string> ToDb = new()
    {
        [GroundingStatus.Pass]    = "Pass",
        [GroundingStatus.Fail]    = "Fail",
        [GroundingStatus.Skipped] = "Skipped",
    };

    private static readonly Dictionary<string, GroundingStatus> FromDb =
        ToDb.ToDictionary(kv => kv.Value, kv => kv.Key);

    public GroundingStatusConverter()
        : base(
            v => ToDb[v],
            v => FromDb[v])
    { }
}
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;
using Prism.ApiService.Data.Schemas;

namespace Prism.ApiService.Data.Converters;

/// <summary>
/// Maps ClaimLabel enum ↔ Postgres snake_case strings written by the Python worker.
/// Kept explicit (not EnumToStringConverter) because C# member names are PascalCase
/// while Python persists snake_case; the two vocabularies must be pinned in one place.
/// </summary>
public sealed class ClaimLabelConverter : ValueConverter<ClaimLabel, string>
{
    private static readonly Dictionary<ClaimLabel, string> ToDb = new()
    {
        [ClaimLabel.Supported]          = "supported",
        [ClaimLabel.PartiallySupported] = "partially_supported",
        [ClaimLabel.NotSupported]       = "not_supported",
    };

    private static readonly Dictionary<string, ClaimLabel> FromDb =
        ToDb.ToDictionary(kv => kv.Value, kv => kv.Key);

    public ClaimLabelConverter()
        : base(
            v => ToDb[v],
            v => FromDb[v])
    { }
}
using System.Diagnostics;

namespace Prism.ApiService.Telemetry;

internal static class PrismTelemetry
{
    // Name must match builder.Environment.ApplicationName ("Prism.ApiService") - that's the
    // source ServiceDefaults' tracing.AddSource(builder.Environment.ApplicationName) registers.
    internal static readonly ActivitySource ActivitySource = new("Prism.ApiService");
}

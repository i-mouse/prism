using Prism.ApiService.Data.Schemas;

namespace Prism.ApiService.Extensions;

public static class ExtractionStatusExtensions
{
    public static string ToFrontendString(this ExtractionStatus status)
    {
        return status switch
        {
            ExtractionStatus.Pending => "Pending",
            ExtractionStatus.InProgress => "In progress",
            ExtractionStatus.Completed => "Completed",
            ExtractionStatus.Failed => "Failed",
            _ => "Pending"
        };
    }
}

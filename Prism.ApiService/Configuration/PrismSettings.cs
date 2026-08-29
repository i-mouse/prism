using System.ComponentModel.DataAnnotations;

namespace Prism.ApiService.Configuration;

public sealed class PrismSettings
{
    [Required]
    public string PythonApiUrl { get; set; } = string.Empty;

    public string AllowedOrigins { get; set; } = "http://localhost:7000";

    public string? SystemAdminToken { get; set; }

    public bool RunMigrationsOnStartup { get; set; }
}

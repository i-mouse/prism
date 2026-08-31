using System.ComponentModel.DataAnnotations;

namespace Prism.ApiService.Configuration;

public sealed class PrismSettings
{
    [Required]
    public string PythonApiUrl { get; set; } = string.Empty;

    public bool RunMigrationsOnStartup { get; set; }
}

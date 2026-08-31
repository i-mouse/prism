namespace Prism.ApiService.Configuration;

public sealed class CorsSettings
{
    public string[] AllowedOrigins { get; set; } = Array.Empty<string>();
}

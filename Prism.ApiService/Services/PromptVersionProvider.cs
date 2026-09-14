using System.Text.Json;

namespace Prism.ApiService.Services;

// Caches the pipeline's current prompt-version hash for the process lifetime.
// The Python service (Prism.PythonService/api.py) already computes this once
// at its own startup and serves it from memory - this wrapper adds a second,
// C#-side cache so GetPaperClaims (called on every papers/{id}/claims fetch)
// never re-hits the network after the first successful call, let alone
// re-reads/re-hashes the prompt files themselves.
public class PromptVersionProvider
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<PromptVersionProvider> _logger;
    private readonly SemaphoreSlim _lock = new(1, 1);
    private string? _cachedVersion;

    public PromptVersionProvider(IHttpClientFactory httpClientFactory, ILogger<PromptVersionProvider> logger)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
    }

    public async Task<string?> GetCurrentPromptVersionAsync(CancellationToken ct)
    {
        if (_cachedVersion != null)
        {
            return _cachedVersion;
        }

        await _lock.WaitAsync(ct);
        try
        {
            if (_cachedVersion != null)
            {
                return _cachedVersion;
            }

            var client = _httpClientFactory.CreateClient("pythonapi");
            var response = await client.GetAsync("/api/system/prompt-version", ct);
            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("Failed to fetch current prompt version: {StatusCode}", response.StatusCode);
                return null;
            }

            var body = await response.Content.ReadAsStringAsync(ct);
            using var doc = JsonDocument.Parse(body);
            _cachedVersion = doc.RootElement.TryGetProperty("promptVersion", out var pv) ? pv.GetString() : null;
            return _cachedVersion;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to fetch current prompt version");
            return null;
        }
        finally
        {
            _lock.Release();
        }
    }
}

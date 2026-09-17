using System.Net.Http.Json;

namespace Prism.ApiService.Services;

// Injects a synthetic "processing completed" AI message into a chat's
// LangGraph-backed history (see Prism.PythonService/api.py's
// inject_summary endpoint) for chats that reach a Completed file WITHOUT
// running the extraction pipeline themselves — a cache hit, or a chat that
// joined while another chat's run was still Pending/InProgress. A chat
// whose own upload actually ran the pipeline gets this same message
// directly from Prism.PythonService/main.py's own aupdate_state call
// instead; this exists so every OTHER chat gets it too, rather than none.
public static class ChatSummaryInjector
{
    public static async Task InjectAsync(IHttpClientFactory httpClientFactory, string chatId, string? summary, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(summary))
        {
            return;
        }

        try
        {
            var client = httpClientFactory.CreateClient("pythonapi");
            await client.PostAsJsonAsync($"/api/chat/{chatId}/inject-summary", new { summary }, ct);
        }
        catch
        {
            // Best-effort — a failed injection shouldn't fail the upload/
            // join/completion flow it's attached to. The chat just won't
            // have the summary turn; the paper's claims are unaffected.
        }
    }
}

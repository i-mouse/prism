using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Data;

namespace Prism.ApiService.Features.Auth;

public static class GuestAuthEndpoints
{
    public const string CookieName = "prism-guest-session";

    public static void MapGuestAuthEndpoints(this IEndpointRouteBuilder app)
    {
        // Generates a server-side random guest session ID and returns it as an
        // HttpOnly cookie. The client never sees the raw ID — it is transmitted
        // only as a browser cookie on subsequent requests. This replaces the old
        // insecure pattern of trusting a UserId from the request body.
        app.MapPost("/api/auth/guest", (HttpContext httpContext) =>
        {
            var sessionId = Guid.NewGuid().ToString();

            httpContext.Response.Cookies.Append(CookieName, sessionId, new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Strict,
                // No explicit Expires -> session cookie; cleared when browser closes.
                // Guest sessions are intentionally ephemeral.
                Path = "/"
            });

            // Return the provider hint so the frontend can update its local user state
            // without knowing the actual session ID value.
            return Results.Ok(new { provider = "guest" });
        })
        .WithName("GuestSignIn")
        .AllowAnonymous();

        // Clears the guest session cookie. Called on sign-out for guest users.
        // For Google-authenticated users the frontend calls MSAL logoutRedirect()
        // and this endpoint is not needed, but calling it is harmless.
        app.MapPost("/api/auth/logout", async (HttpContext httpContext, PrismDBContext dbContext, IHttpClientFactory httpClientFactory, ILogger<Program> logger, CancellationToken ct) =>
        {
            // Guest chat history isn't persisted once the session ends (unlike
            // Google-authenticated users' chats, which keep full persistence) — the
            // underlying paper/claims data is left untouched (it's shared/reused by
            // the content-hash dedupe), only this guest's LangGraph chat memory
            // (checkpoints, keyed by chat_id as thread_id) is deleted. Must resolve
            // and act on the guest id BEFORE the cookie is deleted below.
            var isAuthenticated = httpContext.User.Identity?.IsAuthenticated == true;
            if (!isAuthenticated && httpContext.Request.Cookies.TryGetValue(CookieName, out var guestId) && !string.IsNullOrEmpty(guestId))
            {
                var chatIds = await dbContext.PrismDocuments
                    .Where(d => d.UserId == guestId)
                    .Select(d => d.ChatId)
                    .ToListAsync(ct);

                var client = httpClientFactory.CreateClient("pythonapi");
                foreach (var chatId in chatIds)
                {
                    try
                    {
                        await client.DeleteAsync($"/api/chat/{chatId}/checkpoint", ct);
                    }
                    catch (Exception ex)
                    {
                        logger.LogWarning(ex, "Failed to delete checkpoint for guest chat {ChatId} on logout", chatId);
                    }
                }
            }

            httpContext.Response.Cookies.Delete(CookieName, new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Strict,
                Path = "/"
            });

            return Results.NoContent();
        })
        .WithName("SignOut")
        .AllowAnonymous();
    }

    /// <summary>
    /// Resolves the caller's identity from either a validated JWT (Google-authenticated
    /// users) or the secure guest-session cookie (guest users). Returns null if neither
    /// is present — endpoints should return 401 in that case.
    /// </summary>
    /// <remarks>
    /// CLAIM MAPPING NOTE: MapInboundClaims is explicitly disabled in Program.cs.
    /// Read the authenticated user's ID as User.FindFirst("oid")?.Value.
    /// ("oid" is the stable, tenant-wide user identifier. "sub" is a pairwise identifier
    /// that differs per app, which is incorrect for linking across our services).
    /// </remarks>
    public static string? ResolveUserId(HttpContext httpContext)
    {
        if (httpContext.User.Identity?.IsAuthenticated == true)
        {
            return httpContext.User.FindFirst("oid")?.Value;
        }

        return httpContext.Request.Cookies.TryGetValue(CookieName, out var guestId)
            ? guestId
            : null;
    }
}

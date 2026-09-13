using Microsoft.AspNetCore.Http;

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
        app.MapPost("/api/auth/logout", (HttpContext httpContext) =>
        {
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
    /// CLAIM MAPPING NOTE: Microsoft.Identity.Web 4.x sets MapInboundClaims = false by
    /// default, meaning the JWT "sub" claim is NOT remapped to ClaimTypes.NameIdentifier.
    /// Read the authenticated user's ID as User.FindFirst("sub")?.Value.
    /// </remarks>
    public static string? ResolveUserId(HttpContext httpContext)
    {
        if (httpContext.User.Identity?.IsAuthenticated == true)
        {
            // "sub" = subject claim (Entra External ID CIAM issues this as the user's
            // immutable object ID). MapInboundClaims is false, so use the raw claim name.
            return httpContext.User.FindFirst("sub")?.Value;
        }

        return httpContext.Request.Cookies.TryGetValue(CookieName, out var guestId)
            ? guestId
            : null;
    }
}

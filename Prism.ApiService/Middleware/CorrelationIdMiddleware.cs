using System.Diagnostics;

namespace Prism.ApiService.Middleware;

public static class CorrelationIdMiddlewareExtensions
{
    public const string HeaderName = "X-Correlation-Id";
    public const string ItemsKey = "CorrelationId";

    public static IApplicationBuilder UseCorrelationId(this IApplicationBuilder app)
    {
        return app.Use(async (context, next) =>
        {
            var correlationId = context.Request.Headers.TryGetValue(HeaderName, out var headerValue)
                && !string.IsNullOrWhiteSpace(headerValue)
                ? headerValue.ToString()
                : Guid.NewGuid().ToString();

            context.Items[ItemsKey] = correlationId;
            Activity.Current?.SetTag("correlation.id", correlationId);

            context.Response.OnStarting(() =>
            {
                context.Response.Headers[HeaderName] = correlationId;
                return Task.CompletedTask;
            });

            await next();
        });
    }

    public static string? GetCorrelationId(this HttpContext context)
    {
        return context.Items.TryGetValue(ItemsKey, out var value) ? value as string : null;
    }
}

using System.Diagnostics;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Http;

namespace Prism.ApiService.Middleware;

public sealed class GlobalExceptionHandler(IHostEnvironment env, ILogger<GlobalExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(HttpContext httpContext, Exception exception, CancellationToken cancellationToken)
    {
        logger.LogError(exception, "Unhandled exception");

        Activity.Current?.SetStatus(ActivityStatusCode.Error, exception.Message);

        var (status, title) = MapStatus(exception);

        var problemDetailsService = httpContext.RequestServices.GetRequiredService<IProblemDetailsService>();

        return await problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            Exception = exception,
            ProblemDetails =
            {
                Status = status,
                Title = title,
                Detail = env.IsDevelopment() ? exception.Message : "An internal error occurred",
            },
        });
    }

    // Most exceptions really are 500s - an unexpected server-side fault with
    // no better answer. The exceptions below already know their own correct
    // status (e.g. Kestrel's MaxRequestBodySize rejection is a client-side
    // 413, not a server fault) - branch to pass that through instead of
    // reporting every failure the same way regardless of cause.
    private static (int Status, string Title) MapStatus(Exception exception) => exception switch
    {
        BadHttpRequestException badRequest => (badRequest.StatusCode, "The request could not be processed"),
        _ => (StatusCodes.Status500InternalServerError, "An unexpected error occurred"),
    };
}

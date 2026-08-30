using System.Diagnostics;
using Microsoft.AspNetCore.Diagnostics;

namespace Prism.ApiService.Middleware;

public sealed class GlobalExceptionHandler(IHostEnvironment env, ILogger<GlobalExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(HttpContext httpContext, Exception exception, CancellationToken cancellationToken)
    {
        logger.LogError(exception, "Unhandled exception");

        Activity.Current?.SetStatus(ActivityStatusCode.Error, exception.Message);

        var problemDetailsService = httpContext.RequestServices.GetRequiredService<IProblemDetailsService>();

        return await problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            Exception = exception,
            ProblemDetails =
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "An unexpected error occurred",
                Detail = env.IsDevelopment() ? exception.Message : "An internal error occurred",
            },
        });
    }
}

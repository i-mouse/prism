using Prism.ApiService.Data;
using Prism.ApiService.Services;
using MassTransit;
using Prism.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using Prism.ApiService.Configuration;

namespace Prism.ApiService.Features.System;

public static class SystemEndPoint
{
        public static void MapSystemEndPoint(this IEndpointRouteBuilder app)
        {
        app.MapDelete("/api/system/reset", async (
            HttpContext ctx,
            IOptions<PrismSettings> settings,
            IWebHostEnvironment env,
            PrismDBContext db,
            IHttpClientFactory httpClientFactory,
            ILogger<PrismDBContext> logger) =>
        {
            var expectedToken = settings.Value.SystemAdminToken;
            if (string.IsNullOrEmpty(expectedToken))
            {
                return Results.Problem("System reset disabled: no admin token configured", statusCode: 403);
            }

            var providedToken = ctx.Request.Headers["X-Admin-Token"].ToString();
            if (providedToken != expectedToken)
            {
                return Results.Problem("Unauthorized", statusCode: 401);
            }

            try
            {
                await db.Database.ExecuteSqlRawAsync("TRUNCATE TABLE \"prism_documents\" CASCADE;");

                // 2. Command Python to wipe LangGraph and Qdrant
                var pythonClient = httpClientFactory.CreateClient("pythonapi");
                pythonClient.DefaultRequestHeaders.Add("X-Admin-Token", expectedToken);
                var pythonResponse = await pythonClient.DeleteAsync("/api/system/reset");

                if (!pythonResponse.IsSuccessStatusCode) {
                    return Results.Problem("C# DB wiped, but Python failed to wipe Qdrant/LangGraph.");
                }

                return Results.Ok(new { message = "Total system wipe successful." });
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "System reset failed");
                return env.IsDevelopment()
                    ? Results.Problem(ex.Message, statusCode: 500)
                    : Results.Problem("An internal error occurred", statusCode: 500);
            }
        });
    }
}

using Prism.ApiService.Services;
using MassTransit;
using Prism.ApiService.Contracts;
using Prism.ApiService.Middleware;
using Microsoft.AspNetCore.Mvc;
using System.Data.Common;
using Microsoft.EntityFrameworkCore;

namespace Prism.ApiService.Features.Chat;

public static class ChatEndPoint
{

    public static void MapChatEndPoint(this IEndpointRouteBuilder app)
    {
      app.MapPost("/api/chat/ask/stream", async (HttpContext httpContext, [FromBody] PaperChatAskRequest request, IHttpClientFactory httpClientFactory, ILogger<PaperChatAskRequest> logger, CancellationToken ct) =>
        {
            // Paper-scoped chat (Slice 3a): proxies the Python SSE stream through to the
            // client unbuffered. Bypasses RabbitMQ - direct C# -> Python HTTP call.
            var client = httpClientFactory.CreateClient("pythonapi");
            client.Timeout = TimeSpan.FromMinutes(10);

            using var pythonRequest = new HttpRequestMessage(HttpMethod.Post, "/api/chat/ask/stream")
            {
                Content = JsonContent.Create(request)
            };
            var correlationId = httpContext.GetCorrelationId();
            if (correlationId is not null)
            {
                pythonRequest.Headers.TryAddWithoutValidation(CorrelationIdMiddlewareExtensions.HeaderName, correlationId);
            }

            HttpResponseMessage pythonResponse;
            try
            {
                pythonResponse = await client.SendAsync(
                    pythonRequest, HttpCompletionOption.ResponseHeadersRead, ct);
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Failed to reach python paper-chat stream endpoint.");
                httpContext.Response.StatusCode = StatusCodes.Status502BadGateway;
                await httpContext.Response.WriteAsync(ex.Message, ct);
                return;
            }

            using (pythonResponse)
            {
                if (!pythonResponse.IsSuccessStatusCode)
                {
                    var error = await pythonResponse.Content.ReadAsStringAsync(ct);
                    logger.LogError($"Python paper-chat stream error: {error}");
                    httpContext.Response.StatusCode = (int)pythonResponse.StatusCode;
                    await httpContext.Response.WriteAsync(error, ct);
                    return;
                }

                httpContext.Response.ContentType = "text/event-stream";
                httpContext.Response.Headers["Cache-Control"] = "no-cache";
                httpContext.Response.Headers["Connection"] = "keep-alive";
                httpContext.Response.Headers["X-Accel-Buffering"] = "no";

                await using var stream = await pythonResponse.Content.ReadAsStreamAsync(ct);
                var buffer = new byte[4096];
                int bytesRead;
                while ((bytesRead = await stream.ReadAsync(buffer, ct)) > 0)
                {
                    await httpContext.Response.Body.WriteAsync(buffer.AsMemory(0, bytesRead), ct);
                    await httpContext.Response.Body.FlushAsync(ct);
                }
            }
        })
        .WithName("AskPaperChatStream")
        .DisableAntiforgery();

      app.MapGet("/api/chat/{chatId}/history", async(string chatId,IHttpClientFactory httpClientFactory, IWebHostEnvironment env, ILogger<PaperChatAskRequest> logger, CancellationToken ct)=>
        {
          try
          {
            var client =  httpClientFactory.CreateClient("pythonapi");
            var result = await client.GetAsync($"/api/chat/{chatId}/history",ct);

            if (!result.IsSuccessStatusCode)
            {
              var error =  await result.Content.ReadAsStringAsync(ct);
               logger.LogError($"Problem getting history API error: {error}\n");
               return Results.Problem($"Problem getting history API error: {error}");
            }
            var history = await result.Content.ReadFromJsonAsync(typeof(object),ct);
            return Results.Ok(history);
          }
          catch (Exception ex)
         {
          logger.LogError(ex, "Failed to get chat history");
          return env.IsDevelopment()
              ? Results.Problem(ex.Message, statusCode: 500)
              : Results.Problem("An internal error occurred", statusCode: 500);
          }
        });
    }
}
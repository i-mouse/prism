using Prism.ApiService.Services;
using MassTransit;
using Prism.ApiService.Contracts;
using Prism.ApiService.Middleware;
using Microsoft.AspNetCore.Mvc;
using System.Data.Common;
using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Data;
using Prism.ApiService.Features.Auth;

namespace Prism.ApiService.Features.Chat;

public static class ChatEndPoint
{

    public static void MapChatEndPoint(this IEndpointRouteBuilder app)
    {
      app.MapPost("/api/chat/ask/stream", async (HttpContext httpContext, [FromBody] PaperChatAskRequest request, IHttpClientFactory httpClientFactory, PrismDBContext dbContext, ILogger<PaperChatAskRequest> logger, CancellationToken ct) =>
        {
            var userId = GuestAuthEndpoints.ResolveUserId(httpContext);
            if (string.IsNullOrEmpty(userId))
            {
                httpContext.Response.StatusCode = StatusCodes.Status401Unauthorized;
                return;
            }

            if (!Guid.TryParse(request.chat_id, out var chatGuid))
            {
                httpContext.Response.StatusCode = StatusCodes.Status400BadRequest;
                await httpContext.Response.WriteAsync("Invalid chat_id", ct);
                return;
            }

            var ownerId = await dbContext.PrismDocuments
                .Where(d => d.ChatId == chatGuid)
                .Select(d => d.UserId)
                .FirstOrDefaultAsync(ct);

            if (ownerId == null)
            {
                httpContext.Response.StatusCode = StatusCodes.Status404NotFound;
                return;
            }

            if (ownerId != userId)
            {
                httpContext.Response.StatusCode = StatusCodes.Status403Forbidden;
                return;
            }

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

      app.MapGet("/api/chat/{chatId}/history", async(string chatId, HttpContext httpContext, IHttpClientFactory httpClientFactory, PrismDBContext dbContext, IWebHostEnvironment env, ILogger<PaperChatAskRequest> logger, CancellationToken ct)=>
        {
          var userId = GuestAuthEndpoints.ResolveUserId(httpContext);
          if (string.IsNullOrEmpty(userId))
          {
              return Results.Unauthorized();
          }

          if (!Guid.TryParse(chatId, out var chatGuid))
          {
              return Results.Problem(detail: "Invalid chatId", statusCode: StatusCodes.Status400BadRequest);
          }

          var ownerId = await dbContext.PrismDocuments
              .Where(d => d.ChatId == chatGuid)
              .Select(d => d.UserId)
              .FirstOrDefaultAsync(ct);

          if (ownerId == null)
          {
              return Results.NotFound();
          }

          if (ownerId != userId)
          {
              return Results.Problem(detail: "You do not have access to this chat.", statusCode: StatusCodes.Status403Forbidden);
          }

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
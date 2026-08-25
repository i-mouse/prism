using Prism.ApiService.Data;
using Prism.ApiService.Services;
using MassTransit;
using Prism.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;
using Minio.DataModel.Args;
using System.Data.Common;
using Microsoft.EntityFrameworkCore;

namespace Prism.ApiService.Features.Chat;

public static class ChatEndPoint
{

    public static void MapChatEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/chat/ask", async ([FromBody] ChatRequest request, IHttpClientFactory httpClientFactory, PrismDBContext dBContext, ILogger<ChatRequest> logger) =>
        {

           try
           {

             var client = httpClientFactory.CreateClient("pythonapi");
              await AddToDatabase(request,dBContext);
             var result = await client.PostAsJsonAsync("/api/chat/ask",request);
 
             if(!result.IsSuccessStatusCode)
             {
               var error =  await result.Content.ReadAsStringAsync();
               logger.LogError($"Python chat API error: {error}\n");
               return Results.Problem($"Python chat API error: {error}");
             }
 
             var ans =  await result.Content.ReadFromJsonAsync<ChatResponse>();
             return Results.Ok(ans);
           }
           catch (Exception ex)
           {
               logger.LogError(ex,$"Failed to call python worker ASK api.");
                return Results.InternalServerError(ex.Message);
           }

        }  ).WithName("AskAgent") .DisableAntiforgery();

      app.MapPost("/api/chat/ask/stream", async (HttpContext httpContext, [FromBody] PaperChatAskRequest request, IHttpClientFactory httpClientFactory, ILogger<ChatRequest> logger) =>
        {
            // Paper-scoped chat (Slice 3a): proxies the Python SSE stream through to the
            // client unbuffered. Bypasses RabbitMQ - direct C# -> Python HTTP call.
            var client = httpClientFactory.CreateClient("pythonapi");
            client.Timeout = TimeSpan.FromMinutes(10);

            using var pythonRequest = new HttpRequestMessage(HttpMethod.Post, "/api/chat/ask/stream")
            {
                Content = JsonContent.Create(request)
            };

            HttpResponseMessage pythonResponse;
            try
            {
                pythonResponse = await client.SendAsync(
                    pythonRequest, HttpCompletionOption.ResponseHeadersRead, httpContext.RequestAborted);
            }
            catch (Exception ex)
            {
                logger.LogError(ex, "Failed to reach python paper-chat stream endpoint.");
                httpContext.Response.StatusCode = StatusCodes.Status502BadGateway;
                await httpContext.Response.WriteAsync(ex.Message);
                return;
            }

            using (pythonResponse)
            {
                if (!pythonResponse.IsSuccessStatusCode)
                {
                    var error = await pythonResponse.Content.ReadAsStringAsync();
                    logger.LogError($"Python paper-chat stream error: {error}");
                    httpContext.Response.StatusCode = (int)pythonResponse.StatusCode;
                    await httpContext.Response.WriteAsync(error);
                    return;
                }

                httpContext.Response.ContentType = "text/event-stream";
                httpContext.Response.Headers["Cache-Control"] = "no-cache";
                httpContext.Response.Headers["Connection"] = "keep-alive";
                httpContext.Response.Headers["X-Accel-Buffering"] = "no";

                await using var stream = await pythonResponse.Content.ReadAsStreamAsync(httpContext.RequestAborted);
                var buffer = new byte[4096];
                int bytesRead;
                while ((bytesRead = await stream.ReadAsync(buffer, httpContext.RequestAborted)) > 0)
                {
                    await httpContext.Response.Body.WriteAsync(buffer.AsMemory(0, bytesRead), httpContext.RequestAborted);
                    await httpContext.Response.Body.FlushAsync(httpContext.RequestAborted);
                }
            }
        })
        .WithName("AskPaperChatStream")
        .DisableAntiforgery();

      app.MapGet("/api/chat/{chatId}/history", async(string chatId,IHttpClientFactory httpClientFactory, ILogger<ChatRequest> logger )=>
        {
          try
          {
            var client =  httpClientFactory.CreateClient("pythonapi");
            var result = await client.GetAsync($"/api/chat/{chatId}/history");

            if (!result.IsSuccessStatusCode)
            {
              var error =  await result.Content.ReadAsStringAsync();
               logger.LogError($"Problem getting history API error: {error}\n");
               return Results.Problem($"Problem getting history API error: {error}");
            }
            var history = await result.Content.ReadFromJsonAsync(typeof(object));
            return Results.Ok(history);
          }
          catch (Exception ex)
         { 
          return Results.InternalServerError(ex.Message); 
          }
        });
    }
    public static async Task AddToDatabase(ChatRequest request,PrismDBContext prismDBContext)
    {
       var existingRecord =  prismDBContext.PrismDocuments.FirstOrDefault(a=>a.ChatId==Guid.Parse(request.chatId));
       if (existingRecord!=null)
       {
        existingRecord.Status = "In progress";
       }
       else
       {
        var entry = new PrismDocument{
            UserId = request.userId,
            ChatTitle = $"Chat: {request.question}",
            CreatedAt = DateTime.UtcNow,
            Status = "In progress",
            ChatId = Guid.Parse(request.chatId)
            ,UploadedAt =DateTime.UtcNow
        };

        prismDBContext.PrismDocuments.Add(entry);
       }
       await prismDBContext.SaveChangesAsync();
    }
    
}
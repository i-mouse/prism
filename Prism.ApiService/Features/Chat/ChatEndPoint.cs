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
       var existingRecord =  prismDBContext.prismDocuments.FirstOrDefault(a=>a.ChatId==request.chatId);
       if (existingRecord!=null)
       {
        existingRecord.Status = "In progress";
       }
       else
       {
        var entry = new PrismDocument{
            Id = Guid.NewGuid().ToString(),
            UserId = request.userId,
            ChatTitle = $"Chat: {request.question}",
            CreatedAt = DateTime.UtcNow,
            Status = "In progress",
            ChatId = request.chatId
            ,UploadedAt =DateTime.UtcNow
        };

        prismDBContext.prismDocuments.Add(entry);
       }
       await prismDBContext.SaveChangesAsync();
    }
    
}
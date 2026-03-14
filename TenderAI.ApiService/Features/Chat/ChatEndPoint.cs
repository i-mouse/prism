using TenderAI.ApiService.Data;
using TenderAI.ApiService.Services;
using MassTransit;
using TenderAI.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;

namespace TenderAI.ApiService.Features.Chat;

public static class ChatEndPoint
{

    public static void MapChatEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/chat", async ([FromBody] ChatRequest request, IHttpClientFactory httpClientFactory,ILogger<ChatRequest> logger) =>
        {

           try
           {
             var client = httpClientFactory.CreateClient("pythonapi");
 
             var result = await client.PostAsJsonAsync("/ask",request);
 
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
    }
}
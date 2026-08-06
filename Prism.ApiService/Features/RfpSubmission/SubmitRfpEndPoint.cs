using Prism.ApiService.Data;
using Prism.ApiService.Services;
using MassTransit;
using Prism.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;

namespace Prism.ApiService.Features.RfpSubmission;

public static class SubmitRfpEndpoint
{

    public static void MapRfpEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/rfp", async ([FromForm] SubmitRfpRequest request,PrismDBContext dBContext, IfileUploader fileUploader,IPublishEndpoint publishEndpoint,MinioStorageService storageService) =>
        {
            if (request == null || request.Files == null || request.Files.Count == 0)
            {
                return Results.BadRequest("Request is blank");
            }
            else if(String.IsNullOrEmpty(request.ConnectionId))
            {
                 return Results.BadRequest("ConnectionId is blank. Please reconnect your signalR.");
            }
            var result = new
            {
              Message = "RFP Received",
              UserId = request.UserId  
            };
             foreach (var file in request.Files)
             {
                var fileId = Guid.NewGuid();
                var stream = file.OpenReadStream();
                await storageService.UploadFileAsync(stream,file.FileName,file.ContentType);
                await AddToDatabase(fileId,file, request.ChatId, request.UserId, dBContext);
                var contract = new PrismUploaded(fileId.ToString(),request.UserId,file.FileName,request.ConnectionId,request.ChatId);
                await publishEndpoint.Publish(contract);
         
             }
         

            return Results.Ok(result);

        }  ).WithName("SubmitRfp") .DisableAntiforgery();


    }

    public static void MapChatHistoryEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/chats/{userId}", async (string userId, PrismDBContext dbContext) =>
        {
            var userChats = await dbContext.PrismDocuments
                .Where(doc => doc.UserId == userId)
                .Select(doc => new 
                {
                    ChatId = doc.ChatId,
                    ChatTitle= doc.ChatTitle,
                    Status = doc.Status,
                    UploadedAt = doc.UploadedAt
                })
                .OrderByDescending(doc => doc.UploadedAt)
                .ToListAsync();

            if (userChats == null || userChats.Count == 0)
            {
                return Results.Ok(new List<object>());
            }

            return Results.Ok(userChats);
        })
        .WithName("GetUserChats");

        // Backfill endpoint: lets the client recover file summaries it may have
        // missed via SignalR (closed tab, dropped connection, page never open).
        app.MapGet("/api/chats/{chatId}/files", async (string chatId, PrismDBContext dbContext) =>
        {
            if (!Guid.TryParse(chatId, out var chatGuid))
            {
                return Results.BadRequest("Invalid chatId");
            }

            var files = await dbContext.FileRecords
                .Where(f => f.ChatId == chatGuid)
                .OrderBy(f => f.UploadedAt)
                .Select(f => new
                {
                    FileId = f.FileId,
                    FileName = f.FileName,
                    Summary = f.Summary,
                    UploadedAt = f.UploadedAt,
                    Status = f.Summary != null ? "Completed" : "In progress"
                })
                .ToListAsync();

            return Results.Ok(files);
        })
        .WithName("GetChatFiles");
    }

    public static async Task AddToDatabase(Guid fileId, IFormFile file, string chatId, string userId, PrismDBContext prismDBContext)
    {
        var chatGuid = Guid.Parse(chatId);

        var existingRecord = await prismDBContext.PrismDocuments
            .FirstOrDefaultAsync(a => a.ChatId == chatGuid);

        if (existingRecord == null)
        {
            prismDBContext.PrismDocuments.Add(new PrismDocument
            {
                UserId = userId,
                ChatTitle = $"Chat: {file.FileName}",
                UploadedAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                Status = "In progress",
                ChatId = chatGuid
            });
        }
        else
        {
            existingRecord.UploadedAt = DateTime.UtcNow;
            existingRecord.Status = "In progress";
        }

        prismDBContext.FileRecords.Add(new FileRecord
        {
            FileId = fileId,
            FileName = file.FileName,
            UploadedAt = DateTime.UtcNow,
            ChatId = chatGuid
        });

        await prismDBContext.SaveChangesAsync();
    }
}
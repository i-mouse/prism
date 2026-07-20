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
                var fileId = Guid.NewGuid().ToString();
                var stream = file.OpenReadStream();
                await storageService.UploadFileAsync(stream,file.FileName,file.ContentType);
                await AddToDatabase(fileId,file, request.ChatId, request.UserId, dBContext);
                var contract = new PrismUploaded(fileId,request.UserId,file.FileName,request.ConnectionId,request.ChatId);
                await publishEndpoint.Publish(contract);
         
             }
         

            return Results.Ok(result);

        }  ).WithName("SubmitRfp") .DisableAntiforgery();


    }

    public static void MapChatHistoryEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/chats/{userId}", async (string userId, PrismDBContext dbContext) =>
        {
            var userChats = await dbContext.prismDocuments
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
    }

    public static async Task AddToDatabase2(string fileId,IFormFile file,string chatId,string userId, PrismDBContext prismDBContext)
    {
       var existingRecord = await prismDBContext.prismDocuments.FirstOrDefaultAsync(a=>a.ChatId==chatId);
       if (existingRecord!=null)
       {
         
            existingRecord.UploadedAt = DateTime.UtcNow;
            existingRecord.Status = "In progress";
       }
       else
       {
            var prismEntry = new PrismDocument{
                Id = Guid.NewGuid().ToString(),
                UserId = userId,
                ChatTitle = $"Chat: {file.FileName}",
                UploadedAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                Status = "In progress",
                ChatId = chatId
            };

            prismDBContext.prismDocuments.Add(prismEntry);
            await prismDBContext.SaveChangesAsync();
        }
            var recordEntry = new FileRecords{
                FileName = file.FileName,
                UploadedAt = DateTime.UtcNow,
                ChatId = chatId,
                FileId =fileId
            };
        prismDBContext.fileRecords.Add(recordEntry);
        await prismDBContext.SaveChangesAsync();
    }
    public static async Task AddToDatabase(string fileId, IFormFile file, string chatId, string userId, PrismDBContext prismDBContext)
    {
       // 1. Grab the parent chat
       var existingRecord = await prismDBContext.prismDocuments.FirstOrDefaultAsync(a => a.ChatId == chatId);
       
       if (existingRecord == null)
       {
           existingRecord = new PrismDocument{
               Id = Guid.NewGuid().ToString(),
               UserId = userId,
               ChatTitle = $"Chat: {file.FileName}",
               UploadedAt = DateTime.UtcNow,
               CreatedAt = DateTime.UtcNow,
               Status = "In progress",
               ChatId = chatId
           };

           prismDBContext.prismDocuments.Add(existingRecord);
           await prismDBContext.SaveChangesAsync();
       }
       else
       {
           existingRecord.UploadedAt = DateTime.UtcNow; 
           existingRecord.Status = "In progress";
       }
       
       var fileEntry = new FileRecords {
           FileName = file.FileName,
           UploadedAt = DateTime.UtcNow,
           ChatId = chatId,
           FileId = fileId
       };
       
       // THE FIX: Attach it directly to the Parent Entity!
       // This guarantees Entity Framework understands the relationship perfectly.
       if (existingRecord.Files == null) existingRecord.Files = new List<FileRecords>();
       existingRecord.Files.Add(fileEntry);

       await prismDBContext.SaveChangesAsync();
    }
}
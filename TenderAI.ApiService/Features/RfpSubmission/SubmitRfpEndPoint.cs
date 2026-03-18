using TenderAI.ApiService.Data;
using TenderAI.ApiService.Services;
using MassTransit;
using TenderAI.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;

namespace TenderAI.ApiService.Features.RfpSubmission;

public static class SubmitRfpEndpoint
{

    public static void MapRfpEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/rfp", async ([FromForm] SubmitRfpRequest request,TenderDBContext dBContext, IfileUploader fileUploader,IPublishEndpoint publishEndpoint,MinioStorageService storageService) =>
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
                var contract = new TenderUploaded(fileId,request.UserId,file.FileName,request.ConnectionId,request.ChatId);
                await publishEndpoint.Publish(contract);
         
             }
         

            return Results.Ok(result);

        }  ).WithName("SubmitRfp") .DisableAntiforgery();


    }

    public static void MapChatHistoryEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/chats/{userId}", async (string userId, TenderDBContext dbContext) =>
        {
            var userChats = await dbContext.tenderDocuments
                .Where(doc => doc.UserId == userId)
                .Select(doc => new 
                {
                    ChatId = doc.ChatId,
                    ChatTitle= doc.ChatTitle,
                    FileName = doc.FileName,
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

    public static async Task AddToDatabase2(string fileId,IFormFile file,string chatId,string userId, TenderDBContext tenderDBContext)
    {
       var existingRecord = await tenderDBContext.tenderDocuments.FirstOrDefaultAsync(a=>a.ChatId==chatId);
       if (existingRecord!=null)
       {
         
            existingRecord.UploadedAt = DateTime.UtcNow;
            existingRecord.Status = "In progress";
       }
       else
       {
            var tenderEntry = new TenderDocument{
                Id = Guid.NewGuid().ToString(),
                UserId = userId,
                FileName =file.FileName,
                ChatTitle = $"Chat: {file.FileName}",
                UploadedAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                Status = "In progress",
                ChatId = chatId
            };

            tenderDBContext.tenderDocuments.Add(tenderEntry);
            await tenderDBContext.SaveChangesAsync();
        }
            var recordEntry = new FileRecords{
                FileName = file.FileName,
                UploadedAt = DateTime.UtcNow,
                ChatId = chatId,
                FileId =fileId
            };
        tenderDBContext.fileRecords.Add(recordEntry);
        await tenderDBContext.SaveChangesAsync();
    }
    public static async Task AddToDatabase(string fileId, IFormFile file, string chatId, string userId, TenderDBContext tenderDBContext)
    {
       // 1. Grab the parent chat
       var existingRecord = await tenderDBContext.tenderDocuments.FirstOrDefaultAsync(a => a.ChatId == chatId);
       
       if (existingRecord == null)
       {
           // 2. If it doesn't exist, create it and SAVE it immediately
           existingRecord = new TenderDocument{
               Id = Guid.NewGuid().ToString(),
               UserId = userId,
               FileName = file.FileName, // Can act as the primary file name
               ChatTitle = $"Chat: {file.FileName}",
               UploadedAt = DateTime.UtcNow,
               CreatedAt = DateTime.UtcNow,
               Status = "In progress",
               ChatId = chatId
           };

           tenderDBContext.tenderDocuments.Add(existingRecord);
           await tenderDBContext.SaveChangesAsync(); // FORCE the parent to exist in PostgreSQL
       }
       else
       {
           // Just update the timestamp if it already existed
           existingRecord.UploadedAt = DateTime.UtcNow; 
           existingRecord.Status = "In progress";
       }
       
       // 3. Create the file record
       var fileEntry = new FileRecords {
           FileName = file.FileName,
           UploadedAt = DateTime.UtcNow,
           ChatId = chatId, // Link it by ID
           FileId = fileId
       };
       
       // 4. 🔥 THE FIX: Attach it directly to the Parent Entity!
       // This guarantees Entity Framework understands the relationship perfectly.
       if (existingRecord.Files == null) existingRecord.Files = new List<FileRecords>();
       existingRecord.Files.Add(fileEntry);

       // 5. Final Save
       await tenderDBContext.SaveChangesAsync();
    }
}
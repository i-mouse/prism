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
            if(request==null)
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
              File = request.File.Name,
              UserId = request.UserId  
            };
             request.FileId = Guid.NewGuid().ToString();
            var stream = request.File.OpenReadStream();
            await storageService.UploadFileAsync(stream,request.File.FileName,request.File.ContentType);

           await AddToDatabase(request,dBContext);
            var contract = new TenderUploaded(request.FileId,request.UserId,request.File.FileName,request.ConnectionId,request.ChatId);
            await publishEndpoint.Publish(contract);
         

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

    public static async Task AddToDatabase(SubmitRfpRequest request,TenderDBContext tenderDBContext)
    {
       var existingRecord =  tenderDBContext.tenderDocuments.FirstOrDefault(a=>a.ChatId==request.ChatId);
       if (existingRecord!=null)
       {
          var entry = new FileRecords{
            FileName = request.File.FileName,
            UploadedAt = DateTime.UtcNow,
            ChatId = request.ChatId,
            FileId = request.FileId!
        };
        existingRecord.UploadedAt = DateTime.Now;
        existingRecord.Status = "In progress";

        tenderDBContext.fileRecords.Add(entry);
       }
       else
       {
        var entry = new TenderDocument{
            Id = Guid.NewGuid().ToString(),
            UserId = request.UserId,
            FileName = request.File.FileName,
            ChatTitle = $"Chat: {request.File.FileName}",
            UploadedAt = DateTime.UtcNow,
            CreatedAt = DateTime.UtcNow,
            Status = "In progress",
            ChatId = request.ChatId
        };

        tenderDBContext.tenderDocuments.Add(entry);
       }
       await tenderDBContext.SaveChangesAsync();
    }
}
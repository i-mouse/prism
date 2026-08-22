using Prism.ApiService.Data;
using Prism.ApiService.Data.Schemas;
using Prism.ApiService.Services;
using MassTransit;
using Prism.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Data.Converters;

namespace Prism.ApiService.Features.PaperSubmission;

public static class SubmitPaperEndpoint
{

    public static void MapPaperEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/papers", async ([FromForm] SubmitPaperRequest request,PrismDBContext dBContext, IfileUploader fileUploader,IPublishEndpoint publishEndpoint,MinioStorageService storageService) =>
        {
            if (request == null || request.Files == null || request.Files.Count == 0)
            {
                return Results.BadRequest("Request is blank");
            }
            else if(String.IsNullOrEmpty(request.ConnectionId))
            {
                 return Results.BadRequest("ConnectionId is blank. Please reconnect your signalR.");
            }
            else if (request.Files.Count != 1)
            {
                return Results.BadRequest("Prism audits one paper at a time. Upload a single PDF.");
            }
            var result = new
            {
              Message = "Paper received",
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

        }  ).WithName("SubmitPaper") .DisableAntiforgery();

        app.MapGet("/api/papers/{paperId}/claims", async (Guid paperId, PrismDBContext dbContext) =>
        {
            var file = await dbContext.FileRecords
                .Where(f => f.FileId == paperId)
                .Select(f => new { f.FileId, f.FileName, f.Summary })
                .FirstOrDefaultAsync();

            if (file == null)
            {
                return Results.NotFound();
            }
            var labelConverter = new ClaimLabelConverter();
            var statusConverter = new GroundingStatusConverter();
            
            var extractor = await dbContext.DocumentExtractors
                .Where(e => e.FileId == paperId)
                .OrderByDescending(e => e.CreatedAt)
                .FirstOrDefaultAsync();

            if (extractor == null)
            {
                return Results.Ok(new PaperClaimsResponse(
                    file.FileId,
                    file.FileName,
                    "Pending",
                    null,
                    new ClaimsSummary(0, 0, 0, 0),
                    new List<ClaimDto>()));
            }

            var claims = await dbContext.PaperClaims
                .Where(c => c.DocumentExtractorId == extractor.Id)
                .OrderBy(c => c.Position)
                .AsNoTracking()
                .ToListAsync();

            var claimDtos = claims
            .Select(c => new ClaimDto(
                c.Id,
                c.ClaimTextVerbatim,
                c.ClaimSummary,
                labelConverter.ConvertToProvider(c.Label) as string ?? "",
                c.Missing,
                c.Reason,
                statusConverter.ConvertToProvider(c.GroundingStatus) as string ?? "",
                c.Position,
                c.EvidenceSpans
                    .Select(s => new EvidenceSpanDto(
                        s.SourceText,
                        s.SourceSection,
                        s.SectionHeader,
                        s.PageNumber,
                        statusConverter.ConvertToProvider(s.GroundingStatus) as string ?? ""))
                    .ToList()))
            .ToList();

            var summary = new ClaimsSummary(
                claims.Count,
                claims.Count(c => c.Label == ClaimLabel.Supported),
                claims.Count(c => c.Label == ClaimLabel.PartiallySupported),
                claims.Count(c => c.Label == ClaimLabel.NotSupported));

            return Results.Ok(new PaperClaimsResponse(
                file.FileId,
                file.FileName,
                file.Summary != null ? "Completed" : "In progress",
                extractor.CreatedAt,
                summary,
                claimDtos));
        })
        .WithName("GetPaperClaims");

    }

    public static void MapChatHistoryEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/chats/{userId}", async (string userId, PrismDBContext dbContext) =>
        {
            var userChats = await dbContext.PrismDocuments
                .Where(doc => doc.UserId == userId)
                .Where(doc => dbContext.FileRecords.Any(f => f.ChatId == doc.ChatId))
                .Select(doc => new
                {
                    ChatId = doc.ChatId,
                    File = dbContext.FileRecords
                        .Where(f => f.ChatId == doc.ChatId)
                        .OrderByDescending(f => f.UploadedAt)
                        .First(),
                    UploadedAt = doc.UploadedAt
                })
                .Select(x => new
                {
                    ChatId = x.ChatId,
                    FileName = x.File.FileName,
                    ExtractionStatus = x.File.Summary != null ? "Completed" : "In progress",
                    UploadedAt = x.UploadedAt
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
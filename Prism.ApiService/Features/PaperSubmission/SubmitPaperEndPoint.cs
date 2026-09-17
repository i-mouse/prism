using Prism.ApiService.Data;
using Prism.ApiService.Data.Schemas;
using Prism.ApiService.Services;
using MassTransit;
using Prism.ApiService.Contracts;
using Prism.ApiService.Middleware;
using Prism.ApiService.Telemetry;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Data.Converters;
using Prism.ApiService.Features.Auth;
using Prism.ApiService.Hubs;
using Microsoft.AspNetCore.SignalR;
using System.Security.Cryptography;
using System.Text.Json;
using Prism.ApiService.Extensions;

namespace Prism.ApiService.Features.PaperSubmission;

public static class SubmitPaperEndpoint
{

    public static void MapPaperEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/papers", async (HttpContext httpContext, [FromForm] SubmitPaperRequest request,PrismDBContext dBContext, IfileUploader fileUploader,IPublishEndpoint publishEndpoint,AzureBlobStorageService storageService, IHubContext<DocumentHub, IDocumentClient> hubContext, IHttpClientFactory httpClientFactory, CancellationToken ct) =>
        {
            // Resolve user identity: JWT sub claim (Google) or HttpOnly guest-session cookie.
            // Never trust a UserId from the request body — that was the previous insecure pattern.
            var userId = GuestAuthEndpoints.ResolveUserId(httpContext);
            if (string.IsNullOrEmpty(userId))
            {
                return Results.Unauthorized();
            }

            if (request == null || request.Files == null || request.Files.Count == 0)
            {
                return Results.Problem(detail: "Request is blank", statusCode: StatusCodes.Status400BadRequest);
            }
            else if(String.IsNullOrEmpty(request.ConnectionId))
            {
                 return Results.Problem(detail: "ConnectionId is blank. Please reconnect your signalR.", statusCode: StatusCodes.Status400BadRequest);
            }
            else if (request.Files.Count != 1)
            {
                return Results.Problem(detail: "Prism audits one paper at a time. Upload a single PDF.", statusCode: StatusCodes.Status400BadRequest);
            }

            // Guests (no validated JWT) are capped at 2 papers per cookie-session -
            // Google-authenticated users are never capped. Counted via distinct
            // ChatFiles.FileId across every chat this guest owns, so a dedupe hit
            // (linking to an already-existing file) still counts toward the cap.
            var isGuest = httpContext.User.Identity?.IsAuthenticated != true;
            if (isGuest)
            {
                var guestFileCount = await (
                    from cf in dBContext.ChatFiles
                    join d in dBContext.PrismDocuments on cf.ChatId equals d.ChatId
                    where d.UserId == userId
                    select cf.FileId
                ).CountAsync(ct);

                if (guestFileCount >= 2)
                {
                    return Results.Problem(
                        detail: "Guest limit reached. Sign in to upload more than 2 papers.",
                        statusCode: StatusCodes.Status403Forbidden);
                }
            }

            var correlationId = httpContext.GetCorrelationId();
            var isCacheHit = false;
             foreach (var file in request.Files)
             {
                if (file.Length > 20_000_000)
                {
                    return Results.Problem(statusCode: 413, detail: "File exceeds 20MB limit");
                }

                using var activity = PrismTelemetry.ActivitySource.StartActivity("paper.upload");
                activity?.SetTag("file.name", file.FileName);
                activity?.SetTag("chat.id", request.ChatId);
                activity?.SetTag("correlation.id", correlationId);

                // Hash the content BEFORE any blob upload or pipeline work — an
                // already-audited paper (by content, not just by name) is recognized
                // here regardless of who uploaded it originally or which session
                // this is, and the expensive blob upload + pipeline is skipped
                // entirely below when it matches.
                string contentHash;
                using (var hashStream = file.OpenReadStream())
                {
                    contentHash = Convert.ToHexStringLower(await SHA256.HashDataAsync(hashStream, ct));
                }

                var existingFile = await dBContext.FileRecords
                    .OrderByDescending(f => f.UploadedAt)
                    .FirstOrDefaultAsync(f => f.ContentHash == contentHash, ct);

                if (existingFile != null)
                {
                    isCacheHit = existingFile.Status == Prism.ApiService.Data.Schemas.ExtractionStatus.Completed;
                    await HandleExistingFileAsync(existingFile, request, userId, dBContext, hubContext, httpClientFactory, publishEndpoint, storageService, file, correlationId, ct);
                    continue;
                }

                var fileId = Guid.NewGuid();

                await NotifyProgress(hubContext, fileId, request.ChatId, "preparing",
                    "Checking if we've seen this paper before...");
                await NotifyProgress(hubContext, fileId, request.ChatId, "preparing",
                    "New paper — starting audit");

                var stream = file.OpenReadStream();
                await storageService.UploadFileAsync(stream,file.FileName,file.ContentType,ct);
                
                try
                {
                    await AddToDatabase(fileId,file, request.ChatId, userId, contentHash, dBContext, ct);
                }
                catch (DbUpdateException)
                {
                    // A concurrent upload beat us to the database insert and claimed this
                    // ContentHash. Re-fetch whichever row won and hand it to the exact
                    // same existing-file dispatch every other cache-hit/join/retry case
                    // goes through — there is no separate "race" code path left to drift
                    // from those (there used to be one; it's why this branch used to emit
                    // a different message than the ordinary Pending/InProgress join).
                    var winnerFile = await dBContext.FileRecords
                        .FirstOrDefaultAsync(f => f.ContentHash == contentHash, ct);

                    if (winnerFile == null)
                    {
                        throw;
                    }

                    await HandleExistingFileAsync(winnerFile, request, userId, dBContext, hubContext, httpClientFactory, publishEndpoint, storageService, file, correlationId, ct);
                    continue;
                }

                var contract = new PrismUploaded(fileId.ToString(),userId,file.FileName,request.ConnectionId,request.ChatId);
                await publishEndpoint.Publish(contract, Pipe.Execute<PublishContext<PrismUploaded>>(publishContext =>
                {
                    if (correlationId is not null)
                    {
                        publishContext.Headers.Set("x-correlation-id", correlationId);
                    }
                }), ct);

             }

            var result = new
            {
              Message = "Paper received",
              UserId = userId,
              IsCacheHit = isCacheHit
            };

            return Results.Ok(result);

        }  ).WithName("SubmitPaper") .DisableAntiforgery().AllowAnonymous();

        app.MapPost("/api/papers/{paperId}/rerun", async (Guid paperId, HttpContext httpContext, [FromBody] RerunPaperRequest request, PrismDBContext dbContext, IPublishEndpoint publishEndpoint, CancellationToken ct) =>
        {
            var userId = GuestAuthEndpoints.ResolveUserId(httpContext);
            if (string.IsNullOrEmpty(userId))
            {
                return Results.Unauthorized();
            }

            // Re-run is a Google-authenticated-only feature — guests never see the
            // option, and the server enforces that independently of the UI.
            if (httpContext.User.Identity?.IsAuthenticated != true)
            {
                return Results.Problem(detail: "Guests cannot trigger a re-run.", statusCode: StatusCodes.Status403Forbidden);
            }

            if (request == null || string.IsNullOrEmpty(request.ChatId) || string.IsNullOrEmpty(request.ConnectionId))
            {
                return Results.Problem(detail: "ChatId and ConnectionId are required.", statusCode: StatusCodes.Status400BadRequest);
            }

            var file = await dbContext.FileRecords
                .Where(f => f.FileId == paperId)
                .Select(f => new { f.FileId, f.FileName })
                .FirstOrDefaultAsync(ct);

            if (file == null)
            {
                return Results.NotFound();
            }

            var isOwner = await (
                from cf in dbContext.ChatFiles
                join d in dbContext.PrismDocuments on cf.ChatId equals d.ChatId
                where cf.FileId == paperId && d.UserId == userId
                select cf.FileId
            ).AnyAsync(ct);

            if (!isOwner)
            {
                return Results.Problem(detail: "You do not have access to this paper.", statusCode: StatusCodes.Status403Forbidden);
            }

            // Deliberately bypasses the content-hash dedupe check in the upload
            // endpoint above — re-run means "force a fresh pipeline run", so this
            // publishes straight to the pipeline unconditionally. write_extraction_result
            // (Python) always inserts a brand-new document_extractor/extraction_run
            // row, so the previous run's claims are never overwritten.
            var correlationId = httpContext.GetCorrelationId();
            var contract = new PrismUploaded(file.FileId.ToString(), userId, file.FileName, request.ConnectionId, request.ChatId);
            await publishEndpoint.Publish(contract, Pipe.Execute<PublishContext<PrismUploaded>>(publishContext =>
            {
                if (correlationId is not null)
                {
                    publishContext.Headers.Set("x-correlation-id", correlationId);
                }
            }), ct);

            return Results.Ok(new { Message = "Re-run started" });
        })
        .WithName("RerunPaper");

        app.MapGet("/api/papers/{paperId}/claims", async (Guid paperId, HttpContext httpContext, PrismDBContext dbContext, PromptVersionProvider promptVersionProvider, CancellationToken ct) =>
        {
            var userId = GuestAuthEndpoints.ResolveUserId(httpContext);
            if (string.IsNullOrEmpty(userId))
            {
                return Results.Unauthorized();
            }

            using var activity = PrismTelemetry.ActivitySource.StartActivity("paper.claims.read");
            activity?.SetTag("paper.id", paperId);

            var file = await dbContext.FileRecords
                .Where(f => f.FileId == paperId)
                .Select(f => new { f.FileId, f.FileName, f.Summary, f.Status })
                .FirstOrDefaultAsync(ct);

            if (file == null)
            {
                return Results.NotFound();
            }

            // A deduped file can be linked to many chats/users — ownership means
            // "does this user own at least one chat linked to this file", not a
            // single ChatId lookup like before.
            var isOwner = await (
                from cf in dbContext.ChatFiles
                join d in dbContext.PrismDocuments on cf.ChatId equals d.ChatId
                where cf.FileId == paperId && d.UserId == userId
                select cf.FileId
            ).AnyAsync(ct);

            if (!isOwner)
            {
                return Results.Problem(detail: "You do not have access to this paper.", statusCode: StatusCodes.Status403Forbidden);
            }
            var labelConverter = new ClaimLabelConverter();
            var statusConverter = new GroundingStatusConverter();

            var extractor = await dbContext.DocumentExtractors
                .Where(e => e.FileId == paperId)
                .OrderByDescending(e => e.CreatedAt)
                .FirstOrDefaultAsync(ct);

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
                .ToListAsync(ct);

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

            // Surfaces whether this extraction was produced by the prompts currently
            // in use, so the frontend can offer Google-authenticated users a "Re-run"
            // option on cache-hit results with an accurate expectation ("may improve
            // results" vs "will likely return the same result").
            string? storedPromptVersion = null;
            try
            {
                using var fieldsDoc = JsonDocument.Parse(extractor.Fields);
                if (fieldsDoc.RootElement.TryGetProperty("prompt_version", out var pv))
                {
                    storedPromptVersion = pv.GetString();
                }
            }
            catch (JsonException)
            {
                // Fields is malformed/legacy — leave storedPromptVersion null rather than fail the request.
            }

            bool? isCurrentPromptVersion = null;
            if (storedPromptVersion != null)
            {
                var currentPromptVersion = await promptVersionProvider.GetCurrentPromptVersionAsync(ct);
                isCurrentPromptVersion = currentPromptVersion != null && storedPromptVersion == currentPromptVersion;
            }

            return Results.Ok(new PaperClaimsResponse(
                file.FileId,
                file.FileName,
                file.Status.ToFrontendString(),
                extractor.CreatedAt,
                summary,
                claimDtos,
                storedPromptVersion,
                isCurrentPromptVersion));
        })
        .WithName("GetPaperClaims");

    }

    public static void MapChatHistoryEndpoints(this IEndpointRouteBuilder app)
    {
        // Route changed from /api/chats/{userId} to /api/chats to avoid exposing
        // the userId in the URL and to prevent cross-user data access. The userId
        // is now resolved server-side from the authenticated JWT or guest cookie.
        app.MapGet("/api/chats", async (HttpContext httpContext, PrismDBContext dbContext, CancellationToken ct) =>
        {
            var userId = GuestAuthEndpoints.ResolveUserId(httpContext);
            if (string.IsNullOrEmpty(userId))
            {
                return Results.Unauthorized();
            }

            var userChats = await dbContext.PrismDocuments
                .Where(doc => doc.UserId == userId)
                .Where(doc => dbContext.ChatFiles.Any(cf => cf.ChatId == doc.ChatId))
                .Select(doc => new
                {
                    ChatId = doc.ChatId,
                    File = dbContext.ChatFiles
                        .Where(cf => cf.ChatId == doc.ChatId)
                        .Join(dbContext.FileRecords, cf => cf.FileId, f => f.FileId, (cf, f) => f)
                        .OrderByDescending(f => f.UploadedAt)
                        .First(),
                    UploadedAt = doc.UploadedAt
                })
                .Select(x => new
                {
                    ChatId = x.ChatId,
                    FileName = x.File.FileName,
                    ExtractionStatus = x.File.Status.ToFrontendString(),
                    UploadedAt = x.UploadedAt
                })
                .OrderByDescending(doc => doc.UploadedAt)
                .ToListAsync(ct);

            if (userChats == null || userChats.Count == 0)
            {
                return Results.Ok(new List<object>());
            }

            return Results.Ok(userChats);
        })
        .WithName("GetUserChats")
        .AllowAnonymous();

        // Backfill endpoint: lets the client recover file summaries it may have
        // missed via SignalR (closed tab, dropped connection, page never open).
        app.MapGet("/api/chats/{chatId}/files", async (string chatId, HttpContext httpContext, PrismDBContext dbContext, CancellationToken ct) =>
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

            var files = await dbContext.ChatFiles
                .Where(cf => cf.ChatId == chatGuid)
                .Join(dbContext.FileRecords, cf => cf.FileId, f => f.FileId, (cf, f) => f)
                .OrderBy(f => f.UploadedAt)
                .Select(f => new
                {
                    FileId = f.FileId,
                    FileName = f.FileName,
                    Summary = f.Summary,
                    UploadedAt = f.UploadedAt,
                    Status = f.Status.ToFrontendString()
                })
                .ToListAsync(ct);

            return Results.Ok(files);
        })
        .WithName("GetChatFiles");
    }

    // Sends one ExtractionProgress SignalR event. PascalCase property names below
    // are intentional — the SignalR JSON hub protocol's default camelCase naming
    // policy converts them to the fileId/chatId/stage/detail shape the frontend's
    // ExtractionProgressEvent type expects, matching what the Python pipeline sends.
    private static Task NotifyProgress(
        IHubContext<DocumentHub, IDocumentClient> hubContext,
        Guid fileId,
        string chatId,
        string stage,
        string? detail = null)
    {
        return hubContext.Clients.Group($"chat-{chatId}").ExtractionProgress(new
        {
            FileId = fileId.ToString(),
            ChatId = chatId,
            Stage = stage,
            Detail = detail
        });
    }

    // Single dispatch for "this content-hash already has a FileRecord" —
    // covers every way that fact can be discovered: the initial lookup
    // finding one, or a concurrent upload losing the insert race and
    // re-querying the winner. All four ExtractionStatus values funnel
    // through here so there is exactly one place that links the chat,
    // joins/notifies over SignalR, and injects the chat summary — not four
    // near-copies (cache-hit / join-in-progress / failed-retry / race
    // recovery) that drift independently, which is what let the race-
    // recovery branch and the ordinary join branch emit different messages
    // for what is, from the client's point of view, the same event.
    private static async Task HandleExistingFileAsync(
        FileRecord existingFile,
        SubmitPaperRequest request,
        string userId,
        PrismDBContext dbContext,
        IHubContext<DocumentHub, IDocumentClient> hubContext,
        IHttpClientFactory httpClientFactory,
        IPublishEndpoint publishEndpoint,
        AzureBlobStorageService storageService,
        IFormFile file,
        string? correlationId,
        CancellationToken ct)
    {
        switch (existingFile.Status)
        {
            case Prism.ApiService.Data.Schemas.ExtractionStatus.Completed:
                await HandleCacheHitAsync(existingFile, request, userId, hubContext, httpClientFactory, dbContext, ct);
                return;

            case Prism.ApiService.Data.Schemas.ExtractionStatus.Pending:
            case Prism.ApiService.Data.Schemas.ExtractionStatus.InProgress:
                await LinkExistingFileToChatAsync(Guid.Parse(request.ChatId), existingFile.FileId, userId, existingFile.FileName, dbContext, ct);

                // Ordered by the owning chat's CreatedAt (write-once at chat
                // creation, never mutated elsewhere) so which chat's SignalR
                // group we join is deterministic — the original uploader's
                // chat, not whatever order Postgres happens to return once a
                // file is linked to 3+ chats.
                var originalChatId = await dbContext.ChatFiles
                    .Where(cf => cf.FileId == existingFile.FileId)
                    .Join(dbContext.PrismDocuments, cf => cf.ChatId, d => d.ChatId, (cf, d) => new { cf.ChatId, d.CreatedAt })
                    .OrderBy(x => x.CreatedAt)
                    .Select(x => x.ChatId)
                    .FirstOrDefaultAsync(ct);

                if (originalChatId != Guid.Empty)
                {
                    await hubContext.Groups.AddToGroupAsync(request.ConnectionId, $"chat-{originalChatId}");
                }

                // Every path that can discover an in-progress file lands
                // here — an ordinary join against a not-yet-finished run, or
                // a concurrent upload that lost the insert race — so it
                // always gets the same "you're joining, not starting"
                // feedback instead of sometimes being silent.
                await NotifyProgress(hubContext, existingFile.FileId, request.ChatId, "preparing",
                    "Joining an audit already in progress...");
                return;

            default: // Failed — reset for a fresh retry. Can't use a new FileId/
                     // FileRecord row here because ContentHash is a unique constraint.
                existingFile.Status = Prism.ApiService.Data.Schemas.ExtractionStatus.Pending;
                existingFile.Summary = null;
                existingFile.UploadedAt = DateTime.UtcNow;

                await LinkExistingFileToChatAsync(Guid.Parse(request.ChatId), existingFile.FileId, userId, existingFile.FileName, dbContext, ct);

                await NotifyProgress(hubContext, existingFile.FileId, request.ChatId, "preparing",
                    "Checking if we've seen this paper before...");
                await NotifyProgress(hubContext, existingFile.FileId, request.ChatId, "preparing",
                    "Previous audit failed — starting fresh extraction");

                var retryStream = file.OpenReadStream();
                await storageService.UploadFileAsync(retryStream, file.FileName, file.ContentType, ct);

                var retryContract = new PrismUploaded(existingFile.FileId.ToString(), userId, file.FileName, request.ConnectionId, request.ChatId);
                await publishEndpoint.Publish(retryContract, Pipe.Execute<PublishContext<PrismUploaded>>(publishContext =>
                {
                    if (correlationId is not null)
                    {
                        publishContext.Headers.Set("x-correlation-id", correlationId);
                    }
                }), ct);
                return;
        }
    }

    // Cache-hit path: the paper's content hash already matches a Completed
    // FileRecord, so the blob upload and the entire extraction pipeline are
    // skipped. Progress messaging stops after "Found it..." — the client
    // renders an inline decision (Continue/Re-run) instead of an automatic
    // finalizing/done sequence, and resumes the log itself once the user
    // chooses. The file is linked to the chat here regardless of that later
    // choice, so the paper is never left in an ambiguous state if the user
    // never returns to decide (see IsCacheHit response field / frontend).
    // The link is written and committed before any SignalR message goes
    // out — the client is already listening on this chat's group by the
    // time this runs, so a message referencing this FileId must never be
    // able to arrive before the ownership link that makes /claims work.
    private static async Task HandleCacheHitAsync(
        FileRecord existingFile,
        SubmitPaperRequest request,
        string userId,
        IHubContext<DocumentHub, IDocumentClient> hubContext,
        IHttpClientFactory httpClientFactory,
        PrismDBContext dbContext,
        CancellationToken ct)
    {
        if (!Guid.TryParse(request.ChatId, out var chatGuid))
        {
            return;
        }

        var auditedAt = await dbContext.DocumentExtractors
            .Where(e => e.FileId == existingFile.FileId)
            .OrderByDescending(e => e.CreatedAt)
            .Select(e => (DateTime?)e.CreatedAt)
            .FirstOrDefaultAsync(ct) ?? existingFile.UploadedAt;

        // The ownership link must be committed before the client can hear
        // about this FileId at all — the client is already listening on this
        // chat's SignalR group (joined before the upload POST was even
        // sent), so any NotifyProgress call issued before this write commits
        // is a real race: the client can react to a message referencing a
        // FileId that /claims will still 403 on, since ownership isn't
        // linked yet. Every message below must come after this line, not
        // just the first one.
        var isNewLink = await LinkExistingFileToChatAsync(chatGuid, existingFile.FileId, userId, existingFile.FileName, dbContext, ct);

        await NotifyProgress(hubContext, existingFile.FileId, request.ChatId, "preparing",
            "Checking if we've seen this paper before...");

        await NotifyProgress(hubContext, existingFile.FileId, request.ChatId, "preparing",
            $"Found it — already audited on {auditedAt:MMM d, yyyy}");

        // A cache hit skips the pipeline entirely, so nothing would otherwise
        // inject the "processing completed" summary turn a fresh extraction's
        // own chat_id gets automatically (Prism.PythonService/main.py). Every
        // chat that reaches a Completed file should get that same summary
        // turn in its own conversation — see the RabbitMqListenerService
        // side for the equivalent injection when a *joined* (Pending/
        // InProgress) chat's shared run finishes instead. Only on a genuinely
        // new link, though — a repeat cache hit against a chat that already
        // owns this file (double-submit, retried request) must not inject a
        // second copy of the same summary turn.
        if (isNewLink)
        {
            await ChatSummaryInjector.InjectAsync(httpClientFactory, request.ChatId, existingFile.Summary, ct);
        }

        await hubContext.Clients.Group($"chat-{request.ChatId}").DocumentProcessed(new
        {
            FileId = existingFile.FileId.ToString(),
            FileName = existingFile.FileName,
            ConnectionId = request.ConnectionId,
            ChatId = request.ChatId,
            Status = "Completed",
            Summary = existingFile.Summary
        });
    }

    // Returns true when this call created a new ChatFile link (this chat had
    // never been linked to this file before), false when the link already
    // existed — callers that only want to act once per chat+file pair (see
    // HandleCacheHitAsync's summary injection) key off this instead of
    // re-deriving the same AnyAsync check themselves.
    private static async Task<bool> LinkExistingFileToChatAsync(
        Guid chatId,
        Guid fileId,
        string userId,
        string fileName,
        PrismDBContext prismDBContext,
        CancellationToken ct)
    {
        var existingChat = await prismDBContext.PrismDocuments
            .FirstOrDefaultAsync(a => a.ChatId == chatId, ct);

        if (existingChat == null)
        {
            prismDBContext.PrismDocuments.Add(new PrismDocument
            {
                UserId = userId,
                ChatTitle = $"Chat: {fileName}",
                UploadedAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                ChatId = chatId
            });
        }
        else
        {
            existingChat.UploadedAt = DateTime.UtcNow;
        }

        var alreadyLinked = await prismDBContext.ChatFiles.AnyAsync(cf => cf.ChatId == chatId && cf.FileId == fileId, ct);
        if (!alreadyLinked)
        {
            prismDBContext.ChatFiles.Add(new ChatFile { ChatId = chatId, FileId = fileId });
        }

        await prismDBContext.SaveChangesAsync(ct);
        return !alreadyLinked;
    }

    public static async Task AddToDatabase(Guid fileId, IFormFile file, string chatId, string userId, string contentHash, PrismDBContext prismDBContext, CancellationToken ct)
    {
        var chatGuid = Guid.Parse(chatId);

        var existingRecord = await prismDBContext.PrismDocuments
            .FirstOrDefaultAsync(a => a.ChatId == chatGuid, ct);

        if (existingRecord == null)
        {
            prismDBContext.PrismDocuments.Add(new PrismDocument
            {
                UserId = userId,
                ChatTitle = $"Chat: {file.FileName}",
                UploadedAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                ChatId = chatGuid
            });
        }
        else
        {
            existingRecord.UploadedAt = DateTime.UtcNow;
        }

        // ContentHash is written only once the blob upload above has already
        // succeeded (the caller only reaches AddToDatabase after that call
        // returns without throwing), so a failed upload never leaves a dangling
        // hash that would falsely dedupe a later, successful upload of the same content.
        prismDBContext.FileRecords.Add(new FileRecord
        {
            FileId = fileId,
            FileName = file.FileName,
            UploadedAt = DateTime.UtcNow,
            ContentHash = contentHash,
            Status = Prism.ApiService.Data.Schemas.ExtractionStatus.InProgress
        });

        prismDBContext.ChatFiles.Add(new ChatFile { ChatId = chatGuid, FileId = fileId });

        await prismDBContext.SaveChangesAsync(ct);
    }
}

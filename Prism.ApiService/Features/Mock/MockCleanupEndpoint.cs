using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Data;

namespace Prism.ApiService.Features.Mock;

public static class MockCleanupEndpoint
{
    public static void MapMockEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapGet("/api/mock/status", async (IConfiguration configuration, PrismDBContext dbContext, CancellationToken ct) =>
        {
            var isMockEnabled = configuration.GetValue<bool>("PRISM_MOCK_EXTRACTION", false);
            
            var mockFileIds = await dbContext.Database
                .SqlQuery<Guid>($"SELECT DISTINCT file_id AS \"Value\" FROM document_extractors WHERE fields->>'model_used' = 'MOCK_MODE'")
                .ToListAsync(ct);

            var mockFileCount = mockFileIds.Count;
            var mockChatFileCount = mockFileIds.Count > 0 
                ? await dbContext.ChatFiles.CountAsync(cf => mockFileIds.Contains(cf.FileId), ct)
                : 0;

            return Results.Ok(new { enabled = isMockEnabled, mockFileCount, mockChatFileCount });
        }).WithName("GetMockStatus").AllowAnonymous();

        app.MapPost("/api/mock/cleanup", async (IConfiguration configuration, IWebHostEnvironment env, PrismDBContext dbContext, CancellationToken ct) =>
        {
            var isMockEnabled = configuration.GetValue<bool>("PRISM_MOCK_EXTRACTION", false);
            var isProd = env.EnvironmentName.Equals("Production", StringComparison.OrdinalIgnoreCase) || 
                         (configuration["ASPIRE_ENVIRONMENT"]?.Equals("Production", StringComparison.OrdinalIgnoreCase) == true);

            if (!isMockEnabled || isProd)
            {
                return Results.Problem(detail: "Mock cleanup is disabled or running in production.", statusCode: StatusCodes.Status403Forbidden);
            }

            var mockFileIds = await dbContext.Database
                .SqlQuery<Guid>($"SELECT DISTINCT file_id AS \"Value\" FROM document_extractors WHERE fields->>'model_used' = 'MOCK_MODE'")
                .ToListAsync(ct);

            if (mockFileIds.Count == 0)
            {
                return Results.Ok(new
                {
                    deletedChats = 0,
                    deletedChatFiles = 0,
                    deletedClaims = 0,
                    deletedExtractors = 0,
                    deletedFiles = 0
                });
            }

            var strategy = dbContext.Database.CreateExecutionStrategy();
            return await strategy.ExecuteAsync(async () =>
            {
                using var transaction = await dbContext.Database.BeginTransactionAsync(ct);

                try
                {
                    // 1. Delete ChatFiles
                    var deletedChatFiles = await dbContext.ChatFiles
                        .Where(cf => mockFileIds.Contains(cf.FileId))
                        .ExecuteDeleteAsync(ct);

                    // 2. Delete PaperClaims
                    // PaperClaims has DocumentExtractorId, so we join or use subquery
                    var mockExtractorIds = await dbContext.DocumentExtractors
                        .Where(e => mockFileIds.Contains(e.FileId))
                        .Select(e => e.Id)
                        .ToListAsync(ct);

                    var deletedClaims = 0;
                    if (mockExtractorIds.Count > 0)
                    {
                        deletedClaims = await dbContext.PaperClaims
                            .Where(pc => mockExtractorIds.Contains(pc.DocumentExtractorId))
                            .ExecuteDeleteAsync(ct);
                    }

                    // 3. Delete DocumentExtractors
                    var deletedExtractors = await dbContext.DocumentExtractors
                        .Where(e => mockFileIds.Contains(e.FileId))
                        .ExecuteDeleteAsync(ct);

                    // 4. Delete FileRecords
                    var deletedFiles = await dbContext.FileRecords
                        .Where(f => mockFileIds.Contains(f.FileId))
                        .ExecuteDeleteAsync(ct);

                    // 5. Delete orphaned PrismDocuments
                    // A PrismDocument is orphaned if it has no associated ChatFiles
                    var deletedChats = await dbContext.PrismDocuments
                        .Where(doc => !dbContext.ChatFiles.Any(cf => cf.ChatId == doc.ChatId))
                        .ExecuteDeleteAsync(ct);

                    await transaction.CommitAsync(ct);

                    return Results.Ok(new
                    {
                        deletedChats,
                        deletedChatFiles,
                        deletedClaims,
                        deletedExtractors,
                        deletedFiles
                    });
                }
                catch (Exception)
                {
                    await transaction.RollbackAsync(ct);
                    throw;
                }
            });
        }).WithName("CleanupMockData").AllowAnonymous();
    }
}

using TenderAI.ApiService.Data;
using TenderAI.ApiService.Services;
using MassTransit;
using TenderAI.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Http.HttpResults;
using Microsoft.EntityFrameworkCore;

namespace TenderAI.ApiService.Features.RfpSubmission;

public static class SystemEndPoint
{
        public static void MapSystemEndPoint(this IEndpointRouteBuilder app)
        {
        app.MapDelete("/api/system/reset", async (TenderDBContext db,IHttpClientFactory httpClientFactory) => 
        {
            try 
            {
                await db.Database.ExecuteSqlRawAsync("TRUNCATE TABLE \"tenderDocuments\" CASCADE;");
                
                // 2. Command Python to wipe LangGraph and Qdrant
                var pythonClient = httpClientFactory.CreateClient("pythonapi");
                var pythonResponse = await pythonClient.DeleteAsync("/api/system/reset");
                
                if (!pythonResponse.IsSuccessStatusCode) {
                    return Results.Problem("C# DB wiped, but Python failed to wipe Qdrant/LangGraph.");
                }

                return Results.Ok(new { message = "Total system wipe successful." });
            } 
            catch (Exception ex) 
            {
                return Results.Problem(ex.Message);
            }
        });
    }
}
using TenderAI.ApiService.Data;
using TenderAI.ApiService.Services;

namespace TenderAI.ApiService.Features.RfpSubmission;

public static class SubmitRfpEndpoint
{

    public static void MapRfpEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/rfp", async (SubmitRfpRequest request,TenderDBContext dBContext, IfileUploader fileUploader) =>
        {
            var result = new
            {
              Message = "RFP Received",
              File = request.File.Name,
              UserId = request.UserId  
            };
           await fileUploader.UploadFileAsync(request.File);

            return Results.Ok(result);

        }  ).WithName("SubmitRfp") .DisableAntiforgery();
    }
}
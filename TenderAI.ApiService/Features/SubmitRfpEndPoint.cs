using TenderAI.ApiService.Data;
using TenderAI.ApiService.Services;
using MassTransit;
using TenderAI.ApiService.Contracts;
using Microsoft.AspNetCore.Mvc;

namespace TenderAI.ApiService.Features.RfpSubmission;

public static class SubmitRfpEndpoint
{

    public static void MapRfpEndPoint(this IEndpointRouteBuilder app)
    {
        app.MapPost("/rfp", async ([FromForm] SubmitRfpRequest request,TenderDBContext dBContext, IfileUploader fileUploader,IPublishEndpoint publishEndpoint) =>
        {
            var result = new
            {
              Message = "RFP Received",
              File = request.File.Name,
              UserId = request.UserId  
            };
            await fileUploader.UploadFileAsync(request.File);
            var contract = new TenderUploaded(Guid.NewGuid(),request.UserId,request.File.Name);
            await publishEndpoint.Publish(contract);
         

            return Results.Ok(result);

        }  ).WithName("SubmitRfp") .DisableAntiforgery();
    }
}
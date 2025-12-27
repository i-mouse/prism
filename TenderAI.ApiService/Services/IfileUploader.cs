namespace TenderAI.ApiService.Services;

public interface IfileUploader
{
    Task<string> UploadFileAsync(IFormFile file);
}
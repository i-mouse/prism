namespace Prism.ApiService.Services;

public interface IfileUploader
{
    Task<string> UploadFileAsync(IFormFile file);
}
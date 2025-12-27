namespace TenderAI.ApiService.Services;

public class FakeFileUploader : IfileUploader
{
 public   Task<string> UploadFileAsync(IFormFile file)
    {
        //Set delay
        //await Task.Delay(1000);

        Console.WriteLine($"[Fake upload] processed Name : {file.Name} \n Size : {file.Length}");

        return Task.FromResult(Guid.NewGuid().ToString());
    }

}
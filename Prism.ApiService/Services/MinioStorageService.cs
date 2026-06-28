using System.Reflection;
using Minio;
using Minio.DataModel.Args;
using Prism.ApiService.Services;

namespace Prism.ApiService.Services;
public class MinioStorageService(IMinioClient minioClient) 
{
  public async Task EnsureBucketExistAsync(string bucket = "prism-uploads" )
    {
        var args = new BucketExistsArgs().WithBucket(bucket);
        var found = await minioClient.BucketExistsAsync(args).ConfigureAwait(false);

        if(!found)
        {
            var makeArgs = new MakeBucketArgs().WithBucket(bucket);
            await minioClient.MakeBucketAsync(makeArgs).ConfigureAwait(false);
        }
    }

    public async Task<string> UploadFileAsync(Stream stream, string fileName,string contentType)
    {
        var args = new PutObjectArgs()
                    .WithBucket("prism-uploads")
                    .WithObject(fileName)
                    .WithStreamData(stream)
                    .WithObjectSize(stream.Length)
                    .WithContentType(contentType);

         await  minioClient.PutObjectAsync(args);         

        return fileName;
    } 
}

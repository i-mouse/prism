using Minio;
using Minio.DataModel.Args;

public class MinioStorageService(IMinioClient minioClient)
{
    public async Task EnsureBucketExistsAsync(string bucketName = "tender-uploads")
    {
        var args = new BucketExistsArgs().WithBucket(bucketName);
        bool found = await minioClient.BucketExistsAsync(args).ConfigureAwait(false);
        
        if (!found)
        {
            var makeArgs = new MakeBucketArgs().WithBucket(bucketName);
            await minioClient.MakeBucketAsync(makeArgs).ConfigureAwait(false);
            Console.WriteLine($"[Storage] Created bucket: {bucketName}");
        }
    }
}
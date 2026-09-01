using Azure.Storage.Blobs;
using Azure.Storage.Blobs.Models;

namespace Prism.ApiService.Services;

public class AzureBlobStorageService(BlobContainerClient containerClient)
{
    public async Task EnsureContainerExistsAsync(CancellationToken cancellationToken = default)
    {
        // Unlike MinIO/S3-style stores, Blob Storage doesn't auto-vivify a container on
        // first write - a PutBlob against a missing container returns 404 ContainerNotFound.
        await containerClient.CreateIfNotExistsAsync(cancellationToken: cancellationToken).ConfigureAwait(false);
    }

    public async Task<string> UploadFileAsync(Stream stream, string fileName, string contentType, CancellationToken cancellationToken = default)
    {
        var blobClient = containerClient.GetBlobClient(fileName);

        await blobClient.UploadAsync(
            stream,
            new BlobUploadOptions { HttpHeaders = new BlobHttpHeaders { ContentType = contentType } },
            cancellationToken).ConfigureAwait(false);

        return fileName;
    }
}

using System.ComponentModel.DataAnnotations;

namespace Prism.ApiService.Data;

public class PrismDocument
{
    public string UserId { get; set; } = string.Empty;
    public DateTime UploadedAt {get;set;} = DateTime.Now;
    public DateTime CreatedAt {get;set;} = DateTime.Now;
    public string Status {get;set;}= "Uploaded";
    public Guid ChatId {get;set;}
    public string ChatTitle {get;set;}= string.Empty;
}
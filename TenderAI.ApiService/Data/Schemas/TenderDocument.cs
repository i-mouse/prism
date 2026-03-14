using System.ComponentModel.DataAnnotations;

namespace TenderAI.ApiService.Data;

public class TenderDocument
{
   
    public string UserId { get; set; } = string.Empty;

    [Key]
    public string FileId {get;set;} = string.Empty;
    public string FileName {get;set;} = string.Empty;
    public string? Summary {get;set;} = string.Empty;
    public DateTime UploadedAt {get;set;} = DateTime.Now;
    public string Status {get;set;}= "Uploaded";
    public string ChatId {get;set;}= string.Empty;
    public string ChatTitle {get;set;}= string.Empty;

}
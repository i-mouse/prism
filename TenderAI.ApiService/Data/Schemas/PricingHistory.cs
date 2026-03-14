using System.ComponentModel.DataAnnotations;

namespace TenderAI.ApiService.Data;

public class PricingHistory
{
    [Key]
    public int Id {get;set;}
   
    public string Industry { get; set; } = string.Empty; 
    
    public decimal Price { get; set; } 
    
    public DateTime CompletedDate { get; set; }

}
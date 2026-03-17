using Microsoft.EntityFrameworkCore;

namespace TenderAI.ApiService.Data;

public class TenderDBContext : DbContext
{
    public TenderDBContext( DbContextOptions<TenderDBContext> options ) : base(options)
    {
        
    }

    public DbSet<TenderDocument> tenderDocuments    {get;set;}
    public DbSet<PricingHistory> pricingHistories {get;set;}
    public DbSet<FileRecords> fileRecords {get;set;}
}

using Microsoft.EntityFrameworkCore;

namespace Prism.ApiService.Data;

public class PrismDBContext : DbContext
{
    public PrismDBContext( DbContextOptions<PrismDBContext> options ) : base(options)
    {
        
    }

    public DbSet<PrismDocument> prismDocuments    {get;set;}
    public DbSet<PricingHistory> pricingHistories {get;set;}
    public DbSet<FileRecords> fileRecords {get;set;}
}

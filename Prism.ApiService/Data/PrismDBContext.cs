using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Data.Schemas;
namespace Prism.ApiService.Data;

public class PrismDBContext : DbContext
{
    public PrismDBContext( DbContextOptions<PrismDBContext> options ) : base(options)
    {
        
    }

    public DbSet<PrismDocument> prismDocuments    {get;set;}
    public DbSet<FileRecords> fileRecords {get;set;}
    public DbSet<Domain> Domains { get; set; }
    public DbSet<DocumentExtractor> DocumentExtractors { get; set; }


protected override void OnModelCreating(ModelBuilder modelBuilder)
{
    base.OnModelCreating(modelBuilder);

    modelBuilder.Entity<Domain>(entity =>
    {
        entity.ToTable("domains");
        entity.HasIndex(d => d.Name).IsUnique();
    });

    modelBuilder.Entity<DocumentExtractor>(entity =>
    {
        entity.ToTable("document_extractors");

        entity.HasOne(e => e.FileRecord)
            .WithMany()
            .HasForeignKey(e => e.FileId)
            .OnDelete(DeleteBehavior.Cascade);

        entity.HasOne(e => e.Domain)
            .WithMany(d => d.DocumentExtractors)
            .HasForeignKey(e => e.DomainId)
            .OnDelete(DeleteBehavior.Restrict);

        entity.HasIndex(e => e.FileId);
        entity.HasIndex(e => e.DomainId);
    });
}
}

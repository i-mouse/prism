using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Data.Schemas;

namespace Prism.ApiService.Data;

public class PrismDBContext : DbContext
{
    public PrismDBContext(DbContextOptions<PrismDBContext> options) : base(options) { }

    public DbSet<PrismDocument> PrismDocuments { get; set; }
    public DbSet<FileRecord> FileRecords { get; set; }
    public DbSet<Domain> Domains { get; set; }
    public DbSet<DocumentExtractor> DocumentExtractors { get; set; }
    public DbSet<PaperClaim> PaperClaims { get; set; }


    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        modelBuilder.Entity<PrismDocument>(entity =>
        {
            entity.HasKey(x => x.ChatId);
        });

        modelBuilder.Entity<FileRecord>(entity =>
        {
            entity.HasKey(f => f.FileId);
            entity.HasOne<PrismDocument>()
                  .WithMany()
                  .HasForeignKey(f => f.ChatId)
                  .OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<Domain>(entity =>
        {
            entity.HasIndex(d => d.Name).IsUnique();
        });

        modelBuilder.Entity<DocumentExtractor>(entity =>
        {
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

        modelBuilder.Entity<PaperClaim>(entity =>
        {
            entity.HasKey(x => x.Id);
            entity.Property(x => x.Label).HasConversion<string>();
            entity.Property(x => x.GroundingStatus).HasConversion<string>();
            entity.OwnsMany(x => x.EvidenceSpans, b =>
            {
                b.ToJson();
                b.Property(s => s.GroundingStatus).HasConversion<string>();
            });
            entity.HasOne(x => x.DocumentExtractor)
                  .WithMany(x => x.PaperClaims)
                  .HasForeignKey(x => x.DocumentExtractorId)
                  .OnDelete(DeleteBehavior.Cascade);
            entity.HasIndex(x => new { x.DocumentExtractorId, x.Label });
            entity.HasIndex(x => x.ExtractionRunId);
        });
    }
}

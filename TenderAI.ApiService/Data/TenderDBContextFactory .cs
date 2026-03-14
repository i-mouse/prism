using Microsoft.EntityFrameworkCore.Design;
using Microsoft.EntityFrameworkCore;

namespace TenderAI.ApiService.Data;

 public class TenderDBContextFactory : IDesignTimeDbContextFactory<TenderDBContext>
    {
        public TenderDBContext CreateDbContext(string[] args)
        {
            var optionsBuilder = new DbContextOptionsBuilder<TenderDBContext>();
            var connectionString ="Host=localhost;Port=5432;Database=tender-db;Username=postgres;Password=postgres";
            optionsBuilder.UseNpgsql(connectionString);
            return new TenderDBContext(optionsBuilder.Options);
        }
    }
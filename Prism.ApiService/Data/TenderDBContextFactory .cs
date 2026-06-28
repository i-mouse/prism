using Microsoft.EntityFrameworkCore.Design;
using Microsoft.EntityFrameworkCore;

namespace Prism.ApiService.Data;

 public class PrismDBContextFactory : IDesignTimeDbContextFactory<PrismDBContext>
    {
        public PrismDBContext CreateDbContext(string[] args)
        {
            var optionsBuilder = new DbContextOptionsBuilder<PrismDBContext>();
            var connectionString ="Host=localhost;Port=5432;Database=prism-db;Username=postgres;Password=postgres";
            optionsBuilder.UseNpgsql(connectionString);
            return new PrismDBContext(optionsBuilder.Options);
        }
    }
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace Prism.ApiService.Data;

public class PrismDBContextFactory : IDesignTimeDbContextFactory<PrismDBContext>
{
    public PrismDBContext CreateDbContext(string[] args)
    {
        var optionsBuilder = new DbContextOptionsBuilder<PrismDBContext>();
        optionsBuilder
            .UseNpgsql("Host=localhost;Database=prism-db;Username=postgres;Password=postgres")
            .UseSnakeCaseNamingConvention();
        return new PrismDBContext(optionsBuilder.Options);
    }
}
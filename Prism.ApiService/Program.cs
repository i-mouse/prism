
using System.Data.Common;
using System.Diagnostics;
using Azure.Extensions.AspNetCore.Configuration.Secrets;
using Azure.Identity;
using MassTransit;
using Microsoft.Extensions.Options;
using Microsoft.Identity.Web;
using Prism.ApiService.Configuration;
using Prism.ApiService.Data;
using Prism.ApiService.Features.Auth;
using Prism.ApiService.Features.PaperSubmission;
using Prism.ApiService.Services;
using Microsoft.EntityFrameworkCore;
using Prism.ApiService.Features.Chat;
using Prism.ApiService.Hubs;
using Prism.ApiService.Middleware;
using Microsoft.AspNetCore.Connections;
using RabbitMQ.Client;

var builder = WebApplication.CreateBuilder(args);

// Wires OpenTelemetry (traces/metrics/logs + OTLP export), health checks, service
// discovery, and HttpClient resilience - see Prism.ServiceDefaults/Extensions.cs.
// This project previously had no reference to Prism.ServiceDefaults at all, so
// none of that ever ran despite the exporter/instrumentation packages being
// installed - the API service exported zero spans as a result.
builder.AddServiceDefaults();

// Key Vault: AppHost's .WithReference(keyVault) injects the vault URI as the
// "prism-secrets" connection string, but does NOT load secrets into IConfiguration.
// We must wire the AzureKeyVault config provider explicitly so Microsoft.Identity.Web
// (and any future secret reads) can resolve values by Key Vault secret name.
// DefaultAzureCredential resolves via the Managed Identity that AppHost already
// provisions with KeyVaultSecretsUser role on apiservice.
// Skipped locally when the connection string is absent (no vault in Aspire local mode).
var keyVaultUri = builder.Configuration.GetConnectionString("prism-secrets");
if (!string.IsNullOrEmpty(keyVaultUri))
{
    builder.Configuration.AddAzureKeyVault(new Uri(keyVaultUri), new DefaultAzureCredential());
}

// JWT Bearer auth via Entra External ID (CIAM).
// AddMicrosoftIdentityWebApi sets MapInboundClaims = false by default, meaning
// JWT claims are passed through with their original names ("sub", "email", etc.)
// rather than being remapped to WS-Fed/SOAP long-form URIs.
// Consequence: read the authenticated user's ID as httpContext.User.FindFirst("sub")?.Value,
// NOT ClaimTypes.NameIdentifier. This deviates from the plan's assumed code and is
// intentional — the plan assumed the old MapInboundClaims=true default. See PR description.
builder.Services.AddAuthentication()
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));
builder.Services.AddAuthorization();

builder.Services.AddOpenApi();


builder.Services.AddProblemDetails(options =>
{
    options.CustomizeProblemDetails = ctx =>
    {
        ctx.ProblemDetails.Extensions["traceId"] = Activity.Current?.Id ?? ctx.HttpContext.TraceIdentifier;
        ctx.ProblemDetails.Extensions["correlationId"] = ctx.HttpContext.GetCorrelationId();
    };
});
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddMassTransit(busConfiguration =>
{
    busConfiguration.SetKebabCaseEndpointNameFormatter();

    busConfiguration.UsingRabbitMq((context,config) =>
    {
        // we dont ahve apss cred n username because c# handle its own and MasTransit follow AMQP Standard.eg - amqp://user:password@localhost:5672
        var connctionString = builder.Configuration.GetConnectionString("messaging");
         config.Host(connctionString);

    });


});

builder.Services.AddSwaggerGen();
builder.Services.AddEndpointsApiExplorer();


builder.Services.AddScoped<IfileUploader,FakeFileUploader>();

// AddAzureNpgsqlDbContext (not plain AddNpgsqlDbContext) - the deployed Azure Postgres
// Flexible Server is Entra-only (no password exists at all), and per Aspire's own docs
// "Microsoft Entra ID... requires changes to the application code to use an azure
// credential." Confirmed via a live deploy: plain AddNpgsqlDbContext produced a
// connection with no SSL and a placeholder username, rejected by pg_hba.conf. Locally,
// the RunAsContainer Postgres connection string still carries a real username/password,
// so this same call transparently uses password auth there - no local/prod branch needed.
builder.AddAzureNpgsqlDbContext<PrismDBContext>("prism-db",
    configureDbContextOptions: options => options.UseSnakeCaseNamingConvention());

// Registers BlobContainerClient in DI, resolving the Azurite connection string
// locally or DefaultAzureCredential against the real account in prod - same
// local/prod split the Npgsql client integration already does for Postgres.
builder.AddAzureBlobContainerClient("uploads");

builder.Services.AddSignalR();
builder.Services.AddSingleton<RabbitMQ.Client.IConnectionFactory>(sp =>
{
      var connctionString = builder.Configuration.GetConnectionString("messaging");

        return new ConnectionFactory
        {
            Uri = new Uri(connctionString!)
        };
});

 builder.Services.AddScoped<AzureBlobStorageService>();

 // Caches the pipeline's current prompt-version hash for the process lifetime -
 // fetched from Prism.PythonService at most once, never re-hashed per request.
 builder.Services.AddSingleton<PromptVersionProvider>();

 builder.Services.AddHostedService<RabbitMqListenerService>();

// Local Aspire dev resolves the python service through service discovery (`services:...:0`);
// Azure deploys it as a standalone container, so PYTHON_API_URL takes priority when set.
var pythonApiUrl = builder.Configuration["PYTHON_API_URL"]
    ?? builder.Configuration["services:prism-ai-pythonAPI:pythonapi:0"]
    ?? throw new InvalidOperationException("PYTHON_API_URL not configured");

    builder.Services.AddHttpClient("pythonapi", client =>
    {
        client.BaseAddress = new Uri(pythonApiUrl);
    });

// CORS_ALLOWED_ORIGINS (env var / config) is the only source of truth for allowed
// origins in prod. In dev, fall back to the local Vite dev server and Aspire-proxied
// ports so `dotnet run` / F5 works without extra setup. Never AllowAnyOrigin().
var corsAllowedOrigins = builder.Configuration["CORS_ALLOWED_ORIGINS"]
    ?.Split(",", StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

if (corsAllowedOrigins is null || corsAllowedOrigins.Length == 0)
{
    corsAllowedOrigins = builder.Environment.IsDevelopment()
        ? new[] { "http://localhost:5173", "http://localhost:7000" }
        : new[] { "https://prism-ai-reactui.nicesky-c6f0b846.centralindia.azurecontainerapps.io" };
}

builder.Services.Configure<CorsSettings>(options => options.AllowedOrigins = corsAllowedOrigins);

builder.Services.AddCors(options =>
{
    options.AddPolicy("SignalRPolicy", policy =>
    {
        policy.WithOrigins(corsAllowedOrigins)
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials();
    });
});

var runMigrationsOnStartup = builder.Configuration.GetValue<bool>("RUN_MIGRATIONS_ON_STARTUP");

// Feed the values resolved above (env-var fallback chains, etc.) back into IConfiguration
// under the PrismSettings property names so the typed options below bind to the same
// resolved values instead of re-reading raw keys.
builder.Configuration["PythonApiUrl"] = pythonApiUrl;
builder.Configuration["RunMigrationsOnStartup"] = runMigrationsOnStartup.ToString();

builder.Services.AddOptions<PrismSettings>()
    .Bind(builder.Configuration)
    .ValidateDataAnnotations()
    .ValidateOnStart();

// Cap request body size at 20MB (paper uploads) - rejects oversized bodies before
// they're buffered.
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 20_000_000);

var app = builder.Build();

app.UseExceptionHandler();
app.UseCorrelationId();
// UseAuthentication/UseAuthorization must come after routing middleware and before
// endpoint mapping. Guest endpoints are anonymous — RequireAuthorization() is NEVER
// called globally; each endpoint opts into auth individually.
app.UseAuthentication();
app.UseAuthorization();

using (var scope = app.Services.CreateAsyncScope())
{
    var service = scope.ServiceProvider.GetRequiredService<AzureBlobStorageService>();
    await service.EnsureContainerExistsAsync();
}
// Migrations run once per Container Apps revision via a separate one-shot deploy task,
// not on every container start (multiple replicas starting together would deadlock on
// the migration lock). Local Aspire dev keeps this on via AppHost.cs.
if (runMigrationsOnStartup)
{
    using var scope = app.Services.CreateAsyncScope();
    var service = scope.ServiceProvider.GetRequiredService<PrismDBContext>();
    await service.Database.MigrateAsync();
}
using (var scope = app.Services.CreateAsyncScope())
{
    var connectionFactory = scope.ServiceProvider.GetRequiredService<RabbitMQ.Client.IConnectionFactory>();
    var connection = await connectionFactory.CreateConnectionAsync();
    var channel = await connection.CreateChannelAsync();

     var rabbitMqSetupService = new RabbitMqSetupService();
     await rabbitMqSetupService.SetupQueuesAsync(channel);
}
app.MapPaperEndPoint();
app.MapChatEndPoint();
app.MapChatHistoryEndpoints();
app.MapGuestAuthEndpoints();

// Fast liveness probe for Azure Container Apps - no DB/Qdrant ping, must return 200 quickly
// even under load. A deeper /readiness endpoint can come post-V1.
app.MapGet("/health", () => Results.Ok(new { status = "healthy" }))
    .WithName("HealthCheck")
    .ExcludeFromDescription();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.UseSwagger();
    app.UseSwaggerUI();
}
app.UseCors("SignalRPolicy");
app.MapHub<DocumentHub>("/hubs/document");
app.UseHttpsRedirection();
app.Run();


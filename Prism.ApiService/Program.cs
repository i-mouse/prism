
using System.Data.Common;
using System.Diagnostics;
using MassTransit;
using Microsoft.Extensions.Options;
using Prism.ApiService.Configuration;
using Prism.ApiService.Data;
using Prism.ApiService.Features.PaperSubmission;
using Prism.ApiService.Services;
using Microsoft.EntityFrameworkCore;
using Minio;
using Prism.ApiService.Features.Chat;
using Prism.ApiService.Features.System;
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

// builder.AddNpgsqlDbContext<PrismDBContext>("prism-db");
builder.AddNpgsqlDbContext<PrismDBContext>("prism-db",
    configureDbContextOptions: options => options.UseSnakeCaseNamingConvention());

builder.Services.AddMinio(configureClient =>    
{
    // we have to pass cred n username because AddMinio follow HTTP Standard. eg - http://localhost:9000
    var connectionString = builder.Configuration.GetConnectionString("storage");
    var settings = connectionString!.Split(";").Select(part=> part.Split("=")).ToDictionary(split => split[0], split => split[1]);
    var endpointUrl = new Uri(settings["Endpoint"]);
    var accessKey = settings["AccessKey"];
    var secretKey = settings["SecretKey"];

    bool useSSL = endpointUrl.Scheme == "https";
    configureClient.WithEndpoint(endpointUrl.Authority).WithCredentials(accessKey,secretKey).WithSSL(useSSL);
}  );

builder.Services.AddSignalR();
builder.Services.AddSingleton<RabbitMQ.Client.IConnectionFactory>(sp => 
{
      var connctionString = builder.Configuration.GetConnectionString("messaging");

        return new ConnectionFactory
        {
            Uri = new Uri(connctionString!)
        };
});

 builder.Services.AddScoped<MinioStorageService>();
 
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

var allowedOrigins = builder.Configuration["AllowedOrigins"]
    ?.Split(",", StringSplitOptions.RemoveEmptyEntries)
    ?? new[] { "http://localhost:7000" };

builder.Services.AddCors(options =>
{
    options.AddPolicy("SignalRPolicy", policy =>
    {
        policy.WithOrigins(allowedOrigins)
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
builder.Configuration["AllowedOrigins"] = string.Join(",", allowedOrigins);
builder.Configuration["RunMigrationsOnStartup"] = runMigrationsOnStartup.ToString();

builder.Services.AddOptions<PrismSettings>()
    .Bind(builder.Configuration)
    .ValidateDataAnnotations()
    .ValidateOnStart();

var app = builder.Build();

app.UseExceptionHandler();
app.UseCorrelationId();

using (var scope = app.Services.CreateAsyncScope())
{
    var service = scope.ServiceProvider.GetRequiredService<MinioStorageService>();
    await service.EnsureBucketExistAsync("prism-uploads");
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
app.MapSystemEndPoint();

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


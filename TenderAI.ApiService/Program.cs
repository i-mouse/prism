
using System.Data.Common;
using MassTransit;
using Microsoft.Extensions.Options;
using TenderAI.ApiService.Data;
using TenderAI.ApiService.Features.RfpSubmission;
using TenderAI.ApiService.Services;
using Microsoft.EntityFrameworkCore;
using Minio;
using TenderAI.ApiService.Features.Chat;
using TenderAI.ApiService.Hubs;
using Microsoft.AspNetCore.Connections;
using RabbitMQ.Client;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddOpenApi();
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

builder.AddNpgsqlDbContext<TenderDBContext>("tender-db");

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

    builder.Services.AddHttpClient("pythonapi", client =>
    {
        client.BaseAddress = new Uri(builder.Configuration["services:tender-ai-pythonAPI:pythonapi:0"]!);
    });

builder.Services.AddCors(options =>
{
    options.AddPolicy("SignalRPolicy", policy =>
    {
        policy.WithOrigins("http://localhost:7000")
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials();
    });
});

var app = builder.Build();

using (var scope = app.Services.CreateAsyncScope())
{
    var service = scope.ServiceProvider.GetRequiredService<MinioStorageService>();
    await service.EnsureBucketExistAsync("tender-uploads");
}
using (var scope = app.Services.CreateAsyncScope())
{
    var service = scope.ServiceProvider.GetRequiredService<TenderDBContext>();
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
app.MapRfpEndPoint();
app.MapChatEndPoint();
app.MapChatHistoryEndpoints();
app.MapSystemEndPoint();

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


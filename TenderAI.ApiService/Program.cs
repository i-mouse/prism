
using System.Data.Common;
using MassTransit;
using Microsoft.Extensions.Options;
using TenderAI.ApiService.Data;
using TenderAI.ApiService.Features.RfpSubmission;
using TenderAI.ApiService.Services;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
// Use the Action<ConfigurationOptions> delegate directly

// Add services to the container.
builder.Services.AddOpenApi();
builder.Services.AddMassTransit(busConfiguration =>
{
    busConfiguration.SetKebabCaseEndpointNameFormatter();

    busConfiguration.UsingRabbitMq((context,config) =>
    {
        var connctionString = builder.Configuration.GetConnectionString("messaging");
        config.Host(connctionString);

    });

    
});

builder.Services.AddSwaggerGen();
builder.Services.AddEndpointsApiExplorer();


builder.Services.AddScoped<IfileUploader,FakeFileUploader>();

builder.Services.AddDbContext<TenderDBContext>(options =>
{

    var connectionString = builder.Configuration.GetConnectionString("tender-db");
        options.UseSqlServer(connectionString);
    
});

var app = builder.Build();

app.MapRfpEndPoint();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.Run();



using Microsoft.Extensions.Options;
using TenderAI.ApiService.Services;

var builder = WebApplication.CreateBuilder(args);
// Use the Action<ConfigurationOptions> delegate directly

// Add services to the container.
builder.Services.AddOpenApi();

builder.Services.AddScoped<IfileUploader,FakeFileUploader>();
var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.UseHttpsRedirection();
app.Run();


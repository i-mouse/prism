using YamlDotNet.Serialization;

var builder = DistributedApplication.CreateBuilder(args);

//add Redis
var cache = builder.AddRedis("redis-cache");

var miniIO = builder.AddMinioContainer("storage").WithDataVolume();

var sqlDB = builder.AddSqlServer ("sql").AddDatabase("tender-db");
var rabbitMQ = builder.AddRabbitMQ ("messaging").WithDataVolume().WithManagementPlugin();
var dqrantDB = builder.AddQdrant ("qdrant").WithDataVolume();

// adding Services
builder.AddProject<Projects.TenderAI_ApiService>("apiservice")
       .WithEnvironment("DEPLOYMENT_REGION","US-East")
       .WithReference(cache)
       .WithReference(sqlDB)
       .WithReference(rabbitMQ)
       .WithReference(dqrantDB)
       .WithReference(miniIO);
       

builder.Build().Run();

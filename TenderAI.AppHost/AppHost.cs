using Microsoft.Extensions.Configuration;
using YamlDotNet.Serialization;

var builder = DistributedApplication.CreateBuilder(args);

//add Redis
var cache = builder.AddRedis("redis-cache");

var apiKey = builder.Configuration["AI_API_KEY"];
var qdrantSecretKey = builder.Configuration["QDRANT_SECRET_KEY"];

var userrabbitmq = builder.AddParameter( name:"rabbitmquser",secret :true);
var passrabbitmq = builder.AddParameter( name:"rabbitmqpass",secret :true);

var minioUser = builder.AddParameter("MinioUser");
var minioPass = builder.AddParameter("MinioSecret", secret: true);

var qdrantKey = builder.AddParameter("QdrantApiKey", secret: true);

var rabbitMQ = builder.AddRabbitMQ ("messaging",userName : userrabbitmq,password:passrabbitmq).WithDataVolume().WithManagementPlugin();
var miniIO = builder.AddMinioContainer("storage",rootUser:minioUser,rootPassword:minioPass).WithDataVolume();

var postgres = builder.AddPostgres("postgres")
                        .WithPgAdmin()
                        .WithDataVolume()
                      .AddDatabase("tender-db");

var qdrantDB = builder.AddQdrant ("qdrant",apiKey:qdrantKey).WithDataVolume();

//  var pythonAPI = builder.AddPythonApp("tender-ai-pythonAPI","../TenderAI.PythonService","api.py")
//                         .WithHttpEndpoint(port:8000,name: "pythonapi",env: "PORT")
//                         .WithReference(qdrantDB)
//                         .WithEnvironment("AI_API_KEY",apiKey)
//                         .WithReference(postgres)
//                         .WithUv();


var pythonAPI = builder.AddDockerfile("tender-ai-pythonAPI", "../TenderAI.PythonService")
    .WithHttpEndpoint(targetPort: 8000, name: "pythonapi", env: "PORT")
    .WithReference(qdrantDB)
    .WithEnvironment("AI_API_KEY", apiKey)
    .WithReference(postgres)
    .WaitFor(postgres);
                


  var pythonWorker = builder.AddPythonApp("tender-ai-pythonWorker","../TenderAI.PythonService","main.py")
                        .WithReference(miniIO)
                        .WithReference(rabbitMQ)
                        .WithReference(qdrantDB)
                         .WithReference(postgres) 
                        .WithEnvironment("AI_API_KEY",apiKey)
                        .WithUv()
                        .WithDebugging()
                        .WaitFor(postgres);

var apiservice =     builder.AddProject<Projects.TenderAI_ApiService>("apiservice")
                     .WithEnvironment("DEPLOYMENT_REGION","US-East")
                     .WithReference(cache)
                     .WithReference(postgres)
                     .WaitFor(postgres)
                     .WithReference(rabbitMQ)
                     .WaitFor(rabbitMQ)
                     .WithReference(qdrantDB)
                     .WithReference(miniIO)
                    .WithReference(pythonAPI.GetEndpoint("pythonapi"));

var reactUI  =       builder.AddNpmApp("tender-ai-reactUI","../TenderAI.Web")
                     .WithHttpEndpoint(port:7000,name: "reactUI",env: "VITE_PORT")
                     .WithEnvironment("VITE_API_BASE_URL", apiservice.GetEndpoint("https"))
                     .WithReference(apiservice);              

builder.Build().Run();

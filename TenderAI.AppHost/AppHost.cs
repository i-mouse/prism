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

var sqlDB = builder.AddSqlServer ("sql").AddDatabase("tender-db");


var qdrantDB = builder.AddQdrant ("qdrant",apiKey:qdrantKey).WithDataVolume();

 var pythonAPI = builder.AddPythonApp("tender-ai-pythonAPI","../TenderAI.PythonService","api.py")
                        .WithHttpEndpoint(port:8000,name: "pythonapi",env: "PORT")
                        .WithReference(qdrantDB)
                        .WithEnvironment("AI_API_KEY",apiKey)
                        .WithUv();

  var pythonWorker = builder.AddPythonApp("tender-ai-pythonWorker","../TenderAI.PythonService","main.py")
                        .WithReference(miniIO)
                        .WithReference(rabbitMQ)
                        .WithReference(qdrantDB)
                        .WithEnvironment("AI_API_KEY",apiKey)
                        .WithUv()
                        .WithDebugging();

       // adding Services
       builder.AddProject<Projects.TenderAI_ApiService>("apiservice")
              .WithEnvironment("DEPLOYMENT_REGION","US-East")
              .WithReference(cache)
              .WithReference(sqlDB)
              .WithReference(rabbitMQ)
              .WithReference(qdrantDB)
              .WithReference(miniIO)
              .WithReference(pythonAPI);
builder.Build().Run();

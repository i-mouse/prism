using Microsoft.Extensions.Configuration;

var builder = DistributedApplication.CreateBuilder(args);

// Redis provisioned for future response caching — caching logic NOT yet implemented (see README Roadmap)
var cache = builder.AddRedis("redis-cache");

var apiKey = builder.Configuration["GoogleApiKey"];
var groqApiKey = builder.Configuration["GroqApiKey"];
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
                      .AddDatabase("prism-db");

var qdrantDB = builder.AddQdrant ("qdrant",apiKey:qdrantKey).WithDataVolume();

var pythonAPI = builder.AddDockerfile("prism-ai-pythonAPI", "../Prism.PythonService")
    .WithHttpEndpoint(targetPort: 8000, name: "pythonapi", env: "PORT")
    .WithReference(qdrantDB)
    .WithEnvironment("AI_API_KEY", apiKey)
    .WithEnvironment("GROQ_API_KEY", groqApiKey)
    .WithEnvironment("LLM_EXTRACTION_MODEL", "gemini-3.6-flash")
    .WithEnvironment("LLM_AUDIT_MODEL", "gemini-3.1-flash-lite")
    .WithEnvironment("LLM_SUMMARY_MODEL", "gemini-3.1-flash-lite")
    .WithEnvironment("LLM_FAST_MODEL", "gemini-3.1-flash-lite")
    .WithEnvironment("LLM_AGENT_MODEL", "gemini-3.6-flash")
    .WithReference(postgres)
    .WithReference(rabbitMQ)    // ADD THIS
    .WithReference(miniIO)      // ADD THIS
    .WaitFor(postgres);
                
 builder.AddPythonApp("prism-ai-pythonWorker","../Prism.PythonService","main.py")
                        .WithReference(miniIO)
                        .WithReference(rabbitMQ)
                        .WithReference(qdrantDB)
                         .WithReference(postgres) 
                        .WithEnvironment("AI_API_KEY",apiKey)
                        .WithEnvironment("GROQ_API_KEY", groqApiKey)
                        .WithEnvironment("LLM_EXTRACTION_MODEL", "gemini-3.6-flash")
                        .WithEnvironment("LLM_AUDIT_MODEL", "gemini-3.1-flash-lite")
                        .WithEnvironment("LLM_SUMMARY_MODEL", "gemini-3.1-flash-lite")
                        .WithEnvironment("LLM_FAST_MODEL", "gemini-3.1-flash-lite")
                        .WithEnvironment("LLM_AGENT_MODEL", "gemini-3.6-flash")
                        .WithEnvironment("PRISM_DEBUG", "1") 
                        .WithUv()
                        .WithDebugging()
                        .WaitFor(postgres).WaitFor(rabbitMQ);

var apiservice =     builder.AddProject<Projects.Prism_ApiService>("apiservice")
                     .WithEnvironment("DEPLOYMENT_REGION","US-East")
                     .WithEnvironment("RUN_MIGRATIONS_ON_STARTUP", "true")
                     .WithReference(cache)
                     .WithReference(postgres)
                     .WaitFor(postgres)
                     .WithReference(rabbitMQ)
                     .WaitFor(rabbitMQ)
                     .WithReference(qdrantDB)
                     .WithReference(miniIO)
                    .WithReference(pythonAPI.GetEndpoint("pythonapi"));

 builder.AddNpmApp("prism-ai-reactUI","../Prism.Web")
                     .WithHttpEndpoint(port:7000,name: "reactUI",env: "VITE_PORT")
                     .WithEnvironment("VITE_API_BASE_URL", apiservice.GetEndpoint("https"))
                     .WithReference(apiservice);

// Aspire dashboard external-exposure check (pre-deploy hardening, 2026-08-31): no
// AddAzureContainerAppEnvironment() resource exists in this AppHost yet - the
// Aspire.Hosting.Azure.AppContainers package isn't even referenced (Prism.AppHost.csproj).
// Azure infra provisioning is still deferred to a future azd-driven PR (see
// docs/decisions.md, "Azure pre-deploy foundation"). None of the endpoints above call
// .WithExternalHttpEndpoints()/.ExternalHttpEndpoints(true), so nothing here - including
// a future dashboard component - is externally routable today. When
// AddAzureContainerAppEnvironment() is added, keep the dashboard internal-only
// (Azure's managed-environment dashboard component has no public ingress by default;
// it's reached via `az containerapp env dashboard show`, not a WithHttpEndpoint call) and
// don't call .WithExternalHttpEndpoints() on it.
builder.Build().Run();

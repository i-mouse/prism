using Microsoft.Extensions.Configuration;

var builder = DistributedApplication.CreateBuilder(args);

// Redis provisioned for future response caching — caching logic NOT yet implemented (see README Roadmap)
var cache = builder.AddRedis("redis-cache");

var apiKey = builder.Configuration["GoogleApiKey"];
var groqApiKey = builder.Configuration["GroqApiKey"];

var qdrantKey = builder.AddParameter("QdrantApiKey", secret: true);
var userrabbitmq = builder.AddParameter( name:"rabbitmquser",secret :true);
var passrabbitmq = builder.AddParameter( name:"rabbitmqpass",secret :true);

// Azure resource declarations (PR4): local dev runs the same containers/emulators
// as before via RunAsContainer()/RunAsEmulator(); azd provisions the real Azure
// resources (Postgres Flexible Server, Blob Storage) in prod from this same
// declaration. Messaging stays RabbitMQ (self-hosted, MassTransit-abstracted) and
// Qdrant stays a plain container in both - see docs/decisions.md, "Managed vs
// self-hosted service split". A Service Bus migration was attempted here and
// reverted 2026-09-01 - it surfaced four distinct bugs in the Aspire Service Bus
// emulator + azure-servicebus Python SDK combination (including an upstream Aspire
// gap, https://github.com/microsoft/aspire/issues/14041) and end-to-end never
// completed cleanly. Deferred to its own PR post-live-URL.
var postgres = builder.AddAzurePostgresFlexibleServer("postgres")
                        .RunAsContainer(c => c.WithPgAdmin().WithDataVolume())
                        .AddDatabase("prism-db");

var storage = builder.AddAzureStorage("storage").RunAsEmulator();
var uploads = storage.AddBlobContainer("uploads", blobContainerName: "prism-uploads");
// AzureStorageResource (the bare account resource `storage`) doesn't implement
// IResourceWithConnectionString - only child resources do. AddBlobs gives a blob
// *service*-level child (no specific container baked in, unlike AddBlobContainer) with
// a plain standards-compliant connection string - what Python needs (see the note below).
var blobs = storage.AddBlobs("blobs");

var rabbitMQ = builder.AddRabbitMQ ("messaging",userName : userrabbitmq,password:passrabbitmq).WithDataVolume().WithManagementPlugin();

// Key Vault has no local emulator (unlike Postgres/Storage above) - only
// add it in publish mode (azd), where it's actually provisioned. Adding it
// unconditionally would make F5 block forever on a resource that can never reach
// "Running" locally, since there's nothing to run - it would need a real Azure
// subscription even for `dotnet run`. Local dev keeps using user-secrets/env vars
// directly, exactly as before.
var keyVault = builder.ExecutionContext.IsPublishMode
    ? builder.AddAzureKeyVault("prism-secrets")
    : null;

var qdrantDB = builder.AddQdrant ("qdrant",apiKey:qdrantKey).WithDataVolume();

// Storage: C# (apiservice) references the `uploads` container child resource directly
// - Aspire's AddAzureBlobContainerClient client integration expects that (its connection
// string carries a ";ContainerName=prism-uploads" suffix that only Aspire's own .NET
// client knows to parse/strip). Python references the `blobs` service-level resource
// instead (plain account resource `storage` has no connection string at all - only
// child resources do): its connection string is a plain, standards-compliant Azure
// Storage connection string, which is what the raw azure-storage-blob SDK's
// ContainerClient.from_connection_string expects - handing it the "uploads" child's
// decorated string throws "Connection string is either blank or malformed." (confirmed
// via a live F5 run). Python targets the "prism-uploads" container by name explicitly
// (get_blob_container_client's container_name param), same as the bucket name was a
// literal under MinIO. config.py's alias points at ConnectionStrings__blobs to match.
//
// Messaging: RabbitMQ, unchanged from before the Service Bus attempt -
// WithReference(rabbitMQ) injects the same ConnectionStrings__messaging env var
// config.py and Program.cs already expect.
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
    .WithReference(rabbitMQ)
    .WithReference(blobs)
    .WaitFor(postgres)
    .WaitFor(blobs);
if (keyVault is not null) pythonAPI.WithReference(keyVault);

var pythonWorker = builder.AddPythonApp("prism-ai-pythonWorker","../Prism.PythonService","main.py")
                        .WithReference(blobs)
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
                        .WaitFor(postgres).WaitFor(rabbitMQ).WaitFor(blobs);
if (keyVault is not null) pythonWorker.WithReference(keyVault);

var apiservice =     builder.AddProject<Projects.Prism_ApiService>("apiservice")
                     .WithEnvironment("DEPLOYMENT_REGION","US-East")
                     .WithEnvironment("RUN_MIGRATIONS_ON_STARTUP", "true")
                     .WithReference(cache)
                     .WithReference(postgres)
                     .WaitFor(postgres)
                     .WithReference(rabbitMQ)
                     .WaitFor(rabbitMQ)
                     .WithReference(qdrantDB)
                     .WithReference(uploads)
                     .WaitFor(uploads)
                    .WithReference(pythonAPI.GetEndpoint("pythonapi"));
if (keyVault is not null) apiservice.WithReference(keyVault);

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

using Microsoft.Extensions.Configuration;
using Aspire.Hosting.Azure;

var builder = DistributedApplication.CreateBuilder(args);

// PR5: Azure Container Apps environment - only meaningful in publish mode (aspire
// deploy); F5 ignores it since there's nothing to run locally for a compute
// environment. Provisions the managed environment, Log Analytics workspace,
// container registry, and Aspire dashboard component. See docs/decisions.md,
// "First Azure deploy".


// App Insights: OTel exporter swap only (docs/decisions.md, "Managed vs self-hosted
// service split") - instrumentation itself is already vendor-neutral OTel, unchanged
// from PR2. WithReference injects APPLICATIONINSIGHTS_CONNECTION_STRING.
// Publish-mode-only Azure resources
var acaEnv = builder.ExecutionContext.IsPublishMode
    ? builder.AddAzureContainerAppEnvironment("prism-env")
    : null;

var appInsights = builder.ExecutionContext.IsPublishMode
    ? builder.AddAzureApplicationInsights("appInsights")
    : null;

// Redis provisioned for future response caching — caching logic NOT yet implemented (see README Roadmap)
var cache = builder.AddRedis("redis-cache");

var geminiKey = builder.AddParameter("GoogleApiKey", secret: true);
var groqKey = builder.AddParameter("GroqApiKey", secret: true);

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

// PR5: WithDataVolume() maps to an Azure Files-backed volume on Container Apps
// (local bind-mount semantics don't carry over - see AddAzureContainerAppEnvironment
// comment above). RabbitMQ's Erlang runtime refuses to start if /var/lib/rabbitmq's
// .erlang.cookie isn't owner-only (0600) - confirmed via a live deploy crash
// ("Cookie file ... must be accessible by owner only") - and Azure Files (SMB-backed)
// doesn't preserve that permission bit the way a local Docker bind mount does. Qdrant
// and Redis use the same WithDataVolume() pattern and deploy healthy, so this is
// RabbitMQ-specific, not a general Azure Files problem. Skip the volume in publish
// mode: this is a single-node, low-throughput dev/early-prod queue (docs/decisions.md,
// "Managed vs self-hosted service split") with no durability requirement yet, so
// losing queue state across container restarts is an acceptable trade for a working
// deploy. F5 keeps the volume (Docker Desktop bind mounts don't have this problem).
var rabbitMQBuilder = builder.AddRabbitMQ("messaging", userName: userrabbitmq, password: passrabbitmq).WithManagementPlugin();
if (!builder.ExecutionContext.IsPublishMode) rabbitMQBuilder.WithDataVolume();
var rabbitMQ = rabbitMQBuilder;

// Key Vault has no local emulator (unlike Postgres/Storage above) - only
// add it in publish mode (azd), where it's actually provisioned. Adding it
// unconditionally would make F5 block forever on a resource that can never reach
// "Running" locally, since there's nothing to run - it would need a real Azure
// subscription even for `dotnet run`. Local dev keeps using user-secrets/env vars
// directly (Parameters:GoogleApiKey / Parameters:GroqApiKey via user-secrets),
// exactly as before.
var keyVault = builder.ExecutionContext.IsPublishMode
    ? builder.AddAzureKeyVault("prism-secrets")
    : null;
if (keyVault is not null)
{
    keyVault.AddSecret("gemini-api-key", geminiKey);
    keyVault.AddSecret("groq-api-key", groqKey);
}

// Postgres Entra auth needs a username Python's raw psycopg client can look up (unlike
// apiservice's .NET Npgsql client integration, which auto-detects it from managed identity
// - docs/decisions.md, "First Azure deploy", item 8). Aspire's default per-app Container
// App identity (docs/decisions.md item 7) has no accessible name reference from AppHost
// code, so pythonAPI/pythonWorker get explicit named identities instead: each one's
// NameOutputReference becomes PRISM_DB_USERNAME below, and Aspire's PostgreSQL
// role-assignment support (dotnet/aspire#8209) registers the explicit identity as a
// Postgres Entra admin through the WithReference(postgres) calls already in place -
// same mechanism as the default per-app identity, no extra role-assignment wiring needed.
var pythonAPIIdentity = builder.ExecutionContext.IsPublishMode
    ? builder.AddAzureUserAssignedIdentity("prism-pythonAPI-identity")
    : null;
var pythonWorkerIdentity = builder.ExecutionContext.IsPublishMode
    ? builder.AddAzureUserAssignedIdentity("prism-pythonWorker-identity")
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
    .WithEnvironment("LLM_EXTRACTION_MODEL", "gemini-3.6-flash")
    .WithEnvironment("LLM_AUDIT_MODEL", "gemini-3.1-flash-lite")
    .WithEnvironment("LLM_SUMMARY_MODEL", "gemini-3.1-flash-lite")
    .WithEnvironment("LLM_FAST_MODEL", "gemini-3.1-flash-lite")
    .WithEnvironment("LLM_AGENT_MODEL", "gemini-3.6-flash")
    .WithReference(postgres)
    .WithReference(rabbitMQ)
    .WithReference(blobs)
    .WaitFor(postgres)
    .WaitFor(blobs)
    // Replica pin (docs/deployment_notes.md) - matches apiservice; no shared state here
    // today, but keeping all three app containers at a fixed 1 replica avoids surprises.
    // CPU/memory: default 0.5/1Gi OOM-killed this service under real load during the
    // 2026-09-01 deploy (docs/decisions.md, "First Azure deploy", item 10) - sized to
    // 2.0/4Gi to match the manual `az containerapp update` fix already live.
    .PublishAsAzureContainerApp((infra, app) =>
    {
        app.Template.Scale.MinReplicas = 1;
        app.Template.Scale.MaxReplicas = 1;
        var container = app.Template.Containers.Single().Value!;
        container.Resources.Cpu = 2.0;
        container.Resources.Memory = "4Gi";
    });
if (appInsights is not null) pythonAPI.WithReference(appInsights);

if (pythonAPIIdentity is not null)
{
    pythonAPI
        .WithAzureUserAssignedIdentity(pythonAPIIdentity)
        .WithEnvironment("PRISM_DB_USERNAME", pythonAPIIdentity.Resource.NameOutputReference);
}

if (keyVault is not null)
{
    pythonAPI
        .WithReference(keyVault)
        .WithEnvironment("AI_API_KEY", keyVault.GetSecret("gemini-api-key"))
        .WithEnvironment("GROQ_API_KEY", keyVault.GetSecret("groq-api-key"));
}
else
{
    pythonAPI
        .WithEnvironment("AI_API_KEY", geminiKey)
        .WithEnvironment("GROQ_API_KEY", groqKey);
}

var pythonWorker = builder.AddPythonApp("prism-ai-pythonWorker","../Prism.PythonService","main.py")
                        .WithReference(blobs)
                        .WithReference(rabbitMQ)
                        .WithReference(qdrantDB)
                         .WithReference(postgres)
                        .WithEnvironment("LLM_EXTRACTION_MODEL", "gemini-3.6-flash")
                        .WithEnvironment("LLM_AUDIT_MODEL", "gemini-3.1-flash-lite")
                        .WithEnvironment("LLM_SUMMARY_MODEL", "gemini-3.1-flash-lite")
                        .WithEnvironment("LLM_FAST_MODEL", "gemini-3.1-flash-lite")
                        .WithEnvironment("LLM_AGENT_MODEL", "gemini-3.6-flash")
                        .WithEnvironment("PRISM_DEBUG", "1")
                        .WithUv()
                        .WithDebugging()
                        .WaitFor(postgres).WaitFor(rabbitMQ).WaitFor(blobs)
                        // AddPythonApp's auto-generated publish container ran api.py (the FastAPI
                        // server) instead of main.py (the RabbitMQ consumer loop) - docs/decisions.md,
                        // "First Azure deploy", item 9. Dockerfile.worker already has the correct
                        // CMD ["python", "main.py"] but was never referenced. Point publish at it
                        // explicitly instead of Aspire's generated build.
                        .PublishAsDockerFile(c => c.WithDockerfile("../Prism.PythonService", "Dockerfile.worker"))
                        // CPU/memory: default 0.5/1Gi silently OOM-killed this service right after
                        // the embedding-model-load + PDF-processing stage (docs/decisions.md,
                        // "First Azure deploy", item 10) - sized to 2.0/4Gi to match the manual
                        // `az containerapp update` fix already live.
                        .PublishAsAzureContainerApp((infra, app) =>
                        {
                            var container = app.Template.Containers.Single().Value!;
                            container.Resources.Cpu = 2.0;
                            container.Resources.Memory = "4Gi";
                        });

if (appInsights is not null) pythonWorker.WithReference(appInsights);

if (pythonWorkerIdentity is not null)
{
    pythonWorker
        .WithAzureUserAssignedIdentity(pythonWorkerIdentity)
        .WithEnvironment("PRISM_DB_USERNAME", pythonWorkerIdentity.Resource.NameOutputReference);
}

if (keyVault is not null)
{
    pythonWorker
        .WithReference(keyVault)
        .WithEnvironment("AI_API_KEY", keyVault.GetSecret("gemini-api-key"))
        .WithEnvironment("GROQ_API_KEY", keyVault.GetSecret("groq-api-key"));
}
else
{
    pythonWorker
        .WithEnvironment("AI_API_KEY", geminiKey)
        .WithEnvironment("GROQ_API_KEY", groqKey);
}

var apiservice =     builder.AddProject<Projects.Prism_ApiService>("apiservice")
                     .WithEnvironment("DEPLOYMENT_REGION","US-East")
                     // Migrations must not run on Container App startup in prod - concurrent
                     // replica starts would race for the migration lock (docs/deployment_notes.md,
                     // "Migration strategy"). Run once manually post-deploy instead. Locally
                     // (F5) this stays "true" so the dev DB is always up to date.
                     .WithEnvironment("RUN_MIGRATIONS_ON_STARTUP", builder.ExecutionContext.IsPublishMode ? "false" : "true")
                     .WithReference(cache)
                     .WithReference(postgres)
                     .WaitFor(postgres)
                     .WithReference(rabbitMQ)
                     .WaitFor(rabbitMQ)
                     .WithReference(qdrantDB)
                     .WithReference(uploads)
                     .WaitFor(uploads)
                    .WithReference(pythonAPI.GetEndpoint("pythonapi"))
                    // Frontend calls this directly from the browser (VITE_API_BASE_URL is baked
                    // into the static bundle at build time) - needs public ingress.
                    .WithExternalHttpEndpoints()
                    // No SignalR backplane (docs/deployment_notes.md, "Replica pin") - in-memory
                    // group routing only works with exactly one apiservice replica.
                    .PublishAsAzureContainerApp((infra, app) =>
                    {
                        app.Template.Scale.MinReplicas = 1;
                        app.Template.Scale.MaxReplicas = 1;
                    });
if (appInsights is not null) apiservice.WithReference(appInsights);
if (keyVault is not null) apiservice.WithReference(keyVault);

 // PR5: AddNpmApp alone runs `npm run dev` locally but isn't picked up by `aspire
 // deploy` at all - it never appears in the publish pipeline (confirmed via a live
 // deploy: zero mentions of prism-ai-reactUI in the log, no Container App created).
 // PublishAsDockerFile() switches the publish target to the existing
 // Prism.Web/Dockerfile (nginx + `npm run build`) without touching local F5 behavior.
 // VITE_API_BASE_URL is a Vite build-time value baked into the static bundle by
 // `npm run build` (docs/deployment_notes.md) - WithEnvironment only reaches the F5
 // dev server process, so the container build needs the same value as a build arg too.

//  builder.AddNpmApp("prism-ai-reactUI","../Prism.Web")
//                      .WithHttpEndpoint(port:7000,name: "reactUI",env: "VITE_PORT")
//                      .WithEnvironment("VITE_API_BASE_URL", apiservice.GetEndpoint("https"))
//                      .WithReference(apiservice)
//                      .WithExternalHttpEndpoints()
//                      .PublishAsDockerFile(c => c.WithBuildArg("VITE_API_BASE_URL", apiservice.GetEndpoint("https")));

builder.AddJavaScriptApp("prism-ai-reactUI", "../Prism.Web")
    .WithNpm(install: true)
    .WithHttpEndpoint(port: 7000, name: "reactUI", env: "VITE_PORT")
    .WithEnvironment("VITE_API_BASE_URL", apiservice.GetEndpoint("https"))
    .WithReference(apiservice)
    .WithExternalHttpEndpoints();

// Aspire dashboard external-exposure check (PR5): AddAzureContainerAppEnvironment is
// now present (prism-env, above). Only apiservice and reactUI call
// .WithExternalHttpEndpoints() - everything else (pythonAPI, pythonWorker, rabbitMQ,
// qdrant, redis, postgres, storage) stays internal-only within the environment. The
// dashboard component itself gets no WithExternalHttpEndpoints() call anywhere in this
// file, so it has no public ingress by default; it's reached via
// `az containerapp env dashboard show`, not a URL.
builder.Build().Run();

# Prism Reference Index

`Prism.ApiService/Contracts/PrismUploaded.cs` – DTO for publishing prism upload events to RabbitMQ.
`Prism.ApiService/Data/PrismDBContext.cs` – EF Core database context configuring PostgreSQL tables.
`Prism.ApiService/Data/PrismDBContextFactory .cs` – Factory for design-time DB context creation.
`Prism.ApiService/Data/Schemas/FileRecords.cs` – Schema representing individual files within a prism document chat.
`Prism.ApiService/Data/Schemas/PricingHistory.cs` – Schema for tracking historical pricing data (currently unused).
`Prism.ApiService/Data/Schemas/PrismDocument.cs` – Schema representing a parent chat and its associated prism documents.
`Prism.ApiService/Features/Chat/ChatEndPoint.cs` – API endpoints for routing chat questions to Python and fetching history.
`Prism.ApiService/Features/Chat/ChatRequest.cs` – Request/response DTOs for chat interactions.
`Prism.ApiService/Features/RfpSubmission/SubmitRfpEndPoint.cs` – Endpoints for handling document uploads and fetching user chat histories.
`Prism.ApiService/Features/RfpSubmission/SubmitRfpRequest.cs` – Request DTO for RFP document submission.
`Prism.ApiService/Features/System/SystemEndPoint.cs` – Nuclear reset endpoint truncating DB and signaling Python to wipe memory.
`Prism.ApiService/Hubs/DocumentHub.cs` – Empty SignalR hub definition for React clients to receive document processing events.
`Prism.ApiService/Migrations/20260318065814_InitialCreate.cs` – Initial EF Core migration defining the database schema.
`Prism.ApiService/Migrations/PrismDBContextModelSnapshot.cs` – EF Core model snapshot.
`Prism.ApiService/Properties/launchSettings.json` – Launch configuration for the C# API Gateway.
`Prism.ApiService/Services/FakeFileUploader.cs` – Mock implementation of a file uploader service.
`Prism.ApiService/Services/IAddChatDataBaseService.cs` – Interface for adding chat records to the database.
`Prism.ApiService/Services/IfileUploader.cs` – Interface for file uploading functionality.
`Prism.ApiService/Services/MinioStorageService.cs` – Service for handling file uploads to the MinIO storage bucket.
`Prism.ApiService/Services/RabbitMqListenerService.cs` – Background service consuming `document_processed_queue` and broadcasting via SignalR.
`Prism.ApiService/Services/RabbitMqSetupService.cs` – Utility for declaring RabbitMQ queues and exchanges on startup.
`Prism.AppHost/AppHost copy.cs.old` – Backup of previous AppHost configuration.
`Prism.AppHost/AppHost.cs` – Aspire orchestration builder defining containers, secrets, and dependency bindings.
`Prism.AppHost/appsettings.Development.json` – Development settings for the Aspire AppHost.
`Prism.AppHost/appsettings.json` – Application settings for the Aspire AppHost.
`Prism.PythonService/.env` – Local environment variables configuration for Python.
`Prism.PythonService/agent_service.py` – Core LangGraph state graph implementation for the CRAG agent.
`Prism.PythonService/ai_service.py` – LLM service wrapper for summarization and audio transcription.
`Prism.PythonService/api.py` – FastAPI entry points serving the LangGraph agent and chat history.
`Prism.PythonService/Dockerfile` – Docker image definition for the Python FastAPI service.
`Prism.PythonService/main.py` – Async background worker consuming RabbitMQ tasks for document ingestion and embedding.
`Prism.PythonService/memory_db.py` – PostgreSQL connection pool manager for LangGraph checkpoints.
`Prism.PythonService/pyproject.toml` – Python package configuration file for uv.
`Prism.PythonService/RAGService.py` – Qdrant vector database wrapper handling text chunking and embedding generation.
`Prism.PythonService/requirements.txt` – Dependency list for the Python services.
`Prism.ServiceDefaults/Extensions.cs` – Common service default configurations for Aspire observability and health checks.
`Prism.Web/eslint.config.js` – ESLint configuration for the React frontend.
`Prism.Web/index.html` – Entry HTML template for the Vite React application.
`Prism.Web/package.json` – Node.js dependencies and script definitions for the frontend.
`Prism.Web/tsconfig.json` – TypeScript configuration for the React application.
`Prism.Web/vite.config.ts` – Vite build and development server configuration.
`Prism.Web/src/App.css` – CSS styling for the main React application.
`Prism.Web/src/App.tsx` – Primary React component managing chat state, SignalR connection, and document uploads.
`Prism.Web/src/index.css` – Global CSS styles for the React frontend.
`Prism.Web/src/main.tsx` – React application bootstrapping entry point.

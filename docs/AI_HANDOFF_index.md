# TenderAI Reference Index

`TenderAI.ApiService/Contracts/TenderUploaded.cs` – DTO for publishing tender upload events to RabbitMQ.
`TenderAI.ApiService/Data/TenderDBContext.cs` – EF Core database context configuring PostgreSQL tables.
`TenderAI.ApiService/Data/TenderDBContextFactory .cs` – Factory for design-time DB context creation.
`TenderAI.ApiService/Data/Schemas/FileRecords.cs` – Schema representing individual files within a tender document chat.
`TenderAI.ApiService/Data/Schemas/PricingHistory.cs` – Schema for tracking historical pricing data (currently unused).
`TenderAI.ApiService/Data/Schemas/TenderDocument.cs` – Schema representing a parent chat and its associated tender documents.
`TenderAI.ApiService/Features/Chat/ChatEndPoint.cs` – API endpoints for routing chat questions to Python and fetching history.
`TenderAI.ApiService/Features/Chat/ChatRequest.cs` – Request/response DTOs for chat interactions.
`TenderAI.ApiService/Features/RfpSubmission/SubmitRfpEndPoint.cs` – Endpoints for handling document uploads and fetching user chat histories.
`TenderAI.ApiService/Features/RfpSubmission/SubmitRfpRequest.cs` – Request DTO for RFP document submission.
`TenderAI.ApiService/Features/System/SystemEndPoint.cs` – Nuclear reset endpoint truncating DB and signaling Python to wipe memory.
`TenderAI.ApiService/Hubs/DocumentHub.cs` – Empty SignalR hub definition for React clients to receive document processing events.
`TenderAI.ApiService/Migrations/20260318065814_InitialCreate.cs` – Initial EF Core migration defining the database schema.
`TenderAI.ApiService/Migrations/TenderDBContextModelSnapshot.cs` – EF Core model snapshot.
`TenderAI.ApiService/Properties/launchSettings.json` – Launch configuration for the C# API Gateway.
`TenderAI.ApiService/Services/FakeFileUploader.cs` – Mock implementation of a file uploader service.
`TenderAI.ApiService/Services/IAddChatDataBaseService.cs` – Interface for adding chat records to the database.
`TenderAI.ApiService/Services/IfileUploader.cs` – Interface for file uploading functionality.
`TenderAI.ApiService/Services/MinioStorageService.cs` – Service for handling file uploads to the MinIO storage bucket.
`TenderAI.ApiService/Services/RabbitMqListenerService.cs` – Background service consuming `document_processed_queue` and broadcasting via SignalR.
`TenderAI.ApiService/Services/RabbitMqSetupService.cs` – Utility for declaring RabbitMQ queues and exchanges on startup.
`TenderAI.AppHost/AppHost copy.cs.old` – Backup of previous AppHost configuration.
`TenderAI.AppHost/AppHost.cs` – Aspire orchestration builder defining containers, secrets, and dependency bindings.
`TenderAI.AppHost/appsettings.Development.json` – Development settings for the Aspire AppHost.
`TenderAI.AppHost/appsettings.json` – Application settings for the Aspire AppHost.
`TenderAI.PythonService/.env` – Local environment variables configuration for Python.
`TenderAI.PythonService/agent_service.py` – Core LangGraph state graph implementation for the CRAG agent.
`TenderAI.PythonService/ai_service.py` – LLM service wrapper for summarization and audio transcription.
`TenderAI.PythonService/api.py` – FastAPI entry points serving the LangGraph agent and chat history.
`TenderAI.PythonService/Dockerfile` – Docker image definition for the Python FastAPI service.
`TenderAI.PythonService/main.py` – Async background worker consuming RabbitMQ tasks for document ingestion and embedding.
`TenderAI.PythonService/memory_db.py` – PostgreSQL connection pool manager for LangGraph checkpoints.
`TenderAI.PythonService/pyproject.toml` – Python package configuration file for uv.
`TenderAI.PythonService/RAGService.py` – Qdrant vector database wrapper handling text chunking and embedding generation.
`TenderAI.PythonService/requirements.txt` – Dependency list for the Python services.
`TenderAI.ServiceDefaults/Extensions.cs` – Common service default configurations for Aspire observability and health checks.
`TenderAI.Web/eslint.config.js` – ESLint configuration for the React frontend.
`TenderAI.Web/index.html` – Entry HTML template for the Vite React application.
`TenderAI.Web/package.json` – Node.js dependencies and script definitions for the frontend.
`TenderAI.Web/tsconfig.json` – TypeScript configuration for the React application.
`TenderAI.Web/vite.config.ts` – Vite build and development server configuration.
`TenderAI.Web/src/App.css` – CSS styling for the main React application.
`TenderAI.Web/src/App.tsx` – Primary React component managing chat state, SignalR connection, and document uploads.
`TenderAI.Web/src/index.css` – Global CSS styles for the React frontend.
`TenderAI.Web/src/main.tsx` – React application bootstrapping entry point.

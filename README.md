# 🏢 TenderAI: Enterprise-Grade Document Intelligence Agent

![Architecture: Microservices](https://img.shields.io/badge/Architecture-Microservices-success)
![Orchestration: .NET Aspire](https://img.shields.io/badge/Orchestration-.NET_Aspire-purple)
![AI: LangGraph CRAG](https://img.shields.io/badge/AI-Corrective_RAG-blue)
![Quality: SonarQube](https://img.shields.io/badge/Code_Quality-SonarQube-orange)

TenderAI is a highly decoupled, event-driven AI Agent designed to analyze complex enterprise documents (RFPs, Tenders, Contracts). Moving beyond standard RAG wrappers, this system implements a **Corrective RAG (CRAG)** architecture with strict hallucination guardrails, intent routing, and real-time asynchronous document processing.

The entire distributed system is locally orchestrated using **.NET Aspire**, ensuring seamless container management, secure secret injection, and unified telemetry.

---

### 🏗️ Complete System Architecture (Current State)

![System Architecture](ProjectDoc/architecture.png)
*(This diagram represents the currently implemented, asynchronous event-driven workflow.)*

---

## ✨ Enterprise Features

* **🛡️ Hallucination Safeguards (Grounding Checker):** A dedicated LangGraph node audits the Agent's final response against the retrieved source chunks. If a claim cannot be verified, the UI actively warns the user with a "Caveat Banner."
* **⚡ Event-Driven Ingestion:** Uploaded documents are securely saved to **MinIO**, which triggers background extraction and embedding via **RabbitMQ**. The React UI receives real-time progress updates via **SignalR** websockets.
* **🎯 Intent Classification & HyDE:** A fast LLM acts as a "Bouncer," classifying user intent before executing costly searches. Queries are automatically rewritten into optimized keyword strings to maximize vector retrieval accuracy.
* **🧠 Persistent Native Memory:** Conversation state and tool-call history are natively managed and persisted using LangGraph's PostgreSQL Checkpointer.
* **🥇 Traceability & Observability:** Full LLM call tracing via **LangSmith** and system-wide orchestration logging via the .NET Aspire Dashboard.
* **✅ Code Quality:** Integrated **SonarQube** analysis in the build pipeline to maintain high enterprise coding standards.

---

## 🏗️ Architecture Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Orchestrator** | `.NET 8 Aspire` | Manages Docker containers, networking, and secure secret injection. |
| **Frontend** | `React`, `TypeScript`, `Vite` | Real-time UI, Markdown rendering, Source citations. |
| **API Gateway** | `C# .NET 8`, `SignalR` | Proxy routing, WebSocket management, EF Core database operations. |
| **AI Services** | `Python 3.13`, `FastAPI`, `uv` | Runs the LangGraph state graph and asynchronous background workers. |
| **LLM Engine** | `Google Gemini` | Tool-calling (Flash) and fast classification tasks (Flash-Lite). |
| **Infrastructure** | `PostgreSQL`, `Qdrant`, `MinIO` | Relational data/memory, Vector storage, and S3-compatible Blob storage. |
| **Message Broker** | `RabbitMQ` | Decouples document uploads from heavy AI embedding tasks. |
| **Caching** | `Redis` | High-speed data caching. |

---

## 🚀 Getting Started

### Prerequisites
* **Docker Desktop** (Must be running to spin up Postgres, Qdrant, MinIO, RabbitMQ, and Redis)
* **.NET 8.0 SDK**
* **Python 3.13** (with `uv` package manager installed)
* **Node.js** (v18+)

### 🔐 Configuration & Secrets Management
For enterprise security, API keys and database credentials are **not** stored in `.env` files. They are securely injected via .NET Aspire using the Secret Manager (`dotnet user-secrets`).

**1. Setup Aspire Secrets:**
Navigate to the `TenderAI.AppHost` project directory in your terminal and run the following commands, replacing the placeholders with your actual values:

```bash
cd TenderAI.AppHost

# AI Keys
dotnet user-secrets set "GoogleApiKey" "your-gemini-api-key"

# Database & Infra Credentials (Create your own strong passwords)
dotnet user-secrets set "Parameters:rabbitmquser" "admin"
dotnet user-secrets set "Parameters:rabbitmqpass" "your-secure-password"
dotnet user-secrets set "Parameters:MinioUser" "admin"
dotnet user-secrets set "Parameters:MinioSecret" "your-secure-password"
dotnet user-secrets set "Parameters:QdrantApiKey" "your-secure-qdrant-key"

**2. Setup LangSmith Observability (Optional but Recommended):**
Create a `.env` file in the root of your `TenderAI.PythonService` directory to enable LangGraph tracing:
```env
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=[https://api.smith.langchain.com](https://api.smith.langchain.com)
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT="TenderAI"

```
---

## 🔮 Future Tasks

These items are on the immediate roadmap to complete the full enterprise design spec and enhance system performance and reliability.

- [ ] **🚀 Synchronous Direct Querying:** Implement **gRPC** to allow the frontend to bypass RabbitMQ and directly query the Python AI service for low-latency tasks (e.g., summarizing an already-opened document without searching).
- [ ] **🛡️ Fault Tolerance:** Implement **Dead Letter Queues (DLQ)** in RabbitMQ to automatically capture and handle failed document processing jobs without data loss.
- [ ] **⚡ Low-Latency Caching:** Implement **Redis** to cache common AI responses in the C# Gateway API, drastically reducing cost and latency for repeated user questions.

---
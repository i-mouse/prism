# Prism.ApiService

ASP.NET Core (.NET 10) API gateway: paper upload, chat streaming (SSE), progress over SignalR, and claim reads from PostgreSQL with EF Core. It hands new papers to the Python worker over RabbitMQ.

- Run: started by Prism.AppHost (root README, Quick start).
- Tests: `dotnet test Prism.ApiService.Tests` from the repo root.

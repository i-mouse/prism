# Prism.AppHost

.NET Aspire orchestrator. `AppHost.cs` starts the UI, the API gateway, the Python worker and the containers they need, and wires their settings.

- Run: see the root README, Quick start. Setup and troubleshooting: `docs/RUNBOOK.md`.
- Publish settings: copy `.deploy.env.template` to `.deploy.env` (gitignored). Azure design: `docs/deployment-and-environment-architecture.md` (environment decommissioned 2026-09-28).

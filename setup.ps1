# Prism one-time setup — run after a fresh Windows install or clone.
# Installs host tools (winget) and prompts for secrets.

Write-Host "=== Prism setup ===" -ForegroundColor Cyan
Write-Host ""

# 1. Loosen script policy so uv/others can run
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# 2. Install host tools (idempotent — skips what's already there)
Write-Host "Installing host tools via winget..." -ForegroundColor Cyan
winget install --id Docker.DockerDesktop    --silent --accept-source-agreements --accept-package-agreements
winget install --id Microsoft.DotNet.SDK.10 --silent --accept-source-agreements --accept-package-agreements
winget install --id OpenJS.NodeJS.LTS       --silent --accept-source-agreements --accept-package-agreements
winget install --id astral-sh.uv            --silent --accept-source-agreements --accept-package-agreements

# 3. Prompt for secrets and store in dotnet user-secrets (NOT in the repo)
Write-Host ""
Write-Host "Setting user-secrets (stored in %APPDATA%, never in git)..." -ForegroundColor Cyan
Push-Location "$PSScriptRoot\Prism.AppHost"

$gemini = Read-Host "Gemini API key (get one at https://aistudio.google.com/apikey)"
dotnet user-secrets set "GoogleApiKey" $gemini | Out-Null

$rabbitPass = Read-Host "RabbitMQ password (Enter for default)"
if ([string]::IsNullOrWhiteSpace($rabbitPass)) { $rabbitPass = "PrismLocal!2026" }

$minioPass = Read-Host "MinIO password (Enter for default)"
if ([string]::IsNullOrWhiteSpace($minioPass)) { $minioPass = "PrismLocal!2026" }

$qdrantKey = Read-Host "Qdrant API key (Enter for default)"
if ([string]::IsNullOrWhiteSpace($qdrantKey)) { $qdrantKey = "PrismLocalQdrant!2026" }

dotnet user-secrets set "Parameters:rabbitmquser" "admin"     | Out-Null
dotnet user-secrets set "Parameters:rabbitmqpass" $rabbitPass | Out-Null
dotnet user-secrets set "Parameters:MinioUser"    "admin"     | Out-Null
dotnet user-secrets set "Parameters:MinioSecret"  $minioPass  | Out-Null
dotnet user-secrets set "Parameters:QdrantApiKey" $qdrantKey  | Out-Null

Pop-Location

Write-Host ""
Write-Host "Setup done." -ForegroundColor Green
Write-Host "Next: CLOSE this shell, open a new one, start Docker Desktop, then run:" -ForegroundColor Yellow
Write-Host "    .\dev.ps1" -ForegroundColor Yellow
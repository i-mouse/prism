# Prism daily runner - one command to start everything.
Push-Location $PSScriptRoot

$missing = @()
if (-not (Get-Command uv     -ErrorAction SilentlyContinue)) { $missing += "uv" }
if (-not (Get-Command node   -ErrorAction SilentlyContinue)) { $missing += "node" }
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { $missing += "dotnet" }
try   { docker info 2>$null | Out-Null; if ($LASTEXITCODE -ne 0) { $missing += "Docker Desktop (not running)" } }
catch { $missing += "Docker Desktop (not running)" }

if ($missing.Count -gt 0) {
    Write-Host "Missing: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Run .\setup.ps1 first, and make sure Docker Desktop is running." -ForegroundColor Yellow
    Pop-Location
    exit 1
}

if (-not (Test-Path ".\Prism.Web\node_modules")) {
    Write-Host "First run - installing React deps..." -ForegroundColor Cyan
    Push-Location ".\Prism.Web"
    npm install
    Pop-Location
}

Push-Location ".\Prism.AppHost"
dotnet run
Pop-Location
Pop-Location

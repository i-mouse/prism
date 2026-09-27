# H:\Work projects\Prism\Prism.Web\deploy.ps1
$ErrorActionPreference = "Stop"

Write-Host "== Prism.Web deploy ==" -ForegroundColor Cyan

# 1. Preflight: verify we're on main and clean
$branch = git rev-parse --abbrev-ref HEAD
if ($branch -ne "main") {
    Write-Error "Not on main branch (on: $branch). Aborting."
}

$status = git status --porcelain
if ($status) {
    Write-Error "Working tree not clean. Commit or stash first."
}

# 2. Pull latest
git pull

# 2b. Resolve the commit being built for an immutable image tag
$sha = git rev-parse --short HEAD
if (-not $sha) {
    Write-Error "Could not resolve short commit hash. Aborting."
}
Write-Host "Building commit $sha" -ForegroundColor Yellow

# 3. Preflight: verify nginx.conf listens on 7000
$nginxCheck = Select-String -Path "nginx.conf" -Pattern "listen 7000;"
if (-not $nginxCheck) {
    Write-Error "nginx.conf must listen on 7000 to match Azure targetPort. Aborting."
}

# 4. Build fresh (no cache to avoid stale nginx.conf)
Write-Host "Building fresh Docker image (no cache)..." -ForegroundColor Yellow
docker build --no-cache `
  -t prismenvacrudnvqoy3me2bs.azurecr.io/prism-ai-reactui:latest `
  -t prismenvacrudnvqoy3me2bs.azurecr.io/prism-ai-reactui:$sha .

# 5. Verify image contents BEFORE push
$imageNginx = docker run --rm --entrypoint sh prismenvacrudnvqoy3me2bs.azurecr.io/prism-ai-reactui:latest -c "grep listen /etc/nginx/conf.d/default.conf"
if ($imageNginx -notmatch "listen 7000") {
    Write-Error "Image nginx.conf does not listen on 7000. Aborting push. Got: $imageNginx"
}
Write-Host "Image nginx config verified: $imageNginx" -ForegroundColor Green

# 6. Push
Write-Host "Pushing to ACR..." -ForegroundColor Yellow
az acr login --name prismenvacrudnvqoy3me2bs
docker push prismenvacrudnvqoy3me2bs.azurecr.io/prism-ai-reactui:latest
docker push prismenvacrudnvqoy3me2bs.azurecr.io/prism-ai-reactui:$sha

# 7. Deploy with unique revision suffix
$suffix = Get-Date -Format "yyyyMMddHHmmss"
Write-Host "Deploying revision $suffix..." -ForegroundColor Yellow

# Pin ingress target port before the revision deploy: aspire deploy resets it to
# 80 and nothing restored it, so ingress silently pointed at the wrong port.
# Note: containerapp update takes no --target-port; ingress is app-scoped config.
az containerapp ingress update `
  --name prism-ai-reactui `
  --resource-group prism-rg `
  --target-port 7000

az containerapp update `
  --name prism-ai-reactui `
  --resource-group prism-rg `
  --image prismenvacrudnvqoy3me2bs.azurecr.io/prism-ai-reactui:latest `
  --revision-suffix $suffix

# 8. Wait and verify health
Write-Host "Waiting 60s for revision to become healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 60

az containerapp revision list `
  --name prism-ai-reactui `
  --resource-group prism-rg `
  --query "[].{name:name, active:properties.active, traffic:properties.trafficWeight, health:properties.healthState}" `
  -o table

Write-Host "== Deploy complete. Verify at https://prism-ai-reactui.nicesky-c6f0b846.centralindia.azurecontainerapps.io/ ==" -ForegroundColor Cyan
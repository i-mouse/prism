# Prism.PythonService\eval-live.ps1
$envFile = Join-Path $PSScriptRoot ".env"
$originalContent = Get-Content -Path $envFile -Raw

try {
    $modifiedContent = $originalContent -replace '(?m)^PRISM_DB_PASSWORD=.*$', '# PRISM_DB_PASSWORD (disabled for live-DB eval run)'
    Set-Content -Path $envFile -Value $modifiedContent -NoNewline

    $env:PRISM_DB_HOST = "postgres-udnvqoy3me2bs.postgres.database.azure.com"
    $env:PRISM_DB_USERNAME = "nitin8764_live.com#EXT#@nitin8764live.onmicrosoft.com"
    $env:PRISM_DB_PORT = "5432"

    Push-Location $PSScriptRoot
    uv run python -m eval.matrix_runner --source db
    Pop-Location
}
finally {
    Set-Content -Path $envFile -Value $originalContent -NoNewline
}
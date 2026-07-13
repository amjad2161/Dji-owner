# SkyCore Singularity launcher (Windows / PowerShell)
# Builds the GCS, sets up the backend, and runs the WHOLE system as one process on http://localhost:8080
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "== SkyCore Singularity ==" -ForegroundColor Green

# 1. Build the GCS if not already built
if (-not (Test-Path "$root\gcs-web\dist\index.html")) {
    Write-Host "Building GCS (npm install + build)..." -ForegroundColor Yellow
    Push-Location "$root\gcs-web"
    npm install
    npm run build
    Pop-Location
}

# 2. Python venv + backend deps
$py = "$root\backend\venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Creating Python venv..." -ForegroundColor Yellow
    python -m venv "$root\backend\venv"
}
& "$root\backend\venv\Scripts\pip.exe" install -q -r "$root\backend\requirements.txt"

# 3. Run the single unified server (serves UI + telemetry/threat APIs + real AUKF/LQR/C-UAS)
Write-Host "SkyCore up  ->  http://localhost:8080" -ForegroundColor Cyan
& $py "$root\backend\serve.py"

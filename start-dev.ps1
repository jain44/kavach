# Kavach Full-Stack Dev Startup Script
# Starts PostgreSQL (via Docker), FastAPI backend, and Vite frontend in one go.
#
# Prerequisites:
#   - Docker Desktop running (for Postgres)
#   - Python 3.11+ with virtualenv in sentinel-backend\venv
#   - Node 20+ installed
#
# Usage:
#   .\start-dev.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Kavach Full-Stack Dev Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ROOT = $PSScriptRoot

# ─── Step 1: Start PostgreSQL via Docker ──────────────────────────────────────
Write-Host "[1/4] Starting PostgreSQL (Docker)..." -ForegroundColor Yellow

$pgRunning = docker ps --filter "name=kavach_postgres" --format "{{.Names}}" 2>$null
if ($pgRunning -eq "kavach_postgres") {
    Write-Host "      PostgreSQL already running." -ForegroundColor Green
} else {
    docker run -d `
        --name kavach_postgres `
        --restart unless-stopped `
        -e POSTGRES_USER=kavach `
        -e POSTGRES_PASSWORD=kavach123 `
        -e POSTGRES_DB=kavach_db `
        -p 5432:5432 `
        postgres:16-alpine | Out-Null

    Write-Host "      Waiting for Postgres to be ready..." -ForegroundColor Gray
    $retries = 0
    do {
        Start-Sleep -Seconds 2
        $ready = docker exec kavach_postgres pg_isready -U kavach -d kavach_db 2>$null
        $retries++
    } while ($LASTEXITCODE -ne 0 -and $retries -lt 15)

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: PostgreSQL did not start in time." -ForegroundColor Red
        exit 1
    }
    Write-Host "      PostgreSQL ready." -ForegroundColor Green
}

# ─── Step 2: Backend — migrate + seed + run ────────────────────────────────────
Write-Host ""
Write-Host "[2/4] Preparing backend..." -ForegroundColor Yellow

$backendDir = Join-Path $ROOT "sentinel-backend"
$venvPython = Join-Path $backendDir "venv\Scripts\python.exe"
$venvActivate = Join-Path $backendDir "venv\Scripts\Activate.ps1"

# Create venv if missing
if (-not (Test-Path $venvPython)) {
    Write-Host "      Creating Python virtual environment..." -ForegroundColor Gray
    python -m venv (Join-Path $backendDir "venv")
}

# Install / update dependencies
Write-Host "      Installing Python dependencies..." -ForegroundColor Gray
& $venvPython -m pip install --quiet -r (Join-Path $backendDir "requirements.txt")

# Set DATABASE_URL for all subsequent commands
$env:DATABASE_URL = "postgresql+psycopg://kavach:kavach123@localhost:5432/kavach_db"
$env:KAVACH_SECRET_KEY = "36eadbd8d997ba82d14837e2bee9de87617b4d9698ea0d06d22c63d5ba9b1143"
$env:KAVACH_ALLOWED_ORIGINS = "http://localhost:5173,http://localhost:3000"

# Run Alembic migrations
Write-Host "      Running DB migrations..." -ForegroundColor Gray
Push-Location $backendDir
& $venvPython -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Alembic migration failed." -ForegroundColor Red
    Pop-Location
    exit 1
}
Write-Host "      Running DB seed..." -ForegroundColor Gray
& $venvPython -m db.seed
Pop-Location

Write-Host "      Backend ready." -ForegroundColor Green

# ─── Step 3: Start backend in background ──────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Starting FastAPI backend (port 8000)..." -ForegroundColor Yellow

$backendJob = Start-Job -ScriptBlock {
    param($dir, $python, $dbUrl, $secret, $origins)
    $env:DATABASE_URL = $dbUrl
    $env:KAVACH_SECRET_KEY = $secret
    $env:KAVACH_ALLOWED_ORIGINS = $origins
    Set-Location $dir
    & $python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $backendDir, $venvPython, $env:DATABASE_URL, $env:KAVACH_SECRET_KEY, $env:KAVACH_ALLOWED_ORIGINS

Write-Host "      Backend starting (PID job: $($backendJob.Id))..." -ForegroundColor Gray
Start-Sleep -Seconds 4

# ─── Step 4: Start frontend ───────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Starting Vite frontend (port 5173)..." -ForegroundColor Yellow

$frontendDir = Join-Path $ROOT "sentinel-frontend"
Push-Location $frontendDir

if (-not (Test-Path "node_modules")) {
    Write-Host "      Installing npm packages..." -ForegroundColor Gray
    npm install --silent
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Kavach is running!" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend:  http://localhost:5173" -ForegroundColor White
Write-Host "  Backend:   http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor White
Write-Host "  DB:        localhost:5432/kavach_db" -ForegroundColor White
Write-Host ""
Write-Host "  Login credentials:" -ForegroundColor Gray
Write-Host "    risk_officer / kavach123" -ForegroundColor Gray
Write-Host "    rm           / kavach123" -ForegroundColor Gray
Write-Host "    cro          / kavach123" -ForegroundColor Gray
Write-Host "    compliance   / kavach123" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C to stop frontend." -ForegroundColor Gray
Write-Host "  Run: Stop-Job $($backendJob.Id) to stop backend." -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

npm run dev
Pop-Location

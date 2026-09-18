<#
Starts FUSAA locally without opening a connection to the hosted database.

The project .env can contain both local and hosting settings. This script
sets process-only values, runs migrations on the local SQLite file, then
starts the development server. It never changes the hosted database.
#>
param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$env:DATABASE_URL = "sqlite:///./fusaa.db"
$env:STORAGE_DIR = "./storage"
$env:ENVIRONMENT = "development"

Push-Location $backendRoot
try {
    py -3.11 -m alembic upgrade head
    py -3.11 -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
}
finally {
    Pop-Location
}

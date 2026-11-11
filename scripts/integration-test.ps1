# SmartBook API integration tests (auth + Account Set against local MySQL).
# Prerequisites: MySQL (platform_registry + smartbook_shared), Redis, Python deps.
param(
    [string]$ApiBase = "",
    [switch]$SkipHealthCheck
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DevEnvFile = Join-Path $PSScriptRoot "dev.env"

function Import-DevEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"')
            if ($name) { Set-Item -Path "env:$name" -Value $value }
        }
    }
}

Import-DevEnv -Path $DevEnvFile
$env:PIP_CONFIG_FILE = Join-Path $Root "backend\pip.conf"
$env:PYTHONPATH = Join-Path $Root "backend"
$env:INTEGRATION = "1"
$env:ENVIRONMENT = "development"
$env:EMAIL_PROVIDER = "console"
if (-not $env:SHARED_TENANT_DB_URL) {
    $env:SHARED_TENANT_DB_URL = "mysql+aiomysql://smartbook:smartbook@localhost:3306/smartbook_shared"
}
Remove-Item Env:TENANT_DB_URL -ErrorAction SilentlyContinue

Write-Host "SmartBook API integration tests" -ForegroundColor Cyan
Write-Host "  SHARED_TENANT_DB_URL=$($env:SHARED_TENANT_DB_URL)" -ForegroundColor DarkGray
Write-Host "  DATABASE_URL=$($env:DATABASE_URL)" -ForegroundColor DarkGray

if (-not $SkipHealthCheck -and $ApiBase) {
    Write-Host "==> Live API health: $ApiBase/health" -ForegroundColor Yellow
    try {
        $h = curl.exe --max-time 5 -s "$ApiBase/health"
        Write-Host "    $h"
    } catch {
        Write-Warning "Live API not reachable at $ApiBase (ASGI in-process tests still run)."
    }
}

# Frontend bundle sanity: API_BASE_URL must be inlined (not gated on process)
$bundle = Join-Path $Root "frontend\.dev\assets\app.js"
if (Test-Path $bundle) {
    Write-Host "==> Frontend bundle API base check" -ForegroundColor Yellow
    $line = Select-String -Path $bundle -Pattern 'var DEFAULT_BASE\s*=' | Select-Object -First 1
    if (-not $line) {
        throw "frontend bundle missing DEFAULT_BASE - run npm run dev / build first"
    }
    if ($line.Line -match 'typeof process') {
        throw "frontend bundle still gates API_BASE_URL on process - rpc.js bug regressed"
    }
    if ($line.Line -match 'DEFAULT_BASE = ""' -or $line.Line -match "DEFAULT_BASE = ''") {
        throw "frontend DEFAULT_BASE is empty - set API_BASE_URL when running npm run dev"
    }
    Write-Host "    $($line.Line.Trim())" -ForegroundColor DarkGray
} else {
    Write-Warning "No frontend/.dev/assets/app.js - skip frontend bundle check"
}

Write-Host "==> pytest -m integration" -ForegroundColor Yellow
Push-Location (Join-Path $Root "backend")
try {
    # Prefer integration pytest.ini (session-scoped asyncio loop for aiomysql)
    python -m pytest tests/integration -m integration -v --tb=short -c tests/integration/pytest.ini
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "Integration tests passed." -ForegroundColor Green

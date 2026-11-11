# Local build (no Docker). Dockerfiles and docker-compose remain for deployment.
param(
    [switch]$SkipTests,
    [switch]$SkipLint
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PIP_CONFIG_FILE = Join-Path $Root "backend\pip.conf"

Write-Host "==> SmartBook local build (no Docker)" -ForegroundColor Cyan

Write-Host "`n==> Frontend: npm run build" -ForegroundColor Yellow
Push-Location "$Root\frontend"
try {
    if (-not (Test-Path "node_modules")) {
        npm ci
    }
    npm run build
    if (-not (Test-Path "dist\index.html")) {
        throw "Frontend build failed: dist/index.html not found"
    }
}
finally {
    Pop-Location
}

Write-Host "`n==> Backend: install + verify" -ForegroundColor Yellow
Push-Location "$Root\backend"
try {
    # Clear PYTHONPATH so pip does not pick up backend/platform/ instead of stdlib.
    $env:PYTHONPATH = ""
    python -m pip install -e ".[dev]"
    $pipOk = ($LASTEXITCODE -eq 0)
    $env:PYTHONPATH = "."

    if (-not $pipOk) {
        Write-Warning "pip install failed (backend requires Python 3.11+). Continuing with PYTHONPATH=. for tests."
    }

    if (-not $SkipLint) {
        Write-Host "`n==> Backend: ruff check" -ForegroundColor Yellow
        ruff check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if (-not $SkipTests) {
        Write-Host "`n==> Backend: pytest" -ForegroundColor Yellow
        python -m pytest tests/ -q --tb=line
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if ($pipOk) {
        python -c "from app.main import app; print('Backend import OK')"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}
finally {
    Pop-Location
}

Write-Host "`nBuild complete." -ForegroundColor Green
Write-Host "  Frontend -> frontend/dist/"
Write-Host "  Backend  -> editable install in current Python env"
Write-Host "To use Docker builds later: docker compose build"

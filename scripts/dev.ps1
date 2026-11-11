# Local development (no Docker). Starts backend hot-reload + frontend dev server.
param(
    [ValidateSet("all", "backend", "frontend")]
    [string]$Target = "all",

    [int]$BackendPort = 8000,
    [int]$FrontendPort = 8080,
    [switch]$NoNewWindow
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$DevEnvFile = Join-Path $PSScriptRoot "dev.env"
$env:PIP_CONFIG_FILE = Join-Path $Root "backend\pip.conf"

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

function Set-DevDefaults {
    if (-not $env:ENVIRONMENT) { $env:ENVIRONMENT = "development" }
    if (-not $env:PLATFORM_DB_TYPE) { $env:PLATFORM_DB_TYPE = "mysql" }
    if (-not $env:DATABASE_URL) {
        $env:DATABASE_URL = "mysql+aiomysql://smartbook:smartbook@localhost:3306/platform_registry"
    }
    if (-not $env:REDIS_URL) { $env:REDIS_URL = "redis://localhost:6379/0" }
    if (-not $env:VAULT_ADDR) { $env:VAULT_ADDR = "http://localhost:8200" }
    if (-not $env:VAULT_TOKEN) { $env:VAULT_TOKEN = "dev-root-token" }
    if (-not $env:JWT_ALGORITHM) { $env:JWT_ALGORITHM = "HS256" }
    if (-not $env:EMAIL_PROVIDER) { $env:EMAIL_PROVIDER = "console" }
    if (-not $env:SMARTBOOK_MCP_ENABLED) { $env:SMARTBOOK_MCP_ENABLED = "true" }
}

Import-DevEnv -Path $DevEnvFile
Set-DevDefaults

function Test-DevPrerequisites {
    param([string]$Need)
    if ($Need -in @("all", "backend")) {
        $env:PYTHONPATH = ""
        python -c "import uvicorn" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning @"
uvicorn not found. Install with:
  `$env:PYTHONPATH=''; python -m pip install `"uvicorn[standard]`"
"@
        }
    }
    if ($Need -in @("all", "frontend")) {
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
            throw "npm is required for frontend dev. Install Node.js 20+."
        }
    }
}

Test-DevPrerequisites -Need $Target

$backendProc = $null

function Start-BackendDev {
    param([int]$Port)
    $backendDir = "$Root\backend"
# Run from backend with PYTHONPATH so `platform.*` imports resolve; stdlib
# platform APIs are re-exported by backend/platform/__init__.py.
$uvicornArgs = @(
    "-m", "uvicorn", "app.main:app",
    "--reload", "--host", "127.0.0.1", "--port", "$Port"
)
$cmd = @(
    "cd '$backendDir'",
    "`$env:PYTHONPATH='$backendDir'",
    "`$env:ENVIRONMENT='$($env:ENVIRONMENT)'",
    "`$env:EMAIL_PROVIDER='$($env:EMAIL_PROVIDER)'",
    "`$env:SMARTBOOK_MCP_ENABLED='$($env:SMARTBOOK_MCP_ENABLED)'",
    "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port"
) -join "; "

if ($NoNewWindow) {
    Write-Host "==> Backend: http://127.0.0.1:$Port (reload)" -ForegroundColor Yellow
    $env:PYTHONPATH = $backendDir
    return Start-Process -PassThru -NoNewWindow -FilePath "python" -ArgumentList $uvicornArgs -WorkingDirectory $backendDir
}

Write-Host "==> Backend: new window -> http://127.0.0.1:$Port" -ForegroundColor Yellow
return Start-Process -PassThru powershell -ArgumentList @("-NoExit", "-Command", $cmd)
}

function Start-FrontendDev {
    param([int]$Port, [int]$ApiPort)
    Push-Location "$Root\frontend"
    try {
        if (-not (Test-Path "node_modules")) {
            Write-Host "==> Frontend: npm ci" -ForegroundColor Yellow
            npm ci
        }

        $env:PORT = "$Port"
        $env:API_BASE_URL = "http://127.0.0.1:$ApiPort"
        Remove-Item Env:DEV_BOOTSTRAP -ErrorAction SilentlyContinue

        Write-Host "==> Frontend: http://127.0.0.1:$Port (watch)" -ForegroundColor Yellow
        Write-Host "    API proxy target: $($env:API_BASE_URL)" -ForegroundColor DarkGray
        Write-Host "    Auth: real register/login (same as test/prod)" -ForegroundColor DarkGray
        npm run dev
    }
    finally {
        Pop-Location
    }
}

Write-Host "SmartBook development mode (no Docker)" -ForegroundColor Cyan
if (-not (Test-Path $DevEnvFile)) {
    Write-Host "Tip: copy scripts/dev.env.example -> scripts/dev.env to customize env." -ForegroundColor DarkGray
}

try {
    if ($Target -in @("all", "backend")) {
        $backendProc = Start-BackendDev -Port $BackendPort
        if ($Target -eq "all") { Start-Sleep -Seconds 2 }
    }

    if ($Target -in @("all", "frontend")) {
        Start-FrontendDev -Port $FrontendPort -ApiPort $BackendPort
    }
    elseif ($Target -eq "backend" -and $backendProc) {
        Write-Host "Backend running. Press Enter to stop..." -ForegroundColor Green
        Read-Host | Out-Null
    }
}
finally {
    if ($backendProc -and -not $backendProc.HasExited) {
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}

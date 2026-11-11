# Run platform (registry) migrations — PostgreSQL or MySQL.
param(
    [ValidateSet("upgrade", "current", "history")]
    [string]$Action = "upgrade"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:PIP_CONFIG_FILE = Join-Path $Root "backend\pip.conf"
$env:MIGRATION_SCOPE = "platform"
$env:PYTHONPATH = ""

if (-not $env:PLATFORM_DB_URL -and -not $env:DATABASE_URL) {
    if ($env:PLATFORM_DB_TYPE -eq "postgresql") {
        $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/platform_registry"
    } else {
        $env:DATABASE_URL = "mysql+aiomysql://smartbook:smartbook@localhost:3306/platform_registry"
    }
}

Push-Location $Root
try {
    switch ($Action) {
        # Platform and tenant revisions are independent Alembic heads; pin platform tip.
        "upgrade" {
            if ($env:MIGRATION_SCOPE -eq "tenant") {
                python -m alembic -c migrations/alembic.ini upgrade heads
            } else {
                python -m alembic -c migrations/alembic.ini upgrade 0002
            }
        }
        "current" { python -m alembic -c migrations/alembic.ini current }
        "history" { python -m alembic -c migrations/alembic.ini history }
    }
}
finally {
    Pop-Location
}

#!/usr/bin/env bash
# Run platform (registry) migrations — PostgreSQL or MySQL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PIP_CONFIG_FILE="$ROOT/backend/pip.conf"
export MIGRATION_SCOPE=platform
export PYTHONPATH=""

ACTION="${1:-upgrade}"

if [ -z "${PLATFORM_DB_URL:-}" ] && [ -z "${DATABASE_URL:-}" ]; then
  if [ "${PLATFORM_DB_TYPE:-mysql}" = "postgresql" ]; then
    export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/platform_registry"
  else
    export DATABASE_URL="mysql+aiomysql://smartbook:smartbook@localhost:3306/platform_registry"
  fi
fi

cd "$ROOT"
case "$ACTION" in
  upgrade) python -m alembic -c migrations/alembic.ini upgrade head ;;
  current) python -m alembic -c migrations/alembic.ini current ;;
  history) python -m alembic -c migrations/alembic.ini history ;;
  *) echo "Usage: $0 [upgrade|current|history]" >&2; exit 1 ;;
esac

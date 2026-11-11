#!/usr/bin/env bash
# SmartBook API integration tests (auth + Account Set against local MySQL).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PIP_CONFIG_FILE="$ROOT/backend/pip.conf"
export PYTHONPATH="$ROOT/backend"
export INTEGRATION=1
export ENVIRONMENT="${ENVIRONMENT:-development}"
export EMAIL_PROVIDER="${EMAIL_PROVIDER:-console}"
export SHARED_TENANT_DB_URL="${SHARED_TENANT_DB_URL:-mysql+aiomysql://smartbook:smartbook@localhost:3306/smartbook_shared}"
unset TENANT_DB_URL || true

if [ -f "$ROOT/scripts/dev.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/scripts/dev.env"
  set +a
fi

echo "SmartBook API integration tests"
cd "$ROOT/backend"
python -m pytest tests/integration -m integration -v --tb=short -c tests/integration/pytest.ini
echo "Integration tests passed."

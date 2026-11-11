#!/usr/bin/env bash
# Local build (no Docker). Dockerfiles and docker-compose remain for deployment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PIP_CONFIG_FILE="$ROOT/backend/pip.conf"
SKIP_TESTS=false
SKIP_LINT=false

for arg in "$@"; do
  case "$arg" in
    --skip-tests) SKIP_TESTS=true ;;
    --skip-lint) SKIP_LINT=true ;;
  esac
done

echo "==> SmartBook local build (no Docker)"

echo ""
echo "==> Frontend: npm run build"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm ci
fi
npm run build
test -f dist/index.html

echo ""
echo "==> Backend: install + verify"
cd "$ROOT/backend"
PYTHONPATH="" python -m pip install -e ".[dev]"
pip_ok=0
if [ $? -ne 0 ]; then
  pip_ok=1
  echo "WARNING: pip install failed (backend requires Python 3.11+). Continuing with PYTHONPATH=. for tests." >&2
fi
export PYTHONPATH=.

if [ "$SKIP_LINT" = false ]; then
  echo ""
  echo "==> Backend: ruff check"
  ruff check .
fi

if [ "$SKIP_TESTS" = false ]; then
  echo ""
  echo "==> Backend: pytest"
  python -m pytest tests/ -q --tb=line
fi

if [ "$pip_ok" -eq 0 ]; then
  python -c "from app.main import app; print('Backend import OK')"
fi

echo ""
echo "Build complete."
echo "  Frontend -> frontend/dist/"
echo "  Backend  -> editable install in current Python env"
echo "To use Docker builds later: docker compose build"

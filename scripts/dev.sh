#!/usr/bin/env bash
# Local development (no Docker). Starts backend hot-reload + frontend dev server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PIP_CONFIG_FILE="$ROOT/backend/pip.conf"
TARGET="all"
BACKEND_PORT=8000
FRONTEND_PORT=8080
BACKEND_PID=""

usage() {
  cat <<'EOF'
Usage: ./scripts/dev.sh [options]

Options:
  --backend-only     Start backend only
  --frontend-only    Start frontend only
  --backend-port N   Backend port (default 8000)
  --frontend-port N  Frontend dev server port (default 8080)
  -h, --help         Show this help
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --backend-only) TARGET="backend" ;;
    --frontend-only) TARGET="frontend" ;;
    --backend-port) BACKEND_PORT="$2"; shift ;;
    --frontend-port) FRONTEND_PORT="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

load_env() {
  local file="$ROOT/scripts/dev.env"
  [ -f "$file" ] || return 0
  set -a
  # shellcheck disable=SC1090
  source "$file"
  set +a
}

set_defaults() {
  export ENVIRONMENT="${ENVIRONMENT:-development}"
  export DATABASE_URL="${DATABASE_URL:-mysql+aiomysql://smartbook:smartbook@localhost:3306/platform_registry}"
  export PLATFORM_DB_TYPE="${PLATFORM_DB_TYPE:-mysql}"
  export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
  export VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
  export VAULT_TOKEN="${VAULT_TOKEN:-dev-root-token}"
  export JWT_ALGORITHM="${JWT_ALGORITHM:-HS256}"
}

cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

load_env
set_defaults

if [ "$TARGET" = "all" ] || [ "$TARGET" = "backend" ]; then
  if ! python -c "import uvicorn" 2>/dev/null; then
    echo "WARNING: uvicorn not found. Install backend deps first (Python 3.11+ recommended):" >&2
    echo "  cd backend && PYTHONPATH= python -m pip install -e \".[dev]\"" >&2
  fi
fi

if [ "$TARGET" = "all" ] || [ "$TARGET" = "frontend" ]; then
  command -v npm >/dev/null 2>&1 || { echo "npm is required for frontend dev" >&2; exit 1; }
fi

echo "SmartBook development mode (no Docker)"
if [ ! -f "$ROOT/scripts/dev.env" ]; then
  echo "Tip: copy scripts/dev.env.example -> scripts/dev.env to customize env."
fi

start_backend() {
  echo "==> Backend: http://127.0.0.1:$BACKEND_PORT (reload)"
  cd "$ROOT"
  PYTHONPATH="$ROOT/backend" python -m uvicorn app.main:app \
    --reload --host 127.0.0.1 --port "$BACKEND_PORT" &
  BACKEND_PID=$!
}

start_frontend() {
  cd "$ROOT/frontend"
  if [ ! -d node_modules ]; then
    echo "==> Frontend: npm ci"
    npm ci
  fi
  export PORT="$FRONTEND_PORT"
  export API_BASE_URL="http://127.0.0.1:$BACKEND_PORT"
  unset DEV_BOOTSTRAP || true
  echo "==> Frontend: http://127.0.0.1:$FRONTEND_PORT (watch)"
  echo "    API target: $API_BASE_URL"
  echo "    Auth: real register/login (same as test/prod)"
  npm run dev
}

case "$TARGET" in
  all)
    start_backend
    sleep 2
    start_frontend
    ;;
  backend)
    start_backend
    wait "$BACKEND_PID"
    ;;
  frontend)
    start_frontend
    ;;
esac

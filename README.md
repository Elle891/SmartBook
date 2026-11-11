# Smart Accounting Software

Multi-tenant cloud-based financial management platform for small enterprises.
Supports Chinese Accounting Standards (CAS) and IFRS as first-class accounting standards.

## Architecture

4 independent microservices:

| Service | Technology | Port |
|---|---|---|
| `svc-frontend` | OWL + Nginx | 3000 |
| `svc-accounting` | FastAPI + Celery | 8000 |
| `svc-ml` | FastAPI + Celery + MLflow | 8001 |
| `svc-nlp` | FastAPI + vLLM | 8002 |

## Build (local, no Docker)

Use this when Docker is not installed or you want a fast local build:

```powershell
# Windows
.\scripts\build.ps1

# Skip tests for a faster build
.\scripts\build.ps1 -SkipTests
```

```bash
# Linux / macOS
./scripts/build.sh

# Skip tests
./scripts/build.sh --skip-tests
```

Output:
- Frontend static assets → `frontend/dist/`
- Backend editable install in the current Python environment (requires **Python 3.11+**)

## Quick Start (Docker)

Dockerfiles and `docker-compose.yml` are kept for deployment. Use when Docker is available:

```bash
# Start all services (MySQL platform DB — default)
docker compose up -d

# Platform center DB on PostgreSQL instead of MySQL
docker compose -f docker-compose.yml -f docker-compose.platform-postgres.yml up -d

# Run platform migrations (follows DATABASE_URL / PLATFORM_DB_TYPE)
./scripts/migrate-platform.sh
# Windows: .\scripts\migrate-platform.ps1
```

### Platform center database (MySQL default)

The registry / users / auth tables default to **MySQL 8.0+**. For PostgreSQL:

```bash
docker compose -f docker-compose.yml -f docker-compose.platform-postgres.yml up -d
```

## Development (local, no Docker)

Frontend already ships with a hot-reload dev server (`frontend/dev.js`). Use the unified scripts to run backend + frontend together. Dev uses the **same auth flow as test/prod**: register → login → create Account Set (with datasource). There is no mock login / DEV_BOOTSTRAP path.

```powershell
# Windows — both backend (uvicorn --reload) + frontend (esbuild watch)
.\scripts\dev.ps1

# Start only one side
.\scripts\dev.ps1 -Target backend
.\scripts\dev.ps1 -Target frontend
```

```bash
# Linux / macOS
./scripts/dev.sh
./scripts/dev.sh --backend-only
./scripts/dev.sh --frontend-only
```

| Service | URL | Notes |
|---------|-----|-------|
| Frontend dev server | http://localhost:8080 | Hot reload (JS + SCSS); starts at Login |
| Backend API | http://localhost:8000 | Swagger UI at `/docs` |
| Health check | http://localhost:8000/health | No DB required |

Optional: copy `scripts/dev.env.example` → `scripts/dev.env` to override database/redis settings.

**VS Code debugging**
- Run & Debug → **Backend: FastAPI (uvicorn reload)** — breakpoints in Python
- Terminal → Run Task → **dev: frontend** / **dev: backend**

For full API integration (auth, DB), start MySQL/Redis via `docker compose up mysql redis -d`.

Manual frontend dev:

```bash
cd frontend
API_BASE_URL=http://localhost:8000 npm run dev
```

Backend tests:

```bash
cd backend
export PIP_CONFIG_FILE=backend/pip.conf   # Tsinghua mirror
pip install -r requirements-dev.txt
pytest --run
```

API integration tests (auth + Account Set against local MySQL/Redis):

```powershell
# Windows — requires MySQL (platform_registry + smartbook_shared) and Redis
.\scripts\integration-test.ps1
# Optional live health probe:
.\scripts\integration-test.ps1 -ApiBase http://127.0.0.1:8002
```

```bash
# Linux/macOS
./scripts/integration-test.sh
```

Configure pip mirror permanently: `.\scripts\setup-pip-mirror.ps1` (Windows) or `./scripts/setup-pip-mirror.sh` (Linux/macOS).

## Directory Layout

```
backend/          Python backend (svc-accounting, svc-ml, svc-nlp)
frontend/         OWL frontend (svc-frontend)
infra/            Infrastructure configs (K8s, Vault, Prometheus, Grafana, Loki)
migrations/       Alembic migration scripts
tests/            Integration and end-to-end tests
```

# Autonomous Software Recovery & Trust PaaS

This monorepo establishes the core architecture for the **Autonomous Software Recovery & Trust PaaS** — a multi-tenant platform designed to autonomously detect software failures, localize faults, generate patches, validate them in sandboxes, compute trust scores, and manage pull requests.

## Architecture & Monorepo Structure

```text
/
├── apps/
│   ├── api/                   # FastAPI Control Plane & Ingestion API
│   ├── recovery-worker/       # Celery Worker simulating diagnosis/recovery loops
│   ├── sandbox-worker/        # Celery Worker executing isolated test runs
│   ├── trust-engine/          # Celery Worker executing mutation sensitivity metrics
│   └── github-worker/         # Celery Worker automating Git / PR operations
│
├── packages/
│   ├── recovery-sdk/          # Non-blocking error monitoring middleware
│   ├── core/                  # Core baseline modules and shared logic
│   ├── fault-localizer/       # Stack-trace and AST analyzer package
│   ├── patch-engine/          # LLM patch generator connector package
│   ├── sandbox-manager/       # Docker sandbox runtime controller
│   ├── trust-engine-core/     # Mutation testing trust aggregator
│   ├── github-client/         # Octokit/REST API GitHub wrapper
│   └── shared/                # Shared logging, schemas, and configurations
│
├── frontend/                  # React + Vite + TypeScript + Tailwind dashboard
├── demo-repo/                 # Buggy demo repository for verification
├── infrastructure/            # Configs for Postgres, Redis, and Sandboxes
├── tests/                     # Integration and verification test suite
└── docker-compose.yml         # Dev environment container orchestrator
```

---

## Service Port Mapping

| Service Name | Port | Description |
| :--- | :--- | :--- |
| **API Gateway** | `8000` | FastAPI app serving OpenAPI endpoints and health checks |
| **Frontend** | `3000` | React Dashboard using Vite dev server |
| **PostgreSQL** | `5432` | Core database equipped with `pgvector` extension |
| **Redis** | `6379` | Message broker and caching backend for Celery queues |

---

## Getting Started Locally

### Prerequisites

- Python 3.11+
- Node.js 18+ (npm)
- Docker & Docker Compose

### 1. Local Environment Setup

Create a Python virtual environment and install backend requirements:

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows:
.\venv\Scripts\activate
# Activate on macOS/Linux:
source venv/bin/activate

# Install requirements (also installs internal packages in editable mode)
pip install -r apps/api/requirements.txt
pip install pytest pytest-asyncio pytest-cov
```

Install frontend packages:

```bash
cd frontend
npm install
cd ..
```

---

## Running Verification Tests

### Backend Unit Tests

Runs mock-based verification tests checking route handlers, schemas, and SDK operation:

```bash
# Make sure virtualenv is active
pytest tests/
```

### Frontend Unit Tests

Runs frontend UI specs using Vitest:

```bash
cd frontend
npm run test
```

---

## Starting the Docker Compose Environment

Run the full stack (Database, Redis, API Gateway, Celery Worker, React Dashboard):

```bash
# Build and launch all services
docker compose up -d --build
```

### Verifying Service Connectivity

Once running, you can access:
- **FastAPI OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)

To programmatically verify connectivity to PostgreSQL, Redis, and Celery workers, query the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected Response:
```json
{
  "status": "healthy",
  "database": "healthy",
  "redis": "healthy",
  "celery": "healthy"
}
```

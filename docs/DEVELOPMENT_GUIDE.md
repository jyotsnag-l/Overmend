# Development & Operations Guide

This guide details how to set up, build, test, and run the **Overmend / Agent SDK** platform locally.

---

## 1. Prerequisites & Environment Setup

### Required Tools
- **Python**: 3.11 or higher
- **Node.js**: 18.x or higher & `npm`
- **Docker**: (Optional, for running Redis and isolated sandbox containers)

### Initial Setup Commands

1. **Clone & Virtual Environment**:
   ```powershell
   git clone <repo-url>
   cd agent_sdk
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Install Python Packages**:
   ```powershell
   pip install -e packages/core
   pip install -e packages/fault-localizer
   pip install -e packages/patch-engine
   pip install -e packages/trust-engine-core
   pip install -e packages/sandbox-manager
   pip install -e packages/github-client
   pip install -e packages/recovery-sdk
   pip install -r apps/api/requirements.txt
   ```

3. **Install Frontend Dependencies**:
   ```powershell
   cd frontend
   npm install
   cd ..
   ```

---

## 2. Environment Variables Configuration

Create a `.env` file in the root workspace directory:

```env
ENVIRONMENT=development
DATABASE_URL=sqlite+aiosqlite:///./recovery_test.db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=super_secret_dev_key_change_in_production
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY_PATH=./github-private-key.pem
```

---

## 3. Running Local Services

### Start API Server
```powershell
uvicorn apps.api.main:app --reload --port 8000
```
* API Swagger Documentation: `http://localhost:8000/docs`

### Start Celery Workers
```powershell
celery -A celery_app worker --loglevel=info
```

### Start Frontend Dev Dashboard
```powershell
cd frontend
npm run dev
```
* Dashboard URL: `http://localhost:5173`

---

## 4. Running Test Suites & Demos

### Automated Pytest Suite
```powershell
pytest tests/
```

### Run Recovery Pipeline Simulation Demo
```powershell
python simulate_recovery_demo.py
```

### Test Sandbox Stream Endpoint
```powershell
python scratch/test_sandbox_stream.py
```

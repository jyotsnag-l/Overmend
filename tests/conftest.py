import os
import sys

# Force SQLite during testing to avoid trying to resolve postgres
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_recovery.db"
os.environ["BYPASS_CELERY"] = "true"

# Ensure backend services are discoverable during tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/api")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/recovery-worker")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../packages/shared")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../packages/recovery-sdk")))

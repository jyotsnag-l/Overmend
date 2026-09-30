import os
import sys

# Force SQLite during testing to avoid trying to resolve postgres
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_recovery.db"
os.environ["BYPASS_CELERY"] = "true"

# Ensure backend services and packages are discoverable during tests
packages = [
    "apps/api",
    "apps/recovery-worker",
    "apps/github-worker",
    "packages/shared",
    "packages/core",
    "packages/github-client",
    "packages/fault-localizer",
    "packages/patch-engine",
    "packages/sandbox-manager",
    "packages/trust-engine-core",
    "packages/recovery-sdk",
]
for pkg in packages:
    pkg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", pkg))
    if pkg_path not in sys.path:
        sys.path.append(pkg_path)


import time
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone

os.environ['BYPASS_CELERY'] = 'true'
os.environ['PATCH_PROVIDER'] = 'mock'
os.environ['GITHUB_MOCK'] = 'true'

sys.path.extend([
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\apps\recovery-worker",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\apps\api",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\packages\shared",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\packages\core",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\packages\fault-localizer",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\packages\patch-engine",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\packages\sandbox-manager",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\packages\trust-engine-core",
    r"c:\Users\sreej\OneDrive\Desktop\agent_sdk\packages\github-client",
])

from database import AsyncSessionLocal
from sqlalchemy import select
import models
from tasks import run_recovery_pipeline  # type: ignore

async def setup_incident():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Project).where(models.Project.id == "proj_seed"))
        proj = res.scalar_one_or_none()
        if not proj:
            proj = models.Project(
                id="proj_seed",
                organization_id="org_seed",
                name="Seed Project",
                repository="seed-org/seed-repo"
            )
            db.add(proj)
        
        inc_id = f"inc_{uuid.uuid4().hex[:8]}"
        stack_trace = """Traceback (most recent call last):
  File "auth/verification.py", line 42, in run_task
    raise KeyError("stripe_signature header missing")"""
        
        inc = models.Incident(
            id=inc_id,
            organization_id="org_seed",
            project_id="proj_seed",
            exception_type="KeyError",
            exception_message="stripe_signature header missing",
            stack_trace=stack_trace,
            status="DETECTED",
            fingerprint="key_error_benchmark",
            environment="production",
            created_at=datetime.now(timezone.utc),
            first_seen=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            occurrence_count=1
        )
        db.add(inc)
        await db.commit()
        return inc_id, stack_trace

async def main():
    inc_id, stack_trace = await setup_incident()
    
    t0 = time.perf_counter()
    result = run_recovery_pipeline.run(inc_id, "seed-org/seed-repo", stack_trace)
    t1 = time.perf_counter()

    print("\n" + "="*60)
    print(f"COMPLETE 6-STEP PIPELINE BENCHMARK:")
    print(f"Incident ID: {inc_id}")
    print(f"Total Execution Duration: {t1 - t0:.3f} seconds")
    print(f"Pipeline Result Status: {result.get('status')}")
    print(f"Decision Action: {result.get('decision')}")
    print(f"PR Number / Action: {result.get('pr_number') or result.get('action')}")
    print("="*60 + "\n")

asyncio.run(main())

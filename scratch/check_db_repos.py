import asyncio, os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath("apps/api"))

from database import AsyncSessionLocal
from sqlalchemy import select
import models

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Incident).order_by(models.Incident.created_at.desc()))
        inc = res.scalars().first()
        if inc:
            print("INCIDENT ID:", inc.id)
            print("STATUS:", inc.status)
            print("TYPE:", inc.exception_type)
            print("REPO:", inc.affected_repository)
            hist_res = await db.execute(select(models.IncidentHistory).where(models.IncidentHistory.incident_id == inc.id).order_by(models.IncidentHistory.timestamp.asc()))
            for h in hist_res.scalars().all():
                print(f"  History: {h.from_state} -> {h.to_state} ({h.reason})")

            job_res = await db.execute(select(models.SandboxJob).where(models.SandboxJob.project_id == inc.project_id).order_by(models.SandboxJob.created_at.desc()))
            jobs = job_res.scalars().all()
            print(f"  Sandbox Jobs ({len(jobs)}):")
            for j in jobs[:2]:
                ex_res = await db.execute(select(models.SandboxExecution).where(models.SandboxExecution.sandbox_job_id == j.id))
                ex = ex_res.scalar_one_or_none()
                exit_str = f", exit_code={ex.exit_code}" if ex else ""
                print(f"    Job: {j.id}, status: {j.status}, patch: {j.patch_candidate_id}{exit_str}")

if __name__ == "__main__":
    asyncio.run(check())

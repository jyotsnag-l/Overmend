import logging
import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone
from celery import Celery
from dotenv import load_dotenv
load_dotenv(override=False)
from shared import setup_logging

# Ensure apps/api is in sys.path to access models and database
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from database import AsyncSessionLocal
import models
from sqlalchemy import select

import sandbox_manager
from sandbox_manager.runner import SandboxConfig, SandboxRunner
from sandbox_manager.storage import upload_artifact

setup_logging(service_name="sandbox-worker", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("sandbox_worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("sandbox_worker", broker=REDIS_URL, backend=REDIS_URL)

def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()


from typing import Optional, Dict, Any

async def db_transition_and_publish(job_id: str, to_state: str, details: Optional[str] = None, metadata_info: Optional[Dict[str, Any]] = None):
    """
    Persists a state transition in the database and publishes it to Redis.
    """
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.SandboxJob).where(models.SandboxJob.id == job_id))
        job = res.scalar_one_or_none()
        if job:
            from_state = job.status
            job.status = to_state
            
            transition = models.SandboxJobTransition(
                id=f"trans_{uuid.uuid4().hex[:8]}",
                organization_id=job.organization_id,
                sandbox_job_id=job.id,
                from_state=from_state,
                to_state=to_state,
                details=details,
                metadata_info=metadata_info or {}
            )
            db.add(transition)
            await db.commit()
            
            # Publish to Redis Pub/Sub for live status streaming
            try:
                import redis
                import json
                try:
                    r = redis.from_url(REDIS_URL, protocol=2)
                except TypeError:
                    r = redis.from_url(REDIS_URL)
                event_payload = {
                    "job_id": job_id,
                    "status": to_state,
                    "from_state": from_state,
                    "details": details,
                    "metadata": metadata_info or {},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                r.publish(f"sandbox_job:{job_id}", json.dumps(event_payload))
            except Exception as e:
                logger.error(f"Failed to publish to Redis: {e}")


def make_publish_callback(job_id: str):
    def callback(jid: str, event_data: dict):
        run_async(db_transition_and_publish(
            job_id=job_id,
            to_state=event_data["status"],
            details=event_data["details"],
            metadata_info=event_data["metadata"]
        ))
    return callback


@celery_app.task(
    bind=True,
    name="tasks.run_sandbox_job",
    max_retries=3,
    default_retry_delay=10
)
def run_sandbox_job(self, job_id_or_patch: str, test_cmd: Optional[str] = None) -> dict:
    """
    Celery task that executes a sandbox job.
    Supports both new async run_sandbox_job(job_id) and legacy compatibility modes.
    """
    # 1. Compatibility check
    if test_cmd is not None:
        logger.info("Executing legacy sandbox run compatibility mode...")
        # Direct run with raw patch and command
        return sandbox_manager.run_in_sandbox(job_id_or_patch, test_cmd)

    job_id = job_id_or_patch
    logger.info(f"Executing sandbox run task for job {job_id}...")

    # 2. Fetch Job from database
    async def fetch_job_details(jid):
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(models.SandboxJob).where(models.SandboxJob.id == jid))
            j = res.scalar_one_or_none()
            if not j:
                return None
            
            # Fetch patch candidate
            pc_res = await db.execute(select(models.PatchCandidate).where(models.PatchCandidate.id == j.patch_candidate_id))
            pc = pc_res.scalar_one_or_none()
            
            # Fetch project
            proj_res = await db.execute(select(models.Project).where(models.Project.id == j.project_id))
            proj = proj_res.scalar_one_or_none()
            
            # Fetch repository URL
            repo_res = await db.execute(select(models.Repository).where(models.Repository.project_id == j.project_id))
            repo = repo_res.scalar_one_or_none()
            
            # Fetch incident for commit hash
            commit = None
            if pc:
                inc_res = await db.execute(select(models.Incident).where(models.Incident.id == pc.incident_id))
                inc = inc_res.scalar_one_or_none()
                if inc:
                    commit = inc.context.get("commit_sha") or inc.context.get("git_commit") or inc.context.get("commit")
                    if not commit:
                        ev_res = await db.execute(
                            select(models.IncidentEvent)
                            .where(models.IncidentEvent.incident_id == inc.id)
                            .order_by(models.IncidentEvent.timestamp.desc())
                        )
                        ev = ev_res.scalars().first()
                        if ev:
                            commit = ev.payload.get("commit_sha") or ev.payload.get("git_commit") or ev.payload.get("commit")
            
            repo_url = repo.url if repo else None
            if not repo_url and proj:
                proj_repo_str = str(proj.repository) if proj.repository is not None else ""
                if proj_repo_str and os.path.isdir(proj_repo_str):
                    repo_url = os.path.abspath(proj_repo_str)
                elif proj_repo_str and os.path.isdir(os.path.join(os.getcwd(), proj_repo_str)):
                    repo_url = os.path.abspath(os.path.join(os.getcwd(), proj_repo_str))
                elif proj_repo_str:
                    repo_url = f"https://github.com/{proj_repo_str}"
            
            return {
                "job": j,
                "patch_diff": pc.diff if pc else "",
                "repo_url": repo_url,
                "commit_hash": commit or "HEAD",
                "status": j.status
            }

    details = run_async(fetch_job_details(job_id))
    if not details:
        logger.error(f"Sandbox job {job_id} not found in database.")
        return {"status": "error", "error": "Job not found"}

    # 3. Idempotency Check
    if details["status"] in ["COMPLETED", "FAILED", "TIMED_OUT", "DESTROYED"]:
        logger.info(f"Sandbox job {job_id} already has final status {details['status']}. Skipping.")
        return {"status": "skipped", "message": "Already executed"}

    try:
        # Build SandboxConfig from SandboxJob database config column
        db_config = details["job"].config
        sandbox_config = SandboxConfig(**db_config)
        
        # Instantiate runner with Redis publishing callback
        publish_cb = make_publish_callback(job_id)
        runner = SandboxRunner(sandbox_config, publish_func=publish_cb)
        
        # Execute sandbox
        result = runner.run(
            job_id=job_id,
            repo_url=details["repo_url"],
            commit_hash=details["commit_hash"],
            patch_diff=details["patch_diff"]
        )
        
        # 4. Save results to database
        async def save_execution_results(jid, res):
            async with AsyncSessionLocal() as db:
                res_job = await db.execute(select(models.SandboxJob).where(models.SandboxJob.id == jid))
                j = res_job.scalar_one_or_none()
                if not j:
                    return
                
                # Upload large artifacts to S3 if configured
                stdout_content = res.get("stdout", "")
                stderr_content = res.get("stderr", "")
                
                stdout_url = upload_artifact(jid, "stdout", stdout_content)
                stderr_url = upload_artifact(jid, "stderr", stderr_content)
                
                # If uploaded, clear standard text column if large, or keep for quick preview
                db_stdout = stdout_content if not stdout_url else None
                db_stderr = stderr_content if not stderr_url else None
                
                exec_record = models.SandboxExecution(
                    id=f"exec_{uuid.uuid4().hex[:8]}",
                    organization_id=j.organization_id,
                    sandbox_job_id=j.id,
                    stdout=db_stdout,
                    stderr=db_stderr,
                    stdout_url=stdout_url,
                    stderr_url=stderr_url,
                    exit_code=res.get("exit_code"),
                    duration=res.get("duration"),
                    resource_usage=res.get("resource_usage", {}),
                    created_at=datetime.now(timezone.utc)
                )
                db.add(exec_record)
                
                # Log audit event
                audit_log = models.AuditLog(
                    id=f"aud_{uuid.uuid4().hex[:8]}",
                    organization_id=j.organization_id,
                    action="EXECUTE_SANDBOX_JOB",
                    resource_type="SandboxJob",
                    resource_id=j.id,
                    details={
                        "exit_code": res.get("exit_code"),
                        "duration": res.get("duration"),
                        "resource_usage": res.get("resource_usage", {})
                    },
                    created_at=datetime.now(timezone.utc)
                )
                db.add(audit_log)
                await db.commit()

        run_async(save_execution_results(job_id, result))
        return result.to_dict() if hasattr(result, "to_dict") else result

    except Exception as exc:
        logger.error(f"Error running sandbox task {job_id}: {exc}", exc_info=True)
        # Handle Celery retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task {job_id}. Attempt {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
        else:
            # Mark job as failed after all retries exhausted
            run_async(db_transition_and_publish(
                job_id=job_id,
                to_state="FAILED",
                details=f"All execution retries exhausted. Last error: {str(exc)}"
            ))
            raise exc

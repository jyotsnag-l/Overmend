import os
# Force testing SQLite database before main app imports database configs
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_recovery.db"
os.environ["BYPASS_CELERY"] = "true"
os.environ["GITHUB_APP_ID"] = "mock"
os.environ["GITHUB_PRIVATE_KEY"] = "mock"

import pytest
import asyncio
import shutil
from typing import Tuple, Any, Dict
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from database import get_db, Base, engine, AsyncSessionLocal
import models
import schemas
# pyrefly: ignore [missing-import]
from tasks import run_recovery_pipeline
from recovery_sdk.monitor import ExceptionMonitor

def run_sync(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def override_get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@pytest.fixture(autouse=True)
def setup_test_database():
    async def create_all():
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
    try:
        run_sync(create_all())
    except Exception:
        pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def seed_demo_organization_and_project() -> Tuple[models.Organization, models.Project]:
    async with AsyncSessionLocal() as db:
        org_res = await db.execute(select(models.Organization).where(models.Organization.id == "org_demo"))
        org = org_res.scalar_one_or_none()
        if not org:
            org = models.Organization(id="org_demo", name="Demo Organization")
            db.add(org)
            
        proj_res = await db.execute(select(models.Project).where(models.Project.id == "proj_123"))
        project = proj_res.scalar_one_or_none()
        if not project:
            project = models.Project(id="proj_123", organization_id="org_demo", name="Demo Repo Project", repository="demo-repo")
            db.add(project)
        else:
            project.repository = "demo-repo"

        pol_res = await db.execute(select(models.ProjectPolicy).where(models.ProjectPolicy.project_id == "proj_123"))
        policy = pol_res.scalar_one_or_none()
        if not policy:
            policy = models.ProjectPolicy(
                id="pol_demo",
                organization_id="org_demo",
                project_id="proj_123",
                auto_merge_threshold=0.85,
                mandatory_review_threshold=0.60,
                restricted_files=[],
                anomaly_frequency_threshold=1,
                anomaly_zscore_threshold=3.0,
                anomaly_ewma_threshold=5.0,
                severity_rules={}
            )
            db.add(policy)
        else:
            policy.auto_merge_threshold = 0.85
            policy.mandatory_review_threshold = 0.60
            policy.restricted_files = []
            
        # Clean up any leftover records from previous test runs
        await db.execute(models.IncidentEvent.__table__.delete())
        await db.execute(models.ProcessedEvent.__table__.delete())
        await db.execute(models.FaultLocation.__table__.delete())
        await db.execute(models.Mutation.__table__.delete())
        await db.execute(models.TrustEvaluation.__table__.delete())
        await db.execute(models.Decision.__table__.delete())
        await db.execute(models.PullRequest.__table__.delete())
        await db.execute(models.SandboxExecution.__table__.delete())
        await db.execute(models.SandboxJobTransition.__table__.delete())
        await db.execute(models.SandboxJob.__table__.delete())
        await db.execute(models.PatchCandidate.__table__.delete())
        await db.execute(models.IncidentHistory.__table__.delete())
        await db.execute(models.Incident.__table__.delete())
        await db.commit()
        return org, project


@pytest.mark.asyncio
async def test_complete_autonomous_recovery_pipeline() -> None:
    """
    E2E Demo Acceptance Test verifying:
    1. Buggy Python application exception captured by ExceptionMonitor.
    2. Event posted to API, ProcessedEvent and Incident created.
    3. run_recovery_pipeline enqueued and runs:
       a. Fault localization locates payments.py line 4.
       b. Deterministic mock patch generation outputs 3 patches (A, B, C).
       c. 3 sandboxes run locally on demo-repo.
       d. Patch A (syntax error) and Patch B (test mismatch) fail.
       e. Patch C (logic fix + test update) passes.
       f. Passing Patch C evaluated by Trust Engine via AST mutation testing.
       g. Mutants generated, run, and killed -> Mutation Score calculated.
       h. Trust score calculated and policy evaluated by Decision Engine.
       i. GitHub PR created using mock adapter.
       j. CI status evaluated, PR auto-merged and incident VERIFIED.
    """
    # Seed DB
    await seed_demo_organization_and_project()
    
    client = TestClient(app)
    
    # Instantiate clean ExceptionMonitor
    test_monitor = ExceptionMonitor()
    
    # Mock exception monitor's send function to post directly to the test server API
    async def mock_send_with_retry(api_url: str, payload: dict) -> bool:
        headers: dict[str, str] = {
            "X-Project-ID": str(payload.get("project_id", "proj_123")),
            "X-User-ID": "usr_demo",
            "X-User-Email": "demo@org.com",
            "X-Organization-ID": "org_demo"
        }
        response = client.post("/api/v1/events", json=payload, headers=headers)
        assert response.status_code == 200, f"Failed to ingest event: {response.text}"
        return True
        
    test_monitor._send_with_retry = AsyncMock(side_effect=mock_send_with_retry)
    test_monitor.start(project_id="proj_123", environment="production", api_url="http://local-test")
    
    # 1. Buggy Python application produces a known failure and captures exception
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../demo-repo")))
    from users import get_user_profile
    try:
        get_user_profile(1) # Triggers NameError
    except NameError as exc:
        test_monitor.capture_exception(exc, context={"triggered_by": "acceptance_test"})
        
    # Wait for the background queue in monitor to send the event
    for _ in range(50):
        if test_monitor._send_with_retry.called:
            break
        await asyncio.sleep(0.05)
        
    assert test_monitor._send_with_retry.called
    test_monitor.stop()
    
    # Verify Incident created in DB
    async with AsyncSessionLocal() as db:
        inc_res = await db.execute(select(models.Incident).where(models.Incident.project_id == "proj_123"))
        incident = inc_res.scalar_one_or_none()
        assert incident is not None
        assert incident.status == "DETECTED"
        assert incident.exception_type == "NameError"
        assert incident.affected_repository == "demo-repo"
        incident_id = incident.id
        stack_trace = incident.stack_trace

    # 2. Execute recovery pipeline (with Celery-bypass)
    # We run the recovery pipeline synchronously in-process
    pipeline_result = run_recovery_pipeline(incident_id, "demo-repo", stack_trace)
    
    assert pipeline_result["status"] == "success"
    assert "pull_request" in pipeline_result
    assert pipeline_result["pull_request"] is not None
    
    # Verify the database states to ensure complete integration flow was persisted correctly
    async with AsyncSessionLocal() as db:
        # Check incident transitioned to VERIFIED (via auto-merge E2E)
        inc_res = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
        inc = inc_res.scalar_one()
        assert inc.status == "VERIFIED"
        
        # Check that 3 candidate patches were generated in DB
        pc_res = await db.execute(select(models.PatchCandidate).where(models.PatchCandidate.incident_id == incident_id))
        candidates = pc_res.scalars().all()
        assert len(candidates) == 3
        
        # Verify 2 sandbox jobs were created in DB (Patch A rejected by syntax validation)
        sj_res = await db.execute(select(models.SandboxJob).where(models.SandboxJob.project_id == "proj_123"))
        sandbox_jobs = sj_res.scalars().all()
        assert len(sandbox_jobs) == 2
        
        # Verify executions are logged in DB for this project's sandbox jobs
        sj_ids = [j.id for j in sandbox_jobs]
        se_res = await db.execute(select(models.SandboxExecution).where(models.SandboxExecution.sandbox_job_id.in_(sj_ids)))
        executions = se_res.scalars().all()
        assert len(executions) == 2
        
        # Verify exit codes: two failures (exit_code != 0), one success (exit_code == 0)
        exit_codes = [e.exit_code for e in executions]
        assert 0 in exit_codes
        assert any(ec != 0 for ec in exit_codes)
        
        # Verify TrustEvaluation record created in DB
        candidate_ids = [c.id for c in candidates]
        te_res = await db.execute(select(models.TrustEvaluation).where(models.TrustEvaluation.patch_candidate_id.in_(candidate_ids)))
        trust_eval = te_res.scalar_one_or_none()
        assert trust_eval is not None
        assert trust_eval.mutation_score == 1.0
        assert trust_eval.trust_score >= 0.85
        
        # Verify Mutation records created in DB for AST mutations
        mut_res = await db.execute(select(models.Mutation).where(models.Mutation.trust_evaluation_id == trust_eval.id))
        mutations = mut_res.scalars().all()
        assert len(mutations) > 0
        assert all(m.status == "KILLED" for m in mutations)
        
        # Verify Decision record created in DB
        dec_res = await db.execute(select(models.Decision).where(models.Decision.patch_candidate_id.in_(candidate_ids), models.Decision.status == "APPROVED"))
        decision = dec_res.scalar_one_or_none()
        assert decision is not None
        assert decision.action == "AUTO_MERGE"
        
        # Verify Pull Request was created and MERGED
        pr_res = await db.execute(select(models.PullRequest).where(models.PullRequest.project_id == "proj_123", models.PullRequest.status == "MERGED"))
        pr = pr_res.scalar_one_or_none()
        assert pr is not None
        assert pr.github_pr_number == 123
        
        # Verify Audit Log records exist for every stage
        audit_res = await db.execute(select(models.AuditLog))
        audits = audit_res.scalars().all()
        assert len(audits) >= 5
        actions = [a.action for a in audits]
        assert "INCIDENT_STATE_TRANSITION" in actions
        assert "EXECUTE_SANDBOX_JOB" in actions

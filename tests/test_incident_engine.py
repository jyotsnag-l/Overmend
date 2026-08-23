import os
# Force testing SQLite database before main app imports database configs
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_recovery.db"
os.environ["BYPASS_CELERY"] = "true"

import pytest
import asyncio
from typing import Tuple, Any, Dict
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from database import get_db, Base, engine, AsyncSessionLocal
import models
import schemas
from tasks import run_recovery_pipeline

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
    # Remove database file if it exists from a previous aborted run
    if os.path.exists("test_recovery.db"):
        try:
            os.remove("test_recovery.db")
        except Exception:
            pass

    async def create_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    run_sync(create_all())
    
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    
    async def drop_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    run_sync(drop_all())
    
    # Remove file after test completion
    if os.path.exists("test_recovery.db"):
        try:
            os.remove("test_recovery.db")
        except Exception:
            pass


# Seeding helper functions
def seed_org_project(org_id: str, proj_id: str, repo: str = "org/repo") -> Tuple[models.Organization, models.Project]:
    async def _run():
        async with AsyncSessionLocal() as db:
            org = models.Organization(id=org_id, name=f"Org {org_id}")
            project = models.Project(id=proj_id, organization_id=org_id, name=f"Project {proj_id}", repository=repo)
            
            # Create a project policy
            policy = models.ProjectPolicy(
                id=f"pol_{proj_id}",
                organization_id=org_id,
                project_id=proj_id,
                anomaly_frequency_threshold=5,
                anomaly_zscore_threshold=3.0,
                anomaly_ewma_threshold=5.0,
                severity_rules={}
            )
            
            db.add(org)
            db.add(project)
            db.add(policy)
            await db.commit()
            return org, project
    return run_sync(_run())


# --- TESTS ---

def test_new_incidents() -> None:
    """
    Verifies that separate fingerprints create separate incidents,
    and a resolved/terminal state incident allows a new incident creation on a new event.
    """
    client = TestClient(app)
    seed_org_project("org_1", "proj_1")

    # Ingest event 1
    payload1 = {
        "project_id": "proj_1",
        "exception_type": "ValueError",
        "exception_message": "Invalid value provided",
        "stack_trace": 'File "main.py", line 10, in calculate\n  x = int("abc")',
        "environment": "production"
    }
    response1 = client.post("/api/v1/events", json=payload1, headers={"X-Project-ID": "proj_1"})
    assert response1.status_code == 200
    inc1 = response1.json()
    assert inc1["status"] == "DETECTED"
    
    # Ingest event 2 with different exception type (different fingerprint)
    payload2 = {
        "project_id": "proj_1",
        "exception_type": "TypeError",
        "exception_message": "Unsupported type",
        "stack_trace": 'File "helper.py", line 4, in parse\n  x + None',
        "environment": "production"
    }
    response2 = client.post("/api/v1/events", json=payload2, headers={"X-Project-ID": "proj_1"})
    assert response2.status_code == 200
    inc2 = response2.json()
    assert inc1["id"] != inc2["id"]

    # Mark the first incident as MERGED (terminal state)
    async def mark_merged():
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(models.Incident).where(models.Incident.id == inc1["id"]))
            incident = res.scalar_one()
            incident.status = "MERGED"
            await db.commit()
    run_sync(mark_merged())

    # Send the first event again. Since it was MERGED, it should create a NEW incident.
    response3 = client.post("/api/v1/events", json=payload1, headers={"X-Project-ID": "proj_1"})
    assert response3.status_code == 200
    inc3 = response3.json()
    assert inc3["id"] != inc1["id"]
    assert inc3["status"] == "DETECTED"


def test_duplicate_errors_and_aggregation() -> None:
    """
    Verifies that duplicate events aggregate under the same active incident,
    incrementing occurrence_count, and updating last_seen and rolling metrics.
    """
    client = TestClient(app)
    seed_org_project("org_1", "proj_1")

    payload = {
        "project_id": "proj_1",
        "exception_type": "KeyError",
        "exception_message": "Missing dictionary key: 'user'",
        "stack_trace": 'File "auth.py", line 12, in get_user\n  return data["user"]',
        "environment": "production"
    }

    # First ingestion
    res1 = client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_1"})
    inc1 = res1.json()
    assert inc1["status"] == "DETECTED"

    # Second ingestion (duplicate)
    res2 = client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_1"})
    inc2 = res2.json()

    # Same incident ID
    assert inc1["id"] == inc2["id"]

    # Verify database aggregation fields
    async def check_db():
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(models.Incident).where(models.Incident.id == inc1["id"]))
            inc = res.scalar_one()
            assert inc.occurrence_count == 2
            assert inc.last_seen > inc.first_seen
            assert inc.rolling_metrics["timestamps"] is not None
            assert len(inc.rolling_metrics["timestamps"]) == 2
    run_sync(check_db())


def test_repeated_webhook_delivery_idempotency() -> None:
    """
    Verifies that sending an event with the same client-supplied event_id
    returns the exact same incident without double-aggregating.
    """
    client = TestClient(app)
    seed_org_project("org_1", "proj_1")

    payload = {
        "event_id": "evt_unique_123",
        "project_id": "proj_1",
        "exception_type": "IndexError",
        "exception_message": "List index out of range",
        "stack_trace": 'File "runner.py", line 8, in run\n  return items[99]',
        "environment": "production"
    }

    # Delivery 1
    res1 = client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_1"})
    inc1 = res1.json()

    # Delivery 2 (repeated webhook retry)
    res2 = client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_1"})
    inc2 = res2.json()

    # Assert responses are identical
    assert inc1["id"] == inc2["id"]

    # Assert database occurrence_count is exactly 1 (duplicate delivery was suppressed)
    async def check_db():
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(models.Incident).where(models.Incident.id == inc1["id"]))
            inc = res.scalar_one()
            assert inc.occurrence_count == 1
            
            # Check ProcessedEvent table
            pe_res = await db.execute(select(models.ProcessedEvent).where(models.ProcessedEvent.event_id == "evt_unique_123"))
            assert pe_res.scalar_one_or_none() is not None
    run_sync(check_db())


def test_severity_classification() -> None:
    """
    Verifies LOW/MEDIUM/HIGH/CRITICAL severity levels assignments based on:
    - Exception default mappings (e.g. ValueError -> HIGH)
    - Production upgrade behavior
    - Custom policy severity_rules
    """
    client = TestClient(app)
    seed_org_project("org_1", "proj_1")

    # Ingest TypeError in development (default: HIGH, dev does not upgrade)
    payload_dev = {
        "project_id": "proj_1",
        "exception_type": "TypeError",
        "exception_message": "Type mismatch",
        "stack_trace": 'File "calc.py", line 2, in add\n  return a + b',
        "environment": "development"
    }
    res_dev = client.post("/api/v1/events", json=payload_dev, headers={"X-Project-ID": "proj_1"})
    assert res_dev.json()["severity"] == "HIGH"

    # Ingest TypeError in production (default: HIGH, production upgrades to CRITICAL)
    payload_prod = {
        "project_id": "proj_1",
        "exception_type": "TypeError",
        "exception_message": "Type mismatch",
        "stack_trace": 'File "calc.py", line 2, in add\n  return a + b',
        "environment": "production"
    }
    res_prod = client.post("/api/v1/events", json=payload_prod, headers={"X-Project-ID": "proj_1"})
    assert res_prod.json()["severity"] == "CRITICAL"

    # Seed custom project policy severity rule for custom exception
    async def apply_custom_policy():
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(models.ProjectPolicy).where(models.ProjectPolicy.project_id == "proj_1"))
            policy = res.scalar_one()
            policy.severity_rules = {
                "exception_type_map": {
                    "CustomPaymentError": "CRITICAL",
                    "CustomValidationError": "LOW"
                }
            }
            await db.commit()
    run_sync(apply_custom_policy())

    payload_custom = {
        "project_id": "proj_1",
        "exception_type": "CustomValidationError",
        "exception_message": "Invalid zip code",
        "stack_trace": 'File "zip.py", line 5, in validate\n  raise CustomValidationError()',
        "environment": "development"
    }
    res_custom = client.post("/api/v1/events", json=payload_custom, headers={"X-Project-ID": "proj_1"})
    assert res_custom.json()["severity"] == "LOW"


def test_high_frequency_anomalies() -> None:
    """
    Verifies that high event frequency triggers an anomaly flag, upgrades severity,
    and initiates the Celery recovery pipeline.
    """
    client = TestClient(app)
    seed_org_project("org_1", "proj_1")

    # Set frequency threshold to 3 and map CustomError to LOW to avoid immediate actionability
    async def set_policy():
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(models.ProjectPolicy).where(models.ProjectPolicy.project_id == "proj_1"))
            policy = res.scalar_one()
            policy.anomaly_frequency_threshold = 3
            policy.severity_rules = {
                "exception_type_map": {
                    "CustomError": "LOW"
                }
            }
            await db.commit()
    run_sync(set_policy())

    payload = {
        "project_id": "proj_1",
        "exception_type": "CustomError",
        "exception_message": "Freq error",
        "stack_trace": 'File "main.py", line 2\n  pass',
        "environment": "production"
    }

    # Mock celery send_task to inspect if enqueued
    with patch.dict(os.environ, {"BYPASS_CELERY": "false"}):
        with patch("pipeline.celery_app.send_task") as mock_send:
            # Ingest 2 times (below threshold of 3)
            client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_1"})
            res = client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_1"})
            assert res.json()["is_anomaly"] is False
            assert mock_send.called is False

            # 3rd ingestion breaches frequency threshold of 3
            res3 = client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_1"})
            incident = res3.json()
            assert incident["is_anomaly"] is True
            assert incident["severity"] == "LOW"
            assert mock_send.called is True
            mock_send.assert_called_with(
                "tasks.run_recovery_pipeline",
                args=[incident["id"], "org/repo", payload["stack_trace"]]
            )


def test_organization_isolation() -> None:
    """
    Ensures events are isolated by organization.
    - Org A cannot access Org B's projects
    - Org A header mismatch with Org B project ID causes failure
    """
    client = TestClient(app)
    seed_org_project("org_a", "proj_a")
    seed_org_project("org_b", "proj_b")

    payload = {
        "project_id": "proj_b", # Org B project
        "exception_type": "ValueError",
        "exception_message": "Isolated error",
        "stack_trace": 'File "main.py", line 1\n  pass',
        "environment": "production"
    }

    # Ingest event using mismatching header: X-Project-ID is proj_a, but body has proj_b
    response = client.post("/api/v1/events", json=payload, headers={"X-Project-ID": "proj_a"})
    assert response.status_code == 401
    assert "Project ID mismatch" in response.text


@patch("tasks.github_client")
@patch("tasks.trust_engine_core")
@patch("tasks.sandbox_manager")
@patch("tasks.patch_engine")
@patch("tasks.fault_localizer")
def test_worker_lifecycle_state_transitions(
    mock_localizer: MagicMock,
    mock_patch: MagicMock,
    mock_sandbox: MagicMock,
    mock_trust: MagicMock,
    mock_github: MagicMock
) -> None:
    """
    Verifies the complete recovery lifecycle state transitions:
    DETECTED -> TRIAGED -> LOCALIZED -> PATCH_GENERATED -> SANDBOX_RUNNING -> TESTED -> TRUST_EVALUATED -> AUTO_MERGE -> MERGED -> VERIFIED.
    Also verifies audit records are successfully created in IncidentHistory and AuditLog.
    """
    # Seed db
    seed_org_project("org_1", "proj_1")
    
    # 1. Create a dummy incident in DETECTED state
    async def create_dummy_inc():
        async with AsyncSessionLocal() as db:
            inc = models.Incident(
                id="inc_dummy_123",
                organization_id="org_1",
                project_id="proj_1",
                exception_type="ValueError",
                exception_message="Triage failure",
                stack_trace="Traceback...",
                status="DETECTED",
                fingerprint="tri_dummy_123",
                environment="production"
            )
            db.add(inc)
            await db.commit()
            return inc
    run_sync(create_dummy_inc())

    # Configure mocks for worker pipeline
    mock_localizer.localize_fault.return_value = {"file": "main.py", "line": 5}
    mock_patch.generate_patch.return_value = "diff --git a/main.py b/main.py"
    mock_sandbox.run_in_sandbox.return_value = {"exit_code": 0, "mutation_score": 0.95}
    mock_trust.evaluate_trust.return_value = {"trust_score": 0.95, "verdict": "TRUSTED"}
    mock_github.create_pull_request.return_value = "https://github.com/org/repo/pull/1"

    # Reset retry attributes to defaults
    run_recovery_pipeline.request.retries = 0
    run_recovery_pipeline.max_retries = 3

    from celery import Celery
    def get_github_worker_tasks():
        import sys
        import importlib.util
        spec = importlib.util.spec_from_file_location("github_worker_tasks", "apps/github-worker/tasks.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["github_worker_tasks"] = module
        spec.loader.exec_module(module)
        return module

    class MockCeleryResult:
        def __init__(self, val):
            self.val = val
        def get(self, timeout=None):
            return self.val

    def mock_send_task_sync(name, *args, **kwargs):
        task_args = kwargs.get("args", [])
        if name == "tasks.run_sandbox_job":
            return MockCeleryResult({"exit_code": 0, "mutation_score": 0.95})
        elif name == "tasks.monitor_pr_ci_task":
            github_worker_tasks = get_github_worker_tasks()
            github_worker_tasks.monitor_pr_ci_task.run(*task_args)
        elif name == "tasks.evaluate_and_merge_pr_task":
            github_worker_tasks = get_github_worker_tasks()
            github_worker_tasks.evaluate_and_merge_pr_task.run(*task_args)

    with patch.dict(os.environ, {"BYPASS_CELERY": "false"}):
        with patch.object(Celery, "send_task", side_effect=mock_send_task_sync):
            # Run celery pipeline task synchronously (Celery binds self to task instance)
            result = run_recovery_pipeline("inc_dummy_123", "org/repo", "Traceback...")
    
    assert result["status"] == "success"
    assert result["pull_request"] == "https://github.com/org/repo/pull/1"

    # Verify lifecycle states and audits in DB
    async def verify_db():
        async with AsyncSessionLocal() as db:
            # Check final status
            inc_res = await db.execute(select(models.Incident).where(models.Incident.id == "inc_dummy_123"))
            inc = inc_res.scalar_one()
            assert inc.status == "VERIFIED"

            # Check IncidentHistory transition entries
            hist_res = await db.execute(
                select(models.IncidentHistory)
                .where(models.IncidentHistory.incident_id == "inc_dummy_123")
                .order_by(models.IncidentHistory.timestamp.asc())
            )
            transitions = hist_res.scalars().all()
            states = [t.to_state for t in transitions]
            
            # Should have gone through full pipeline states
            expected_states = [
                "TRIAGED", "LOCALIZED", "PATCH_GENERATED", "SANDBOX_RUNNING",
                "TESTED", "TRUST_EVALUATED", "PENDING_CI", "MERGED", "VERIFIED"
            ]
            for state in expected_states:
                assert state in states

            # Verify AuditLog entries exist
            audit_res = await db.execute(
                select(models.AuditLog)
                .where(models.AuditLog.resource_id == "inc_dummy_123")
            )
            audits = audit_res.scalars().all()
            assert len(audits) >= len(expected_states)
            actions = [a.action for a in audits]
            assert "INCIDENT_STATE_TRANSITION" in actions

    run_sync(verify_db())


@patch("tasks.trust_engine_core")
@patch("tasks.sandbox_manager")
@patch("tasks.patch_engine")
@patch("tasks.fault_localizer")
def test_worker_recovery_failure_and_retry_exhaustion(
    mock_localizer: MagicMock,
    mock_patch: MagicMock,
    mock_sandbox: MagicMock,
    mock_trust: MagicMock
) -> None:
    """
    Verifies worker dead-letter behavior: when a task raises errors, it retries
    and upon failure exhaustion transitions the incident to HUMAN_REVIEW with audit logs.
    """
    seed_org_project("org_1", "proj_1")
    
    async def create_dummy_inc():
        async with AsyncSessionLocal() as db:
            inc = models.Incident(
                id="inc_fail_123",
                organization_id="org_1",
                project_id="proj_1",
                exception_type="ValueError",
                exception_message="Transient error test",
                stack_trace="Traceback...",
                status="DETECTED",
                fingerprint="fail_dummy_123",
                environment="production"
            )
            db.add(inc)
            await db.commit()
    run_sync(create_dummy_inc())

    # Simulate localized fault, but patch generation raises error
    mock_localizer.localize_fault.return_value = {"file": "main.py", "line": 5}
    mock_patch.generate_patch.side_effect = RuntimeError("Patch engine offline")

    # Mock celery task self-retry to simulate exhaustion directly
    run_recovery_pipeline.request.retries = 3
    run_recovery_pipeline.max_retries = 3

    with pytest.raises(RuntimeError):
        # Call the task with bound mock_task context
        run_recovery_pipeline("inc_fail_123", "org/repo", "Traceback...")

    # Assert dead-letter behavior: incident should be transitioned to HUMAN_REVIEW
    async def verify_db():
        async with AsyncSessionLocal() as db:
            inc_res = await db.execute(select(models.Incident).where(models.Incident.id == "inc_fail_123"))
            inc = inc_res.scalar_one()
            assert inc.status == "HUMAN_REVIEW"

            hist_res = await db.execute(
                select(models.IncidentHistory)
                .where(models.IncidentHistory.incident_id == "inc_fail_123")
                .where(models.IncidentHistory.to_state == "HUMAN_REVIEW")
            )
            hist = hist_res.scalar_one()
            assert "Recovery pipeline failed after max retries" in hist.reason
    run_sync(verify_db())

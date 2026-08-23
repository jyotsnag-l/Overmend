import os
import pytest
import asyncio
import hmac
import hashlib
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import select

# Setup SQLite test database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_recovery.db"
os.environ["BYPASS_CELERY"] = "true"
os.environ["GITHUB_WEBHOOK_SECRET"] = "super-secret-key"

from main import app
from database import get_db, Base, engine, AsyncSessionLocal
import models
from github_client import verify_signature
from github_client.client import GitHubAppClient

client = TestClient(app)

def get_github_worker_tasks():
    import importlib.util
    import sys
    if "github_worker_tasks" in sys.modules:
        return sys.modules["github_worker_tasks"]
    worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/github-worker/tasks.py"))
    spec = importlib.util.spec_from_file_location("github_worker_tasks", worker_path)
    github_worker_tasks = importlib.util.module_from_spec(spec)
    sys.modules["github_worker_tasks"] = github_worker_tasks
    spec.loader.exec_module(github_worker_tasks)
    return github_worker_tasks

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
    
    if os.path.exists("test_recovery.db"):
        try:
            os.remove("test_recovery.db")
        except Exception:
            pass


def test_signature_verification() -> None:
    payload = b'{"zen": "Keep it simple"}'
    secret = "my-secret-key"
    
    # Generate signature
    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    assert verify_signature(payload, signature, secret) is True
    assert verify_signature(payload, signature + "error", secret) is False
    assert verify_signature(payload, "invalid_header_format", secret) is False


def test_webhook_ping_event() -> None:
    payload_bytes = b'{"zen": "Ping event payload"}'
    signature = "sha256=" + hmac.new(b"super-secret-key", payload_bytes, hashlib.sha256).hexdigest()
    
    headers = {
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "delivery-id-1234",
        "X-Hub-Signature-256": signature
    }
    
    response = client.post("/api/v1/webhooks/github", content=payload_bytes, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["message"] == "pong"


def test_webhook_idempotency() -> None:
    payload_bytes = b'{"zen": "Idempotency test payload"}'
    signature = "sha256=" + hmac.new(b"super-secret-key", payload_bytes, hashlib.sha256).hexdigest()
    
    headers = {
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "unique-delivery-id-999",
        "X-Hub-Signature-256": signature
    }
    
    # First delivery
    response1 = client.post("/api/v1/webhooks/github", content=payload_bytes, headers=headers)
    assert response1.status_code == 200
    assert response1.json()["message"] == "pong"

    # Second delivery with the same X-GitHub-Delivery
    response2 = client.post("/api/v1/webhooks/github", content=payload_bytes, headers=headers)
    assert response2.status_code == 200
    assert "Duplicate event" in response2.json()["message"]


def test_webhook_ci_status_recording() -> None:
    # 1. Seed org, project, patch candidate, and PR
    async def seed_data():
        async with AsyncSessionLocal() as db:
            org = models.Organization(id="org_test", name="Test Org")
            proj = models.Project(id="proj_test", organization_id="org_test", name="Test Repo", repository="test-owner/test-repo")
            inc = models.Incident(
                id="inc_test", organization_id="org_test", project_id="proj_test",
                exception_type="ValueError", exception_message="Oops",
                stack_trace="Traceback...", fingerprint="fp_test", status="PENDING_CI"
            )
            pc = models.PatchCandidate(
                id="patch_test", organization_id="org_test", incident_id="inc_test",
                diff="+++ fix.py", explanation="fix", is_valid=True
            )
            pr = models.PullRequest(
                id="pr_test", organization_id="org_test", project_id="proj_test",
                patch_candidate_id="patch_test", github_pr_number=100,
                github_pr_url="https://github.com/test-owner/test-repo/pull/100", status="OPEN"
            )
            db.add_all([org, proj, inc, pc, pr])
            await db.commit()
    run_sync(seed_data())

    # 2. Trigger check_run event webhook
    payload = {
        "repository": {"full_name": "test-owner/test-repo"},
        "check_run": {
            "head_sha": "a1b2c3d4e5f6",
            "name": "continuous-integration/github-actions",
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/test-owner/test-repo/actions/runs/1",
            "pull_requests": [{"number": 100}]
        }
    }
    payload_bytes = bytes(json_str := json_serialize(payload), "utf-8")
    signature = "sha256=" + hmac.new(b"super-secret-key", payload_bytes, hashlib.sha256).hexdigest()
    
    headers = {
        "X-GitHub-Event": "check_run",
        "X-GitHub-Delivery": "delivery-id-check-run",
        "X-Hub-Signature-256": signature
    }
    
    with patch.dict(os.environ, {"BYPASS_CELERY": "false"}):
        with patch("celery_app.celery_app.send_task") as mock_send_task:
            response = client.post("/api/v1/webhooks/github", content=payload_bytes, headers=headers)
            assert response.status_code == 200
            
            # Verify Celery evaluate task was triggered
            assert mock_send_task.called
            assert mock_send_task.call_args[0][0] == "tasks.evaluate_and_merge_pr_task"
            assert mock_send_task.call_args[1]["args"] == ["inc_test"]

    # 3. Verify CIStatus was written in DB
    async def verify_ci():
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(models.CIStatus).where(models.CIStatus.pull_request_id == "pr_test"))
            ci = res.scalar_one_or_none()
            assert ci is not None
            assert ci.status == "SUCCESS"
            assert ci.context == "continuous-integration/github-actions"
            assert ci.target_url == "https://github.com/test-owner/test-repo/actions/runs/1"
    run_sync(verify_ci())


def test_merge_evaluation_success_flow() -> None:
    # 1. Seed data for successful evaluation
    async def seed_data():
        async with AsyncSessionLocal() as db:
            org = models.Organization(id="org_test", name="Test Org")
            proj = models.Project(id="proj_test", organization_id="org_test", name="Test Repo", repository="test-owner/test-repo")
            policy = models.ProjectPolicy(
                id="pol_test", organization_id="org_test", project_id="proj_test",
                auto_merge_threshold=0.85
            )
            inc = models.Incident(
                id="inc_test", organization_id="org_test", project_id="proj_test",
                exception_type="ValueError", exception_message="Oops",
                stack_trace="Traceback...", fingerprint="fp_test", status="PENDING_CI",
                affected_repository="test-owner/test-repo"
            )
            pc = models.PatchCandidate(
                id="patch_test", organization_id="org_test", incident_id="inc_test",
                diff="+++ fix.py", explanation="fix", is_valid=True
            )
            pr = models.PullRequest(
                id="pr_test", organization_id="org_test", project_id="proj_test",
                patch_candidate_id="patch_test", github_pr_number=100,
                github_pr_url="https://github.com/test-owner/test-repo/pull/100", status="OPEN"
            )
            dec = models.Decision(
                id="dec_test", organization_id="org_test", patch_candidate_id="patch_test",
                status="APPROVED", action="AUTO_MERGE", reason="Auto-merge authorized",
                inputs={
                    "trust_score": 0.90,
                    "test_result": True,
                    "sensitive_file_flags": False
                }
            )
            ci = models.CIStatus(
                id="ci_test", organization_id="org_test", pull_request_id="pr_test",
                status="SUCCESS", context="continuous-integration/github-actions"
            )
            db.add_all([org, proj, policy, inc, pc, pr, dec, ci])
            await db.commit()
    run_sync(seed_data())

    # 2. Call evaluate_and_merge_pr_task in github-worker tasks
    github_worker_tasks = get_github_worker_tasks()
    evaluate_and_merge_pr_task = github_worker_tasks.evaluate_and_merge_pr_task
    
    with patch("github_worker_tasks.GitHubAppClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.mock = True
        mock_client.get_branch_protection.return_value = {
            "required_status_checks": {"contexts": ["continuous-integration/github-actions"]},
            "required_pull_request_reviews": {"required_approving_review_count": 0}
        }
        mock_client.merge_pull_request.return_value = True
        mock_client_class.return_value = mock_client
        
        # Run task
        evaluate_and_merge_pr_task("inc_test")
        
        # Verify client merge called
        assert mock_client.merge_pull_request.called
        assert mock_client.merge_pull_request.call_args[0] == ("test-owner/test-repo", 100)

    # 3. Verify final DB states (Incident should be closed as VERIFIED/MERGED, PR should be MERGED)
    async def verify_terminal_states():
        async with AsyncSessionLocal() as db:
            pr_res = await db.execute(select(models.PullRequest).where(models.PullRequest.id == "pr_test"))
            pr = pr_res.scalar_one()
            assert pr.status == "MERGED"

            inc_res = await db.execute(select(models.Incident).where(models.Incident.id == "inc_test"))
            inc = inc_res.scalar_one()
            assert inc.status == "VERIFIED"
    run_sync(verify_terminal_states())


def test_merge_evaluation_fails_low_trust() -> None:
    # 1. Seed data with low trust score (e.g. 0.60)
    async def seed_data():
        async with AsyncSessionLocal() as db:
            org = models.Organization(id="org_test", name="Test Org")
            proj = models.Project(id="proj_test", organization_id="org_test", name="Test Repo", repository="test-owner/test-repo")
            policy = models.ProjectPolicy(
                id="pol_test", organization_id="org_test", project_id="proj_test",
                auto_merge_threshold=0.85
            )
            inc = models.Incident(
                id="inc_test", organization_id="org_test", project_id="proj_test",
                exception_type="ValueError", exception_message="Oops",
                stack_trace="Traceback...", fingerprint="fp_test", status="PENDING_CI",
                affected_repository="test-owner/test-repo"
            )
            pc = models.PatchCandidate(
                id="patch_test", organization_id="org_test", incident_id="inc_test",
                diff="+++ fix.py", explanation="fix", is_valid=True
            )
            pr = models.PullRequest(
                id="pr_test", organization_id="org_test", project_id="proj_test",
                patch_candidate_id="patch_test", github_pr_number=100,
                github_pr_url="https://github.com/test-owner/test-repo/pull/100", status="OPEN"
            )
            dec = models.Decision(
                id="dec_test", organization_id="org_test", patch_candidate_id="patch_test",
                status="APPROVED", action="AUTO_MERGE", reason="Auto-merge authorized",
                inputs={
                    "trust_score": 0.60, # Below 0.85!
                    "test_result": True,
                    "sensitive_file_flags": False
                }
            )
            ci = models.CIStatus(
                id="ci_test", organization_id="org_test", pull_request_id="pr_test",
                status="SUCCESS", context="continuous-integration/github-actions"
            )
            db.add_all([org, proj, policy, inc, pc, pr, dec, ci])
            await db.commit()
    run_sync(seed_data())

    github_worker_tasks = get_github_worker_tasks()
    evaluate_and_merge_pr_task = github_worker_tasks.evaluate_and_merge_pr_task
    
    with patch("github_worker_tasks.GitHubAppClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.mock = True
        mock_client_class.return_value = mock_client
        
        # Run task
        evaluate_and_merge_pr_task("inc_test")
        
        # Merge must not be called
        assert not mock_client.merge_pull_request.called

    # 2. Verify Incident transitioned to HUMAN_REVIEW
    async def verify_human_review():
        async with AsyncSessionLocal() as db:
            inc_res = await db.execute(select(models.Incident).where(models.Incident.id == "inc_test"))
            inc = inc_res.scalar_one()
            assert inc.status == "HUMAN_REVIEW"
            
            pr_res = await db.execute(select(models.PullRequest).where(models.PullRequest.id == "pr_test"))
            pr = pr_res.scalar_one()
            assert pr.status == "OPEN" # Kept open for human review
    run_sync(verify_human_review())


def json_serialize(obj: dict) -> str:
    import json
    return json.dumps(obj)

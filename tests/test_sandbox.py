import os
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from database import get_db
import models
import schemas
from sandbox_manager.runner import SandboxConfig, SandboxRunner
from sandbox_manager.storage import upload_artifact

client = TestClient(app)

# Check if Docker is available locally for integration tests
try:
    import docker
    docker_client = docker.from_env()
    docker_client.ping()
    DOCKER_AVAILABLE = True
    docker_client.close()
except Exception:
    DOCKER_AVAILABLE = False

print(f"Docker available for integration tests: {DOCKER_AVAILABLE}")


def test_sandbox_config_schema():
    """
    Verify SandboxConfig schema validation.
    """
    config = schemas.SandboxConfig(
        cpu_limit=1.0,
        memory_limit="256m",
        timeout=120,
        network_mode="bridge",
        test_command="pytest tests/test_users.py",
        working_directory="/tmp/workspace",
        environment_allowlist=["TEST_ENV"],
        image="python:3.11-slim"
    )
    assert config.cpu_limit == 1.0
    assert config.memory_limit == "256m"
    assert config.timeout == 120
    assert config.network_mode == "bridge"
    assert config.test_command == "pytest tests/test_users.py"
    assert config.working_directory == "/tmp/workspace"
    assert "TEST_ENV" in config.environment_allowlist
    assert config.image == "python:3.11-slim"


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker is not running or available")
def test_docker_sandbox_runner_success(tmp_path):
    """
    Integration test executing a real docker container.
    Fixes a bug in a temp repo and runs tests.
    """
    # Create a mock python repository locally
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    app_file = repo_dir / "app.py"
    app_file.write_text("def add(x, y):\n    return x + y\n")
    
    test_file = repo_dir / "test_app.py"
    test_file.write_text("from app import add\ndef test_add():\n    assert add(2, 3) == 5\n")
    
    req_file = repo_dir / "requirements.txt"
    req_file.write_text("pytest\n")
    
    # Candidate patch: edit add function behavior (e.g. dummy comment)
    patch_diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def add(x, y):\n"
        "+    # A dummy patch change\n"
        "     return x + y\n"
    )

    config = SandboxConfig(
        cpu_limit=0.5,
        memory_limit="128m",
        timeout=60,
        network_mode="none",  # no internet needed for simple tests
        test_command="pytest test_app.py",
        working_directory="/tmp/workspace",
        image="python:3.11-slim"
    )
    
    runner = SandboxRunner(config)
    result = runner.run(
        job_id="test_run_success",
        repo_url=str(repo_dir),
        commit_hash="HEAD",
        patch_diff=patch_diff
    )
    
    assert result["exit_code"] == 0
    assert result["duration"] > 0
    assert "test_add" in result["stdout"] or "test_add" in result["stderr"] or "passed" in result["stdout"].lower()
    assert result["resource_usage"].get("max_memory_bytes", 0) > 0


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker is not running or available")
def test_docker_sandbox_runner_timeout(tmp_path):
    """
    Integration test validating container execution timeout.
    """
    repo_dir = tmp_path / "test_repo_timeout"
    repo_dir.mkdir()
    
    app_file = repo_dir / "app.py"
    app_file.write_text("import time\ndef hang():\n    time.sleep(30)\n")
    
    test_file = repo_dir / "test_app.py"
    test_file.write_text("from app import hang\ndef test_hang():\n    hang()\n")
    
    patch_diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,3 +1,4 @@\n"
        " import time\n"
        " def hang():\n"
        "+    # modified\n"
        "     time.sleep(30)\n"
    )

    # Set very short timeout of 3 seconds
    config = SandboxConfig(
        cpu_limit=0.5,
        memory_limit="128m",
        timeout=3,
        network_mode="none",
        test_command="pytest test_app.py",
        working_directory="/tmp/workspace",
        image="python:3.11-slim"
    )
    
    runner = SandboxRunner(config)
    result = runner.run(
        job_id="test_run_timeout",
        repo_url=str(repo_dir),
        commit_hash="HEAD",
        patch_diff=patch_diff
    )
    
    assert "timeout" in result["error_message"].lower()
    assert result["exit_code"] == -1


def test_storage_client_no_config():
    """
    Verify storage client uploads return None when env is not configured.
    """
    with patch.dict(os.environ, {}, clear=True):
        res = upload_artifact("job_123", "stdout", "some logs")
        assert res is None


@patch("sandbox_manager.storage.get_s3_client")
def test_storage_client_upload_success(mock_get_s3):
    """
    Verify storage client puts object and returns URL when configured.
    """
    mock_s3 = MagicMock()
    mock_get_s3.return_value = (mock_s3, "my-bucket")
    
    with patch.dict(os.environ, {"S3_ENDPOINT_URL": "http://localhost:9000"}):
        res = upload_artifact("job_123", "stdout", "some logs")
        assert res == "http://localhost:9000/my-bucket/sandbox_runs/job_123/stdout.log"
        mock_s3.put_object.assert_called_once_with(
            Bucket="my-bucket",
            Key="sandbox_runs/job_123/stdout.log",
            Body=b"some logs",
            ContentType="text/plain"
        )


@pytest.mark.asyncio
@patch("routes.sandbox.celery_app.send_task")
@patch("routes.sandbox.aioredis.from_url")
async def test_create_sandbox_job_api(mock_redis_from_url, mock_send_task) -> None:
    """
    Verify FastAPI SandboxJob trigger route.
    """
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    
    # Mock database responses for validation
    mock_pc = models.PatchCandidate(
        id="patch_test_123",
        organization_id="org_test",
        incident_id="inc_test",
        diff="--- diff",
        explanation="ex"
    )
    mock_inc = models.Incident(
        id="inc_test",
        organization_id="org_test",
        project_id="proj_test"
    )
    
    # Setup database execute chain
    mock_pc_res = MagicMock()
    mock_pc_res.scalar_one_or_none.return_value = mock_pc
    
    mock_inc_res = MagicMock()
    mock_inc_res.scalar_one_or_none.return_value = mock_inc
    
    mock_db.execute.side_effect = [mock_pc_res, mock_inc_res]
    
    # Mock Redis client pubsub
    mock_redis = AsyncMock()
    mock_redis_from_url.return_value = mock_redis
    
    from auth.dependencies import require_membership
    
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[require_membership] = lambda: models.Membership(
        id="mem_test", organization_id="org_test", user_id="usr_test", role="OWNER"
    )
    
    try:
        payload = {
            "patch_candidate_id": "patch_test_123",
            "config": {
                "cpu_limit": 0.5,
                "memory_limit": "256m",
                "timeout": 180,
                "test_command": "pytest"
            }
        }
        headers = {
            "X-User-ID": "usr_test",
            "X-User-Email": "test@org.com",
            "X-Organization-ID": "org_test"
        }
        
        response = client.post("/api/v1/sandbox/jobs", json=payload, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "QUEUED"
        assert data["patch_candidate_id"] == "patch_test_123"
        assert data["config"]["cpu_limit"] == 0.5
        
        # Verify Celery send_task was called with tasks.run_sandbox_job
        mock_send_task.assert_called_once_with(
            "tasks.run_sandbox_job",
            args=[data["id"]],
            queue="celery"
        )
    finally:
        app.dependency_overrides.clear()

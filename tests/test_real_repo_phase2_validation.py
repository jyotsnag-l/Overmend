import os
import subprocess
import pytest
from dotenv import load_dotenv
load_dotenv(override=True)

from schemas import EventCreate
from github_client.repo_manager import RepositoryManager, RepositoryWorkspace


def test_real_github_repo_phase2_flow():
    """
    Validates Phase 2 flow against the real GitHub repository:
    incident/event
        ↓
    repository + SHA
        ↓
    RepositoryManager
        ↓
    temporary workspace
        ↓
    workspace contains recovery-test-repo at exact SHA
    """
    repo = "jyotsnag-l/recovery-test-repo"
    target_sha = "a9ca1cde1290cffc76efaea7d4eba107765ebf43"

    # 1. Event layer receives event with commit_sha
    event = EventCreate(
        project_id="proj_recovery_test",
        event_type="error",
        exception_type="ZeroDivisionError",
        exception_message="division by zero",
        stack_trace="Traceback (most recent call last):\n  File 'app/services/order_service.py', line 22\nZeroDivisionError",
        commit_sha=target_sha
    )
    assert event.commit_sha == target_sha

    # 2. Extract repository and commit SHA for recovery
    resolved_repo = repo
    resolved_sha = event.commit_sha

    # 3. RepositoryManager acquires workspace at exact SHA
    repo_manager = RepositoryManager()
    workspace = repo_manager.acquire(
        repository=resolved_repo,
        commit_sha=resolved_sha,
        incident_id="phase2_real_val"
    )

    try:
        # 4. Verify workspace exists and is isolated
        assert os.path.exists(workspace.path), f"Workspace path does not exist: {workspace.path}"
        assert workspace.commit_sha == target_sha
        assert workspace.is_temporary is True

        # 5. Verify git HEAD matches requested exact commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace.path,
            capture_output=True,
            text=True,
            check=True
        )
        actual_head = result.stdout.strip()
        assert actual_head.lower() == target_sha.lower(), f"Expected HEAD {target_sha}, got {actual_head}"

        # 6. Verify contents of recovery-test-repo exist in workspace
        expected_file = os.path.join(workspace.path, "app", "services", "order_service.py")
        assert os.path.exists(expected_file), f"Expected file {expected_file} not found in workspace"

        # Check order_service content
        with open(expected_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "class OrderService" in content or "def " in content

    finally:
        # 7. Verify cleanup
        workspace_path = workspace.path
        workspace.cleanup()
        assert not os.path.exists(workspace_path), f"Workspace was not cleaned up: {workspace_path}"

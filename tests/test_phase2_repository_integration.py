import os
import shutil
import tempfile
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from schemas import EventCreate, IncidentBase
from github_client.repo_manager import (
    RepositoryManager,
    RepositoryWorkspace,
    RepositoryManagerError,
    CommitNotFoundError,
)
import models


def test_schema_event_and_incident_accept_commit_sha():
    """Test A: EventCreate and IncidentBase schemas accept commit_sha and git_commit."""
    # Test commit_sha
    event = EventCreate(
        project_id="proj_test",
        event_type="error",
        exception_type="ValueError",
        exception_message="Invalid value",
        stack_trace="Traceback (most recent call last):\n  File 'test.py', line 1\nValueError",
        commit_sha="a9ca1cde1290cffc76efaea7d4eba107765ebf43"
    )
    assert event.commit_sha == "a9ca1cde1290cffc76efaea7d4eba107765ebf43"
    assert event.git_commit == "a9ca1cde1290cffc76efaea7d4eba107765ebf43"

    # Test git_commit alias compatibility
    event_legacy = EventCreate(
        project_id="proj_test",
        event_type="error",
        exception_type="ValueError",
        exception_message="Invalid value",
        stack_trace="Traceback (most recent call last):\n  File 'test.py', line 1\nValueError",
        git_commit="b0012c6a044beea57c4a830f7631e1cfef5de2af"
    )
    assert event_legacy.commit_sha == "b0012c6a044beea57c4a830f7631e1cfef5de2af"
    assert event_legacy.git_commit == "b0012c6a044beea57c4a830f7631e1cfef5de2af"

    # Test IncidentBase
    inc = IncidentBase(
        title="Test Incident",
        exception_type="ValueError",
        exception_message="Invalid value",
        stack_trace="Traceback (most recent call last):\n  File 'test.py', line 1\nValueError",
        commit_sha="a9ca1cde1290cffc76efaea7d4eba107765ebf43"
    )
    assert inc.commit_sha == "a9ca1cde1290cffc76efaea7d4eba107765ebf43"


@pytest.mark.asyncio
async def test_event_pipeline_stores_commit_sha_in_incident_context(monkeypatch):
    """Test B: Event pipeline stores commit_sha and repository in incident context and dispatches recovery."""
    monkeypatch.setenv("BYPASS_CELERY", "false")
    import pipeline

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    
    mock_project = models.Project(id="proj_1", organization_id="org_1", repository="owner/test-repo")
    mock_policy = models.ProjectPolicy(
        id="pol_1",
        organization_id="org_1",
        project_id="proj_1",
        severity_rules={},
        anomaly_frequency_threshold=10,
        anomaly_zscore_threshold=3.0,
        anomaly_ewma_threshold=5.0
    )

    res_empty_inc = MagicMock()
    res_empty_inc.scalar_one_or_none.return_value = None

    res_pol = MagicMock()
    res_pol.scalar_one_or_none.return_value = mock_policy

    mock_db.execute.side_effect = [res_empty_inc, res_pol]

    event = EventCreate(
        project_id="proj_1",
        event_type="error",
        exception_type="TypeError",
        exception_message="NoneType error",
        stack_trace="Traceback:\n  File 'test.py', line 1\nTypeError",
        commit_sha="a9ca1cde1290cffc76efaea7d4eba107765ebf43"
    )

    with patch("pipeline.celery_app.send_task") as mock_send_task:
        result = await pipeline.process_event_pipeline(mock_db, event, mock_project)
        assert result.affected_repository == "owner/test-repo"
        assert result.context["commit_sha"] == "a9ca1cde1290cffc76efaea7d4eba107765ebf43"
        assert result.context["git_commit"] == "a9ca1cde1290cffc76efaea7d4eba107765ebf43"

        # Verify Celery send_task was called with repository and commit_sha
        mock_send_task.assert_called_once()
        task_name, task_kwargs = mock_send_task.call_args[0], mock_send_task.call_args[1]
        assert task_name[0] == "tasks.run_recovery_pipeline"
        assert task_kwargs["args"][1] == "owner/test-repo"
        assert task_kwargs["args"][3] == "a9ca1cde1290cffc76efaea7d4eba107765ebf43"


def test_repository_manager_acquisition_and_workspace_lifecycle():
    """Test C, D, E, F, G: RepositoryManager receives repo and SHA, creates workspace, passes path, and cleans up."""
    from tasks import run_recovery_pipeline

    incident_id = "inc_test_123"
    repo = "test-org/test-repo"
    commit_sha = "a9ca1cde1290cffc76efaea7d4eba107765ebf43"
    stack_trace = "Traceback (most recent call last):\n  File 'app.py', line 10\nZeroDivisionError"

    # Setup a mock temporary workspace
    temp_dir = tempfile.mkdtemp(prefix="test_overmend_ws_")
    mock_workspace = RepositoryWorkspace(
        path=temp_dir,
        repository=repo,
        commit_sha=commit_sha
    )
    cleanup_called = False
    original_cleanup = mock_workspace.cleanup
    def tracked_cleanup():
        nonlocal cleanup_called
        cleanup_called = True
        original_cleanup()
    mock_workspace.cleanup = tracked_cleanup

    with patch("tasks.github_client.RepositoryManager") as MockRepoManager, \
         patch("tasks.async_transition_state"), \
         patch("tasks.fault_localizer.localize_fault") as mock_localize, \
         patch("tasks.generate_and_store_patches") as mock_patches, \
         patch("tasks.async_store_pull_request"), \
         patch("tasks.async_record_historical_recovery"):

        mock_instance = MockRepoManager.return_value
        mock_instance.acquire.return_value = mock_workspace

        mock_localize.return_value = {"file": "app.py", "line": 10, "confidence": 0.9}
        mock_patches.return_value = [] # End early without error

        result = run_recovery_pipeline(
            incident_id=incident_id,
            repo=repo,
            stack_trace=stack_trace,
            commit_sha=commit_sha
        )

        # C. RepositoryManager receives expected repo and SHA
        mock_instance.acquire.assert_called_once_with(
            repository=repo,
            commit_sha=commit_sha,
            incident_id=incident_id
        )

        # D & E. Workspace path was passed to fault_localizer
        mock_localize.assert_called_once()
        assert mock_localize.call_args[1]["repo_path"] == temp_dir

        # F. Requested SHA was preserved
        assert mock_workspace.commit_sha == commit_sha

        # G. Workspace cleanup was executed
        assert cleanup_called is True
        assert not os.path.exists(temp_dir)


def test_repository_manager_cleanup_on_pipeline_failure():
    """Test H: Workspace cleanup happens in finally even if the recovery pipeline raises an unhandled exception."""
    from tasks import run_recovery_pipeline

    incident_id = "inc_fail_123"
    repo = "test-org/fail-repo"
    commit_sha = "deadbeef1234567890abcdef"
    stack_trace = "Traceback (most recent call last):\n  File 'broken.py', line 1\nSyntaxError"

    temp_dir = tempfile.mkdtemp(prefix="test_overmend_fail_ws_")
    mock_workspace = RepositoryWorkspace(
        path=temp_dir,
        repository=repo,
        commit_sha=commit_sha
    )
    cleanup_called = False
    original_cleanup = mock_workspace.cleanup
    def tracked_cleanup():
        nonlocal cleanup_called
        cleanup_called = True
        original_cleanup()
    mock_workspace.cleanup = tracked_cleanup

    with patch("tasks.github_client.RepositoryManager") as MockRepoManager, \
         patch("tasks.async_transition_state"), \
         patch("tasks.fault_localizer.localize_fault") as mock_localize:

        mock_instance = MockRepoManager.return_value
        mock_instance.acquire.return_value = mock_workspace
        
        # Simulate downstream failure during localization
        mock_localize.side_effect = RuntimeError("Catastrophic downstream analysis failure")

        with pytest.raises(RuntimeError, match="Catastrophic downstream analysis failure"):
            run_recovery_pipeline(
                incident_id=incident_id,
                repo=repo,
                stack_trace=stack_trace,
                commit_sha=commit_sha
            )

        # H. Verify cleanup was still called in finally block
        assert cleanup_called is True
        assert not os.path.exists(temp_dir)


def test_local_repository_behavior_preserved():
    """Test I: Local repository path (e.g. demo-repo) resolves isolated workspace and executes cleanly."""
    repo_manager = RepositoryManager()
    
    # Acquire local demo-repo
    ws = repo_manager.acquire("demo-repo", incident_id="local_test")
    try:
        assert os.path.exists(ws.path)
        assert "demo-repo" in ws.repository
        # Check that demo-repo files exist inside the workspace
        assert os.path.exists(os.path.join(ws.path, "users.py"))
    finally:
        ws.cleanup()
        assert not os.path.exists(ws.path)

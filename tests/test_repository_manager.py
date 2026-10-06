import os
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from github_client import (
    RepositoryManager,
    RepositoryWorkspace,
    InvalidRepositoryError,
    RepositoryNotFoundError,
    CommitNotFoundError,
    AuthenticationError,
    CloneError,
    parse_repository_identity,
)


@pytest.fixture
def local_git_repo(tmp_path):
    """
    Creates a temporary local git repository with multiple commits and branches
    to serve as a realistic, deterministic fixture for unit testing.
    """
    repo_dir = tmp_path / "source_repo"
    repo_dir.mkdir()

    # Helper for running git inside fixture
    def run_git(*args):
        subprocess.run(
            ["git"] + list(args),
            cwd=str(repo_dir),
            check=True,
            capture_output=True,
            text=True
        )

    run_git("init")
    run_git("config", "user.name", "Overmend Unit Test")
    run_git("config", "user.email", "test@overmend.local")

    # Commit 1: base files
    file1 = repo_dir / "app.py"
    file1.write_text("def run():\n    return 'v1'\n", encoding="utf-8")
    run_git("add", "app.py")
    run_git("commit", "-m", "Initial commit (v1)")
    sha1 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()

    # Create a feature branch at commit 1
    run_git("branch", "v1-branch")

    # Commit 2: update app.py and add helper.py
    file1.write_text("def run():\n    return 'v2'\n", encoding="utf-8")
    file2 = repo_dir / "helper.py"
    file2.write_text("def helper():\n    return True\n", encoding="utf-8")
    run_git("add", "app.py", "helper.py")
    run_git("commit", "-m", "Second commit (v2)")
    sha2 = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()

    return {
        "path": str(repo_dir),
        "sha1": sha1,
        "sha2": sha2
    }


# =====================================================================
# Unit Tests
# =====================================================================

def test_parse_repository_identity(tmp_path):
    """Tests URL, slug, and path parsing."""
    # Local path
    dummy_dir = tmp_path / "my_dir"
    dummy_dir.mkdir()
    parsed, is_local = parse_repository_identity(str(dummy_dir))
    assert is_local is True
    assert os.path.samefile(parsed, str(dummy_dir))

    # Slug
    parsed, is_local = parse_repository_identity("acme-corp/payment-service")
    assert is_local is False
    assert parsed == "acme-corp/payment-service"

    # HTTPS URL
    parsed, is_local = parse_repository_identity("https://github.com/acme-corp/payment-service.git")
    assert is_local is False
    assert parsed == "acme-corp/payment-service"

    # SSH URL
    parsed, is_local = parse_repository_identity("git@github.com:acme-corp/payment-service.git")
    assert is_local is False
    assert parsed == "acme-corp/payment-service"

    # Invalid identities
    with pytest.raises(InvalidRepositoryError):
        parse_repository_identity("")

    with pytest.raises(InvalidRepositoryError):
        parse_repository_identity("invalid_no_slash")

    with pytest.raises(RepositoryNotFoundError):
        parse_repository_identity("./non_existent_folder_xyz_123")


def test_temporary_workspace_created(local_git_repo):
    """Test 1: Verifies a unique temporary workspace is created."""
    manager = RepositoryManager()
    ws1 = manager.acquire(local_git_repo["path"], incident_id="inc_001")
    ws2 = manager.acquire(local_git_repo["path"], incident_id="inc_002")

    try:
        assert os.path.exists(ws1.path)
        assert os.path.exists(ws2.path)
        # Ensure workspaces are completely isolated
        assert ws1.path != ws2.path
        assert "inc_001" in ws1.path
        assert "inc_002" in ws2.path
    finally:
        manager.cleanup(ws1)
        manager.cleanup(ws2)


def test_repository_is_obtained(local_git_repo):
    """Test 2 & 4: Verifies repository files are present in the acquired workspace."""
    manager = RepositoryManager()
    with manager.acquire(local_git_repo["path"]) as ws:
        app_file = os.path.join(ws.path, "app.py")
        helper_file = os.path.join(ws.path, "helper.py")

        assert os.path.isfile(app_file)
        assert os.path.isfile(helper_file)

        with open(app_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "def run():" in content


def test_requested_commit_sha_checked_out(local_git_repo):
    """Test 3: Verifies exact commit SHA is checked out and verified."""
    manager = RepositoryManager()

    # Request the older commit (sha1)
    with manager.acquire(local_git_repo["path"], commit_sha=local_git_repo["sha1"]) as ws:
        app_file = os.path.join(ws.path, "app.py")
        helper_file = os.path.join(ws.path, "helper.py")

        # helper.py should NOT exist at commit 1
        assert not os.path.exists(helper_file)

        with open(app_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "'v1'" in content

        # Verify HEAD matches requested sha1
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ws.path,
            capture_output=True,
            text=True,
            check=True
        )
        assert res.stdout.strip() == local_git_repo["sha1"]
        assert ws.commit_sha == local_git_repo["sha1"]

    # Request commit 2 (sha2)
    with manager.acquire(local_git_repo["path"], commit_sha=local_git_repo["sha2"]) as ws:
        helper_file = os.path.join(ws.path, "helper.py")
        assert os.path.exists(helper_file)
        assert ws.commit_sha == local_git_repo["sha2"]


def test_repository_acquisition_does_not_modify_source(local_git_repo):
    """Test 5: Verifies the source repository is never modified."""
    source_app = os.path.join(local_git_repo["path"], "app.py")
    with open(source_app, "r", encoding="utf-8") as f:
        original_content = f.read()

    manager = RepositoryManager()
    # Acquire at older commit
    with manager.acquire(local_git_repo["path"], commit_sha=local_git_repo["sha1"]) as ws:
        # Mutate the acquired workspace copy to simulate patch/work
        mutated_file = os.path.join(ws.path, "app.py")
        with open(mutated_file, "w", encoding="utf-8") as f:
            f.write("# MUTATED IN WORKSPACE\n")

    # Verify source repository file is unchanged
    with open(source_app, "r", encoding="utf-8") as f:
        source_content = f.read()

    assert source_content == original_content
    assert "# MUTATED IN WORKSPACE" not in source_content

    # Verify source git HEAD was not altered
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=local_git_repo["path"],
        capture_output=True,
        text=True,
        check=True
    )
    assert res.stdout.strip() == local_git_repo["sha2"]


def test_cleanup_removes_temporary_workspace(local_git_repo):
    """Test 6: Verifies cleanup removes the temporary workspace."""
    manager = RepositoryManager()
    ws = manager.acquire(local_git_repo["path"])
    ws_path = ws.path
    assert os.path.exists(ws_path)

    # Trigger cleanup
    manager.cleanup(ws)
    assert not os.path.exists(ws_path)

    # Calling cleanup again is safe (idempotent)
    manager.cleanup(ws)
    manager.cleanup(ws_path)


def test_context_manager_cleanup(local_git_repo):
    """Verifies that exiting the context manager automatically deletes the workspace."""
    manager = RepositoryManager()
    saved_path = None
    with manager.acquire(local_git_repo["path"]) as ws:
        saved_path = ws.path
        assert os.path.exists(saved_path)

    assert not os.path.exists(saved_path)


def test_invalid_commit_sha_produces_clear_error(local_git_repo):
    """Test 7: Non-existent commit SHA produces a clear CommitNotFoundError."""
    manager = RepositoryManager()
    fake_sha = "0000000000000000000000000000000000000000"

    with pytest.raises(CommitNotFoundError) as exc_info:
        manager.acquire(local_git_repo["path"], commit_sha=fake_sha)

    assert fake_sha in str(exc_info.value)


def test_invalid_repository_produces_clear_error():
    """Test 7 (continued): Malformed or non-existent repo produces clear errors."""
    manager = RepositoryManager()

    with pytest.raises(InvalidRepositoryError):
        manager.acquire("not-a-valid-identity-no-slash")

    with pytest.raises(RepositoryNotFoundError):
        manager.acquire("./definitely_not_a_real_directory_12345")


def test_explicit_ref_checkout(local_git_repo):
    """Verifies explicit ref (branch) checkout."""
    manager = RepositoryManager()
    with manager.acquire(local_git_repo["path"], ref="v1-branch") as ws:
        app_file = os.path.join(ws.path, "app.py")
        with open(app_file, "r", encoding="utf-8") as f:
            assert "'v1'" in f.read()


def test_simulated_mock_remote_acquisition():
    """Verifies simulated remote acquisition in mock environment."""
    mock_client = MagicMock()
    mock_client.mock = True

    manager = RepositoryManager(github_client=mock_client)
    with manager.acquire("acme/payment-service", commit_sha="mock_sha_123") as ws:
        assert os.path.exists(ws.path)
        assert os.path.exists(os.path.join(ws.path, "main.py"))
        assert ws.commit_sha == "mock_sha_123"

    assert not os.path.exists(ws.path)


def test_token_scrubbing_in_errors():
    """Verifies access tokens are never leaked into error messages."""
    mock_client = MagicMock()
    mock_client.mock = False
    mock_client.get_token.return_value = "ghs_SUPER_SECRET_TOKEN_99999"

    manager = RepositoryManager(github_client=mock_client)

    # Force a clone failure by pointing to non-existent remote repository
    with pytest.raises((CloneError, RepositoryNotFoundError, AuthenticationError)) as exc_info:
        manager.acquire("nonexistent-org-998877/no-such-repo-112233", ref="main")

    error_text = str(exc_info.value)
    # The actual token must NOT appear in the exception message
    assert "ghs_SUPER_SECRET_TOKEN_99999" not in error_text


def test_existing_workspace_reset_and_preparation(local_git_repo, tmp_path):
    """Verifies that an existing workspace directory is cleaned of uncommitted edits before checkout."""
    manager = RepositoryManager()
    target_ws = str(tmp_path / "cached_workspace")

    # First acquisition into explicit target_dir
    ws1 = manager.acquire(local_git_repo["path"], commit_sha=local_git_repo["sha1"], target_dir=target_ws)
    assert os.path.exists(target_ws)
    assert ws1.commit_sha == local_git_repo["sha1"]

    # Dirty the workspace with uncommitted modifications and an untracked file
    dirty_file = os.path.join(target_ws, "app.py")
    with open(dirty_file, "w", encoding="utf-8") as f:
        f.write("# DIRTY MODIFICATION\n")
    untracked_file = os.path.join(target_ws, "untracked.tmp")
    with open(untracked_file, "w", encoding="utf-8") as f:
        f.write("temporary file")

    # Re-acquire into the same existing workspace for sha2
    ws2 = manager.acquire(local_git_repo["path"], commit_sha=local_git_repo["sha2"], target_dir=target_ws)
    assert ws2.commit_sha == local_git_repo["sha2"]
    assert not os.path.exists(untracked_file)
    with open(dirty_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "# DIRTY MODIFICATION" not in content
    assert "'v2'" in content


def test_dynamic_head_resolution(local_git_repo):
    """Verifies that omiting commit_sha or passing HEAD resolves to the latest commit dynamically."""
    manager = RepositoryManager()

    # None commit_sha
    with manager.acquire(local_git_repo["path"], commit_sha=None) as ws:
        assert ws.commit_sha == local_git_repo["sha2"]

    # 'HEAD' commit_sha
    with manager.acquire(local_git_repo["path"], commit_sha="HEAD") as ws:
        assert ws.commit_sha == local_git_repo["sha2"]


def test_target_dir_not_deleted_on_cleanup(local_git_repo, tmp_path):
    """Verifies that custom target_dir workspaces are not wiped by cleanup."""
    manager = RepositoryManager()
    target_ws = str(tmp_path / "persistent_workspace")

    ws = manager.acquire(local_git_repo["path"], target_dir=target_ws)
    assert os.path.exists(target_ws)
    ws.cleanup()
    assert os.path.exists(target_ws)

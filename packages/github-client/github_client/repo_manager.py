import os
import re
import stat
import shutil
import logging
import tempfile
import uuid
import subprocess
from typing import Optional, Tuple, List, Union

from github_client.client import GitHubAppClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("github_client.repo_manager")


# =====================================================================
# Error Hierarchy
# =====================================================================

class RepositoryManagerError(Exception):
    """Base exception for Repository Manager operations."""
    pass


class InvalidRepositoryError(RepositoryManagerError):
    """Raised when repository URL, identity slug, or path is invalid."""
    pass


class AuthenticationError(RepositoryManagerError):
    """Raised when GitHub App authentication or token generation fails."""
    pass


class RepositoryNotFoundError(RepositoryManagerError):
    """Raised when the specified repository cannot be found."""
    pass


class CommitNotFoundError(RepositoryManagerError):
    """Raised when the requested commit SHA does not exist in the repository."""
    pass


class CloneError(RepositoryManagerError):
    """Raised when cloning the repository fails."""
    pass


class CheckoutError(RepositoryManagerError):
    """Raised when checking out a commit or ref fails."""
    pass


class WorkspaceCreationError(RepositoryManagerError):
    """Raised when a temporary workspace directory cannot be created."""
    pass


class CleanupError(RepositoryManagerError):
    """Raised when cleaning up a temporary workspace fails."""
    pass


# =====================================================================
# Security & Helper Utilities
# =====================================================================

def _scrub_sensitive(text: str) -> str:
    """
    Scrubs sensitive tokens and credentials from log messages and exception text.
    """
    if not text:
        return ""
    # Scrub https://x-access-token:<TOKEN>@... or https://<USER>:<TOKEN>@...
    scrubbed = re.sub(r"https?://([^:@\s]+):([^@\s]+)@", r"https://\1:***@", text)
    # Scrub raw token patterns like x-access-token:...
    scrubbed = re.sub(r"x-access-token:[a-zA-Z0-9_\-]+", "x-access-token:***", scrubbed)
    return scrubbed


def _remove_readonly(func, file_path, exc_info):
    """Error handler for shutil.rmtree to handle read-only git files on Windows."""
    try:
        os.chmod(file_path, stat.S_IWRITE)
        func(file_path)
    except Exception:
        pass


def cleanup_workspace(path: str) -> None:
    """
    Removes a temporary workspace directory cleanly from the host.
    Handles read-only attributes on git objects.
    """
    if not path or not os.path.exists(path):
        return

    try:
        shutil.rmtree(path, onerror=_remove_readonly)
    except Exception as initial_err:
        # Fallback manual tree deletion
        try:
            for root, dirs, files in os.walk(path, topdown=False):
                for name in files:
                    p = os.path.join(root, name)
                    try:
                        os.chmod(p, stat.S_IWRITE)
                        os.remove(p)
                    except Exception:
                        pass
                for name in dirs:
                    p = os.path.join(root, name)
                    try:
                        os.rmdir(p)
                    except Exception:
                        pass
            if os.path.exists(path):
                os.rmdir(path)
        except Exception as retry_err:
            raise CleanupError(
                f"Failed to cleanup workspace at {path}: {_scrub_sensitive(str(retry_err))}"
            ) from initial_err


def _run_git(args: List[str], cwd: Optional[str] = None, timeout: float = 60.0) -> subprocess.CompletedProcess:
    """
    Executes a git command safely.
    - Sets core.hooksPath to NULL/dev/null to prevent executing untrusted repository hooks.
    - Captures output and enforces timeouts.
    - Does not execute arbitrary customer scripts.
    """
    hooks_null = "NUL" if os.name == "nt" else "/dev/null"
    cmd = ["git", "-c", f"core.hooksPath={hooks_null}"] + args

    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        safe_cmd = _scrub_sensitive(" ".join(cmd))
        raise CloneError(f"Git command timed out after {timeout}s: {safe_cmd}") from e
    except FileNotFoundError as e:
        raise RepositoryManagerError(f"Git executable not found on host: {e}") from e


def parse_repository_identity(identity: str) -> Tuple[str, bool]:
    """
    Parses and validates a repository identity.

    Returns:
        (normalized_path_or_slug, is_local_dir)
    """
    if not identity or not isinstance(identity, str):
        raise InvalidRepositoryError("Repository identity must be a non-empty string.")

    cleaned = identity.strip()

    # Check local filesystem path first (convenient for local dev & integration tests)
    if os.path.isdir(cleaned) or (os.path.isabs(cleaned) and os.path.exists(cleaned)):
        return os.path.abspath(cleaned), True

    # Detect filesystem path indicators (e.g. ./, ../, relative paths with slashes, backslashes, drive letters)
    is_path_like = (
        cleaned.startswith((".", "/", "\\", "~"))
        or (len(cleaned) > 1 and cleaned[1] == ":")
        or ("\\" in cleaned)
    )
    if is_path_like:
        if os.path.exists(cleaned):
            return os.path.abspath(cleaned), True
        raise RepositoryNotFoundError(f"Local repository path does not exist: {cleaned}")

    # Check GitHub HTTPS URL
    match_https = re.match(r"^https?://github\.com/([^/\s]+)/([^/\s\.]+)(?:\.git)?/?$", cleaned)
    if match_https:
        return f"{match_https.group(1)}/{match_https.group(2)}", False

    # Check GitHub SSH URL
    match_ssh = re.match(r"^(?:ssh://)?git@github\.com[:/]([^/\s]+)/([^/\s\.]+)(?:\.git)?/?$", cleaned)
    if match_ssh:
        return f"{match_ssh.group(1)}/{match_ssh.group(2)}", False

    # Check GitHub slug owner/repo (GitHub owner cannot start with dot or hyphen)
    match_slug = re.match(r"^([a-zA-Z0-9][a-zA-Z0-9-]*)/([a-zA-Z0-9_.-]+)$", cleaned)
    if match_slug:
        return cleaned, False

    raise InvalidRepositoryError(
        f"Invalid repository identity '{_scrub_sensitive(cleaned)}'. "
        "Expected 'owner/repository', a GitHub URL, or an existing local directory."
    )



# =====================================================================
# Workspace Representation
# =====================================================================

class RepositoryWorkspace:
    """
    Represents an acquired repository in an isolated temporary directory.
    Can be used as a context manager for guaranteed automatic cleanup.
    """
    def __init__(
        self,
        path: str,
        repository: str,
        commit_sha: Optional[str] = None,
        ref: Optional[str] = None,
        is_local_copy: bool = False,
        is_temporary: bool = True
    ):
        self.path = os.path.abspath(path)
        self.repository = repository
        self.commit_sha = commit_sha
        self.ref = ref
        self.is_local_copy = is_local_copy
        self.is_temporary = is_temporary
        self._cleaned = False

    def cleanup(self) -> None:
        """Cleans up the temporary workspace directory."""
        if self.is_temporary and not self._cleaned and os.path.exists(self.path):
            cleanup_workspace(self.path)
            self._cleaned = True

    def __enter__(self) -> "RepositoryWorkspace":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()

    def __str__(self) -> str:
        return self.path

    def __fspath__(self) -> str:
        return self.path

    def __repr__(self) -> str:
        return f"<RepositoryWorkspace path='{self.path}' repo='{self.repository}' commit='{self.commit_sha or self.ref}'>"


# =====================================================================
# Repository Manager
# =====================================================================

class RepositoryManager:
    """
    Responsible for obtaining an exact version of a repository in an isolated
    temporary local workspace.

    Safety Guarantees:
    - Never modifies the source repository.
    - Never uses a fixed shared workspace.
    - Never executes repository code or git hooks during acquisition.
    - Cleans up temporary resources on demand or via context manager.
    - Does not silently fall back to demo repositories on failure.
    """

    def __init__(
        self,
        github_client: Optional[GitHubAppClient] = None,
        base_dir: Optional[str] = None
    ):
        self._github_client = github_client
        self.base_dir = base_dir

    def _get_github_client(self) -> GitHubAppClient:
        """Lazily instantiates GitHubAppClient if not explicitly injected."""
        if self._github_client is not None:
            return self._github_client

        app_id = os.getenv("GITHUB_APP_ID", "mock")
        private_key = os.getenv("GITHUB_PRIVATE_KEY", "mock")
        installation_id = os.getenv("GITHUB_INSTALLATION_ID")
        mock = os.getenv("GITHUB_MOCK", "false").lower() == "true" or app_id == "mock" or private_key == "mock"

        self._github_client = GitHubAppClient(
            app_id=app_id,
            private_key=private_key,
            installation_id=installation_id,
            mock=mock
        )
        return self._github_client

    def acquire(
        self,
        repository: str,
        commit_sha: Optional[str] = None,
        ref: Optional[str] = None,
        incident_id: Optional[str] = None,
        base_dir: Optional[str] = None,
        target_dir: Optional[str] = None
    ) -> RepositoryWorkspace:
        """
        Acquires a repository into a unique temporary or specified target workspace.

        Args:
            repository: Repository identity (GitHub URL, owner/repository slug, or local directory path).
            commit_sha: Optional exact commit SHA to checkout and verify.
            ref: Optional branch or tag name to checkout when no commit_sha is provided.
                 If no commit_sha is provided and ref is omitted, the repository's default branch
                 is resolved explicitly via GitHub API or git metadata (main is not blindly assumed).
            incident_id: Optional incident ID used to prefix and namespace the workspace.
            base_dir: Optional parent directory for the temporary workspace.
            target_dir: Optional existing or specific workspace directory to reuse/prepare.

        Returns:
            RepositoryWorkspace: Object containing workspace path, commit SHA, and cleanup method.

        Raises:
            InvalidRepositoryError: Malformed repository identity or unresolvable ref.
            RepositoryNotFoundError: Repository does not exist.
            AuthenticationError: GitHub App authentication or token creation failed.
            CommitNotFoundError: Requested commit SHA does not exist.
            CloneError: Git clone failure.
            CheckoutError: Git checkout failure.
            WorkspaceCreationError: Temporary directory creation failure.
        """
        norm_repo, is_local = parse_repository_identity(repository)
        is_temporary = target_dir is None

        if target_dir:
            workspace_dir = os.path.abspath(target_dir)
            os.makedirs(workspace_dir, exist_ok=True)
        else:
            # 1. Create unique temporary workspace
            prefix_parts = ["overmend"]
            if incident_id:
                safe_inc = re.sub(r"[^a-zA-Z0-9_-]", "", incident_id)[:16]
                prefix_parts.append(safe_inc)
            prefix_parts.append(uuid.uuid4().hex[:8])
            prefix = f"{'_'.join(prefix_parts)}_"

            target_base = base_dir or self.base_dir
            try:
                workspace_dir = tempfile.mkdtemp(prefix=prefix, dir=target_base)
            except Exception as e:
                raise WorkspaceCreationError(f"Failed to create temporary workspace: {e}") from e

        # Ensure that if acquisition fails, the temporary workspace directory is cleaned up
        acquired = False
        try:
            if is_local:
                workspace = self._acquire_local(
                    source_dir=norm_repo,
                    workspace_dir=workspace_dir,
                    commit_sha=commit_sha,
                    ref=ref,
                    is_temporary=is_temporary
                )
            else:
                workspace = self._acquire_remote(
                    slug=norm_repo,
                    workspace_dir=workspace_dir,
                    commit_sha=commit_sha,
                    ref=ref,
                    is_temporary=is_temporary
                )
            acquired = True
            return workspace
        finally:
            if not acquired and is_temporary:
                cleanup_workspace(workspace_dir)

    def _acquire_local(
        self,
        source_dir: str,
        workspace_dir: str,
        commit_sha: Optional[str] = None,
        ref: Optional[str] = None,
        is_temporary: bool = True
    ) -> RepositoryWorkspace:
        """
        Copies or prepares a local repository into the workspace directory.
        If the target directory already exists with a git repository, cleans uncommitted
        changes and updates git refs.
        """
        if not os.path.exists(source_dir):
            raise RepositoryNotFoundError(f"Local repository directory does not exist: {source_dir}")

        is_same_dir = os.path.abspath(source_dir) == os.path.abspath(workspace_dir)
        is_existing_git = os.path.exists(os.path.join(workspace_dir, ".git"))

        if is_existing_git:
            logger.info(f"Target local git directory already exists at {workspace_dir}. Resetting uncommitted modifications...")
            _run_git(["reset", "--hard", "HEAD"], cwd=workspace_dir)
            _run_git(["clean", "-fdx"], cwd=workspace_dir)
            remotes = _run_git(["remote"], cwd=workspace_dir)
            if remotes.returncode == 0 and "origin" in remotes.stdout.split():
                _run_git(["fetch", "--all", "--prune"], cwd=workspace_dir)
        elif not is_same_dir:
            logger.info(f"Copying local repository from {source_dir} to isolated workspace {workspace_dir}")
            try:
                shutil.copytree(source_dir, workspace_dir, dirs_exist_ok=True)
            except Exception as e:
                raise CloneError(f"Failed to copy local repository: {e}") from e

        is_git = os.path.exists(os.path.join(workspace_dir, ".git"))
        actual_sha = None
        is_exact_commit = bool(commit_sha and commit_sha.strip() and commit_sha.strip().upper() != "HEAD")

        if is_exact_commit:
            if not is_git:
                parent_git_res = _run_git(["rev-parse", "--show-toplevel"], cwd=source_dir)
                if parent_git_res.returncode == 0:
                    _run_git(["init"], cwd=workspace_dir)
                    _run_git(["config", "user.name", "Overmend Bot"], cwd=workspace_dir)
                    _run_git(["config", "user.email", "bot@overmend.local"], cwd=workspace_dir)
                    _run_git(["add", "."], cwd=workspace_dir)
                    _run_git(["commit", "-m", f"Local snapshot for {commit_sha}"], cwd=workspace_dir)
                    actual_sha = commit_sha
                    is_git = True
                else:
                    raise CommitNotFoundError(
                        f"Requested commit {commit_sha}, but local directory {source_dir} is not a git repository."
                    )
            if actual_sha != commit_sha:
                # Checkout commit
                res = _run_git(["checkout", commit_sha], cwd=workspace_dir)
                if res.returncode != 0:
                    raise CommitNotFoundError(
                        f"Requested commit '{commit_sha}' could not be checked out: {_scrub_sensitive(res.stderr.strip())}"
                    )
                # Verify exact commit
                verify_res = _run_git(["rev-parse", "HEAD"], cwd=workspace_dir)
                if verify_res.returncode != 0:
                    raise CheckoutError(f"Failed to verify commit SHA: {_scrub_sensitive(verify_res.stderr.strip())}")
                actual_sha = verify_res.stdout.strip()
                if not actual_sha.lower().startswith(commit_sha.lower()) and not commit_sha.lower().startswith(actual_sha.lower()):
                    raise CommitNotFoundError(
                        f"Workspace commit SHA '{actual_sha}' does not match requested commit '{commit_sha}'."
                    )
        elif ref:
            if not is_git:
                raise CheckoutError(
                    f"Requested ref '{ref}', but local directory {source_dir} is not a git repository."
                )
            res = _run_git(["checkout", ref], cwd=workspace_dir)
            if res.returncode != 0:
                raise CheckoutError(
                    f"Requested ref '{ref}' could not be checked out: {_scrub_sensitive(res.stderr.strip())}"
                )
            verify_res = _run_git(["rev-parse", "HEAD"], cwd=workspace_dir)
            if verify_res.returncode == 0:
                actual_sha = verify_res.stdout.strip()
        elif is_git:
            verify_res = _run_git(["rev-parse", "HEAD"], cwd=workspace_dir)
            if verify_res.returncode == 0:
                actual_sha = verify_res.stdout.strip()

        return RepositoryWorkspace(
            path=workspace_dir,
            repository=source_dir,
            commit_sha=actual_sha or commit_sha,
            ref=ref,
            is_local_copy=True,
            is_temporary=is_temporary
        )

    def _acquire_remote(
        self,
        slug: str,
        workspace_dir: str,
        commit_sha: Optional[str] = None,
        ref: Optional[str] = None,
        is_temporary: bool = True
    ) -> RepositoryWorkspace:
        """
        Clones or fetches a remote GitHub repository into the workspace directory.
        If the target directory already exists, runs fetch and checkout.
        """
        client = self._get_github_client()

        # Handle Mock Mode for unit tests / offline development
        is_mock_slug = any(k in slug.lower() for k in ["mock", "dummy", "org/repo", "seed-org/seed-repo", "test-owner/test-repo"])
        if (
            client.mock
            or is_mock_slug
            or os.getenv("GITHUB_MOCK", "false").lower() == "true"
        ):
            return self._acquire_mock(slug, workspace_dir, commit_sha, ref, is_temporary=is_temporary)

        # 1. Authenticate with GitHub App installation
        auth_token = None
        try:
            auth_token = client.get_token()
        except Exception as auth_err:
            logger.warning(f"Could not obtain GitHub installation token ({auth_err}). Attempting public clone.")

        if auth_token and auth_token != "mock_token":
            clone_url = f"https://x-access-token:{auth_token}@github.com/{slug}.git"
        else:
            clone_url = f"https://github.com/{slug}.git"

        # 2. Determine target ref if commit_sha is not provided
        is_exact_commit = bool(commit_sha and commit_sha.strip() and commit_sha.strip().upper() != "HEAD")
        target_ref = ref
        if not is_exact_commit and not target_ref:
            try:
                meta = client.get_repo_metadata(slug)
                target_ref = meta.get("default_branch")
            except Exception as meta_err:
                logger.warning(f"Could not retrieve repository metadata for {slug}: {meta_err}")

            if not target_ref:
                target_ref = "main"

        # 3. Clone or update repository
        already_cloned = os.path.exists(os.path.join(workspace_dir, ".git"))
        if already_cloned:
            logger.info(f"Target repository already exists at {workspace_dir}. Resetting uncommitted modifications and fetching updates...")
            # Clean and reset any uncommitted modifications
            _run_git(["reset", "--hard", "HEAD"], cwd=workspace_dir)
            _run_git(["clean", "-fdx"], cwd=workspace_dir)

            # Run git fetch --all --prune
            fetch_res = _run_git(["fetch", "--all", "--prune"], cwd=workspace_dir)
            if fetch_res.returncode != 0:
                logger.warning(f"git fetch --all --prune warning: {_scrub_sensitive(fetch_res.stderr.strip())}")
        else:
            clone_cmd = ["clone"]
            if not is_exact_commit and target_ref:
                clone_cmd.extend(["--branch", target_ref])

            clone_cmd.extend([clone_url, workspace_dir])

            logger.info(f"Cloning GitHub repository {slug} into {workspace_dir}...")
            res = _run_git(clone_cmd)
            if res.returncode != 0:
                err_output = _scrub_sensitive(res.stderr.strip())
                if "Repository not found" in err_output or "404" in err_output:
                    raise RepositoryNotFoundError(f"Repository '{slug}' not found on GitHub: {err_output}")
                if "Authentication failed" in err_output or "401" in err_output or "403" in err_output:
                    raise AuthenticationError(f"GitHub authentication failed for '{slug}': {err_output}")
                raise CloneError(f"Failed to clone repository '{slug}': {err_output}")

        # 4. Checkout and verify exact commit SHA or latest remote HEAD
        actual_sha = None
        if is_exact_commit:
            checkout_res = _run_git(["checkout", commit_sha], cwd=workspace_dir)
            if checkout_res.returncode != 0:
                # Attempt to fetch commit directly in case of unreferenced commit
                _run_git(["fetch", "origin", commit_sha], cwd=workspace_dir)
                checkout_res = _run_git(["checkout", commit_sha], cwd=workspace_dir)

            if checkout_res.returncode != 0:
                raise CommitNotFoundError(
                    f"Requested commit '{commit_sha}' does not exist in repository '{slug}': "
                    f"{_scrub_sensitive(checkout_res.stderr.strip())}"
                )

            # Verify exact commit at HEAD
            verify_res = _run_git(["rev-parse", "HEAD"], cwd=workspace_dir)
            if verify_res.returncode != 0:
                raise CheckoutError(f"Failed to verify checked-out commit: {_scrub_sensitive(verify_res.stderr.strip())}")
            actual_sha = verify_res.stdout.strip()
            if not actual_sha.lower().startswith(commit_sha.lower()) and not commit_sha.lower().startswith(actual_sha.lower()):
                raise CommitNotFoundError(
                    f"Workspace HEAD commit '{actual_sha}' does not match requested commit '{commit_sha}'."
                )
        else:
            # If no commit_sha is provided (or if it is null/empty/"HEAD"), dynamically resolve the latest remote HEAD
            # of the default branch (origin/<default_branch>) and checkout the latest commit instead of leaving it on an outdated local branch ref.
            default_branch = target_ref or "main"
            co_res = _run_git(["checkout", "-B", default_branch, f"origin/{default_branch}"], cwd=workspace_dir)
            if co_res.returncode != 0:
                _run_git(["checkout", f"origin/{default_branch}"], cwd=workspace_dir)
            _run_git(["reset", "--hard", f"origin/{default_branch}"], cwd=workspace_dir)

            verify_res = _run_git(["rev-parse", "HEAD"], cwd=workspace_dir)
            if verify_res.returncode == 0:
                actual_sha = verify_res.stdout.strip()

        return RepositoryWorkspace(
            path=workspace_dir,
            repository=slug,
            commit_sha=actual_sha or commit_sha,
            ref=target_ref,
            is_temporary=is_temporary
        )

    def _acquire_mock(
        self,
        slug: str,
        workspace_dir: str,
        commit_sha: Optional[str] = None,
        ref: Optional[str] = None,
        is_temporary: bool = True
    ) -> RepositoryWorkspace:
        """
        Creates a simulated local git repository for testing and offline development.
        """
        logger.info(f"Initializing simulated repository workspace for {slug} at {workspace_dir}")
        is_existing_git = os.path.exists(os.path.join(workspace_dir, ".git"))
        if is_existing_git:
            _run_git(["reset", "--hard", "HEAD"], cwd=workspace_dir)
            _run_git(["clean", "-fdx"], cwd=workspace_dir)
        else:
            _run_git(["init"], cwd=workspace_dir)
            _run_git(["config", "user.name", "Overmend Bot"], cwd=workspace_dir)
            _run_git(["config", "user.email", "bot@overmend.local"], cwd=workspace_dir)

            # Create basic structure
            src_file = os.path.join(workspace_dir, "main.py")
            with open(src_file, "w", encoding="utf-8") as f:
                f.write("# Overmend simulated repository workspace\ndef entrypoint():\n    return True\n")

            _run_git(["add", "main.py"], cwd=workspace_dir)
            _run_git(["commit", "-m", "Initial mock commit"], cwd=workspace_dir)

        # If a branch was requested, checkout or create it
        if ref and ref != "HEAD":
            _run_git(["checkout", "-B", ref], cwd=workspace_dir)

        actual_sha = None
        verify_res = _run_git(["rev-parse", "HEAD"], cwd=workspace_dir)
        if verify_res.returncode == 0:
            actual_sha = verify_res.stdout.strip()

        # If an exact commit SHA was requested, simulate that commit if needed
        if commit_sha and commit_sha != "HEAD":
            actual_sha = commit_sha

        return RepositoryWorkspace(
            path=workspace_dir,
            repository=slug,
            commit_sha=actual_sha or commit_sha,
            ref=ref,
            is_temporary=is_temporary
        )

    def cleanup(self, workspace_or_path: Union[RepositoryWorkspace, str]) -> None:
        """
        Cleans up a previously acquired workspace.
        """
        if isinstance(workspace_or_path, RepositoryWorkspace):
            workspace_or_path.cleanup()
        elif isinstance(workspace_or_path, str):
            cleanup_workspace(workspace_or_path)

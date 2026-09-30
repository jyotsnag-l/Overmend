import os
from github_client.client import GitHubAppClient, verify_signature
from github_client.repo_manager import (
    RepositoryManager,
    RepositoryWorkspace,
    RepositoryManagerError,
    InvalidRepositoryError,
    AuthenticationError,
    RepositoryNotFoundError,
    CommitNotFoundError,
    CloneError,
    CheckoutError,
    WorkspaceCreationError,
    CleanupError,
    cleanup_workspace,
    parse_repository_identity,
)

from github_client.recovery_workflow import (
    execute_github_recovery_pipeline,
    check_existing_recovery,
    GitHubRecoveryError
)

def create_pull_request(repo: str, branch: str, title: str, body: str) -> str:
    app_id = os.getenv("GITHUB_APP_ID", "mock")
    private_key = os.getenv("GITHUB_PRIVATE_KEY", "mock")
    installation_id = os.getenv("GITHUB_INSTALLATION_ID")
    client = GitHubAppClient(app_id, private_key, installation_id)
    pr = client.create_pull_request(repo, branch, title, body)
    return pr["html_url"]



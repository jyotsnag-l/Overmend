import os
from github_client.client import GitHubAppClient, verify_signature

def create_pull_request(repo: str, branch: str, title: str, body: str) -> str:
    app_id = os.getenv("GITHUB_APP_ID", "mock")
    private_key = os.getenv("GITHUB_PRIVATE_KEY", "mock")
    installation_id = os.getenv("GITHUB_INSTALLATION_ID")
    client = GitHubAppClient(app_id, private_key, installation_id)
    pr = client.create_pull_request(repo, branch, title, body)
    return pr["html_url"]


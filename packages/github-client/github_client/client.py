import os
import time
import hmac
import hashlib
import requests
from typing import Optional, Dict, Any, List

try:
    import jwt
except ImportError:
    jwt = None


def verify_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifies that the signature in the webhook header matches the payload and secret.
    Uses HMAC-SHA256.
    """
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected_signature = signature_header.split("sha256=")[-1]
    computed_signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, computed_signature)


class GitHubAppClient:
    def __init__(self, app_id: str, private_key: str, installation_id: Optional[str] = None, mock: bool = False):
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.mock = mock or (app_id == "mock" or private_key == "mock")
        
        self._private_key_content: Optional[str] = None
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _get_private_key(self) -> str:
        if self._private_key_content:
            return self._private_key_content
        
        if not self.private_key:
            return ""

        if "BEGIN RSA PRIVATE KEY" in self.private_key or "BEGIN PRIVATE KEY" in self.private_key:
            self._private_key_content = self.private_key
        else:
            candidates = [
                self.private_key,
                os.path.abspath(self.private_key),
                os.path.join(os.getcwd(), self.private_key),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../", self.private_key.lstrip("./\\"))),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../", self.private_key.lstrip("./\\")))
            ]
            loaded = False
            for path in candidates:
                if os.path.isfile(path):
                    try:
                        with open(path, "r") as f:
                            self._private_key_content = f.read()
                            loaded = True
                            break
                    except Exception:
                        pass
            if not loaded:
                self._private_key_content = self.private_key
        return self._private_key_content or ""

    def generate_jwt(self) -> str:
        if self.mock:
            return "mock_jwt"
        if not jwt:
            raise ImportError("pyjwt is not installed")
        payload = {
            "iat": int(time.time()) - 60,
            "exp": int(time.time()) + 540,
            "iss": self.app_id
        }
        private_key = self._get_private_key()
        encoded = jwt.encode(payload, private_key, algorithm="RS256")
        return str(encoded) if not isinstance(encoded, str) else encoded

    def get_installation_id(self) -> str:
        if self.installation_id:
            return self.installation_id

        if self.mock:
            return "mock_installation"

        jwt_token = self.generate_jwt()

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json"
        }

        response = requests.get(
            "https://api.github.com/app/installations",
            headers=headers
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to fetch installations: "
                f"{response.status_code} - {response.text}"
            )

        installations = response.json()

        if not installations:
            raise Exception(
                "No GitHub App installations found. "
                "Make sure the GitHub App is installed."
            )

        self.installation_id = str(installations[0]["id"])
        return self.installation_id

    def get_token(self) -> str:
        if self.mock:
            return "mock_token"
        
        if self._token and time.time() < self._token_expires_at - 300:
            return self._token

        jwt_token = self.generate_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json"
        }
        installation_id = self.get_installation_id()
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        response = requests.post(url, headers=headers)
        if response.status_code != 201:
            raise Exception(f"Failed to generate Installation Access Token: {response.status_code} - {response.text}")
            
        data = response.json()
        self._token = data["token"]
        expires_at_str = data["expires_at"].rstrip("Z")
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            self._token_expires_at = dt.timestamp()
        except Exception:
            self._token_expires_at = time.time() + 3600
            
        return self._token

    def _headers(self, with_token: bool = True) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Autonomous-Recovery-PaaS"
        }
        if with_token:
            token = self.get_token()
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def get_installation_repositories(self) -> List[Dict[str, Any]]:
        """
        List repositories that the GitHub App installation has access to.
        Endpoint: GET /installation/repositories
        """
        if self.mock:
            return [
                {
                    "id": 101,
                    "name": "recovery-test-repo",
                    "full_name": "jyotsnag-l/recovery-test-repo",
                    "private": False,
                    "html_url": "https://github.com/jyotsnag-l/recovery-test-repo",
                    "default_branch": "main",
                    "description": "Autonomous self-healing test repository"
                }
            ]
        url = "https://api.github.com/installation/repositories"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        data = response.json()
        return data.get("repositories", [])

    def get_repo_metadata(self, repo: str) -> Dict[str, Any]:
        if self.mock:
            return {
                "name": repo.split("/")[-1],
                "full_name": repo,
                "private": True,
                "default_branch": "main"
            }
        url = f"https://api.github.com/repos/{repo}"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def get_branch(self, repo: str, branch: str) -> Dict[str, Any]:
        if self.mock:
            return {
                "name": branch,
                "commit": {
                    "sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                    "url": f"https://api.github.com/repos/{repo}/commits/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
                }
            }
        url = f"https://api.github.com/repos/{repo}/branches/{branch}"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def get_commit(self, repo: str, commit_sha: str) -> Dict[str, Any]:
        if self.mock:
            return {
                "sha": commit_sha,
                "commit": {
                    "message": "Mock commit message",
                    "author": {"name": "Bot"}
                }
            }
        url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def create_branch(self, repo: str, branch_name: str, base_sha: str) -> str:
        if self.mock:
            return f"refs/heads/{branch_name}"
        url = f"https://api.github.com/repos/{repo}/git/refs"
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        response = requests.post(url, json=payload, headers=self._headers())
        if response.status_code == 422 and "already exists" in response.text:
            return f"refs/heads/{branch_name}"
        response.raise_for_status()
        return response.json()["ref"]

    def create_pull_request(self, repo: str, branch: str, title: str, body: str, base: str = "main") -> Dict[str, Any]:
        if self.mock:
            return {
                "number": 123,
                "html_url": f"https://github.com/{repo}/pull/123",
                "url": f"https://api.github.com/repos/{repo}/pulls/123",
                "state": "open",
                "title": title,
                "body": body,
                "head": {"ref": branch},
                "base": {"ref": base}
            }
        url = f"https://api.github.com/repos/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": branch,
            "base": base
        }
        response = requests.post(url, json=payload, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def create_commit_status(self, repo: str, commit_sha: str, state: str, context: str, description: str, target_url: Optional[str] = None) -> Dict[str, Any]:
        if self.mock:
            return {
                "state": state,
                "context": context,
                "description": description,
                "target_url": target_url
            }
        url = f"https://api.github.com/repos/{repo}/statuses/{commit_sha}"
        payload = {
            "state": state.lower(),
            "context": context,
            "description": description
        }
        if target_url:
            payload["target_url"] = target_url
        response = requests.post(url, json=payload, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def get_ci_statuses(self, repo: str, ref: str) -> List[Dict[str, Any]]:
        if self.mock:
            return [
                {
                    "context": "continuous-integration/github-actions",
                    "state": "SUCCESS",
                    "target_url": "https://github.com/mock-ci",
                    "type": "check_run"
                }
            ]
        
        status_url = f"https://api.github.com/repos/{repo}/commits/{ref}/status"
        response = requests.get(status_url, headers=self._headers())
        response.raise_for_status()
        status_data = response.json()

        check_run_url = f"https://api.github.com/repos/{repo}/commits/{ref}/check-runs"
        response = requests.get(check_run_url, headers=self._headers())
        response.raise_for_status()
        check_runs_data = response.json()

        combined = []
        for s in status_data.get("statuses", []):
            combined.append({
                "context": s["context"],
                "state": s["state"].upper(),
                "target_url": s.get("target_url"),
                "type": "status"
            })
        for c in check_runs_data.get("check_runs", []):
            status = c["status"].upper()
            conclusion = c.get("conclusion")
            state = "PENDING"
            if status == "COMPLETED":
                if conclusion == "success":
                    state = "SUCCESS"
                elif conclusion in ["failure", "cancelled", "timed_out", "action_required"]:
                    state = "FAILURE"
                else:
                    state = "FAILURE"
            combined.append({
                "context": c["name"],
                "state": state,
                "target_url": c.get("html_url"),
                "type": "check_run"
            })
        return combined

    def get_branch_protection(self, repo: str, branch: str) -> Dict[str, Any]:
        if self.mock:
            return {
                "required_status_checks": {
                    "strict": True,
                    "contexts": ["continuous-integration/github-actions"]
                },
                "required_pull_request_reviews": {
                    "required_approving_review_count": 0
                }
            }
        url = f"https://api.github.com/repos/{repo}/branches/{branch}/protection"
        response = requests.get(url, headers=self._headers())
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()

    def merge_pull_request(self, repo: str, pr_number: int, commit_title: Optional[str] = None) -> bool:
        if (
            self.mock
            or "/" not in repo
            or repo.startswith("mock")
            or os.getenv("GITHUB_MOCK", "false").lower() == "true"
        ):
            return True
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
        payload = {}
        if commit_title:
            payload["commit_title"] = commit_title
        response = requests.put(url, json=payload, headers=self._headers())
        if response.status_code == 200:
            return True
        return False


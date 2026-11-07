import os
import sys
import json
import argparse
import subprocess
import urllib.request
import urllib.error

def resolve_commit_sha(repo_path: str = None, explicit_commit: str = None) -> str:
    """
    Dynamically resolves the current commit SHA from the target repo using GitPython
    or git rev-parse HEAD. Defaults to the dynamic current HEAD if omitted.
    """
    if explicit_commit and explicit_commit.strip().upper() != "HEAD":
        return explicit_commit.strip()

    search_paths = []
    if repo_path:
        search_paths.append(os.path.abspath(repo_path))
    search_paths.extend([
        os.path.abspath("C:/Users/sreej/OneDrive/Desktop/test/recovery-test-repo"),
        os.path.abspath("demo-repo"),
        os.path.abspath(".")
    ])

    for p in search_paths:
        if os.path.exists(p) and os.path.exists(os.path.join(p, ".git")):
            # Try GitPython first
            try:
                import git
                repo = git.Repo(p)
                sha = repo.head.commit.hexsha
                if sha:
                    return sha
            except Exception:
                pass
            # Fallback to subprocess git rev-parse HEAD
            try:
                res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=p, capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip():
                    return res.stdout.strip()
            except Exception:
                pass

    return "HEAD"

def main():
    parser = argparse.ArgumentParser(description="Trigger real stock event with dynamic commit resolution")
    parser.add_argument("--commit", dest="commit_sha", default=None, help="Target commit SHA (defaults to dynamic HEAD)")
    parser.add_argument("--repo-path", dest="repo_path", default=None, help="Path to local target repository")
    args = parser.parse_args()

    commit_sha = resolve_commit_sha(repo_path=args.repo_path, explicit_commit=args.commit_sha)
    print(f"[*] Dynamically resolved commit SHA: {commit_sha}")

    data = {
        "project_id": "proj_04102d07",
        "exception_type": "AssertionError",
        "exception_message": "assert 201 == 400 - Order exceeding stock quantity accepted with status 201 Created instead of 400 Bad Request",
        "stack_trace": """Traceback (most recent call last):
  File "app/services/inventory_service.py", line 52, in validate_stock_availability
    if item.stock_quantity <= 0:
  File "tests/test_orders.py", line 44, in test_create_order_exceeding_stock_should_fail
    assert response.status_code == 400
AssertionError: NEW TEST RUN 201 == 400
+ where 201 = <Response [201 Created]>.status_code""",
        "environment": "production",
        "git_commit": commit_sha,
        "commit_sha": commit_sha,
        "file": "app/services/inventory_service.py",
        "line": 46,
        "function": "validate_stock_availability"
    }

    headers = {
        "Content-Type": "application/json",
        "X-Project-ID": "proj_04102d07",
        "X-Organization-ID": "org_overmend",
        "X-User-Role": "OWNER",
        "X-User-ID": "usr_jyotsna"
    }

    req = urllib.request.Request("http://localhost:8000/api/v1/events", data=json.dumps(data).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            print("RESPONSE STATUS:", res.status)
            print(json.dumps(json.loads(res.read()), indent=2))
    except urllib.error.HTTPError as e:
        print("HTTP ERROR:", e.code)
        print(e.read().decode())
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    main()

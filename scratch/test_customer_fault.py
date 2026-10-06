import os
import sys
import argparse
import subprocess

root_dir = os.path.abspath(os.path.dirname(__file__) + "/..")
sys.path.insert(0, os.path.join(root_dir, "packages", "fault-localizer"))
sys.path.insert(0, os.path.join(root_dir, "packages", "github-client"))

import fault_localizer

def resolve_target_repo(repo_path: str = None) -> str:
    candidates = []
    if repo_path:
        candidates.append(os.path.abspath(repo_path))
    candidates.extend([
        os.path.abspath("C:/Users/sreej/OneDrive/Desktop/test/recovery-test-repo"),
        os.path.abspath(os.path.join(root_dir, "demo-repo")),
        os.path.abspath(root_dir)
    ])
    for p in candidates:
        if os.path.exists(p):
            return p
    return os.path.abspath(".")

def main():
    parser = argparse.ArgumentParser(description="Test customer fault localization with dynamic repository resolution")
    parser.add_argument("--repo-path", dest="repo_path", default=None, help="Target repository path")
    parser.add_argument("--commit", dest="commit", default=None, help="Target commit SHA (optional)")
    args = parser.parse_args()

    repo_path = resolve_target_repo(args.repo_path)
    print(f"[*] Analyzing target repository: {repo_path}")

    # Read current commit dynamically if git repository
    current_sha = args.commit
    if not current_sha and os.path.exists(os.path.join(repo_path, ".git")):
        try:
            import git
            current_sha = git.Repo(repo_path).head.commit.hexsha
        except Exception:
            try:
                res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True)
                if res.returncode == 0:
                    current_sha = res.stdout.strip()
            except Exception:
                pass
    if current_sha:
        print(f"[*] Dynamically resolved commit: {current_sha}")

    stack_trace = """Traceback (most recent call last):
  File "tests/test_order_validation.py", line 19, in test_create_order_exceeding_stock_should_fail
    assert order_resp.status_code == 400
AssertionError: assert 201 == 400"""

    res = fault_localizer.localize_fault(stack_trace, repo_path=repo_path)
    print("TOP FAULT:", res.get("file"), res.get("line"), res.get("function"), res.get("score"))
    print("ALL CANDIDATES:")
    for c in res.get("candidates", []):
        print(f"  - {c.get('file')}:{c.get('line')} in {c.get('function')} (score={c.get('score')})")

if __name__ == "__main__":
    main()

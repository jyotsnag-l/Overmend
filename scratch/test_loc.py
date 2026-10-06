import os
import sys
import re
import argparse
import subprocess

root_dir = os.path.abspath(os.path.dirname(__file__) + "/..")
sys.path.insert(0, os.path.join(root_dir, "packages", "fault-localizer"))
sys.path.insert(0, os.path.join(root_dir, "packages", "github-client"))

from fault_localizer.repository import RepositoryAccess
from fault_localizer.localizer import (
    parse_stack_trace, resolve_repo_path, analyze_candidate_frame, score_candidate
)

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

def is_test_path(file_path: str) -> bool:
    if not file_path:
        return False
    norm = file_path.replace("\\", "/").lower()
    return bool(
        norm.startswith("tests/")
        or norm.startswith("test/")
        or "/tests/" in norm
        or "/test/" in norm
        or norm.endswith("_test.py")
        or os.path.basename(norm).startswith("test_")
    )

def main():
    parser = argparse.ArgumentParser(description="Test fault localization with dynamic repository and commit resolution")
    parser.add_argument("--repo-path", dest="repo_path", default=None, help="Target repository path")
    parser.add_argument("--commit", dest="commit", default=None, help="Target commit SHA (defaults to HEAD)")
    args = parser.parse_args()

    repo_path = resolve_target_repo(args.repo_path)
    print(f"[*] Target repository: {repo_path}")

    repo_access = RepositoryAccess(repo_path)
    if not repo_access.is_git_available():
        print(f"[-] Git is not initialized at {repo_path}")
        return

    target_commit_ref = args.commit or "HEAD"
    try:
        commit = repo_access.repo.commit(target_commit_ref)
        print(f"[*] Dynamically resolved commit: {commit.hexsha} ({target_commit_ref})")
    except Exception as e:
        print(f"[-] Could not resolve commit '{target_commit_ref}': {e}. Falling back to HEAD.")
        commit = repo_access.repo.head.commit
        print(f"[*] HEAD commit: {commit.hexsha}")

    parent = commit.parents[0] if commit.parents else None
    diffs = parent.diff(commit, create_patch=True) if parent else []
    pattern = re.compile(r"@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@")

    hunks = []
    for d in diffs:
        if not d.b_path:
            continue
        norm_rel = d.b_path.replace("\\", "/")
        if is_test_path(norm_rel):
            continue
        diff_text = d.diff.decode("utf-8", errors="ignore") if isinstance(d.diff, bytes) else str(d.diff or "")
        cur = 1
        for line in diff_text.splitlines():
            m = pattern.match(line)
            if m:
                cur = int(m.group(1))
            elif line.startswith("+") and not line.startswith("+++"):
                code_line = line[1:].strip()
                if code_line:
                    hunks.append({"file": norm_rel, "line": cur, "code": code_line})
                cur += 1
            elif not line.startswith("-"):
                cur += 1

    print("Discovered production commit hunks:", hunks)

    # Test candidate analysis
    recent_repo_hashes = {c.hexsha for c in repo_access.repo.iter_commits(max_count=5)}
    for h in hunks:
        frame = {
            "file": h["file"],
            "line": h["line"],
            "function": "",
            "code": h["code"],
            "raw": h["code"],
            "depth": 0
        }
        cand, ev = analyze_candidate_frame(
            frame=frame,
            resolved_rel_path=h["file"],
            repo_access=repo_access,
            is_innermost=True,
            stack_depth_offset=0,
            recent_repo_hashes=recent_repo_hashes
        )
        print("Candidate:", cand["file"], cand["line"], cand["function"], "Score:", cand["score"])
        print("Reasons:", cand["reasons"])

if __name__ == "__main__":
    main()

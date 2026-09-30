import os
import sys
import re

root_dir = os.path.abspath(os.path.dirname(__file__) + "/..")
sys.path.insert(0, os.path.join(root_dir, "packages", "fault-localizer"))
sys.path.insert(0, os.path.join(root_dir, "packages", "github-client"))

from fault_localizer.repository import RepositoryAccess
from fault_localizer.localizer import (
    parse_stack_trace, resolve_repo_path, analyze_candidate_frame, score_candidate
)

repo_path = "C:/Users/sreej/OneDrive/Desktop/test/recovery-test-repo"
repo_access = RepositoryAccess(repo_path)

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

commit = repo_access.repo.commit("HEAD")
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

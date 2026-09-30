import os
from pathlib import Path
from typing import Optional, List, Dict, Any

class RepositoryAccess:
    """
    A safe abstraction to interact with a repository directory and Git history.
    """
    def __init__(self, repo_path: str):
        self.repo_path = Path(os.path.abspath(repo_path))
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
            
        self.repo = None
        # Attempt to import git and initialize repo safely
        try:
            import git
            self.repo = git.Repo(self.repo_path)
        except Exception:
            # Git is not initialized or import failed (fallback gracefully)
            pass

    def is_git_available(self) -> bool:
        """Returns True if Git is initialized and available for this repository."""
        return self.repo is not None

    def close(self):
        """Releases Git repository file handles and locks."""
        if self.repo is not None:
            try:
                self.repo.close()
            except Exception:
                pass
            self.repo = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def get_safe_path(self, relative_path: str) -> Path:
        """
        Resolves a relative or absolute path to a safe absolute path, ensuring
        it is strictly within the repository root to prevent directory traversal.
        """
        if not relative_path:
            return self.repo_path

        # Normalize separators
        normalized = relative_path.replace("\\", "/")
        path_obj = Path(normalized)

        if path_obj.is_absolute():
            resolved = path_obj.resolve()
        else:
            # Strip leading slashes to prevent Path / normalized from resetting to filesystem root
            cleaned = normalized.lstrip("/")
            resolved = (self.repo_path / cleaned).resolve()

        # Check if the resolved path is strictly within repo_path
        if not resolved.is_relative_to(self.repo_path):
            raise PermissionError(
                f"Security breach: path '{relative_path}' points outside repository root '{self.repo_path}'"
            )
        return resolved

    def file_exists(self, relative_path: str) -> bool:
        """Checks if a file exists safely within the repository root."""
        try:
            return self.get_safe_path(relative_path).is_file()
        except (PermissionError, FileNotFoundError, ValueError):
            return False

    def read_file(self, relative_path: str) -> str:
        """Reads file content safely."""
        safe_path = self.get_safe_path(relative_path)
        if not safe_path.is_file():
            raise FileNotFoundError(f"File not found: {relative_path}")
        with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def get_blame(self, relative_path: str, line_no: int) -> Dict[str, Any]:
        """
        Retrieves Git blame information for a specific line of a file.
        Returns a dict with commit details or empty dict if unavailable.
        """
        if not self.repo or line_no <= 0:
            return {}
        try:
            # Ensure the file exists safely within repository
            safe_path = self.get_safe_path(relative_path)
            if not safe_path.is_file():
                return {}

            # Run blame using relative posix path
            normalized_rel = safe_path.relative_to(self.repo_path).as_posix()

            # git.blame returns a list of tuples: (Commit, lines_list)
            blame_runs: Any = self.repo.blame("HEAD", normalized_rel)
            if not blame_runs:
                return {}

            current_line = 1
            for entry in blame_runs:
                if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                    continue
                commit, lines = entry[0], entry[1]
                if not lines:
                    continue
                for line in lines:
                    if current_line == line_no:
                        author = getattr(commit, 'author', None)
                        author_name = getattr(author, 'name', 'Unknown') if author else 'Unknown'
                        author_email = getattr(author, 'email', '') if author else ''
                        committed_datetime = getattr(commit, 'committed_datetime', None)

                        return {
                            "commit_hash": getattr(commit, 'hexsha', ''),
                            "author": author_name,
                            "email": author_email,
                            "date": committed_datetime.isoformat() if committed_datetime else None,
                            "summary": getattr(commit, 'summary', ''),
                            "line_code": line
                        }
                    current_line += 1
        except Exception:
            pass
        return {}

    def get_recent_commits(self, limit: int = 10, relative_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves recent commits in the repository.
        If relative_path is provided, retrieves commits affecting that file.
        """
        if not self.repo:
            return []
        try:
            kwargs: Dict[str, Any] = {"max_count": limit}
            if relative_path:
                safe_path = self.get_safe_path(relative_path)
                kwargs["paths"] = safe_path.relative_to(self.repo_path).as_posix()

            commits = []
            for commit in self.repo.iter_commits(**kwargs):
                changed_files = []
                try:
                    changed_files = list(commit.stats.files.keys())
                except Exception:
                    pass

                author = getattr(commit, 'author', None)
                author_name = getattr(author, 'name', 'Unknown') if author else 'Unknown'
                author_email = getattr(author, 'email', '') if author else ''
                committed_datetime = getattr(commit, 'committed_datetime', None)

                commits.append({
                    "commit_hash": getattr(commit, 'hexsha', ''),
                    "author": author_name,
                    "email": author_email,
                    "date": committed_datetime.isoformat() if committed_datetime else None,
                    "summary": getattr(commit, 'summary', ''),
                    "message": getattr(commit, 'message', ''),
                    "changed_files": changed_files
                })
            return commits
        except Exception:
            return []

    def get_commit_diff_hunks(self, commit_ref: str = "HEAD") -> List[Dict[str, Any]]:
        """
        Extracts modified files and modified line ranges from the specified commit against its parent.
        Returns a list of dicts with:
        {"file": str, "line": int, "code": str, "commit_hash": str}
        """
        if not self.repo:
            return []
        import re
        hunks = []
        try:
            commit = self.repo.commit(commit_ref)
            parent = commit.parents[0] if commit.parents else None
            if not parent:
                return []
            diffs = parent.diff(commit, create_patch=True)
            pattern = re.compile(r"@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@")
            for d in diffs:
                if not d.b_path:
                    continue
                norm_rel = d.b_path.replace("\\", "/")
                if not self.file_exists(norm_rel):
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
                            hunks.append({
                                "file": norm_rel,
                                "line": cur,
                                "code": code_line,
                                "commit_hash": getattr(commit, 'hexsha', '')
                            })
                        cur += 1
                    elif not line.startswith("-"):
                        cur += 1
        except Exception:
            pass
        return hunks


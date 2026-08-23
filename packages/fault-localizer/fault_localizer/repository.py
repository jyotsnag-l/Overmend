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

    def get_safe_path(self, relative_path: str) -> Path:
        """
        Resolves a relative path to an absolute path, ensuring it is within
        the repository root to prevent directory traversal.
        """
        # Normalize separators
        normalized = relative_path.replace("\\", "/")
        # Join and resolve path
        abs_path = (self.repo_path / normalized).resolve()
        
        # Check if the resolved path is relative to the repo_path
        if not abs_path.is_relative_to(self.repo_path):
            raise PermissionError(
                f"Security breach: path '{relative_path}' points outside repository root '{self.repo_path}'"
            )
        return abs_path

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
        Returns a dict with commit details.
        """
        if not self.repo:
            return {}
        try:
            # Ensure the file exists
            self.get_safe_path(relative_path)
            
            # Run blame. Use as_posix() to ensure correct separator on Windows
            normalized_rel = Path(relative_path).as_posix()
            
            # git.blame returns a list of tuples: (Commit, lines_list)
            blame_runs = self.repo.blame("HEAD", normalized_rel)
            
            current_line = 1
            for commit, lines in blame_runs:
                for line in lines:
                    if current_line == line_no:
                        return {
                            "commit_hash": commit.hexsha,
                            "author": commit.author.name,
                            "email": commit.author.email,
                            "date": commit.committed_datetime.isoformat() if hasattr(commit, 'committed_datetime') else None,
                            "summary": commit.summary,
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
            kwargs = {"max_count": limit}
            if relative_path:
                # Ensure path is safe and normalized
                self.get_safe_path(relative_path)
                kwargs["paths"] = Path(relative_path).as_posix()

            commits = []
            for commit in self.repo.iter_commits(**kwargs):
                changed_files = []
                try:
                    # Parse changed files from stats
                    changed_files = list(commit.stats.files.keys())
                except Exception:
                    pass

                commits.append({
                    "commit_hash": commit.hexsha,
                    "author": commit.author.name,
                    "email": commit.author.email,
                    "date": commit.committed_datetime.isoformat() if hasattr(commit, 'committed_datetime') else None,
                    "summary": commit.summary,
                    "message": commit.message,
                    "changed_files": changed_files
                })
            return commits
        except Exception:
            return []

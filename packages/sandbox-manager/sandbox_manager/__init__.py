import os
import uuid
from typing import Dict, Any, Optional, Callable
from .runner import SandboxConfig, SandboxRunner
from .models import SandboxResult, SandboxStatus
from .parser import TestOutputParser
from .resolvers import TestCommandResolver, EcosystemAdapter, PythonAdapter
from .storage import upload_artifact

def run_in_sandbox(patch: str, test_cmd: str, repo_url: Optional[str] = None, commit_hash: Optional[str] = None) -> SandboxResult:
    """
    Backward-compatible helper function to run a patch in a sandbox container.
    """
    # Attempt to locate repo_url
    if not repo_url:
        if os.path.exists("demo-repo"):
            repo_url = os.path.abspath("demo-repo")
        else:
            repo_url = os.path.abspath(".")
            
    if not commit_hash:
        commit_hash = "HEAD"

    config = SandboxConfig(test_command=test_cmd)
    runner = SandboxRunner(config)
    job_id = f"compat_{uuid.uuid4().hex[:8]}"
    return runner.run(job_id, repo_url, commit_hash, patch)

__all__ = [
    "SandboxConfig",
    "SandboxRunner",
    "SandboxResult",
    "SandboxStatus",
    "TestOutputParser",
    "TestCommandResolver",
    "EcosystemAdapter",
    "PythonAdapter",
    "upload_artifact",
    "run_in_sandbox",
]

import os
import asyncio
from typing import Optional, Dict, Any
from .localizer import localize_fault_core
from .context import ContextBuilder
from .repository import RepositoryAccess

def _get_default_repo_path() -> str:
    """Finds a reasonable default repo path for localization."""
    # Check if we are running in the workspace and demo-repo is present
    if os.path.exists("demo-repo"):
        return os.path.abspath("demo-repo")
    # Check parent directory
    parent_demo = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../demo-repo"))
    if os.path.exists(parent_demo):
        return parent_demo
    return os.getcwd()

def localize_fault(
    stack_trace: str,
    repo_path: Optional[str] = None,
    incident_data: Optional[dict] = None
) -> dict:
    """
    Exposes the fault localizer entry point. Compatible with simple stack_trace calls.
    """
    if not repo_path:
        repo_path = _get_default_repo_path()
    res = localize_fault_core(stack_trace, repo_path, incident_data)
    return {
        "file": res.get("file"),
        "line": res.get("line"),
        "function": res.get("function"),
        "class": res.get("class"),
        "stack_frame": res.get("stack_frame"),
        "recent_change": res.get("recent_change"),
        "evidence": res.get("evidence")
    }

def build_patch_context(
    incident_data: dict,
    repo_path: Optional[str] = None,
    db_session: Any = None
) -> dict:
    """
    Exposes the context builder entry point (sync wrapper around async builder).
    """
    if not repo_path:
        repo_path = _get_default_repo_path()
        
    builder = ContextBuilder(repo_path, db_session)
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(builder.build_context(incident_data))
    else:
        return loop.run_until_complete(builder.build_context(incident_data))


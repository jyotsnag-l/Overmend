import os
import ast
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional
from .repository import RepositoryAccess
from .localizer import localize_fault_core, parse_stack_trace, resolve_repo_path

def extract_calling_function(
    frames: List[Dict[str, Any]],
    fault_frame_index: int,
    repo_access: RepositoryAccess
) -> Optional[Dict[str, Any]]:
    """
    Extracts the source code of the calling function from the stack trace if available in the repository.
    """
    if fault_frame_index <= 0 or fault_frame_index >= len(frames):
        return None
        
    caller_frame = frames[fault_frame_index - 1]
    caller_file = caller_frame["file"]
    caller_line = caller_frame["line"]
    caller_func_name = caller_frame["function"]
    
    resolved_caller_path = resolve_repo_path(caller_file, repo_access)
    if not resolved_caller_path:
        return None
        
    try:
        content = repo_access.read_file(resolved_caller_path)
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == caller_func_name:
                    end_line = getattr(node, 'end_lineno', node.lineno) or node.lineno
                    if node.lineno <= caller_line <= end_line:
                        lines = content.splitlines()[node.lineno - 1 : end_line]
                        return {
                            "file": resolved_caller_path,
                            "function": caller_func_name,
                            "start_line": node.lineno,
                            "end_line": end_line,
                            "code": "\n".join(lines)
                        }
    except Exception:
        pass
        
    return {
        "file": resolved_caller_path,
        "function": caller_func_name,
        "start_line": caller_line,
        "end_line": caller_line,
        "code": caller_frame.get("code", "")
    }

async def query_historical_incidents(
    db_session,
    fingerprint: str,
    current_id: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Safely queries database for similar historical incidents (excluding the current one).
    Supports both synchronous and asynchronous database sessions.
    """
    if not db_session:
        return []
    try:
        import models
        from sqlalchemy import select
        
        stmt = select(models.Incident).where(models.Incident.fingerprint == fingerprint)
        if current_id:
            stmt = stmt.where(models.Incident.id != current_id)
        stmt = stmt.limit(limit)
        
        result = db_session.execute(stmt)
        if inspect.iscoroutine(result):
            result = await result
            incidents = result.scalars().all()
        else:
            incidents = result.scalars().all()
            
        history = []
        for inc in incidents:
            history.append({
                "id": inc.id,
                "exception_type": inc.exception_type,
                "exception_message": inc.exception_message,
                "status": inc.status,
                "severity": inc.severity,
                "created_at": inc.created_at.isoformat() if hasattr(inc.created_at, 'isoformat') else None
            })
        return history
    except Exception:
        return []

class ContextBuilder:
    """
    Constructs a structured PatchContext object using prioritized repository context.
    """
    def __init__(self, repo_path: str, db_session=None):
        self.repo_access = RepositoryAccess(repo_path)
        self.db_session = db_session

    def close(self):
        """Releases underlying repository handles."""
        self.repo_access.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    async def build_context(
        self,
        incident_data: Dict[str, Any],
        fault_location: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Builds the structured PatchContext object.
        """
        stack_trace = incident_data.get("stack_trace", "")
        
        # 1. Localize fault if not already provided
        if not fault_location:
            fault_location = localize_fault_core(stack_trace, str(self.repo_access.repo_path), incident_data)
            
        # Parse all frames for calling function extraction
        frames = parse_stack_trace(stack_trace)
        
        # 2. Priority 1 & 2: Faulting function and surrounding source
        faulting_file = fault_location.get("file")
        faulting_line = fault_location.get("line")
        faulting_func = fault_location.get("function")
        
        ast_data = fault_location.get("ast", {})
        boundaries = ast_data.get("function_boundaries")
        surrounding_source = ast_data.get("surrounding_source", {})
        
        faulting_function_src = None
        if faulting_file and boundaries:
            try:
                content = self.repo_access.read_file(faulting_file)
                lines = content.splitlines()[boundaries["start_line"] - 1 : boundaries["end_line"]]
                faulting_function_src = {
                    "name": faulting_func,
                    "start_line": boundaries["start_line"],
                    "end_line": boundaries["end_line"],
                    "code": "\n".join(lines)
                }
            except Exception:
                pass
                
        source_context = {
            "faulting_file": faulting_file,
            "faulting_function": faulting_function_src,
            "surrounding_lines": {
                "start_line": surrounding_source.get("start_line"),
                "end_line": surrounding_source.get("end_line"),
                "code": surrounding_source.get("code_block")
            }
        }
        
        # 3. Priority 3: Imports
        imports = ast_data.get("imports", [])
        
        # 4. Priority 4: Calling function
        calling_function = None
        if faulting_file and frames:
            # Find the frame index matching the faulting line/file
            fault_idx = -1
            for idx, frame in enumerate(frames):
                if frame["line"] == faulting_line and resolve_repo_path(frame["file"], self.repo_access) == faulting_file:
                    fault_idx = idx
                    break
            if fault_idx != -1:
                calling_function = extract_calling_function(frames, fault_idx, self.repo_access)
                
        source_context["calling_function"] = calling_function
        
        # 5. Priority 5: Related tests
        related_tests = fault_location.get("related_tests", [])
        
        # 6. Priority 6: Recent Git changes (blame and repository-wide history)
        git_history = []
        blame_info = fault_location.get("git", {}).get("blame", {})
        if blame_info:
            git_history.append({
                "type": "blame",
                "file": faulting_file,
                "line": faulting_line,
                "info": blame_info
            })
            
        recent_commits = self.repo_access.get_recent_commits(limit=5, relative_path=faulting_file)
        for commit in recent_commits:
            git_history.append({
                "type": "commit",
                "commit_hash": commit["commit_hash"],
                "author": commit["author"],
                "date": commit["date"],
                "summary": commit["summary"],
                "message": commit["message"],
                "changed_files": commit["changed_files"]
            })
            
        # 7. Priority 7: Similar historical incidents using pgvector similarity search
        historical_context = []
        historical_fixes = []
        
        org_id = incident_data.get("organization_id")
        exception_type = incident_data.get("exception_type", "")
        exception_message = incident_data.get("exception_message", "")
        stack_trace = incident_data.get("stack_trace", "")
        
        if self.db_session and org_id:
            try:
                import retrieval
                similar_records = await retrieval.query_similar_recovery_records(
                    db=self.db_session,
                    organization_id=org_id,
                    exception_type=exception_type,
                    exception_message=exception_message,
                    stack_trace=stack_trace,
                    limit=5
                )
                for item in similar_records:
                    historical_context.append({
                        "similarity_score": item["similarity_score"],
                        "incident_id": item["incident_id"],
                        "previous_fault_location": item["previous_fault_location"],
                        "previous_patch": item["previous_patch"],
                        "outcome": item["outcome"],
                        "trust_score": item["trust_score"],
                        "human_decision": item["human_decision"]
                    })
                    historical_fixes.append({
                        "incident_id": item["incident_id"],
                        "patch_id": f"fix_{item['incident_id']}",
                        "unified_diff": item["previous_patch"],
                        "explanation": f"Previous fix with trust score {item['trust_score']} and human decision {item['human_decision']}"
                    })
            except Exception:
                # Fallback to old fingerprint-based query if retrieval module or pgvector search fails
                fingerprint = incident_data.get("fingerprint")
                if not fingerprint:
                    fingerprint = exception_type or "UnknownException"
                current_id = incident_data.get("id")
                historical_context = await query_historical_incidents(
                    self.db_session,
                    fingerprint,
                    current_id=current_id
                )
        else:
            # Standard fallback if db_session or org_id not present
            fingerprint = incident_data.get("fingerprint")
            if not fingerprint:
                fingerprint = exception_type or "UnknownException"
            current_id = incident_data.get("id")
            historical_context = await query_historical_incidents(
                self.db_session,
                fingerprint,
                current_id=current_id
            )
            
        # Build final PatchContext schema
        # Filter raw localization data for clean public output format
        clean_fault_location = {
            "file": fault_location.get("file"),
            "line": fault_location.get("line"),
            "function": fault_location.get("function"),
            "class": fault_location.get("class"),
            "score": fault_location.get("score"),
            "reasons": fault_location.get("reasons", []),
            "stack_frame": fault_location.get("stack_frame"),
            "recent_change": fault_location.get("recent_change"),
            "evidence": fault_location.get("evidence"),
            "candidates": fault_location.get("candidates", []),
            "fault_candidates": fault_location.get("fault_candidates", [])
        }
        
        return {
            "incident": incident_data,
            "fault_location": clean_fault_location,
            "fault_candidates": fault_location.get("candidates", []),
            "source_context": source_context,
            "imports": imports,
            "related_tests": related_tests,
            "git_history": git_history,
            "historical_context": historical_context,
            "historical_fixes": historical_fixes
        }

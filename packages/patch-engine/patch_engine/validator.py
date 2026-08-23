import os
import ast
import logging
from typing import Optional, Dict, Any, List
from unidiff import PatchSet
from .schemas import PatchContext, PatchValidationReport

logger = logging.getLogger("patch_engine.validator")

def apply_patch_to_text(original_text: str, patched_file) -> str:
    """
    Applies the hunks of a PatchedFile from unidiff to the original text.
    Uses reverse sorting by source_start to prevent line shifts from affecting offsets.
    """
    original_lines = original_text.splitlines(keepends=True)
    
    if patched_file.is_added_file:
        new_lines = []
        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    new_lines.append(line.value)
        return "".join(new_lines)

    # Sort hunks in reverse order of source_start line numbers
    hunks = sorted(patched_file, key=lambda h: h.source_start, reverse=True)
    patched_lines = list(original_lines)
    
    for hunk in hunks:
        start_idx = hunk.source_start - 1  # 0-indexed
        end_idx = start_idx + hunk.source_length
        
        new_lines = []
        for line in hunk:
            if line.is_context:
                new_lines.append(line.value)
            elif line.is_added:
                new_lines.append(line.value)
                
        # Replace original lines range with new lines
        patched_lines[start_idx:end_idx] = new_lines
        
    return "".join(patched_lines)

def validate_patch(
    patch_text: str,
    repo_path: str,
    context: PatchContext,
    policy: Optional[dict] = None
) -> PatchValidationReport:
    """
    Validates a generated patch:
    1. Validates diff structure with unidiff
    2. Verifies affected paths (strictly inside repository, no path traversal)
    3. Calculates patch size (additions + deletions) and files changed
    4. Enforces project policies (restricted files, size limits, full-file rewrites)
    5. Validates syntax of Python files by applying patches in-memory and running ast.parse
    """
    repo_abs_path = os.path.abspath(repo_path)
    
    # 1. Parse diff
    try:
        patch_set = PatchSet(patch_text.splitlines(keepends=True))
    except Exception as e:
        logger.error(f"Malformed unified diff: {e}")
        return PatchValidationReport(
            is_valid=False,
            error_reason=f"Malformed unified diff: {str(e)}"
        )
        
    if not patch_set:
        return PatchValidationReport(
            is_valid=False,
            error_reason="Diff contains no changes or is empty."
        )

    # Policy thresholds (can be customized by policy dict)
    policy = policy or {}
    restricted_files = policy.get("restricted_files", [])
    max_patch_size = policy.get("max_patch_size", 100)  # default max 100 lines changed
    max_files_changed = policy.get("max_files_changed", 3)  # default max 3 files
    
    total_size = 0
    files_changed = len(patch_set)
    affected_paths = []
    
    if files_changed > max_files_changed:
        return PatchValidationReport(
            is_valid=False,
            error_reason=f"Patches modified {files_changed} files, exceeding limit of {max_files_changed}."
        )

    for patched_file in patch_set:
        # Get path relative or target path
        file_path = patched_file.path
        affected_paths.append(file_path)
        
        # 2. Path Traversal & Allowed Paths Verification
        file_abs_path = os.path.abspath(os.path.join(repo_abs_path, file_path))
        if not file_abs_path.startswith(repo_abs_path):
            return PatchValidationReport(
                is_valid=False,
                error_reason=f"Path traversal detected: {file_path} resolves outside the repository."
            )
            
        # 3. Project Policy: Restricted Files Verification
        # Check filename or relative path
        if any(restricted in file_path or os.path.basename(file_path) == restricted for restricted in restricted_files):
            return PatchValidationReport(
                is_valid=False,
                error_reason=f"Modifying restricted file is prohibited by policy: {file_path}"
            )
            
        # Read original file contents (if modified/removed)
        original_content = ""
        if not patched_file.is_added_file:
            if not os.path.exists(file_abs_path):
                # If file doesn't exist locally, try reading from repo context or handle
                pass
            else:
                try:
                    with open(file_abs_path, "r", encoding="utf-8") as f:
                        original_content = f.read()
                except Exception as e:
                    logger.warning(f"Could not read file {file_abs_path} to validate: {e}")
                    
        # Check original file size for full-file rewrite rules
        original_lines_count = len(original_content.splitlines())
        
        # Calculate size of changes in this file
        file_adds = 0
        file_dels = 0
        
        for hunk in patched_file:
            file_adds += hunk.added
            file_dels += hunk.removed
            
            # Check for full-file rewrite (hunk covers >90% of file and file is reasonably large)
            if not patched_file.is_added_file and original_lines_count > 15:
                if hunk.source_length >= original_lines_count * 0.9:
                    return PatchValidationReport(
                        is_valid=False,
                        error_reason=f"Full-file rewrite detected in {file_path}. Please modify only the bug area."
                    )
                    
        total_size += (file_adds + file_dels)
        
        # 4. Syntax Validation (for python files)
        if file_path.endswith(".py"):
            try:
                # Apply in-memory
                patched_content = apply_patch_to_text(original_content, patched_file)
                # Run syntax validation
                ast.parse(patched_content, filename=file_path)
            except SyntaxError as se:
                return PatchValidationReport(
                    is_valid=False,
                    error_reason=f"Syntax validation failed for {file_path}: {se.msg} on line {se.lineno}"
                )
            except Exception as e:
                return PatchValidationReport(
                    is_valid=False,
                    error_reason=f"Patch application or AST parsing failed for {file_path}: {str(e)}"
                )

    # 5. Excessively Large Patch Verification
    if total_size > max_patch_size:
        return PatchValidationReport(
            is_valid=False,
            error_reason=f"Patch size of {total_size} lines changed exceeds project policy limit of {max_patch_size}."
        )

    return PatchValidationReport(
        is_valid=True,
        patch_size=total_size,
        files_changed=files_changed,
        affected_paths=affected_paths
    )

import os
import ast
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import re
from unidiff import PatchSet
from .schemas import PatchContext, PatchValidationReport

logger = logging.getLogger("patch_engine.validator")

def normalize_hunk_headers(diff_text: str) -> str:
    """
    Recalculates unified diff hunk header line counts if an LLM miscalculated
    the source/target line counts in the '@@ -s,len +t,len @@' header.
    """
    lines = diff_text.splitlines(keepends=True)
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$", line)
        if m:
            s_start, t_start, rest = m.group(1), m.group(2), m.group(3)
            j = i + 1
            s_count = 0
            t_count = 0
            while j < len(lines):
                hl = lines[j]
                if hl.startswith("@@ ") or hl.startswith("diff --git"):
                    break
                if hl.startswith(" ") or hl.startswith("\\"):
                    s_count += 1
                    t_count += 1
                elif hl.startswith("-"):
                    s_count += 1
                elif hl.startswith("+"):
                    t_count += 1
                j += 1
            nl = "\n" if not rest.endswith("\n") else ""
            out_lines.append(f"@@ -{s_start},{s_count} +{t_start},{t_count} @@{rest}{nl}")
            i += 1
        else:
            out_lines.append(line)
            i += 1
    result = "".join(out_lines)
    if not result.endswith("\n"):
        result += "\n"
    return result

def verify_and_apply_patch(
    original_text: str,
    patched_file,
    file_path: str
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies that all hunks in patched_file match original_text exactly (context and deletions),
    and applies the changes in-memory.
    Returns (is_valid, patched_content, error_reason).
    """
    original_lines = original_text.splitlines(keepends=True)

    if patched_file.is_added_file:
        new_lines = []
        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    new_lines.append(line.value)
        return True, "".join(new_lines), None

    # Step 1: Verify all hunks against original text
    for hunk in patched_file:
        start_idx = hunk.source_start - 1  # 0-based line index
        if start_idx < 0:
            return False, None, (
                f"Patch hunk header invalid in {file_path}: "
                f"source start line {hunk.source_start} must be at least 1."
            )

        curr_idx = start_idx
        for line in hunk:
            if line.is_context or line.is_removed:
                if curr_idx >= len(original_lines):
                    return False, None, (
                        f"Patch hunk does not match repository source at {file_path}:{curr_idx + 1}: "
                        f"hunk expects line beyond end of file (file has {len(original_lines)} line(s))."
                    )
                expected = line.value.rstrip("\r\n")
                actual = original_lines[curr_idx].rstrip("\r\n")
                if expected != actual:
                    return False, None, (
                        f"Patch hunk does not match repository source at {file_path}:{curr_idx + 1}. "
                        f"Expected: {expected!r}, Found: {actual!r}"
                    )
                curr_idx += 1

        checked_lines = curr_idx - start_idx
        if checked_lines != hunk.source_length:
            return False, None, (
                f"Patch hunk source length mismatch in {file_path}: "
                f"expected {hunk.source_length} line(s), but matched {checked_lines} line(s)."
            )

    # Step 2: Apply hunks in reverse order (bottom-up to avoid line offset shifting)
    hunks = sorted(patched_file, key=lambda h: h.source_start, reverse=True)
    patched_lines = list(original_lines)

    for hunk in hunks:
        start_idx = hunk.source_start - 1
        end_idx = start_idx + hunk.source_length

        new_lines = []
        for line in hunk:
            if line.is_context or line.is_added:
                val = line.value
                if not val.endswith("\n") and not val.endswith("\r"):
                    val = val + "\n"
                new_lines.append(val)

        patched_lines[start_idx:end_idx] = new_lines

    return True, "".join(patched_lines), None

def apply_patch_to_text(original_text: str, patched_file) -> str:
    """
    Applies the hunks of a PatchedFile from unidiff to the original text.
    Uses reverse sorting by source_start to prevent line shifts from affecting offsets.
    Maintained for backwards compatibility.
    """
    is_valid, content, _ = verify_and_apply_patch(original_text, patched_file, patched_file.path or "file")
    if is_valid and content is not None:
        return content

    # Fallback to direct hunk application if strict verification failed
    original_lines = original_text.splitlines(keepends=True)
    if patched_file.is_added_file:
        new_lines = []
        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    new_lines.append(line.value)
        return "".join(new_lines)

    hunks = sorted(patched_file, key=lambda h: h.source_start, reverse=True)
    patched_lines = list(original_lines)
    for hunk in hunks:
        start_idx = max(0, hunk.source_start - 1)
        end_idx = start_idx + hunk.source_length
        new_lines = []
        for line in hunk:
            if line.is_context or line.is_added:
                new_lines.append(line.value)
        patched_lines[start_idx:end_idx] = new_lines

    return "".join(patched_lines)

def validate_patch(
    patch_text: str,
    repo_path: str,
    context: Optional[PatchContext] = None,
    policy: Optional[dict] = None
) -> PatchValidationReport:
    """
    Validates a generated patch:
    1. Validates diff structure with unidiff
    2. Verifies affected paths (strictly inside repository using Path.is_relative_to, preventing traversal)
    3. Calculates patch size (additions + deletions) and files changed
    4. Enforces project policies (restricted files, size limits, full-file rewrites)
    5. Verifies that all diff hunks match current repository source lines exactly
    6. Validates syntax of Python files by applying patches in-memory and running ast.parse
    """
    if not patch_text or not patch_text.strip():
        return PatchValidationReport(
            is_valid=False,
            error_reason="Diff contains no changes or is empty."
        )

    # 1. Parse diff
    try:
        patch_set = PatchSet(patch_text.splitlines(keepends=True))
    except Exception:
        # Fallback: attempt hunk header line count normalization
        try:
            normalized_patch = normalize_hunk_headers(patch_text)
            patch_set = PatchSet(normalized_patch.splitlines(keepends=True))
        except Exception as e:
            logger.error(f"Malformed unified diff: {e}")
            return PatchValidationReport(
                is_valid=False,
                error_reason=f"Malformed unified diff: {str(e)}"
            )

    if not patch_set or len(patch_set) == 0:
        return PatchValidationReport(
            is_valid=False,
            error_reason="Diff contains no changes or is empty."
        )

    # Policy thresholds
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

    repo_root = Path(repo_path).resolve()

    for patched_file in patch_set:
        file_path = patched_file.path
        affected_paths.append(file_path)

        # 2. Path Traversal & Repository Boundary Verification (pathlib Path.is_relative_to)
        path_obj = Path(file_path.replace("\\", "/"))
        if path_obj.is_absolute():
            target = path_obj.resolve()
        else:
            target = (repo_root / file_path.replace("\\", "/").lstrip("/")).resolve()

        if not target.is_relative_to(repo_root) or target == repo_root:
            return PatchValidationReport(
                is_valid=False,
                error_reason=f"Path traversal detected: '{file_path}' resolves outside the repository."
            )

        # 3. Project Policy: Restricted Files Verification
        if any(restricted in file_path or target.name == restricted for restricted in restricted_files):
            return PatchValidationReport(
                is_valid=False,
                error_reason=f"Modifying restricted file is prohibited by policy: {file_path}"
            )

        # Calculate size of changes in this file
        file_adds = sum(hunk.added for hunk in patched_file)
        file_dels = sum(hunk.removed for hunk in patched_file)
        total_size += (file_adds + file_dels)

        # 4. Check for full-file rewrite (if file exists and is reasonably large)
        original_content = ""
        if not patched_file.is_added_file:
            if not target.is_file():
                return PatchValidationReport(
                    is_valid=False,
                    error_reason=f"Patch modifies existing file '{file_path}' which does not exist in repository at '{target}'."
                )
            try:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    original_content = f.read()
            except Exception as e:
                return PatchValidationReport(
                    is_valid=False,
                    error_reason=f"Failed to read file '{file_path}' from repository: {str(e)}"
                )

            original_lines_count = len(original_content.splitlines())
            if original_lines_count > 15:
                for hunk in patched_file:
                    if hunk.source_length >= original_lines_count * 0.9:
                        return PatchValidationReport(
                            is_valid=False,
                            error_reason=f"Full-file rewrite detected in {file_path}. Please modify only the bug area."
                        )

        # 5. Exact Hunk Matching & Virtual Patch Application
        is_hunk_valid, patched_content, hunk_error = verify_and_apply_patch(
            original_text=original_content,
            patched_file=patched_file,
            file_path=file_path
        )
        if not is_hunk_valid:
            return PatchValidationReport(
                is_valid=False,
                error_reason=hunk_error,
                hunks_matched=False
            )

        # 6. Syntax Validation (for Python files)
        if file_path.endswith(".py") and patched_content is not None:
            try:
                ast.parse(patched_content, filename=file_path)
            except SyntaxError as se:
                return PatchValidationReport(
                    is_valid=False,
                    error_reason=f"Syntax validation failed for {file_path}: {se.msg} on line {se.lineno}",
                    hunks_matched=True,
                    syntax_valid=False
                )
            except Exception as e:
                return PatchValidationReport(
                    is_valid=False,
                    error_reason=f"Patch application or AST parsing failed for {file_path}: {str(e)}",
                    hunks_matched=True,
                    syntax_valid=False
                )

    # 7. Excessively Large Patch Verification
    if total_size > max_patch_size:
        return PatchValidationReport(
            is_valid=False,
            error_reason=f"Patch size of {total_size} lines changed exceeds project policy limit of {max_patch_size}."
        )

    return PatchValidationReport(
        is_valid=True,
        patch_size=total_size,
        files_changed=files_changed,
        affected_paths=affected_paths,
        hunks_matched=True,
        syntax_valid=True
    )

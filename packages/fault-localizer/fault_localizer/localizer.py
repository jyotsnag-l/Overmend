import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .repository import RepositoryAccess

def parse_stack_trace(stack_trace: str) -> List[Dict[str, Any]]:
    """
    Parses a python stack trace into structured frames.
    Returns list of dicts:
    {"file": str, "line": int, "function": str, "code": str, "raw": str, "depth": int}
    """
    frames = []
    if not stack_trace or not isinstance(stack_trace, str):
        return frames

    # Pattern for standard Python traceback frame:
    # File "path/to/file.py", line 12, in function_name
    # Supports single or double quotes, and optional 'in <function_name>'
    pattern = re.compile(r"""File\s+["']([^"']+)["'],\s+line\s+(\d+)(?:,\s+in\s+(\S+))?""")
    lines = stack_trace.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        match = pattern.search(line)
        if match:
            file_path = match.group(1)
            line_no = int(match.group(2))
            func_name = match.group(3) or ""

            # Extract code snippet and skip Python 3.11+ caret underline markers (e.g. ^^^^^^^)
            code_snippet = ""
            peek = i + 1
            while peek < len(lines):
                peek_line = lines[peek].strip()
                if not peek_line or pattern.search(peek_line) or peek_line.startswith("Traceback"):
                    break
                # If peek_line is just caret/tilde markers, skip it
                if set(peek_line).issubset({"^", "~", " ", "-", "|"}):
                    peek += 1
                    continue
                if not code_snippet:
                    code_snippet = peek_line
                    peek += 1
                else:
                    break

            i = max(i + 1, peek)

            frames.append({
                "file": file_path,
                "line": line_no,
                "function": func_name,
                "code": code_snippet,
                "raw": line.strip(),
                "depth": len(frames)
            })
        else:
            i += 1
    return frames

def resolve_repo_path(file_path: str, repo_access: RepositoryAccess) -> Optional[str]:
    """
    Attempts to map a stack trace file path to a relative path inside the repository.
    Strictly guarantees that any resolved path is inside the repository workspace.
    Returns relative posix path if found and valid, otherwise None.
    """
    if not file_path:
        return None

    repo_path = repo_access.repo_path

    # Normalize separators
    normalized_path = file_path.replace("\\", "/")
    path_obj = Path(normalized_path)

    # 1. Absolute path check
    if path_obj.is_absolute():
        try:
            resolved = path_obj.resolve()
            if resolved.is_relative_to(repo_path) and resolved.is_file():
                return resolved.relative_to(repo_path).as_posix()
        except Exception:
            pass

    # 2. Relative subpath check (e.g. match suffix parts)
    parts = path_obj.parts
    for i in range(len(parts)):
        subpath = Path(*parts[i:])
        try:
            candidate = repo_access.get_safe_path(subpath.as_posix())
            if candidate.is_file():
                return candidate.relative_to(repo_path).as_posix()
        except (PermissionError, FileNotFoundError, ValueError):
            pass

    # 3. Fuzzy filename fallback (find matching file by filename in repo)
    filename = path_obj.name
    matches = []
    ignored_dirs = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", "node_modules", "build", "dist", ".eggs"}

    try:
        for root, dirs, files in os.walk(str(repo_path)):
            # Prune ignored directories in-place for performance
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
            for file in files:
                if file == filename:
                    full_path = Path(root) / file
                    try:
                        if full_path.is_relative_to(repo_path) and full_path.is_file():
                            rel = full_path.relative_to(repo_path).as_posix()
                            matches.append(rel)
                    except Exception:
                        pass
    except Exception:
        pass

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        # Sort by longest common subpath with input path
        matches.sort(key=lambda m: len(os.path.commonpath([m, normalized_path.lstrip("/")])), reverse=True)
        return matches[0]

    return None

class ASTAnalyzer(ast.NodeVisitor):
    """
    AST visitor to discover enclosing functions, classes, boundaries, and imports.
    """
    def __init__(self, line_no: int):
        self.line_no = line_no
        self.current_class = None
        self.current_class_node = None
        self.found_class = None
        self.found_class_node = None
        self.found_function = None
        self.found_func_node = None
        self.imports = []

    def visit_Import(self, node):
        for alias in node.names:
            stmt = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
            self.imports.append(stmt)
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            stmt = f"from {module} import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
            self.imports.append(stmt)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        old_class = self.current_class
        old_class_node = self.current_class_node
        self.current_class = node.name
        self.current_class_node = node
        end_line = getattr(node, 'end_lineno', node.lineno) or node.lineno
        if node.lineno <= self.line_no <= end_line:
            self.found_class = node.name
            self.found_class_node = node
        self.generic_visit(node)
        self.current_class = old_class
        self.current_class_node = old_class_node

    def visit_FunctionDef(self, node):
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._check_function(node)

    def _check_function(self, node):
        end_line = getattr(node, 'end_lineno', node.lineno) or node.lineno
        if node.lineno <= self.line_no <= end_line:
            self.found_function = node.name
            self.found_func_node = node
            if self.current_class:
                self.found_class = self.current_class
                self.found_class_node = self.current_class_node
        self.generic_visit(node)

def get_control_flow_context(tree: ast.AST, line_no: int) -> List[str]:
    """
    Finds enclosing control flow statements (if, try-except, loops, with, etc.) for a line.
    """
    contexts = []

    class ControlFlowFinder(ast.NodeVisitor):
        def __init__(self):
            self.path = []
            self.matching_path = []

        def generic_visit(self, node):
            lineno = getattr(node, 'lineno', None)
            end_lineno = getattr(node, 'end_lineno', None)
            if lineno is not None and end_lineno is not None:
                if lineno <= line_no <= end_lineno:
                    self.path.append(node)
                    self.matching_path = list(self.path)
                    super().generic_visit(node)
                    self.path.pop()
                    return
            super().generic_visit(node)

    finder = ControlFlowFinder()
    finder.visit(tree)

    for node in finder.matching_path:
        if isinstance(node, ast.If):
            contexts.append("if-statement")
        elif isinstance(node, ast.Try):
            contexts.append("try-except-block")
        elif isinstance(node, ast.ExceptHandler):
            contexts.append("except-clause")
        elif isinstance(node, (ast.For, ast.While, getattr(ast, 'AsyncFor', ast.For))):
            contexts.append("loop")
        elif isinstance(node, (ast.With, getattr(ast, 'AsyncWith', ast.With))):
            contexts.append("with-statement")
        elif hasattr(ast, 'Match') and isinstance(node, ast.Match):
            contexts.append("match-statement")
        elif isinstance(node, ast.Raise) and getattr(node, 'lineno', None) == line_no:
            contexts.append("raise-statement")
        elif isinstance(node, ast.Return) and getattr(node, 'lineno', None) == line_no:
            contexts.append("return-statement")
        elif isinstance(node, ast.Assert) and getattr(node, 'lineno', None) == line_no:
            contexts.append("assert-statement")

    # Deduplicate while preserving order
    return list(dict.fromkeys(contexts))

def get_surrounding_source(content: str, line_no: int, window: int = 10) -> Dict[str, Any]:
    """
    Extracts surrounding lines around line_no.
    """
    lines = content.splitlines()
    if not lines or line_no <= 0:
        return {"start_line": 1, "end_line": 1, "lines": [], "code_block": ""}

    start = max(1, line_no - window)
    end = min(len(lines), line_no + window)

    lines_list = []
    for idx in range(start, end + 1):
        lines_list.append({
            "line": idx,
            "code": lines[idx - 1]
        })

    code_block = "\n".join(lines[start - 1 : end])
    return {
        "start_line": start,
        "end_line": end,
        "lines": lines_list,
        "code_block": code_block
    }

def find_related_tests(repo_access: RepositoryAccess, relative_file: str, function_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Finds test cases referring to the file/function using generic naming conventions,
    architectural stem variants, and AST analysis.
    """
    related = []
    file_stem = Path(relative_file).stem
    ignored_dirs = {"venv", ".venv", ".git", ".pytest_cache", "__pycache__", "node_modules", "dist", "build"}

    # Derive generic architectural stem variants (e.g. "inventory_service" -> ["inventory_service", "inventory"])
    stem_variants = {file_stem}
    for suffix in [
        "_service", "_controller", "_router", "_model", "_repository",
        "_repo", "_dao", "_handler", "_manager", "_helper", "_util",
        "_utils", "_view", "_api", "_client"
    ]:
        if file_stem.endswith(suffix):
            base = file_stem[:-len(suffix)]
            if base:
                stem_variants.add(base)
                if base.endswith("ies"):
                    stem_variants.add(base[:-3] + "y")
                elif base.endswith("s"):
                    stem_variants.add(base[:-1])

    test_files = []
    try:
        for root, dirs, files in os.walk(str(repo_access.repo_path)):
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
            for file in files:
                if (file.startswith("test_") or file.endswith("_test.py")) and file.endswith(".py"):
                    test_files.append(Path(root) / file)
    except Exception:
        pass

    for test_file in test_files:
        try:
            rel_test_path = test_file.relative_to(repo_access.repo_path).as_posix()
            content = test_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, getattr(ast, 'AsyncFunctionDef', ast.FunctionDef))) and node.name.startswith("test_"):
                    is_related = False
                    reason = ""

                    if function_name and function_name in node.name:
                        is_related = True
                        reason = f"Test function name contains '{function_name}'"
                    elif function_name:
                        # Inspect function body code snippet
                        end_ln = getattr(node, 'end_lineno', node.lineno) or node.lineno
                        body_lines = content.splitlines()[node.lineno - 1 : end_ln]
                        body_text = "\n".join(body_lines)
                        if function_name in body_text:
                            is_related = True
                            reason = f"Test function references '{function_name}'"

                    if is_related:
                        related.append({
                            "file": rel_test_path,
                            "function": node.name,
                            "line": node.lineno,
                            "reason": reason
                        })

            # Match by module name or generic stem variants if not already matched
            if not any(r["file"] == rel_test_path for r in related):
                matched_variant = None
                test_stem = test_file.stem
                for variant in stem_variants:
                    if variant in test_stem or variant in content:
                        matched_variant = variant
                        break

                if matched_variant:
                    related.append({
                        "file": rel_test_path,
                        "function": None,
                        "line": 1,
                        "reason": f"Test module '{test_file.name}' correlates with source component '{matched_variant}'"
                    })
        except Exception:
            pass

    return related

def score_candidate(
    candidate: Dict[str, Any],
    is_innermost: bool,
    stack_depth_offset: int
) -> Tuple[float, List[str]]:
    """
    Computes an explainable, deterministic ranking score for a candidate fault location.

    Signals & Weights:
    - Base repository presence: +20 points (source code located in repository workspace)
    - Stack traceback position:
        - Innermost repository frame: +25 points (where exception occurred or bubbled)
        - Caller repository frames: +18 to +5 points (offset from innermost)
    - Git blame & recent modification:
        - Failing line modified in recent repository commits: +25 points (prime suspect for regression)
        - Failing line tracked to known commit: +5 points
    - File modified in recent commit history: +10 points
    - Control-flow complexity: +10 points (enclosing if, try/except, loop, raise)
    - Function context: +5 points (enclosed in an identified function)
    - Class context: +3 points (enclosed in a class)
    - Frame source snippet available: +2 points
    - Associated test coverage: +5 points (related test cases exist)
    """
    score = 0.0
    reasons = []

    # 1. Repository presence
    score += 20.0
    reasons.append("File verified in repository workspace (+20)")

    # 2. Traceback depth
    if is_innermost:
        score += 25.0
        reasons.append("Innermost repository frame in call stack (+25)")
    else:
        caller_weight = max(5.0, 18.0 - (stack_depth_offset * 4.0))
        score += caller_weight
        reasons.append(f"Caller frame in call stack (depth offset {stack_depth_offset}) (+{caller_weight:.0f})")

    # 3. Git blame on exact line
    blame = candidate.get("git", {}).get("blame", {})
    commit_hash = blame.get("commit_hash")
    if candidate.get("recent_change"):
        score += 25.0
        short_sha = commit_hash[:8] if commit_hash else "recent"
        author = blame.get("author", "unknown")
        reasons.append(f"Failing line was modified in recent commit {short_sha} by {author} (+25)")
    elif commit_hash:
        score += 5.0
        reasons.append(f"Git blame mapped to commit {commit_hash[:8]} (+5)")

    # 4. File modified in recent commits
    file_recent_commits = candidate.get("git", {}).get("recent_commits", [])
    if file_recent_commits:
        score += 10.0
        reasons.append(f"File was modified in recent commit history ({len(file_recent_commits)} commit(s)) (+10)")

    # 5. Enclosing control flow
    control_flow = candidate.get("ast", {}).get("control_flow_context", [])
    if control_flow:
        score += 10.0
        reasons.append(f"Line is enclosed in control flow: {', '.join(control_flow)} (+10)")

    # 6. Function context
    func = candidate.get("function")
    if func and func not in ("<module>", "<unknown>", ""):
        score += 5.0
        reasons.append(f"Line belongs to function '{func}' (+5)")

    # 7. Class context
    cls = candidate.get("class")
    if cls:
        score += 3.0
        reasons.append(f"Line belongs to class '{cls}' (+3)")

    # 8. Stack frame snippet
    if candidate.get("stack_frame", {}).get("code"):
        score += 2.0
        reasons.append("Stack frame contains executable code snippet (+2)")

    # 9. Related tests
    tests = candidate.get("related_tests", [])
    if tests:
        score += 5.0
        reasons.append(f"Associated test cases discovered ({len(tests)} test(s)) (+5)")

    # 10. Test verification file penalty (test assertions detect regressions, but are rarely the root fault)
    if is_test_path(candidate.get("file")):
        score -= 35.0
        reasons.append("Frame belongs to test verification suite rather than production source (-35)")

    return round(score, 2), reasons

def is_test_path(file_path: Optional[str]) -> bool:
    """Checks if a file path is a test verification file rather than production source."""
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

def analyze_candidate_frame(
    frame: Dict[str, Any],
    resolved_rel_path: str,
    repo_access: RepositoryAccess,
    is_innermost: bool,
    stack_depth_offset: int,
    recent_repo_hashes: set
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Performs full AST, Git, and test analysis on a stack frame located in the repository.
    Returns (candidate_dict, evidence_lines).
    """
    evidence = []
    line_no = frame["line"]
    func_name = frame.get("function", "")

    # AST analysis
    class_name = None
    func_boundaries = None
    class_boundaries = None
    control_flow = []
    file_imports = []
    surrounding_src = {}

    try:
        content = repo_access.read_file(resolved_rel_path)
        surrounding_src = get_surrounding_source(content, line_no)

        try:
            tree = ast.parse(content)
            analyzer = ASTAnalyzer(line_no)
            analyzer.visit(tree)

            class_name = analyzer.found_class
            file_imports = list(dict.fromkeys(analyzer.imports))

            if analyzer.found_func_node:
                func_node = analyzer.found_func_node
                func_boundaries = {
                    "start_line": func_node.lineno,
                    "end_line": getattr(func_node, 'end_lineno', func_node.lineno) or func_node.lineno
                }
                func_name = analyzer.found_function or func_name
                evidence.append(
                    f"AST resolved boundaries for function '{func_name}' as line {func_boundaries['start_line']} to {func_boundaries['end_line']}."
                )
                if class_name:
                    evidence.append(f"AST identified enclosing class as '{class_name}'.")

            if analyzer.found_class_node:
                cls_node = analyzer.found_class_node
                class_boundaries = {
                    "start_line": cls_node.lineno,
                    "end_line": getattr(cls_node, 'end_lineno', cls_node.lineno) or cls_node.lineno
                }

            control_flow = get_control_flow_context(tree, line_no)
            if control_flow:
                evidence.append(f"Enclosing control flow detected for line {line_no}: {', '.join(control_flow)}.")
        except Exception as ast_err:
            evidence.append(f"AST parsing skipped or failed for {resolved_rel_path}: {str(ast_err)}")
    except Exception as read_err:
        evidence.append(f"Could not read source file {resolved_rel_path}: {str(read_err)}")

    # Git history & blame analysis
    recent_change = False
    blame_info = {}
    file_recent_commits = []

    if repo_access.is_git_available():
        try:
            blame_info = repo_access.get_blame(resolved_rel_path, line_no)
            commit_hash = blame_info.get("commit_hash")
            if commit_hash and isinstance(commit_hash, str):
                evidence.append(f"Git blame: line was introduced in commit {commit_hash[:8]} by {blame_info.get('author')}.")
                if commit_hash in recent_repo_hashes:
                    recent_change = True
                    evidence.append("Git blame check: Line was modified in recent commits.")
        except Exception as git_err:
            evidence.append(f"Git blame analysis failed: {str(git_err)}")

        try:
            file_recent_commits = repo_access.get_recent_commits(limit=5, relative_path=resolved_rel_path)
        except Exception:
            pass

    # Related tests
    related_tests = []
    try:
        related_tests = find_related_tests(repo_access, resolved_rel_path, func_name)
        if related_tests:
            evidence.append(f"Found {len(related_tests)} related test(s) for {resolved_rel_path}.")
    except Exception as test_err:
        evidence.append(f"Failed to find related tests: {str(test_err)}")

    # Candidate object
    candidate = {
        "file": resolved_rel_path,
        "line": line_no,
        "function": func_name,
        "class": class_name,
        "score": 0.0,
        "reasons": [],
        "stack_frame": {
            "file": frame["file"],
            "line": frame["line"],
            "function": frame["function"],
            "code": frame.get("code", ""),
            "raw": frame.get("raw", ""),
            "depth": frame.get("depth", 0),
            "is_innermost": is_innermost
        },
        "ast": {
            "function_boundaries": func_boundaries,
            "class_boundaries": class_boundaries,
            "control_flow_context": control_flow,
            "imports": file_imports,
            "surrounding_source": surrounding_src
        },
        "surrounding_source": surrounding_src,
        "git": {
            "blame": blame_info,
            "recent_commits": file_recent_commits
        },
        "recent_change": recent_change,
        "related_tests": related_tests
    }

    # Calculate evidence-based score
    score, reasons = score_candidate(
        candidate=candidate,
        is_innermost=is_innermost,
        stack_depth_offset=stack_depth_offset
    )
    candidate["score"] = score
    candidate["reasons"] = reasons

    return candidate, evidence

def localize_fault_core(
    stack_trace: str,
    repo_path: str,
    incident_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main localized fault runner. Parses stack trace, resolves repository files,
    evaluates all relevant stack frames, computes explainable scores, and returns
    ranked fault candidates alongside backwards-compatible top-level fault fields.
    """
    evidence = []
    repo_access = RepositoryAccess(repo_path)
    try:
        # 1. Parse stack trace
        frames = parse_stack_trace(stack_trace)
        if not frames:
            return {
                "file": None,
                "line": None,
                "function": None,
                "class": None,
                "score": 0.0,
                "reasons": ["No stack frames found in stack trace."],
                "stack_frame": {},
                "recent_change": False,
                "evidence": ["No stack frames found in stack trace."],
                "candidates": [],
                "fault_candidates": [],
                "ast": {
                    "function_boundaries": None,
                    "class_boundaries": None,
                    "control_flow_context": [],
                    "imports": [],
                    "surrounding_source": {}
                },
                "git": {
                    "blame": {},
                    "recent_commits": []
                },
                "related_tests": [],
                "surrounding_source": {}
            }

        evidence.append(f"Successfully parsed {len(frames)} stack trace frame(s).")

        # 2. Retrieve recent repository commit hashes once for blame cross-referencing
        recent_repo_hashes = set()
        if repo_access.is_git_available():
            try:
                recent_commits = repo_access.get_recent_commits(limit=5)
                recent_repo_hashes = {c["commit_hash"] for c in recent_commits if c.get("commit_hash")}
            except Exception:
                pass

        # 3. Resolve frames to repository files
        repo_frame_indices = []
        resolved_paths_map = {}

        for idx, frame in enumerate(frames):
            rel_path = resolve_repo_path(frame["file"], repo_access)
            if rel_path:
                repo_frame_indices.append(idx)
                resolved_paths_map[idx] = rel_path
            else:
                evidence.append(f"Frame {idx} ({frame['file']}) resolved outside repository workspace.")

        # 4. Generate candidates for all repository frames
        candidates = []
        seen_locations = set()

        if repo_frame_indices:
            innermost_repo_idx = repo_frame_indices[-1]

            # Analyze each repository frame (innermost to outermost)
            for offset, idx in enumerate(reversed(repo_frame_indices)):
                frame = frames[idx]
                resolved_path = resolved_paths_map[idx]
                loc_key = (resolved_path, frame["line"])

                if loc_key in seen_locations:
                    continue
                seen_locations.add(loc_key)

                is_innermost = (idx == innermost_repo_idx)
                candidate, frame_evidence = analyze_candidate_frame(
                    frame=frame,
                    resolved_rel_path=resolved_path,
                    repo_access=repo_access,
                    is_innermost=is_innermost,
                    stack_depth_offset=offset,
                    recent_repo_hashes=recent_repo_hashes
                )
                evidence.extend(frame_evidence)
                candidates.append(candidate)

        # Check if all repository frames originate from test suites (e.g. failure detected by test suite)
        all_frames_are_tests = bool(repo_frame_indices) and all(
            is_test_path(resolved_paths_map[i]) for i in repo_frame_indices
        )

        if all_frames_are_tests and repo_access.is_git_available():
            evidence.append("Inspecting recent production commit diffs for regression culprits...")
            commit_hunks = repo_access.get_commit_diff_hunks("HEAD")
            for hunk in commit_hunks:
                if is_test_path(hunk["file"]):
                    continue
                loc_key = (hunk["file"], hunk["line"])
                if loc_key in seen_locations:
                    continue
                seen_locations.add(loc_key)

                frame = {
                    "file": hunk["file"],
                    "line": hunk["line"],
                    "function": "",
                    "code": hunk.get("code", ""),
                    "raw": hunk.get("code", ""),
                    "depth": 0
                }
                candidate, frame_evidence = analyze_candidate_frame(
                    frame=frame,
                    resolved_rel_path=hunk["file"],
                    repo_access=repo_access,
                    is_innermost=True,
                    stack_depth_offset=0,
                    recent_repo_hashes=recent_repo_hashes
                )
                evidence.extend(frame_evidence)
                candidates.append(candidate)

        # 5. Fallback handling if no frames resolved within repository
        if not candidates:
            evidence.append("Warning: No stack frames matched files in the repository. Falling back to the deepest frame.")
            fallback_frame = frames[-1]
            fallback_candidate = {
                "file": fallback_frame["file"],
                "line": fallback_frame["line"],
                "function": fallback_frame["function"],
                "class": None,
                "score": 0.0,
                "reasons": ["External or unresolvable frame (outside repository workspace)"],
                "stack_frame": fallback_frame,
                "ast": {
                    "function_boundaries": None,
                    "class_boundaries": None,
                    "control_flow_context": [],
                    "imports": [],
                    "surrounding_source": {}
                },
                "surrounding_source": {},
                "git": {
                    "blame": {},
                    "recent_commits": []
                },
                "recent_change": False,
                "related_tests": []
            }
            candidates.append(fallback_candidate)

        # 6. Rank candidates: primary by score descending, secondary by stack depth descending
        candidates.sort(
            key=lambda c: (
                c["score"],
                c["stack_frame"].get("depth", 0),
                -c.get("line", 0) if c.get("line") else 0
            ),
            reverse=True
        )

        # 7. Select top candidate for backwards-compatible primary fields
        best = candidates[0]
        evidence.append(
            f"Selected top candidate: file={best['file']}, line={best['line']}, function={best['function']} "
            f"with score {best['score']} ({len(candidates)} total candidate(s) ranked)."
        )

        return {
            "file": best["file"],
            "line": best["line"],
            "function": best["function"],
            "class": best["class"],
            "score": best["score"],
            "reasons": best["reasons"],
            "stack_frame": best["stack_frame"],
            "recent_change": best["recent_change"],
            "evidence": evidence,
            "ast": best["ast"],
            "git": best["git"],
            "related_tests": best["related_tests"],
            "surrounding_source": best.get("surrounding_source", {}),
            "candidates": candidates,
            "fault_candidates": candidates
        }
    finally:
        repo_access.close()

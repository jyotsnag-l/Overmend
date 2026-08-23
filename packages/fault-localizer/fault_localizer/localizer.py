import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .repository import RepositoryAccess

def parse_stack_trace(stack_trace: str) -> List[Dict[str, Any]]:
    """
    Parses a python stack trace into structured frames.
    Returns list of dicts: {"file": str, "line": int, "function": str, "code": str, "raw": str}
    """
    frames = []
    if not stack_trace:
        return frames

    # Pattern for standard Python traceback frame: File "path/to/file.py", line 12, in function_name
    pattern = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
    lines = stack_trace.splitlines()
    
    i = 0
    while i < len(lines):
        line = lines[i]
        match = pattern.search(line)
        if match:
            file_path = match.group(1)
            line_no = int(match.group(2))
            func_name = match.group(3)
            
            # Extract code snippet
            code_snippet = ""
            if i + 1 < len(lines) and not pattern.search(lines[i + 1]) and not lines[i + 1].strip().startswith("Traceback"):
                code_snippet = lines[i + 1].strip()
                i += 1
            
            frames.append({
                "file": file_path,
                "line": line_no,
                "function": func_name,
                "code": code_snippet,
                "raw": line
            })
        i += 1
    return frames

def resolve_repo_path(file_path: str, repo_access: RepositoryAccess) -> Optional[str]:
    """
    Attempts to map a stack trace file path to a relative path inside the repository.
    Returns relative path if found, otherwise None.
    """
    repo_path = repo_access.repo_path
    
    # Normalize separators
    normalized_path = file_path.replace("\\", "/")
    path_obj = Path(normalized_path)
    
    # 1. Absolute path check
    if path_obj.is_absolute():
        try:
            resolved = path_obj.resolve()
            if resolved.is_relative_to(repo_path):
                return str(resolved.relative_to(repo_path).as_posix())
        except Exception:
            pass
            
    # 2. Relative subpath check (e.g. check if segments match)
    parts = path_obj.parts
    for i in range(len(parts)):
        subpath = Path(*parts[i:])
        try:
            # Check if this resolves to a path inside repo
            candidate = repo_access.get_safe_path(str(subpath.as_posix()))
            if candidate.is_file():
                return str(subpath.as_posix())
        except (PermissionError, FileNotFoundError):
            pass
            
    # 3. Fuzzy filename fallback (find unique file matching filename in repo)
    filename = path_obj.name
    matches = []
    # Recursively search the repo directory
    for root, _, files in os.walk(str(repo_path)):
        # Skip hidden directories like .git
        if ".git" in root or ".pytest_cache" in root or "venv" in root:
            continue
        for file in files:
            if file == filename:
                full_path = Path(root) / file
                rel = full_path.relative_to(repo_path).as_posix()
                matches.append(rel)
                
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        # Sort by longest common subpath with input path
        matches.sort(key=lambda m: len(os.path.commonpath([m, normalized_path])), reverse=True)
        return matches[0]
        
    return None

class ASTAnalyzer(ast.NodeVisitor):
    def __init__(self, line_no: int):
        self.line_no = line_no
        self.current_class = None
        self.found_class = None
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
        self.current_class = node.name
        end_line = getattr(node, 'end_lineno', node.lineno) or node.lineno
        if node.lineno <= self.line_no <= end_line:
            self.found_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

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
        self.generic_visit(node)

def get_control_flow_context(tree: ast.AST, line_no: int) -> List[str]:
    """
    Finds enclosing control flow statements (if, try-except, loops, with) for a line.
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
        elif isinstance(node, (ast.For, ast.While)):
            contexts.append("loop")
        elif isinstance(node, ast.With):
            contexts.append("with-statement")
    return contexts

def get_surrounding_source(content: str, line_no: int, window: int = 10) -> Dict[str, Any]:
    """
    Extracts surrounding lines around line_no.
    """
    lines = content.splitlines()
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

def find_related_tests(repo_access: RepositoryAccess, relative_file: str, function_name: str) -> List[Dict[str, Any]]:
    """
    Finds test cases referring to the file/function.
    """
    related = []
    file_stem = Path(relative_file).stem
    
    # Traverse repo to find test files
    test_files = []
    for root, _, files in os.walk(str(repo_access.repo_path)):
        if "venv" in root or ".git" in root or ".pytest_cache" in root:
            continue
        for file in files:
            if (file.startswith("test_") or file.endswith("_test")) and file.endswith(".py"):
                test_files.append(Path(root) / file)
                
    for test_file in test_files:
        rel_test_path = test_file.relative_to(repo_access.repo_path).as_posix()
        try:
            content = test_file.read_text(encoding="utf-8", errors="ignore")
            # Parse test AST
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    is_related = False
                    reason = ""
                    
                    if function_name and function_name in node.name:
                        is_related = True
                        reason = f"Test function name contains '{function_name}'"
                    else:
                        # Inspect function body code snippet
                        body_lines = content.splitlines()[node.lineno-1 : getattr(node, 'end_lineno', node.lineno)]
                        body_text = "\n".join(body_lines)
                        if function_name and function_name in body_text:
                            is_related = True
                            reason = f"Test function references '{function_name}'"
                            
                    if is_related:
                        related.append({
                            "file": rel_test_path,
                            "function": node.name,
                            "line": node.lineno,
                            "reason": reason
                        })
            
            # Match by module name if not already found
            if file_stem in test_file.name and not any(r["file"] == rel_test_path for r in related):
                related.append({
                    "file": rel_test_path,
                    "function": None,
                    "line": 1,
                    "reason": f"Test module name matches source module '{file_stem}'"
                })
        except Exception:
            pass
            
    return related

def localize_fault_core(
    stack_trace: str,
    repo_path: str,
    incident_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main localized fault runner. Parses stack trace, resolves repository files,
    uses AST for structure analysis, and uses GitPython for history blames.
    """
    evidence = []
    repo_access = RepositoryAccess(repo_path)
    
    # 1. Parse stack trace
    frames = parse_stack_trace(stack_trace)
    if not frames:
        return {
            "file": None,
            "line": None,
            "function": None,
            "class": None,
            "stack_frame": {},
            "recent_change": False,
            "evidence": ["No stack frames found in stack trace."]
        }
        
    evidence.append(f"Successfully parsed {len(frames)} stack trace frame(s).")
    
    # 2. Select faulting frame using baseline (deepest frame matching repo file)
    selected_frame = None
    resolved_rel_path = None
    
    for frame in reversed(frames):
        rel_path = resolve_repo_path(frame["file"], repo_access)
        if rel_path:
            selected_frame = frame
            resolved_rel_path = rel_path
            evidence.append(f"Selected frame: file={rel_path}, line={frame['line']}, function={frame['function']} (Deepest match in repository)")
            break
            
    if not selected_frame:
        selected_frame = frames[-1]
        resolved_rel_path = selected_frame["file"]
        evidence.append("Warning: No stack frames matched files in the repository. Falling back to the deepest frame.")
        
    line_no = selected_frame["line"]
    func_name = selected_frame["function"]
    
    # 3. Analyze file with AST
    class_name = None
    func_boundaries = None
    control_flow = []
    file_imports = []
    surrounding_src = {}
    
    try:
        content = repo_access.read_file(resolved_rel_path)
        tree = ast.parse(content)
        
        analyzer = ASTAnalyzer(line_no)
        analyzer.visit(tree)
        
        class_name = analyzer.found_class
        file_imports = list(set(analyzer.imports))
        
        if analyzer.found_func_node:
            func_node = analyzer.found_func_node
            func_boundaries = {
                "start_line": func_node.lineno,
                "end_line": getattr(func_node, 'end_lineno', func_node.lineno) or func_node.lineno
            }
            evidence.append(f"AST resolved boundaries for function '{func_name}' as line {func_boundaries['start_line']} to {func_boundaries['end_line']}.")
            if class_name:
                evidence.append(f"AST identified enclosing class as '{class_name}'.")
        else:
            evidence.append(f"AST did not find function definition enclosing line {line_no}.")
            
        control_flow = get_control_flow_context(tree, line_no)
        if control_flow:
            evidence.append(f"Enclosing control flow detected: {', '.join(control_flow)}.")
            
        surrounding_src = get_surrounding_source(content, line_no)
    except Exception as e:
        evidence.append(f"AST analysis skipped or failed: {str(e)}")
        
    # 4. Git history analysis
    recent_change = False
    blame_info = {}
    
    if repo_access.repo and resolved_rel_path:
        try:
            blame_info = repo_access.get_blame(resolved_rel_path, line_no)
            if blame_info:
                commit_hash = blame_info.get("commit_hash")
                evidence.append(f"Git blame: line was introduced in commit {commit_hash[:8]} by {blame_info.get('author')}.")
                
                # Check if this is a recent change
                recent_commits = repo_access.get_recent_commits(limit=5)
                recent_hashes = {c["commit_hash"] for c in recent_commits}
                if commit_hash in recent_hashes:
                    recent_change = True
                    evidence.append("Git blame check: Line was modified in one of the 5 most recent commits.")
        except Exception as e:
            evidence.append(f"Git analysis failed: {str(e)}")
            
    # 5. Related tests
    related_tests = []
    if resolved_rel_path:
        try:
            related_tests = find_related_tests(repo_access, resolved_rel_path, func_name)
            if related_tests:
                evidence.append(f"Found {len(related_tests)} related test(s).")
        except Exception as e:
            evidence.append(f"Failed to find related tests: {str(e)}")
            
    return {
        "file": resolved_rel_path,
        "line": line_no,
        "function": func_name,
        "class": class_name,
        "stack_frame": {
            "file": selected_frame["file"],
            "line": selected_frame["line"],
            "function": selected_frame["function"],
            "code": selected_frame["code"],
            "raw": selected_frame["raw"]
        },
        "recent_change": recent_change,
        "evidence": evidence,
        "ast": {
            "function_boundaries": func_boundaries,
            "control_flow_context": control_flow,
            "imports": file_imports,
            "surrounding_source": surrounding_src
        },
        "git": {
            "blame": blame_info
        },
        "related_tests": related_tests
    }

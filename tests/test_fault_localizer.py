import os
import shutil
import pytest
import git
from pathlib import Path
from typing import Dict, Any

from fault_localizer.repository import RepositoryAccess
from fault_localizer.localizer import parse_stack_trace, resolve_repo_path, localize_fault_core
from fault_localizer.context import ContextBuilder
from fault_localizer import localize_fault, build_patch_context

# Sample traceback strings representing demo-repo bugs
PAYMENTS_TRACEBACK = """Traceback (most recent call last):
  File "demo-repo/app.py", line 41, in calculate_refund
    return {"refund": payments.calculate_refund(amount, ratio)}
  File "demo-repo/payments.py", line 4, in calculate_refund
    return amount / 0  # Intentionally raise ZeroDivisionError
ZeroDivisionError: division by zero"""

USERS_TRACEBACK = """Traceback (most recent call last):
  File "demo-repo/app.py", line 17, in get_user
    return users.get_user_profile(user_id)
  File "demo-repo/users.py", line 5, in get_user_profile
    return profile_db[user_id]
NameError: name 'profile_db' is not defined"""

@pytest.fixture
def temp_git_repo(tmp_path) -> Path:
    """
    Fixture to copy the demo repository files to a temporary path,
    initialize it as a Git repository, commit files, and return the path.
    """
    demo_repo_src = Path("demo-repo").resolve()
    # Copy files
    shutil.copytree(demo_repo_src, tmp_path, dirs_exist_ok=True)
    
    # Initialize Git repository
    repo = git.Repo.init(tmp_path)
    
    # Configure user credentials for committing
    with repo.config_writer() as writer:
        writer.set_value("user", "name", "Test Developer")
        writer.set_value("user", "email", "dev@test.com")
        
    # Commit all initial files
    repo.git.add(all=True)
    repo.index.commit("Initial commit of demo app")
    
    # Add dummy commits so that the initial files are not in the top 5 most recent commits
    for i in range(6):
        dummy_file = tmp_path / f"dummy_init_{i}.txt"
        dummy_file.write_text(f"dummy init {i}")
        repo.git.add(all=True)
        repo.index.commit(f"Dummy init commit {i}")
    
    return tmp_path

def test_stack_trace_parsing():
    """Verify that a stack trace is correctly parsed into structured frames."""
    frames = parse_stack_trace(PAYMENTS_TRACEBACK)
    assert len(frames) == 2
    
    assert frames[0]["file"] == "demo-repo/app.py"
    assert frames[0]["line"] == 41
    assert frames[0]["function"] == "calculate_refund"
    assert "payments.calculate_refund" in frames[0]["code"]
    
    assert frames[1]["file"] == "demo-repo/payments.py"
    assert frames[1]["line"] == 4
    assert frames[1]["function"] == "calculate_refund"
    assert "amount / 0" in frames[1]["code"]

def test_resolve_repo_path(temp_git_repo):
    """Verify path resolution strategies, including fuzzy fallback matching."""
    repo_access = RepositoryAccess(str(temp_git_repo))
    
    # Relative path match
    path1 = resolve_repo_path("demo-repo/payments.py", repo_access)
    assert path1 == "payments.py"
    
    # Direct filename match
    path2 = resolve_repo_path("payments.py", repo_access)
    assert path2 == "payments.py"
    
    # Deep absolute path simulation
    abs_path = os.path.join(str(temp_git_repo), "users.py")
    path3 = resolve_repo_path(abs_path, repo_access)
    assert path3 == "users.py"

def test_security_path_traversal(temp_git_repo):
    """Verify that safe repository access blocks directory traversal attempts."""
    repo_access = RepositoryAccess(str(temp_git_repo))
    
    # Should resolve safely within repo
    safe_path = repo_access.get_safe_path("payments.py")
    assert safe_path.exists()
    
    # Path traversal should raise PermissionError
    with pytest.raises(PermissionError):
        repo_access.get_safe_path("../../../etc/passwd")

def test_fault_localization_payments(temp_git_repo):
    """Verify localization of the payments zero division incident."""
    fault = localize_fault(PAYMENTS_TRACEBACK, repo_path=str(temp_git_repo))
    
    assert fault["file"] == "payments.py"
    assert fault["line"] == 4
    assert fault["function"] == "calculate_refund"
    assert fault["class"] is None
    assert fault["recent_change"] is False  # Line has not been modified recently yet
    assert len(fault["evidence"]) > 0
    assert any("calculate_refund" in ev for ev in fault["evidence"])

def test_fault_localization_users(temp_git_repo):
    """Verify localization of the users profile name error incident."""
    fault = localize_fault(USERS_TRACEBACK, repo_path=str(temp_git_repo))
    
    assert fault["file"] == "users.py"
    assert fault["line"] == 5
    assert fault["function"] == "get_user_profile"
    assert fault["class"] is None

def test_ast_analysis_context(temp_git_repo):
    """Verify boundary detection, imports extraction, and control flow context."""
    res = localize_fault_core(PAYMENTS_TRACEBACK, repo_path=str(temp_git_repo))
    
    # Check AST attributes extracted
    ast_data = res["ast"]
    assert ast_data["function_boundaries"] == {"start_line": 1, "end_line": 5}
    assert "if-statement" in ast_data["control_flow_context"]
    assert any("import" in imp for imp in ast_data["imports"]) or len(ast_data["imports"]) == 0  # payments.py has no imports
    
    # Check users.py imports
    res_users = localize_fault_core(USERS_TRACEBACK, repo_path=str(temp_git_repo))
    assert res_users["ast"]["function_boundaries"] == {"start_line": 1, "end_line": 5}

def test_git_blame_and_recent_change(temp_git_repo):
    """Verify git blame info and recent change detection flag."""
    repo_access = RepositoryAccess(str(temp_git_repo))
    
    # Initial status: blame is the initial commit (which is old, > 5 commits ago)
    fault = localize_fault(PAYMENTS_TRACEBACK, repo_path=str(temp_git_repo))
    assert fault["recent_change"] is False
    
    # Let's modify payments.py on line 4, commit it, and verify that recent_change is detected as True
    repo = git.Repo(temp_git_repo)
    payments_file = temp_git_repo / "payments.py"
    lines = payments_file.read_text().splitlines()
    lines[3] = "        return amount / 0.0  # Modified line"
    payments_file.write_text("\n".join(lines))
    
    repo.git.add(all=True)
    repo.index.commit("Modify payments refund error line")
    
    # Localize again, it should detect recent change is True
    fault_new = localize_fault(PAYMENTS_TRACEBACK, repo_path=str(temp_git_repo))
    assert fault_new["recent_change"] is True

def test_related_tests_detection(temp_git_repo):
    """Verify detection of related test modules and functions in the repository."""
    res = localize_fault_core(PAYMENTS_TRACEBACK, repo_path=str(temp_git_repo))
    related = res["related_tests"]
    
    assert len(related) > 0
    # The tests should point to tests/test_payments.py
    assert any("test_payments.py" in r["file"] for r in related)
    assert any("test_calculate_refund" in r["function"] for r in related if r["function"])

def test_context_builder(temp_git_repo):
    """Verify structured PatchContext output generation following prioritized context rules."""
    incident = {
        "id": "inc_abc123",
        "exception_type": "ZeroDivisionError",
        "exception_message": "division by zero",
        "stack_trace": PAYMENTS_TRACEBACK,
        "fingerprint": "zp_fingerprint"
    }
    
    context = build_patch_context(incident, repo_path=str(temp_git_repo))
    
    # Schema validation
    assert "incident" in context
    assert "fault_location" in context
    assert "source_context" in context
    assert "imports" in context
    assert "related_tests" in context
    assert "git_history" in context
    assert "historical_context" in context
    
    # 1. Faulting function context
    src_ctx = context["source_context"]
    assert src_ctx["faulting_file"] == "payments.py"
    assert src_ctx["faulting_function"]["name"] == "calculate_refund"
    assert "def calculate_refund" in src_ctx["faulting_function"]["code"]
    
    # 2. Surrounding lines
    assert "surrounding_lines" in src_ctx
    assert src_ctx["surrounding_lines"]["code"] is not None
    
    # 4. Calling function context
    assert src_ctx["calling_function"]["function"] == "calculate_refund"
    assert "def calculate_refund" in src_ctx["calling_function"]["code"]
    
    # 5. Related tests
    assert len(context["related_tests"]) > 0
    
    # 6. Git history
    assert len(context["git_history"]) > 0
    assert any(g["type"] == "blame" for g in context["git_history"])
    assert any(g["type"] == "commit" for g in context["git_history"])

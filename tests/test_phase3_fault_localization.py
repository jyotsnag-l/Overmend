import os
import shutil
import pytest
import git
from pathlib import Path
from typing import Dict, Any

from fault_localizer.repository import RepositoryAccess
from fault_localizer.localizer import (
    parse_stack_trace,
    resolve_repo_path,
    localize_fault_core,
    score_candidate
)
from fault_localizer.context import ContextBuilder
from fault_localizer import localize_fault, build_patch_context

@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    """
    Creates a temporary git workspace with a structured multi-file python project.
    """
    pkg_dir = tmp_path / "app"
    pkg_dir.mkdir(parents=True)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)

    # File 1: utils.py (untouched helper)
    utils_file = pkg_dir / "utils.py"
    utils_file.write_text(
        "def compute_discount(price: float, rate: float) -> float:\n"
        "    if rate < 0:\n"
        "        raise ValueError('Invalid rate')\n"
        "    return price * rate\n"
    )

    # File 2: service.py (class with methods and control flow)
    service_file = pkg_dir / "service.py"
    service_file.write_text(
        "from app.utils import compute_discount\n\n"
        "class OrderService:\n"
        "    def process_order(self, order_id: str, total: float, rate: float):\n"
        "        try:\n"
        "            discount = compute_discount(total, rate)\n"
        "            return total - discount\n"
        "        except Exception as e:\n"
        "            raise RuntimeError(f'Order {order_id} failed: {e}')\n"
    )

    # File 3: test_service.py
    test_file = tests_dir / "test_service.py"
    test_file.write_text(
        "import pytest\n"
        "from app.service import OrderService\n\n"
        "def test_process_order():\n"
        "    service = OrderService()\n"
        "    assert service.process_order('ord_1', 100.0, 0.1) == 90.0\n"
    )

    # Initialize Git repo
    repo = git.Repo.init(tmp_path)
    with repo.config_writer() as writer:
        writer.set_value("user", "name", "Phase 3 Tester")
        writer.set_value("user", "email", "tester@overmend.ai")

    repo.git.add(all=True)
    repo.index.commit("Initial working commit")

    # Add dummy commits so initial commit is > 5 commits ago
    for i in range(6):
        dummy = tmp_path / f"dummy_{i}.txt"
        dummy.write_text(f"dummy {i}")
        repo.git.add(all=True)
        repo.index.commit(f"Dummy commit {i}")

    return tmp_path

# ==============================================================================
# Requirement 1: Normal Python traceback localization
# ==============================================================================
def test_normal_python_traceback_localization(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/service.py", line 6, in process_order\n'
        '    discount = compute_discount(total, rate)\n'
        'RuntimeError: Order ord_1 failed: Invalid rate\n'
    )
    result = localize_fault(tb, repo_path=str(sample_workspace))
    assert result["file"] == "app/service.py"
    assert result["line"] == 6
    assert result["function"] == "process_order"
    assert result["class"] == "OrderService"
    assert result["score"] > 0
    assert len(result["reasons"]) > 0
    assert len(result["candidates"]) == 1

# ==============================================================================
# Requirement 2: Multiple repository stack frames
# ==============================================================================
def test_multiple_repository_stack_frames(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/service.py", line 6, in process_order\n'
        '    discount = compute_discount(total, rate)\n'
        '  File "app/utils.py", line 3, in compute_discount\n'
        '    raise ValueError("Invalid rate")\n'
        'ValueError: Invalid rate\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    candidates = result["candidates"]
    assert len(candidates) == 2

    files = [c["file"] for c in candidates]
    assert "app/utils.py" in files
    assert "app/service.py" in files

# ==============================================================================
# Requirement 3: External/library stack frames
# ==============================================================================
def test_external_library_stack_frames(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "/usr/local/lib/python3.10/site-packages/fastapi/routing.py", line 227, in app\n'
        '    raw_response = await run_endpoint_function(dependant=dependant, values=values, is_coroutine=is_coroutine)\n'
        '  File "app/service.py", line 6, in process_order\n'
        '    discount = compute_discount(total, rate)\n'
        '  File "/usr/lib/python3.10/json/decoder.py", line 355, in raw_decode\n'
        '    raise JSONDecodeError("Expecting value", s, err.value) from None\n'
        'json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    candidates = result["candidates"]

    # Only repository frame app/service.py should be in candidate list
    assert len(candidates) == 1
    assert candidates[0]["file"] == "app/service.py"
    assert candidates[0]["line"] == 6
    assert any("outside repository workspace" in ev for ev in result["evidence"])

# ==============================================================================
# Requirement 4: Absolute stack-trace path
# ==============================================================================
def test_absolute_stack_trace_path(sample_workspace: Path):
    abs_service_path = (sample_workspace / "app" / "service.py").resolve().as_posix()
    tb = (
        f'Traceback (most recent call last):\n'
        f'  File "{abs_service_path}", line 6, in process_order\n'
        f'    discount = compute_discount(total, rate)\n'
    )
    result = localize_fault(tb, repo_path=str(sample_workspace))
    assert result["file"] == "app/service.py"
    assert result["line"] == 6

# ==============================================================================
# Requirement 5: Relative stack-trace path
# ==============================================================================
def test_relative_stack_trace_path(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "./app/utils.py", line 3, in compute_discount\n'
        '    raise ValueError("Invalid rate")\n'
    )
    result = localize_fault(tb, repo_path=str(sample_workspace))
    assert result["file"] == "app/utils.py"
    assert result["line"] == 3

# ==============================================================================
# Requirement 6: Unresolvable stack-trace path
# ==============================================================================
def test_unresolvable_stack_trace_path(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "/nonexistent/remote/cloud/unknown_file.py", line 99, in mystery_func\n'
        '    x = 1 / 0\n'
        'ZeroDivisionError: division by zero\n'
    )
    result = localize_fault(tb, repo_path=str(sample_workspace))
    assert result["score"] == 0.0
    assert result["file"] == "/nonexistent/remote/cloud/unknown_file.py"
    assert result["line"] == 99
    assert any("No stack frames matched files in the repository" in ev for ev in result["evidence"])

# ==============================================================================
# Requirement 7: AST function detection
# ==============================================================================
def test_ast_function_detection(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/utils.py", line 3, in compute_discount\n'
        '    raise ValueError("Invalid rate")\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    ast_data = result["ast"]
    assert ast_data["function_boundaries"] == {"start_line": 1, "end_line": 4}
    assert result["function"] == "compute_discount"

# ==============================================================================
# Requirement 8: AST class detection
# ==============================================================================
def test_ast_class_detection(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/service.py", line 6, in process_order\n'
        '    discount = compute_discount(total, rate)\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    assert result["class"] == "OrderService"
    assert result["ast"]["class_boundaries"]["start_line"] == 3

# ==============================================================================
# Requirement 9: AST control-flow detection
# ==============================================================================
def test_ast_control_flow_detection(sample_workspace: Path):
    # Line 3 in utils.py is inside `if rate < 0:`
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/utils.py", line 3, in compute_discount\n'
        '    raise ValueError("Invalid rate")\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    control_flow = result["ast"]["control_flow_context"]
    assert "if-statement" in control_flow
    assert "raise-statement" in control_flow

    # Line 5 in service.py is inside `try:`
    tb2 = (
        'Traceback (most recent call last):\n'
        '  File "app/service.py", line 5, in process_order\n'
        '    discount = compute_discount(total, rate)\n'
    )
    result2 = localize_fault_core(tb2, repo_path=str(sample_workspace))
    assert "try-except-block" in result2["ast"]["control_flow_context"]

# ==============================================================================
# Requirement 10: Git blame when Git is available
# ==============================================================================
def test_git_blame_when_git_available(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/utils.py", line 3, in compute_discount\n'
        '    raise ValueError("Invalid rate")\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    blame = result["git"]["blame"]
    assert blame.get("commit_hash") is not None
    assert blame.get("author") == "Phase 3 Tester"
    assert blame.get("email") == "tester@overmend.ai"

# ==============================================================================
# Requirement 11: Graceful behavior without Git
# ==============================================================================
def test_graceful_behavior_without_git(tmp_path: Path):
    # Create non-git workspace
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code_file = src_dir / "calculator.py"
    code_file.write_text("def add(a, b):\n    return a + b\n")

    tb = (
        'Traceback (most recent call last):\n'
        '  File "src/calculator.py", line 2, in add\n'
        '    return a + b\n'
    )
    # Must succeed cleanly without git initialized
    result = localize_fault(tb, repo_path=str(tmp_path))
    assert result["file"] == "src/calculator.py"
    assert result["line"] == 2
    assert result["function"] == "add"
    assert result["recent_change"] is False
    assert result["score"] > 0

# ==============================================================================
# Requirement 12: Related test discovery
# ==============================================================================
def test_related_test_discovery(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/service.py", line 5, in process_order\n'
        '    discount = compute_discount(total, rate)\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    related = result["related_tests"]
    assert len(related) > 0
    assert any("test_service.py" in r["file"] for r in related)
    assert any("test_process_order" in (r.get("function") or "") for r in related)

# ==============================================================================
# Requirement 13: Candidate ranking (innermost vs recently changed caller)
# ==============================================================================
def test_candidate_ranking_recent_change_prioritizes_caller(sample_workspace: Path):
    """
    Demonstrates that if an immediate caller frame was recently modified in git,
    its ranking score correctly surpasses an untouched innermost helper frame.
    """
    repo = git.Repo(sample_workspace)
    service_path = sample_workspace / "app" / "service.py"
    service_lines = service_path.read_text().splitlines()
    service_lines[4] = "            discount = compute_discount(total, -1.0)  # Modified with bug"
    service_path.write_text("\n".join(service_lines))

    repo.git.add(all=True)
    repo.index.commit("Refactor order service discount calculation")

    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/service.py", line 5, in process_order\n'
        '    discount = compute_discount(total, -1.0)\n'
        '  File "app/utils.py", line 3, in compute_discount\n'
        '    raise ValueError("Invalid rate")\n'
        'ValueError: Invalid rate\n'
    )
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    candidates = result["candidates"]
    assert len(candidates) == 2

    # The caller app/service.py was recently changed, so it should rank #1!
    top_candidate = candidates[0]
    second_candidate = candidates[1]

    assert top_candidate["file"] == "app/service.py"
    assert top_candidate["recent_change"] is True
    assert top_candidate["score"] > second_candidate["score"]
    assert any("modified in recent commit" in r for r in top_candidate["reasons"])

# ==============================================================================
# Requirement 14: Empty/malformed stack trace
# ==============================================================================
def test_empty_and_malformed_stack_trace(sample_workspace: Path):
    empty_result = localize_fault("", repo_path=str(sample_workspace))
    assert empty_result["file"] is None
    assert empty_result["candidates"] == []
    assert empty_result["score"] == 0.0

    malformed_tb = "Random error log line without stack trace frames\nConnection reset by peer"
    malformed_result = localize_fault(malformed_tb, repo_path=str(sample_workspace))
    assert malformed_result["file"] is None
    assert malformed_result["candidates"] == []

# ==============================================================================
# Requirement 15: Source parsing failure
# ==============================================================================
def test_source_parsing_failure(sample_workspace: Path):
    broken_file = sample_workspace / "app" / "broken.py"
    broken_file.write_text("def syntax_error_here(:\n    pass\n")

    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/broken.py", line 1, in syntax_error_here\n'
        '    def syntax_error_here(:\n'
        'SyntaxError: invalid syntax\n'
    )
    # Must not crash, should record AST error and retain stack-frame evidence
    result = localize_fault_core(tb, repo_path=str(sample_workspace))
    assert result["file"] == "app/broken.py"
    assert len(result["candidates"]) == 1
    assert result["ast"]["function_boundaries"] is None
    assert any("AST parsing skipped or failed" in ev for ev in result["evidence"])

# ==============================================================================
# Requirement 16: Repository traversal protection
# ==============================================================================
def test_repository_traversal_protection(sample_workspace: Path):
    repo_access = RepositoryAccess(str(sample_workspace))

    with pytest.raises(PermissionError):
        repo_access.get_safe_path("../../../etc/passwd")

    with pytest.raises(PermissionError):
        repo_access.get_safe_path("C:/Windows/System32/drivers/etc/hosts")

    # Stack trace referencing traversal paths outside repository
    tb = (
        'Traceback (most recent call last):\n'
        '  File "../../../outside/secret.py", line 42, in leak\n'
        '    return secret\n'
    )
    result = localize_fault(tb, repo_path=str(sample_workspace))
    # Must not resolve or read outside repo
    assert result["score"] == 0.0
    assert any("outside repository workspace" in ev for ev in result["evidence"])

# ==============================================================================
# Requirement 17: Backwards-compatible top-level fault fields
# ==============================================================================
def test_backwards_compatible_top_level_fields(sample_workspace: Path):
    tb = (
        'Traceback (most recent call last):\n'
        '  File "app/service.py", line 6, in process_order\n'
        '    discount = compute_discount(total, rate)\n'
    )
    # 1. Check localize_fault
    fault = localize_fault(tb, repo_path=str(sample_workspace))
    for expected_key in ["file", "line", "function", "class", "stack_frame", "recent_change", "evidence", "candidates", "fault_candidates", "score", "reasons"]:
        assert expected_key in fault, f"Missing key in localize_fault: {expected_key}"

    # 2. Check ContextBuilder
    incident = {
        "id": "inc_test_p3",
        "exception_type": "RuntimeError",
        "exception_message": "Order failed",
        "stack_trace": tb,
        "fingerprint": "fp_test_p3"
    }
    context = build_patch_context(incident, repo_path=str(sample_workspace))
    assert "fault_location" in context
    assert "fault_candidates" in context
    fl = context["fault_location"]
    for expected_key in ["file", "line", "function", "class", "stack_frame", "recent_change", "evidence", "candidates"]:
        assert expected_key in fl, f"Missing key in context fault_location: {expected_key}"
    assert fl["file"] == "app/service.py"
    assert fl["line"] == 6

import os
import sys
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

from sandbox_manager.models import SandboxResult, SandboxStatus
from sandbox_manager.runner import SandboxConfig, SandboxRunner
from sandbox_manager.parser import TestOutputParser
from sandbox_manager.resolvers import TestCommandResolver, PythonAdapter
from github_client.repo_manager import RepositoryManager


@pytest.fixture
def generic_repo(tmp_path: Path) -> Path:
    """
    Creates a generic minimal project with a failing bug and tests:
    - calc.py: subtraction instead of addition (buggy)
    - test_calc.py: asserts add behavior
    - requirements.txt: declares dependencies
    """
    repo_dir = tmp_path / "calc_project"
    repo_dir.mkdir()

    src_file = repo_dir / "calc.py"
    src_file.write_text(
        "def compute(a: int, b: int) -> int:\n"
        "    # Buggy subtraction\n"
        "    return a - b\n",
        encoding="utf-8"
    )

    test_file = repo_dir / "test_calc.py"
    test_file.write_text(
        "from calc import compute\n"
        "def test_compute():\n"
        "    assert compute(2, 3) == 5\n",
        encoding="utf-8"
    )

    req_file = repo_dir / "requirements.txt"
    req_file.write_text("pytest\n", encoding="utf-8")

    return repo_dir


VALID_PATCH = (
    "diff --git a/calc.py b/calc.py\n"
    "--- a/calc.py\n"
    "+++ b/calc.py\n"
    "@@ -1,3 +1,3 @@\n"
    " def compute(a: int, b: int) -> int:\n"
    "-    # Buggy subtraction\n"
    "-    return a - b\n"
    "+    # Correct addition\n"
    "+    return a + b\n"
)

CORRUPT_PATCH = (
    "diff --git a/calc.py b/calc.py\n"
    "--- a/calc.py\n"
    "+++ b/calc.py\n"
    "@@ -999,3 +999,3 @@\n"
    "-non_existent_code_line_404\n"
    "+some_other_code\n"
)


# =====================================================================
# 1. Generic Fixture: Original FAIL -> Patched PASS
# =====================================================================

def test_generic_fixture_original_fail_and_patched_pass(generic_repo: Path):
    """
    Validates:
    - Original unpatched behavior fails the test suite.
    - Applying a valid candidate patch causes tests to PASS.
    - Durations, exit codes, and output are captured cleanly.
    """
    config = SandboxConfig(
        timeout=30,
        test_command="pytest",
        environment_allowlist=["PYTHONPATH"]
    )
    runner = SandboxRunner(config)

    # 1. Run unpatched original code (empty patch)
    res_orig = runner.run(
        job_id="test_orig_fail",
        repo_url=str(generic_repo),
        commit_hash="HEAD",
        patch_diff="",
        candidate_id="cand_orig"
    )

    assert res_orig.status == SandboxStatus.TEST_FAILURE
    assert res_orig.exit_code != 0
    assert res_orig.tests_failed is not None
    assert res_orig.tests_failed >= 1
    assert "assert -1 == 5" in res_orig.stdout or "assert compute(2, 3) == 5" in res_orig.stdout
    assert res_orig.duration_seconds > 0

    # 2. Run with valid candidate patch
    res_patched = runner.run(
        job_id="test_patched_pass",
        repo_url=str(generic_repo),
        commit_hash="HEAD",
        patch_diff=VALID_PATCH,
        candidate_id="cand_valid"
    )

    assert res_patched.status == SandboxStatus.PASSED
    assert res_patched.exit_code == 0
    assert res_patched.tests_passed is not None
    assert res_patched.tests_passed >= 1
    assert res_patched.tests_failed == 0
    assert res_patched.duration_seconds > 0
    assert res_patched["exit_code"] == 0
    assert res_patched.get("status") == "PASSED"


# =====================================================================
# 2. Patch Application Failure (PATCH_APPLY_ERROR)
# =====================================================================

def test_corrupt_patch_returns_patch_apply_error(generic_repo: Path):
    """
    Validates that a patch that fails to apply:
    - Returns structured PATCH_APPLY_ERROR
    - Does NOT execute tests
    - Does NOT misclassify as TEST_FAILURE
    """
    config = SandboxConfig(timeout=30, test_command="pytest")
    runner = SandboxRunner(config)

    res = runner.run(
        job_id="test_corrupt_patch",
        repo_url=str(generic_repo),
        commit_hash="HEAD",
        patch_diff=CORRUPT_PATCH,
        candidate_id="cand_corrupt"
    )

    assert res.status == SandboxStatus.PATCH_APPLY_ERROR
    assert res.error_type == "PATCH_APPLY_ERROR"
    assert res.exit_code != 0
    assert "PATCH APPLY ERROR" in res.stderr
    # Tests should not have executed
    assert "test session starts" not in res.stdout


# =====================================================================
# 3. Dependency Preparation Failure (DEPENDENCY_ERROR)
# =====================================================================

def test_dependency_failure_returns_dependency_error(tmp_path: Path):
    """
    Validates that a project with unresolvable dependencies returns DEPENDENCY_ERROR.
    """
    repo_dir = tmp_path / "dep_fail_project"
    repo_dir.mkdir()

    # Requirements declaring an impossible package version
    req_file = repo_dir / "requirements.txt"
    req_file.write_text("overmend_non_existent_fake_package_xyz == 999.999.999\n", encoding="utf-8")

    src_file = repo_dir / "mod.py"
    src_file.write_text("x = 1\n", encoding="utf-8")

    test_file = repo_dir / "test_mod.py"
    test_file.write_text("def test_ok(): assert True\n", encoding="utf-8")

    config = SandboxConfig(timeout=30, test_command="pytest")
    runner = SandboxRunner(config)

    # Ensure pip install is not skipped
    with patch.dict(os.environ, {"SKIP_PIP_INSTALL": "false"}):
        res = runner.run(
            job_id="test_dep_fail",
            repo_url=str(repo_dir),
            commit_hash="HEAD",
            patch_diff="",
            candidate_id="cand_dep_fail"
        )

    assert res.status == SandboxStatus.DEPENDENCY_ERROR
    assert res.error_type == "DEPENDENCY_ERROR"
    assert res.exit_code != 0
    assert "DEPENDENCY ERROR" in res.stderr
    assert "test session starts" not in res.stdout


# =====================================================================
# 4. Timeout Handling (TIMEOUT)
# =====================================================================

def test_execution_timeout_returns_timeout_status(tmp_path: Path):
    """
    Validates that a long-running/hanging test is terminated and returns TIMEOUT.
    """
    repo_dir = tmp_path / "hang_project"
    repo_dir.mkdir()

    test_file = repo_dir / "test_hang.py"
    test_file.write_text(
        "import time\n"
        "def test_infinite_loop():\n"
        "    time.sleep(15)\n",
        encoding="utf-8"
    )

    # Set very short timeout of 2 seconds
    config = SandboxConfig(timeout=2, test_command="pytest")
    runner = SandboxRunner(config)

    res = runner.run(
        job_id="test_timeout_run",
        repo_url=str(repo_dir),
        commit_hash="HEAD",
        patch_diff="",
        candidate_id="cand_timeout"
    )

    assert res.status == SandboxStatus.TIMEOUT
    assert res.error_type == "TIMEOUT"
    assert res.exit_code == -1
    assert "TIMEOUT ERROR" in res.stderr
    assert "timed out after 2s" in res.error_message


# =====================================================================
# 5. Multiple Candidates & Workspace Isolation
# =====================================================================

def test_multiple_candidates_isolation(generic_repo: Path):
    """
    Validates evaluation of multiple candidates:
    Candidate A -> TEST_FAILURE
    Candidate B -> PASSED
    Candidate C -> TEST_FAILURE
    Candidate B passes cleanly without workspace contamination.
    """
    config = SandboxConfig(timeout=30, test_command="pytest")
    runner = SandboxRunner(config)

    # Candidate A: Produces bad logic
    patch_a = (
        "diff --git a/calc.py b/calc.py\n"
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def compute(a: int, b: int) -> int:\n"
        "     # Buggy subtraction\n"
        "-    return a - b\n"
        "+    return 9999\n"
    )

    # Candidate B: Produces correct fix
    patch_b = VALID_PATCH

    # Candidate C: Syntax error
    patch_c = (
        "diff --git a/calc.py b/calc.py\n"
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def compute(a: int, b: int) -> int:\n"
        "     # Buggy subtraction\n"
        "-    return a - b\n"
        "+    return a +++ b --\n"
    )

    # Candidate A -> TEST_FAILURE
    res_a = runner.run("job_cand_a", str(generic_repo), "HEAD", patch_a, candidate_id="cand_A")
    assert res_a.status == SandboxStatus.TEST_FAILURE

    # Candidate B -> PASSED
    res_b = runner.run("job_cand_b", str(generic_repo), "HEAD", patch_b, candidate_id="cand_B")
    assert res_b.status == SandboxStatus.PASSED
    assert res_b.exit_code == 0

    # Candidate C -> TEST_FAILURE
    res_c = runner.run("job_cand_c", str(generic_repo), "HEAD", patch_c, candidate_id="cand_C")
    assert res_c.status == SandboxStatus.TEST_FAILURE

    # Verify original repository was NOT contaminated
    orig_content = (generic_repo / "calc.py").read_text(encoding="utf-8")
    assert "return a - b" in orig_content
    assert "9999" not in orig_content
    assert "return a + b" not in orig_content


# =====================================================================
# 6. Workspace Cleanup Guarantee
# =====================================================================

def test_workspace_cleanup_guarantee(generic_repo: Path):
    """
    Validates that temporary workspaces created during execution are deleted
    under all circumstances (success, failure, patch error).
    """
    import uuid
    config = SandboxConfig(timeout=30, test_command="pytest")
    runner = SandboxRunner(config)

    temp_root = tempfile.gettempdir()
    run_id = uuid.uuid4().hex[:6]
    job_1 = f"clean1_{run_id}"
    job_2 = f"clean2_{run_id}"
    job_3 = f"clean3_{run_id}"

    # Track directory creation before and after
    def count_sandbox_dirs(job_name: str):
        return [d for d in os.listdir(temp_root) if d.startswith(f"sandbox_workspace_{job_name}_")]

    assert len(count_sandbox_dirs(job_1)) == 0

    # 1. Success
    res_1 = runner.run(job_1, str(generic_repo), "HEAD", VALID_PATCH)
    assert res_1.status == SandboxStatus.PASSED
    assert len(count_sandbox_dirs(job_1)) == 0

    # 2. Patch error
    res_2 = runner.run(job_2, str(generic_repo), "HEAD", CORRUPT_PATCH)
    assert res_2.status == SandboxStatus.PATCH_APPLY_ERROR
    assert len(count_sandbox_dirs(job_2)) == 0

    # 3. Test failure
    res_3 = runner.run(job_3, str(generic_repo), "HEAD", "")
    assert res_3.status == SandboxStatus.TEST_FAILURE
    assert len(count_sandbox_dirs(job_3)) == 0


# =====================================================================
# 7. Network Security & Secret Scrubbing
# =====================================================================

def test_secret_scrubbing_does_not_leak_to_sandbox(tmp_path: Path):
    """
    Validates that parent host secrets (OpenAI, Anthropic, DB URLs, Private Keys)
    are strictly scrubbed from the sandbox process environment.
    """
    repo_dir = tmp_path / "security_project"
    repo_dir.mkdir()

    # A test that inspects its own environment for secrets
    test_file = repo_dir / "test_env.py"
    test_file.write_text(
        "import os\n"
        "def test_secrets_absent():\n"
        "    forbidden = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DATABASE_URL', 'GITHUB_PRIVATE_KEY']\n"
        "    for k in forbidden:\n"
        "        assert k not in os.environ, f'Leaked secret {k} into sandbox environment!'\n",
        encoding="utf-8"
    )

    sensitive_env = {
        "OPENAI_API_KEY": "sk-secret-overmend-test-key",
        "ANTHROPIC_API_KEY": "ant-secret-overmend-test-key",
        "DATABASE_URL": "postgresql://postgres:secretpassword@localhost:5432/overmend",
        "GITHUB_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...",
    }

    config = SandboxConfig(timeout=30, test_command="pytest")
    runner = SandboxRunner(config)

    with patch.dict(os.environ, sensitive_env):
        res = runner.run("job_sec_test", str(repo_dir), "HEAD", "", candidate_id="cand_sec")

    assert res.status == SandboxStatus.PASSED
    assert res.exit_code == 0


# =====================================================================
# 8. Test Command Resolution & Output Parsing
# =====================================================================

def test_command_resolver_and_output_parser():
    """
    Validates:
    - TestCommandResolver detects python projects and preserves explicit configs.
    - TestOutputParser parses pytest and unittest outputs without inventing counts.
    """
    resolver = TestCommandResolver()
    cmd, adapter = resolver.resolve(".", explicit_command="pytest tests/custom_test.py")
    assert cmd == "pytest tests/custom_test.py"

    # Pytest output parsing
    pytest_stdout = (
        "============================= test session starts =============================\n"
        "collected 5 items\n\n"
        "test_one.py ..F.s [100%]\n\n"
        "========================= 1 failed, 3 passed, 1 skipped in 0.42s =========================\n"
    )
    p_res = TestOutputParser.parse("pytest", pytest_stdout, "")
    assert p_res["tests_total"] == 5
    assert p_res["tests_passed"] == 3
    assert p_res["tests_failed"] == 1
    assert p_res["tests_skipped"] == 1

    # Unittest output parsing
    unittest_stdout = (
        "Ran 4 tests in 0.003s\n\n"
        "FAILED (failures=1, errors=1)\n"
    )
    u_res = TestOutputParser.parse("python -m unittest", unittest_stdout, "")
    assert u_res["tests_total"] == 4
    assert u_res["tests_failed"] == 2
    assert u_res["tests_passed"] == 2

    # Unrecognized output does NOT invent numbers
    unrec_res = TestOutputParser.parse("unknown_runner", "Hello World!", "")
    assert unrec_res["tests_total"] is None
    assert unrec_res["tests_passed"] is None


# =====================================================================
# 9. Real Repository Validation (jyotsnag-l/recovery-test-repo)
# =====================================================================

def test_real_repo_phase5_validation():
    """
    Validates Phase 5 against the real GitHub repository:
    jyotsnag-l/recovery-test-repo at faulty commit a9ca1cde1290cffc76efaea7d4eba107765ebf43.

    Proves:
    1. The sandbox obtains the exact repository version via RepositoryManager.
    2. Prepares its declared environment.
    3. Runs its tests.
    4. Observes the known failing behavior (TEST_FAILURE).
    5. Leaves no altered branch or workspace behind.
    """
    repo = "jyotsnag-l/recovery-test-repo"
    target_sha = "a9ca1cde1290cffc76efaea7d4eba107765ebf43"

    # 1. Acquire workspace at exact faulty commit
    repo_mgr = RepositoryManager()
    workspace = repo_mgr.acquire(
        repository=repo,
        commit_sha=target_sha,
        incident_id="phase5_real_val"
    )

    try:
        assert os.path.exists(workspace.path)
        assert workspace.commit_sha == target_sha

        # 2. Run Sandbox on the faulty commit without any patch
        config = SandboxConfig(
            timeout=60,
            test_command="pytest",
            environment_allowlist=["PYTHONPATH"]
        )
        runner = SandboxRunner(config)

        res = runner.run(
            job_id="job_real_p5",
            repo_url=workspace.path,
            commit_hash=target_sha,
            patch_diff="",
            candidate_id="cand_real_baseline"
        )

        # 3. Observe the known failing behavior
        assert res.status == SandboxStatus.TEST_FAILURE
        assert res.exit_code != 0
        assert res.duration_seconds > 0
        assert res.tests_failed is not None
        assert res.tests_failed >= 1
        assert "FAILURES" in res.stdout or "FAILED" in res.stdout

    finally:
        # 4. Clean up original acquired workspace
        workspace.cleanup()
        assert not os.path.exists(workspace.path)

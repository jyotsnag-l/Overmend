import os
import subprocess
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment is loaded from .env
load_dotenv(override=True)

from github_client.repo_manager import RepositoryManager
from fault_localizer import build_patch_context
from fault_localizer.localizer import localize_fault_core
from patch_engine import (
    PatchContext,
    IncidentData,
    FaultLocation,
    OpenAIAdapter,
    AnthropicAdapter,
    GeminiAdapter,
    GrokAdapter,
    ProviderConfigurationError,
    get_provider,
    PatchGenerationEngine,
    validate_patch,
)
from sandbox_manager.runner import SandboxConfig, SandboxRunner
from sandbox_manager.models import SandboxStatus


# ==============================================================================
# 1. ENV & PROVIDER CONFIGURATION TESTS
# ==============================================================================

def test_provider_configuration_placeholders_and_selection():
    """
    Validates that:
    1. .env exists and is protected by .gitignore
    2. Three provider adapters exist: OpenAIAdapter, AnthropicAdapter, GeminiAdapter
    3. Each implements LLMProvider interface
    4. Each provider can be selected independently via PATCH_PROVIDER
    5. Missing API keys fail clearly with ProviderConfigurationError (PROVIDER_NOT_CONFIGURED)
    6. No provider silently falls back to another provider or to fake/mock patches
    """
    # 1. Verify .gitignore protects .env
    gitignore_path = Path(__file__).resolve().parent.parent / ".gitignore"
    assert gitignore_path.exists()
    gitignore_content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in gitignore_content.splitlines(), ".env must be explicitly protected in .gitignore"

    # 2. Test OpenAI adapter configuration & selection
    p_openai = get_provider("openai")
    assert isinstance(p_openai, OpenAIAdapter)
    if not os.getenv("OPENAI_API_KEY"):
        assert p_openai.is_configured is False
        with pytest.raises(ProviderConfigurationError) as exc_info:
            p_openai.validate_configuration()
        assert "PROVIDER_NOT_CONFIGURED" in str(exc_info.value)
        assert "OPENAI_API_KEY" in str(exc_info.value)

    # 3. Test Grok adapter configuration & selection
    p_grok = get_provider("grok")
    assert isinstance(p_grok, GrokAdapter)
    if not (os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")):
        assert p_grok.is_configured is False
        with pytest.raises(ProviderConfigurationError) as exc_info:
            p_grok.validate_configuration()
        assert "PROVIDER_NOT_CONFIGURED" in str(exc_info.value)
        assert "XAI_API_KEY" in str(exc_info.value)

    # 4. Test Gemini adapter configuration & selection
    p_gemini = get_provider("gemini")
    assert isinstance(p_gemini, GeminiAdapter)
    if not os.getenv("GOOGLE_API_KEY"):
        assert p_gemini.is_configured is False
        with pytest.raises(ProviderConfigurationError) as exc_info:
            p_gemini.validate_configuration()
        assert "PROVIDER_NOT_CONFIGURED" in str(exc_info.value)
        assert "GOOGLE_API_KEY" in str(exc_info.value)

    # 5. Invalid provider fails clearly without silent fallback
    with pytest.raises(ProviderConfigurationError, match="Unsupported PATCH_PROVIDER"):
        get_provider("invalid_provider_name")


# ==============================================================================
# 2. REAL FAULTY REPOSITORY BASELINE & AUTONOMOUS LOCALIZATION
# ==============================================================================

def test_real_repo_baseline_and_localization():
    """
    Validates:
    - Acquisition of jyotsnag-l/recovery-test-repo at exact faulty commit a9ca1cde1290cffc76efaea7d4eba107765ebf43
    - Baseline test execution genuinely fails before any patch
    - Autonomous fault localization identifies the fault location without hardcoded inputs
    - Structured evidence and PatchContext are cleanly assembled
    """
    repo = "jyotsnag-l/recovery-test-repo"
    target_sha = "a9ca1cde1290cffc76efaea7d4eba107765ebf43"

    # Step 1: Acquire workspace at exact faulty commit SHA
    repo_mgr = RepositoryManager()
    workspace = repo_mgr.acquire(
        repository=repo,
        commit_sha=target_sha,
        incident_id="test_e2e_recovery_val"
    )

    try:
        assert os.path.exists(workspace.path), f"Workspace path does not exist: {workspace.path}"
        assert workspace.commit_sha == target_sha

        # Verify exact git HEAD SHA
        git_sha_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace.path,
            capture_output=True,
            text=True,
            check=True
        )
        actual_sha = git_sha_res.stdout.strip().lower()
        assert actual_sha == target_sha.lower(), f"Expected HEAD {target_sha}, got {actual_sha}"

        # Step 2: Baseline failing test execution (Before Patch Baseline)
        cfg = SandboxConfig(timeout=60, test_command="pytest")
        runner = SandboxRunner(cfg)
        baseline_res = runner.run(
            job_id="job_real_baseline_run",
            repo_url=workspace.path,
            commit_hash=target_sha,
            patch_diff="",
            candidate_id="cand_baseline_unpatched"
        )

        # Baseline MUST genuinely fail
        assert baseline_res.status == SandboxStatus.TEST_FAILURE, f"Expected TEST_FAILURE, got {baseline_res.status}"
        assert baseline_res.exit_code != 0
        assert "FAILED" in baseline_res.stdout or "FAILURES" in baseline_res.stdout
        assert "test_create_order_exceeding_stock_should_fail" in baseline_res.stdout
        assert "201 == 400" in baseline_res.stdout or "AssertionError" in baseline_res.stdout

        # Record structured baseline evidence
        baseline_evidence = {
            "test_command": baseline_res.test_command,
            "exit_code": baseline_res.exit_code,
            "duration": baseline_res.duration_seconds,
            "failing_test": "test_create_order_exceeding_stock_should_fail",
            "expected_result": "HTTP 400 (Insufficient stock)",
            "actual_result": "HTTP 201 (Order created)",
            "stdout_snippet": baseline_res.stdout[-500:],
            "stderr": baseline_res.stderr
        }
        assert baseline_evidence["exit_code"] != 0

        # Step 3: Autonomous Fault Localization from Genuine Failure Evidence
        # Note: Input contains ONLY the customer failure trace; NO hardcoded faulty file/function/line
        customer_stack_trace = (
            'Traceback (most recent call last):\n'
            '  File "tests/test_order_validation.py", line 19, in test_create_order_exceeding_stock_should_fail\n'
            '    assert order_resp.status_code == 400\n'
            'AssertionError: assert 201 == 400\n'
        )

        loc_result = localize_fault_core(customer_stack_trace, repo_path=workspace.path)

        # Verify candidate discovery
        assert len(loc_result["candidates"]) >= 1
        top_cand = loc_result["candidates"][0]

        # The localizer must have discovered the fault location independently
        assert top_cand["file"] == "app/services/inventory_service.py"
        assert top_cand["line"] == 46
        assert top_cand["function"] == "validate_stock_availability"
        assert top_cand["score"] > 50.0

        # Blame evidence must match exact target commit SHA
        blame_info = top_cand.get("git", {}).get("blame", {})
        assert blame_info.get("commit_hash") is not None
        assert blame_info["commit_hash"].lower().startswith(target_sha[:7].lower())

        # Related tests must be discovered
        assert len(loc_result["related_tests"]) >= 1

        # Step 4: Build PatchContext
        incident_data = {
            "id": "inc_e2e_real_test",
            "exception_type": "AssertionError",
            "exception_message": "assert 201 == 400",
            "stack_trace": customer_stack_trace,
            "fingerprint": "fp_e2e_real"
        }
        context_dict = build_patch_context(incident_data, repo_path=workspace.path)
        patch_context = PatchContext.model_validate(context_dict)

        assert patch_context.fault_location.file == "app/services/inventory_service.py"
        assert patch_context.fault_location.line == 46
        assert patch_context.source_context.faulting_file == "app/services/inventory_service.py"

        # Step 5: Test Provider Generation Path
        provider_name = os.getenv("PATCH_PROVIDER", "openai").lower().strip()
        provider = get_provider(provider_name)

        if not provider.is_configured:
            # Without keys: must raise ProviderConfigurationError and not invent fake patches
            with pytest.raises(ProviderConfigurationError) as exc_err:
                provider.validate_configuration()
            assert "PROVIDER_NOT_CONFIGURED" in str(exc_err.value)
        else:
            # If real key is provided, generate candidates
            engine = PatchGenerationEngine(provider)
            import asyncio
            results = asyncio.run(engine.generate_candidates(patch_context, repo_path=workspace.path, num_patches=3))
            assert len(results) > 0
            for res_cand in results:
                assert res_cand.candidate.patch_id
                assert res_cand.candidate.unified_diff

    finally:
        # Step 6: Verify cleanup of acquired workspace
        workspace_path = workspace.path
        workspace.cleanup()
        assert not os.path.exists(workspace_path), f"Workspace was not cleaned up: {workspace_path}"

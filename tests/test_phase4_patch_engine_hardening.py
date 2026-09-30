import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from patch_engine import (
    PatchContext, IncidentData, FaultLocation, SourceContext, FunctionSignature,
    SurroundingLines, CallingFunction, RelatedTest, GitHistoryItem,
    PatchGenerationEngine, OpenAIAdapter, AnthropicAdapter, GeminiAdapter, GrokAdapter,
    ProviderConfigurationError, get_provider, validate_patch
)
from patch_engine.schemas import CandidatePatchLLMOutput, PatchValidationReport
from patch_engine.engine import normalize_diff

@pytest.fixture
def generic_repo(tmp_path: Path) -> Path:
    """Creates a temporary workspace with arbitrary Python source files."""
    pkg_dir = tmp_path / "src" / "app_logic"
    pkg_dir.mkdir(parents=True)
    
    # Arbitrary file 1: processor.py
    proc_file = pkg_dir / "processor.py"
    proc_file.write_text(
        "class DataProcessor:\n"
        "    def process_records(self, items):\n"
        "        count = len(items)\n"
        "        if count == 0:\n"
        "            raise ValueError('Empty items')\n"
        "        return [item * 2 for item in items]\n"
    )

    # Arbitrary file 2: config.py
    cfg_file = tmp_path / "config.py"
    cfg_file.write_text(
        "SECRET_KEY = 'insecure_default'\n"
        "DEBUG = True\n"
    )

    return tmp_path

@pytest.fixture
def generic_context():
    return PatchContext(
        incident=IncidentData(
            id="inc_generic_999",
            exception_type="ValueError",
            exception_message="Empty items",
            stack_trace='File "src/app_logic/processor.py", line 5, in process_records\n    raise ValueError("Empty items")',
            fingerprint="fp_generic_999"
        ),
        fault_location=FaultLocation(
            file="src/app_logic/processor.py",
            line=5,
            function="process_records",
            class_name="DataProcessor",
            evidence=["Empty items raised on empty list"]
        ),
        source_context=SourceContext(
            faulting_file="src/app_logic/processor.py",
            faulting_function=FunctionSignature(
                name="process_records",
                start_line=2,
                end_line=6,
                code="    def process_records(self, items):\n        count = len(items)\n        if count == 0:\n            raise ValueError('Empty items')\n        return [item * 2 for item in items]"
            ),
            surrounding_lines=SurroundingLines(
                start_line=1,
                end_line=6,
                code="class DataProcessor:\n    def process_records(self, items):\n        count = len(items)\n        if count == 0:\n            raise ValueError('Empty items')\n        return [item * 2 for item in items]"
            )
        ),
        imports=["import os"],
        related_tests=[RelatedTest(file="tests/test_processor.py", function="test_process_records")],
        git_history=[GitHistoryItem(type="commit", commit_hash="1a2b3c4d", author="Alice", summary="Initial processor")]
    )

# ==============================================================================
# PROVIDER TESTS
# ==============================================================================

def test_real_provider_configuration_path():
    # OpenAI provider initialization with real key
    adapter = OpenAIAdapter(api_key="sk-real-format-key-1234567890abcdef")
    assert adapter.api_key == "sk-real-format-key-1234567890abcdef"
    assert adapter.client is not None
    assert adapter.is_configured is True

    # Anthropic provider initialization with real key
    anthropic_adapter = AnthropicAdapter(api_key="sk-ant-real-format-key-1234567890abcdef")
    assert anthropic_adapter.api_key == "sk-ant-real-format-key-1234567890abcdef"
    assert anthropic_adapter.client is not None
    assert anthropic_adapter.is_configured is True

    # Gemini provider initialization with real key
    gemini_adapter = GeminiAdapter(api_key="AIzaSyDummyValidFormatKey1234567890")
    assert gemini_adapter.api_key == "AIzaSyDummyValidFormatKey1234567890"
    assert gemini_adapter.client is not None
    assert gemini_adapter.is_configured is True

def test_missing_openai_key_fails_clearly(generic_context, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter = OpenAIAdapter(api_key=None)
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_mock_openai_key_fails_clearly(generic_context):
    adapter = OpenAIAdapter(api_key="mock")
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_missing_anthropic_key_fails_clearly(generic_context, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    adapter = AnthropicAdapter(api_key=None)
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_mock_anthropic_key_fails_clearly(generic_context):
    adapter = AnthropicAdapter(api_key="mock")
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_missing_gemini_key_fails_clearly(generic_context, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    adapter = GeminiAdapter(api_key=None)
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_mock_gemini_key_fails_clearly(generic_context):
    adapter = GeminiAdapter(api_key="mock")
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_missing_grok_key_fails_clearly(generic_context, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    adapter = GrokAdapter(api_key=None)
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_mock_grok_key_fails_clearly(generic_context):
    adapter = GrokAdapter(api_key="mock")
    assert adapter.is_configured is False
    with pytest.raises(ProviderConfigurationError, match="No real patch-generation provider is configured"):
        import asyncio
        asyncio.run(adapter.generate_patches(generic_context))

def test_provider_factory_resolution():
    p_openai = get_provider("openai")
    assert isinstance(p_openai, OpenAIAdapter)

    p_grok = get_provider("grok")
    assert isinstance(p_grok, GrokAdapter)

    p_xai = get_provider("xai")
    assert isinstance(p_xai, GrokAdapter)

    p_gemini = get_provider("gemini")
    assert isinstance(p_gemini, GeminiAdapter)

    p_anthropic = get_provider("anthropic")
    assert isinstance(p_anthropic, AnthropicAdapter)

    with pytest.raises(ProviderConfigurationError, match="Unsupported PATCH_PROVIDER"):
        get_provider("unsupported_provider_xyz")


@pytest.mark.asyncio
async def test_malformed_llm_response_rejected(generic_context):
    adapter = OpenAIAdapter(api_key="sk-dummy-valid-format")
    # Mock client chat completions returning non-JSON garbage
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "I am an AI, here is your fix: just change line 5."
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    adapter.client = mock_client

    with pytest.raises(RuntimeError, match="OpenAI Patch Generation failed"):
        await adapter.generate_patches(generic_context)

@pytest.mark.asyncio
async def test_schema_mismatch_llm_response_rejected(generic_context):
    adapter = OpenAIAdapter(api_key="sk-dummy-valid-format")
    # Mock client returning JSON that doesn't match schema (e.g. missing patches key)
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"status": "ok", "result": []}'
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    adapter.client = mock_client

    with pytest.raises(RuntimeError, match="OpenAI Patch Generation failed"):
        await adapter.generate_patches(generic_context)

@pytest.mark.asyncio
async def test_candidate_count_empty_raises_runtime_error(generic_context, generic_repo):
    provider = MagicMock()
    provider.generate_patches = MagicMock(side_effect=lambda ctx, num_patches: [])
    
    # Provider returns empty list
    async def empty_patches(ctx, num_patches=3):
        return []
    provider.generate_patches = empty_patches

    engine = PatchGenerationEngine(provider)
    with pytest.raises(RuntimeError, match="LLM provider returned 0 candidate patches"):
        await engine.generate_candidates(generic_context, repo_path=str(generic_repo), num_patches=3)

@pytest.mark.asyncio
async def test_duplicate_candidates_detected_and_rejected(generic_context, generic_repo):
    """
    Verifies that identical candidate patches (even with whitespace or CRLF variations)
    are flagged as duplicates and rejected.
    """
    diff_text_1 = (
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\n"
        "--- a/src/app_logic/processor.py\n"
        "+++ b/src/app_logic/processor.py\n"
        "@@ -4,3 +4,3 @@\n"
        "         if count == 0:\n"
        "-            raise ValueError('Empty items')\n"
        "+            return []\n"
        "         return [item * 2 for item in items]\n"
    )
    # Duplicate with carriage returns and markdown fence
    diff_text_2 = (
        "```diff\r\n"
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\r\n"
        "--- a/src/app_logic/processor.py\r\n"
        "+++ b/src/app_logic/processor.py\r\n"
        "@@ -4,3 +4,3 @@\r\n"
        "         if count == 0:\r\n"
        "-            raise ValueError('Empty items')\r\n"
        "+            return []\r\n"
        "         return [item * 2 for item in items]\r\n"
        "```\r\n"
    )
    # Unique different patch
    diff_text_3 = (
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\n"
        "--- a/src/app_logic/processor.py\n"
        "+++ b/src/app_logic/processor.py\n"
        "@@ -4,3 +4,3 @@\n"
        "         if count == 0:\n"
        "-            raise ValueError('Empty items')\n"
        "+            return items\n"
        "         return [item * 2 for item in items]\n"
    )

    provider = MagicMock()
    async def mock_patches(ctx, num_patches=3):
        return [
            CandidatePatchLLMOutput(
                patch_id="patch_1",
                unified_diff=diff_text_1,
                explanation="Return empty list",
                affected_files=["src/app_logic/processor.py"],
                estimated_change_scope="SMALL",
                reasoning_summary="Handle empty gracefully"
            ),
            CandidatePatchLLMOutput(
                patch_id="patch_2",
                unified_diff=diff_text_2,
                explanation="Return empty list duplicate",
                affected_files=["src/app_logic/processor.py"],
                estimated_change_scope="SMALL",
                reasoning_summary="Duplicate of patch 1"
            ),
            CandidatePatchLLMOutput(
                patch_id="patch_3",
                unified_diff=diff_text_3,
                explanation="Return items unchanged",
                affected_files=["src/app_logic/processor.py"],
                estimated_change_scope="SMALL",
                reasoning_summary="Return input directly"
            )
        ]
    provider.generate_patches = mock_patches

    engine = PatchGenerationEngine(provider)
    results = await engine.generate_candidates(generic_context, repo_path=str(generic_repo), num_patches=3)

    assert len(results) == 3
    # Candidate 1: unique & valid
    assert results[0].candidate.patch_id == "patch_1"
    assert results[0].validation.is_valid is True

    # Candidate 2: duplicate of patch_1
    assert results[1].candidate.patch_id == "patch_2"
    assert results[1].validation.is_valid is False
    assert "Duplicate patch candidate skipped" in results[1].validation.error_reason
    assert "patch_1" in results[1].validation.error_reason
    assert results[1].candidate.is_duplicate is True
    assert results[1].candidate.duplicate_of == "patch_1"

    # Candidate 3: unique & valid
    assert results[2].candidate.patch_id == "patch_3"
    assert results[2].validation.is_valid is True

# ==============================================================================
# VALIDATOR SECURITY & HUNK MATCHING TESTS
# ==============================================================================

def test_valid_unified_diff_passes(generic_repo, generic_context):
    valid_diff = (
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\n"
        "--- a/src/app_logic/processor.py\n"
        "+++ b/src/app_logic/processor.py\n"
        "@@ -4,3 +4,3 @@\n"
        "         if count == 0:\n"
        "-            raise ValueError('Empty items')\n"
        "+            return []\n"
        "         return [item * 2 for item in items]\n"
    )
    report = validate_patch(valid_diff, str(generic_repo), generic_context)
    assert report.is_valid is True
    assert report.hunks_matched is True
    assert report.syntax_valid is True
    assert report.patch_size == 2
    assert report.affected_paths == ["src/app_logic/processor.py"]

def test_invalid_unified_diff_syntax_fails(generic_repo, generic_context):
    broken_diff = "Random text that is not a unified diff format\n+++ not a diff"
    report = validate_patch(broken_diff, str(generic_repo), generic_context)
    assert report.is_valid is False
    assert "Malformed unified diff" in report.error_reason or "no changes" in report.error_reason

def test_path_traversal_relative_rejected(generic_repo, generic_context):
    traversal_diff = (
        "diff --git a/../../etc/passwd b/../../etc/passwd\n"
        "--- a/../../etc/passwd\n"
        "+++ b/../../etc/passwd\n"
        "@@ -1,1 +1,1 @@\n"
        "-root:x:0:0:root:/root:/bin/bash\n"
        "+root:x:0:0:root:/root:/bin/sh\n"
    )
    report = validate_patch(traversal_diff, str(generic_repo), generic_context)
    assert report.is_valid is False
    assert "Path traversal detected" in report.error_reason

def test_prefix_boundary_path_attack_rejected(generic_repo, generic_context):
    """
    Ensures that a directory with the same prefix as repo_path (e.g. /repo_other)
    is rejected using Path.is_relative_to rather than string startswith.
    """
    # Create sibling directory
    sibling_dir = generic_repo.parent / f"{generic_repo.name}_sibling"
    sibling_dir.mkdir(exist_ok=True)
    outside_file = sibling_dir / "sibling.py"
    outside_file.write_text("a = 1\n")

    # Construct path pointing to sibling directory
    sibling_rel_path = f"../{generic_repo.name}_sibling/sibling.py"
    diff = (
        f"diff --git a/{sibling_rel_path} b/{sibling_rel_path}\n"
        f"--- a/{sibling_rel_path}\n"
        f"+++ b/{sibling_rel_path}\n"
        "@@ -1,1 +1,1 @@\n"
        "-a = 1\n"
        "+a = 2\n"
    )
    report = validate_patch(diff, str(generic_repo), generic_context)
    assert report.is_valid is False
    assert "Path traversal detected" in report.error_reason

def test_hunk_matching_actual_source_passes(generic_repo, generic_context):
    diff = (
        "diff --git a/config.py b/config.py\n"
        "--- a/config.py\n"
        "+++ b/config.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-SECRET_KEY = 'insecure_default'\n"
        "+SECRET_KEY = 'production_secret_key'\n"
        " DEBUG = True\n"
    )
    report = validate_patch(diff, str(generic_repo), generic_context)
    assert report.is_valid is True
    assert report.hunks_matched is True

def test_hunk_mismatch_fails_with_clear_error(generic_repo, generic_context):
    """
    Hunk context line does not match repository file.
    Expected: 'SECRET_KEY = 12345', Found: 'SECRET_KEY = \'insecure_default\''.
    """
    diff_wrong_context = (
        "diff --git a/config.py b/config.py\n"
        "--- a/config.py\n"
        "+++ b/config.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-SECRET_KEY = 12345\n"
        "+SECRET_KEY = 'production_secret_key'\n"
        " DEBUG = True\n"
    )
    report = validate_patch(diff_wrong_context, str(generic_repo), generic_context)
    assert report.is_valid is False
    assert report.hunks_matched is False
    assert "Patch hunk does not match repository source" in report.error_reason

def test_stale_patch_against_different_version_fails(generic_repo, generic_context):
    """
    Diff specifies lines starting at line 20, but the file only has 6 lines.
    """
    stale_diff = (
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\n"
        "--- a/src/app_logic/processor.py\n"
        "+++ b/src/app_logic/processor.py\n"
        "@@ -20,1 +20,1 @@\n"
        "-        some_stale_line = 1\n"
        "+        some_stale_line = 2\n"
    )
    report = validate_patch(stale_diff, str(generic_repo), generic_context)
    assert report.is_valid is False
    assert "Patch hunk does not match repository source" in report.error_reason

def test_python_syntax_breaking_patch_fails_ast(generic_repo, generic_context):
    """
    Hunk matches source line, but the replaced addition introduces a Python syntax error.
    """
    broken_syntax_diff = (
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\n"
        "--- a/src/app_logic/processor.py\n"
        "+++ b/src/app_logic/processor.py\n"
        "@@ -4,3 +4,3 @@\n"
        "         if count == 0:\n"
        "-            raise ValueError('Empty items')\n"
        "+            if broken_syntax_here(:\n"
        "         return [item * 2 for item in items]\n"
    )
    report = validate_patch(broken_syntax_diff, str(generic_repo), generic_context)
    assert report.is_valid is False
    assert report.hunks_matched is True
    assert report.syntax_valid is False
    assert "Syntax validation failed" in report.error_reason

def test_restricted_file_policy(generic_repo, generic_context):
    diff = (
        "diff --git a/config.py b/config.py\n"
        "--- a/config.py\n"
        "+++ b/config.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-SECRET_KEY = 'insecure_default'\n"
        "+SECRET_KEY = 'safe'\n"
        " DEBUG = True\n"
    )
    policy = {"restricted_files": ["config.py"]}
    report = validate_patch(diff, str(generic_repo), generic_context, policy=policy)
    assert report.is_valid is False
    assert "restricted file" in report.error_reason

def test_max_patch_size_policy(generic_repo, generic_context):
    diff = (
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\n"
        "--- a/src/app_logic/processor.py\n"
        "+++ b/src/app_logic/processor.py\n"
        "@@ -4,3 +4,5 @@\n"
        "         if count == 0:\n"
        "-            raise ValueError('Empty items')\n"
        "+            a = 1\n"
        "+            b = 2\n"
        "+            return []\n"
        "         return [item * 2 for item in items]\n"
    )
    policy = {"max_patch_size": 2}  # 1 deletion + 3 additions = 4 lines changed > 2
    report = validate_patch(diff, str(generic_repo), generic_context, policy=policy)
    assert report.is_valid is False
    assert "exceeds project policy limit" in report.error_reason

def test_max_files_changed_policy(generic_repo, generic_context):
    diff = (
        "diff --git a/config.py b/config.py\n"
        "--- a/config.py\n"
        "+++ b/config.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-SECRET_KEY = 'insecure_default'\n"
        "+SECRET_KEY = 'safe'\n"
        " DEBUG = True\n"
        "diff --git a/src/app_logic/processor.py b/src/app_logic/processor.py\n"
        "--- a/src/app_logic/processor.py\n"
        "+++ b/src/app_logic/processor.py\n"
        "@@ -4,3 +4,3 @@\n"
        "         if count == 0:\n"
        "-            raise ValueError('Empty items')\n"
        "+            return []\n"
        "         return [item * 2 for item in items]\n"
    )
    policy = {"max_files_changed": 1}  # 2 files changed > 1
    report = validate_patch(diff, str(generic_repo), generic_context, policy=policy)
    assert report.is_valid is False
    assert "exceeding limit of 1" in report.error_reason

def test_full_file_rewrite_protection_fails(generic_repo, generic_context):
    """
    Files with > 15 lines where a patch rewrites >= 90% of lines should be rejected.
    """
    large_file = generic_repo / "large_module.py"
    file_lines = [f"line_{i} = {i}" for i in range(1, 25)]
    large_file.write_text("\n".join(file_lines) + "\n")

    # Diff rewrites 22 out of 24 lines (> 90%)
    diff_lines = [
        "diff --git a/large_module.py b/large_module.py\n",
        "--- a/large_module.py\n",
        "+++ b/large_module.py\n",
        "@@ -1,22 +1,22 @@\n"
    ]
    for i in range(1, 23):
        diff_lines.append(f"-line_{i} = {i}\n")
        diff_lines.append(f"+line_{i} = {i * 10}\n")
    
    full_rewrite_diff = "".join(diff_lines)
    report = validate_patch(full_rewrite_diff, str(generic_repo), generic_context)
    assert report.is_valid is False
    assert "Full-file rewrite detected" in report.error_reason


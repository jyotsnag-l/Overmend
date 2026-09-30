import os
import core
import pytest
from unittest.mock import MagicMock, patch
from datetime import timezone

from patch_engine import (
    PatchContext, IncidentData, FaultLocation, SourceContext, FunctionSignature,
    SurroundingLines, CallingFunction, RelatedTest, GitHistoryItem,
    PatchGenerationEngine, OpenAIAdapter, AnthropicAdapter, validate_patch
)
from patch_engine.schemas import CandidatePatchLLMOutput, PatchValidationReport
from patch_engine.validator import apply_patch_to_text

# Deterministic fixtures for test context
@pytest.fixture
def sample_patch_context():
    incident = IncidentData(
        id="inc_test_123",
        exception_type="ZeroDivisionError",
        exception_message="division by zero",
        stack_trace="Traceback (most recent call last):\n  File \"app.py\", line 10, in div\n    return x / 0",
        fingerprint="fp_test_123"
    )
    fault_location = FaultLocation(
        file="app.py",
        line=10,
        function="div",
        evidence=["division by zero"]
    )
    source_context = SourceContext(
        faulting_file="app.py",
        faulting_function=FunctionSignature(
            name="div",
            start_line=8,
            end_line=11,
            code="def div(x):\n    return x / 0"
        ),
        surrounding_lines=SurroundingLines(
            start_line=5,
            end_line=15,
            code="def foo():\n    pass\n\ndef div(x):\n    return x / 0\n\ndef bar():\n    pass"
        )
    )
    return PatchContext(
        incident=incident,
        fault_location=fault_location,
        source_context=source_context,
        imports=["import os"],
        related_tests=[RelatedTest(file="tests/test_app.py", function="test_div")],
        git_history=[GitHistoryItem(type="blame", file="app.py", line=10, info={"author": "Dev", "commit": "abc"})]
    )

@pytest.fixture
def temp_repo_dir(tmp_path):
    """Creates a mock repo structure with files for syntax validation."""
    app_file = tmp_path / "app.py"
    app_file.write_text("def div(x):\n    return x / 0\n")
    return tmp_path

# ==================== Schema & Pydantic Tests ====================

def test_pydantic_schema_validation(sample_patch_context):
    assert sample_patch_context.incident.exception_type == "ZeroDivisionError"
    assert sample_patch_context.fault_location.file == "app.py"
    assert len(sample_patch_context.imports) == 1

# ==================== Validator Tests ====================

def test_apply_patch_to_text():
    orig_text = "line1\nline2\nline3\n"
    # Create mock PatchedFile from unidiff
    patched_file = MagicMock()
    patched_file.is_added_file = False
    patched_file.is_modified_file = True
    
    # Hunk replacing line 2
    hunk = MagicMock()
    hunk.source_start = 2
    hunk.source_length = 1
    hunk.added = 1
    hunk.removed = 1
    
    line_ctx = MagicMock()
    line_ctx.is_context = False
    line_ctx.is_added = True
    line_ctx.value = "line2_patched\n"
    
    hunk.__iter__.return_value = [line_ctx]
    patched_file.__iter__.return_value = [hunk]
    
    res = apply_patch_to_text(orig_text, patched_file)
    assert res == "line1\nline2_patched\nline3\n"

def test_validate_patch_syntax_success(temp_repo_dir, sample_patch_context):
    # Valid Python change diff
    valid_diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,2 +1,4 @@\n"
        " def div(x):\n"
        "-    return x / 0\n"
        "+    if x == 0:\n"
        "+        return 0\n"
        "+    return x / x\n"
    )
    
    report = validate_patch(valid_diff, str(temp_repo_dir), sample_patch_context)
    assert report.is_valid is True
    assert report.patch_size == 4  # 1 deletion + 3 additions
    assert report.files_changed == 1
    assert "app.py" in report.affected_paths

def test_validate_patch_syntax_failure(temp_repo_dir, sample_patch_context):
    # Python syntax error diff (syntax error in added line)
    invalid_diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def div(x):\n"
        "-    return x / 0\n"
        "+    return x syntax_error_here\n"
    )
    
    report = validate_patch(invalid_diff, str(temp_repo_dir), sample_patch_context)
    assert report.is_valid is False
    assert "Syntax validation failed" in report.error_reason

def test_validate_patch_path_traversal(temp_repo_dir, sample_patch_context):
    # Traversal diff modifying a file outside the repository
    traversal_diff = (
        "diff --git a/../outside.py b/../outside.py\n"
        "--- a/../outside.py\n"
        "+++ b/../outside.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-some content\n"
        "+other content\n"
    )
    
    report = validate_patch(traversal_diff, str(temp_repo_dir), sample_patch_context)
    assert report.is_valid is False
    assert "Path traversal detected" in report.error_reason

def test_validate_patch_restricted_files(temp_repo_dir, sample_patch_context):
    restricted_diff = (
        "diff --git a/secure.py b/secure.py\n"
        "--- a/secure.py\n"
        "+++ b/secure.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-admin = False\n"
        "+admin = True\n"
    )
    # Write file to match diff
    (temp_repo_dir / "secure.py").write_text("admin = False\n")
    
    policy = {"restricted_files": ["secure.py"]}
    report = validate_patch(restricted_diff, str(temp_repo_dir), sample_patch_context, policy=policy)
    assert report.is_valid is False
    assert "restricted file" in report.error_reason

def test_validate_patch_full_file_rewrite(temp_repo_dir, sample_patch_context):
    # File with 20 lines to test rewrite detection (> 15 lines threshold)
    large_file = temp_repo_dir / "large.py"
    large_file.write_text("\n".join([f"line {i}" for i in range(25)]) + "\n")
    
    rewrite_diff = (
        "diff --git a/large.py b/large.py\n"
        "--- a/large.py\n"
        "+++ b/large.py\n"
        "@@ -1,25 +1,2 @@\n"
        "-line 0\n-line 1\n-line 2\n-line 3\n-line 4\n-line 5\n"
        "-line 6\n-line 7\n-line 8\n-line 9\n-line 10\n-line 11\n"
        "-line 12\n-line 13\n-line 14\n-line 15\n-line 16\n-line 17\n"
        "-line 18\n-line 19\n-line 20\n-line 21\n-line 22\n-line 23\n-line 24\n"
        "+# Fully rewritten file\n"
        "+print('hello')\n"
    )
    
    report = validate_patch(rewrite_diff, str(temp_repo_dir), sample_patch_context)
    assert report.is_valid is False
    assert "Full-file rewrite detected" in report.error_reason

def test_validate_patch_excessive_size(temp_repo_dir, sample_patch_context):
    valid_diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,2 +1,5 @@\n"
        " def div(x):\n"
        "-    return x / 0\n"
        "+    x = 1\n"
        "+    y = 2\n"
        "+    z = 3\n"
        "+    return x / x\n"
    )
    
    policy = {"max_patch_size": 3}  # Diff has size 5 (1 del + 4 add), exceeds limit
    report = validate_patch(valid_diff, str(temp_repo_dir), sample_patch_context, policy=policy)
    assert report.is_valid is False
    assert "exceeds project policy limit" in report.error_reason

# ==================== Adapter & Mocks Tests ====================

@pytest.mark.asyncio
async def test_openai_adapter_missing_key_fails_clearly(sample_patch_context):
    adapter = OpenAIAdapter(api_key="mock")
    with pytest.raises(RuntimeError, match="No real patch-generation provider is configured"):
        await adapter.generate_patches(sample_patch_context, num_patches=2)

@pytest.mark.asyncio
async def test_anthropic_adapter_missing_key_fails_clearly(sample_patch_context):
    adapter = AnthropicAdapter(api_key="mock")
    with pytest.raises(RuntimeError, match="No real patch-generation provider is configured"):
        await adapter.generate_patches(sample_patch_context, num_patches=3)

@pytest.mark.asyncio
@patch("patch_engine.providers.OpenAIAdapter.generate_patches")
async def test_patch_engine_coordinator(mock_gen, sample_patch_context, temp_repo_dir):
    # Configure mock provider candidates
    mock_gen.return_value = [
        CandidatePatchLLMOutput(
            patch_id="patch_ok",
            unified_diff=(
                "diff --git a/app.py b/app.py\n"
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def div(x):\n"
                "-    return x / 0\n"
                "+    return x / 1\n"
            ),
            explanation="Fixes div by zero.",
            affected_files=["app.py"],
            estimated_change_scope="SMALL",
            reasoning_summary="Replaces 0 with 1."
        ),
        CandidatePatchLLMOutput(
            patch_id="patch_syntax_error",
            unified_diff=(
                "diff --git a/app.py b/app.py\n"
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def div(x):\n"
                "-    return x / 0\n"
                "+    return x syntax_error_here\n"
            ),
            explanation="Syntax error patch.",
            affected_files=["app.py"],
            estimated_change_scope="SMALL",
            reasoning_summary="Broken Python structure."
        )
    ]
    
    provider = OpenAIAdapter(api_key="sk-testkey")
    engine = PatchGenerationEngine(provider)
    
    results = await engine.generate_candidates(sample_patch_context, repo_path=str(temp_repo_dir))
    assert len(results) == 2
    
    # Check validation results
    assert results[0].candidate.patch_id == "patch_ok"
    assert results[0].validation.is_valid is True
    
    assert results[1].candidate.patch_id == "patch_syntax_error"
    assert results[1].validation.is_valid is False
    assert "Syntax validation failed" in results[1].validation.error_reason

# ==================== Pipeline Integration Tests ====================

@pytest.mark.asyncio
@patch("patch_engine.providers.OpenAIAdapter.generate_patches")
async def test_generate_and_store_patches_integration(mock_gen, temp_repo_dir):
    """
    Seeds organization, project, policy, and incident in the test database,
    invokes generate_and_store_patches with a mocked provider output,
    and verifies that candidates are saved to the DB.
    """
    mock_gen.return_value = [
        CandidatePatchLLMOutput(
            patch_id="patch_1",
            unified_diff=(
                "diff --git a/app.py b/app.py\n"
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def div(x):\n"
                "-    return x / 0\n"
                "+    return x / 1\n"
            ),
            explanation="Fix div by zero",
            affected_files=["app.py"],
            estimated_change_scope="SMALL",
            reasoning_summary="Div by 1"
        ),
        CandidatePatchLLMOutput(
            patch_id="patch_2",
            unified_diff=(
                "diff --git a/app.py b/app.py\n"
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,2 +1,4 @@\n"
                " def div(x):\n"
                "-    return x / 0\n"
                "+    if x == 0:\n"
                "+        return 0\n"
                "+    return x / x\n"
            ),
            explanation="Guard against 0",
            affected_files=["app.py"],
            estimated_change_scope="SMALL",
            reasoning_summary="Guard clause"
        ),
        CandidatePatchLLMOutput(
            patch_id="patch_3",
            unified_diff=(
                "diff --git a/app.py b/app.py\n"
                "--- a/app.py\n"
                "+++ b/app.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def div(x):\n"
                "-    return x / 0\n"
                "+    return 0.0\n"
            ),
            explanation="Return float 0",
            affected_files=["app.py"],
            estimated_change_scope="SMALL",
            reasoning_summary="Fallback return"
        )
    ]

    import models
    from database import AsyncSessionLocal, Base, engine
    from tasks import generate_and_store_patches
    
    # Initialize DB schema for test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    import uuid
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    proj_id = f"proj_{uuid.uuid4().hex[:8]}"
    inc_id = f"inc_{uuid.uuid4().hex[:8]}"
    policy_id = f"policy_{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as db:
        # Seed dependencies
        org = models.Organization(id=org_id, name="Test Org")
        project = models.Project(id=proj_id, organization_id=org_id, name="Test", repository="test/repo")
        policy = models.ProjectPolicy(
            id=policy_id, organization_id=org_id, project_id=proj_id,
            restricted_files=["secure.py"]
        )
        incident = models.Incident(
            id=inc_id, organization_id=org_id, project_id=proj_id,
            exception_type="ZeroDivisionError", exception_message="division by zero",
            stack_trace="Traceback...", fingerprint="fp_test", status="DETECTED"
        )
        db.add_all([org, project, policy, incident])
        await db.commit()
        
    # Write mock fault location file
    app_file = temp_repo_dir / "app.py"
    app_file.write_text("def div(x):\n    return x / 0\n")
    
    fault = {"file": "app.py", "line": 2, "function": "div"}
    
    with patch.dict(os.environ, {"PATCH_PROVIDER": "openai", "OPENAI_API_KEY": "sk-valid-test-key"}):
        selected_patch = await generate_and_store_patches(
            incident_id=inc_id,
            repo_path=str(temp_repo_dir),
            fault=fault
        )
        
    assert selected_patch is not None
    assert len(selected_patch) > 0
    assert selected_patch[0].diff is not None
    assert selected_patch[0].is_valid is True
    
    # Verify DB contains all 3 candidate patches
    async with AsyncSessionLocal() as db:
        import sqlalchemy as sa
        res = await db.execute(sa.select(models.PatchCandidate).where(models.PatchCandidate.incident_id == inc_id))
        candidates = res.scalars().all()
        assert len(candidates) == 3
        
        for c in candidates:
            assert c.patch_id is not None
            assert c.affected_files == ["app.py"]
            assert c.estimated_change_scope == "SMALL"
            assert c.reasoning_summary is not None
            assert c.is_valid is True

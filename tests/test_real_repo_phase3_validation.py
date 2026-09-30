import os
import pytest
from dotenv import load_dotenv
load_dotenv(override=True)

from github_client.repo_manager import RepositoryManager
from fault_localizer import localize_fault, build_patch_context
from fault_localizer.localizer import localize_fault_core

def test_real_repo_phase3_validation():
    """
    Validates Phase 3 Generic Fault Localization against real repository fixture:
    jyotsnag-l/recovery-test-repo at faulty commit a9ca1cde1290cffc76efaea7d4eba107765ebf43.

    The localizer must genericly:
    1. Parse the stack trace.
    2. Resolve repository paths inside the acquired workspace.
    3. Perform AST structure and control-flow analysis.
    4. Inspect Git history and blame at exact commit SHA.
    5. Discover related tests.
    6. Rank candidate locations using explainable evidence.
    7. Generate structured PatchContext cleanly.
    """
    repo = "jyotsnag-l/recovery-test-repo"
    target_sha = "a9ca1cde1290cffc76efaea7d4eba107765ebf43"

    # Acquire workspace via RepositoryManager (Phase 2)
    repo_manager = RepositoryManager()
    workspace = repo_manager.acquire(
        repository=repo,
        commit_sha=target_sha,
        incident_id="phase3_real_val"
    )

    try:
        assert os.path.exists(workspace.path), f"Workspace path does not exist: {workspace.path}"
        assert workspace.commit_sha == target_sha

        # Realistic failure traceback traversing API -> service -> validation
        stack_trace = (
            'Traceback (most recent call last):\n'
            '  File "app/api/routers/orders.py", line 28, in create_order_endpoint\n'
            '    return create_order(db=db, order_in=order_in)\n'
            '  File "app/services/order_service.py", line 32, in create_order\n'
            '    validate_stock_availability(db, item.inventory_item_id, item.quantity)\n'
            '  File "app/services/inventory_service.py", line 46, in validate_stock_availability\n'
            '    if item.stock_quantity <= 0:\n'
            'fastapi.exceptions.HTTPException: 400: Insufficient stock\n'
        )

        # 1. Run generic fault localization core
        result = localize_fault_core(stack_trace, repo_path=workspace.path)

        # 2. Verify candidate generation and ranking
        candidates = result["candidates"]
        assert len(candidates) >= 2, f"Expected multiple candidates, got {len(candidates)}"

        # 3. Top candidate verification
        top = candidates[0]
        assert top["file"] == "app/services/inventory_service.py"
        assert top["line"] == 46
        assert top["function"] == "validate_stock_availability"
        assert top["score"] > 50.0
        assert top["recent_change"] is True
        assert len(top["reasons"]) > 0

        # Check that blame identifies the exact faulty commit SHA
        blame = top["git"]["blame"]
        assert blame.get("commit_hash") is not None
        assert blame["commit_hash"].lower().startswith(target_sha[:7].lower())

        # Check AST analysis extracted control flow and boundaries
        ast_data = top["ast"]
        assert ast_data["function_boundaries"] is not None
        assert "if-statement" in ast_data["control_flow_context"]

        # Check related test discovery
        assert len(result["related_tests"]) > 0

        # 4. Verify backwards compatibility of top-level fields
        assert result["file"] == top["file"]
        assert result["line"] == top["line"]
        assert result["function"] == top["function"]
        assert result["recent_change"] is True
        assert len(result["evidence"]) > 0

        # 5. Verify ContextBuilder works on real workspace
        incident_data = {
            "id": "inc_real_p3",
            "exception_type": "HTTPException",
            "exception_message": "400: Insufficient stock",
            "stack_trace": stack_trace,
            "fingerprint": "fp_real_p3"
        }
        context = build_patch_context(incident_data, repo_path=workspace.path)
        assert "fault_location" in context
        assert "source_context" in context
        assert "fault_candidates" in context
        assert len(context["fault_candidates"]) >= 2
        assert context["fault_location"]["file"] == "app/services/inventory_service.py"
        assert context["fault_location"]["line"] == 46
        assert context["fault_location"]["score"] > 50.0

    finally:
        workspace_path = workspace.path
        workspace.cleanup()
        assert not os.path.exists(workspace_path), f"Workspace was not cleaned up: {workspace_path}"

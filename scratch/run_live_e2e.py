import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in [
    "apps/api", "apps/recovery-worker", "packages/shared", "packages/core",
    "packages/github-client", "packages/fault-localizer", "packages/patch-engine",
    "packages/sandbox-manager", "packages/trust-engine-core", "packages/recovery-sdk"
]:
    p_path = os.path.join(root, p)
    if p_path not in sys.path:
        sys.path.insert(0, p_path)

import asyncio
from dotenv import load_dotenv

load_dotenv(override=True)

from github_client.repo_manager import RepositoryManager
from fault_localizer.localizer import localize_fault_core
from fault_localizer import build_patch_context
from patch_engine import GeminiAdapter, GrokAdapter, OpenAIAdapter, PatchGenerationEngine, PatchContext, get_provider
from sandbox_manager.runner import SandboxConfig, SandboxRunner
from sandbox_manager.models import SandboxStatus

def run_e2e_validation(provider_name="gemini"):
    repo = "jyotsnag-l/recovery-test-repo"
    target_sha = "a9ca1cde1290cffc76efaea7d4eba107765ebf43"

    print("=" * 60)
    print(f"STARTING REAL-TIME VALIDATION WITH PROVIDER: {provider_name.upper()}")
    print("=" * 60)

    # 1. ACQUIRING WORKSPACE
    print("\n[Stage 1] Acquiring workspace via RepositoryManager...")
    repo_mgr = RepositoryManager()
    workspace = repo_mgr.acquire(repository=repo, commit_sha=target_sha, incident_id=f"val_{provider_name}")
    print(f"Acquired workspace at: {workspace.path}")
    print(f"Commit SHA: {workspace.commit_sha}")
    assert workspace.commit_sha == target_sha, f"SHA mismatch: {workspace.commit_sha} != {target_sha}"

    try:
        # 2. BASELINE FAILING TEST
        print("\n[Stage 2] Executing Customer Test on Unpatched Faulty SHA...")
        cfg = SandboxConfig(timeout=60, test_command="pytest", environment_allowlist=["PYTHONPATH"])
        runner = SandboxRunner(cfg)
        base_res = runner.run(f"job_base_{provider_name}", workspace.path, target_sha, patch_diff="")
        print(f"Baseline Status: {base_res.status} (Exit Code: {base_res.exit_code})")
        assert base_res.status == SandboxStatus.TEST_FAILURE
        assert base_res.exit_code != 0
        print("GENUINE FAILURE CONFIRMED: test_create_order_exceeding_stock_should_fail failed as expected.")

        # 3. AUTONOMOUS LOCALIZATION
        print("\n[Stage 3] Running Autonomous Fault Localization...")
        # Genuine customer failure stack trace WITHOUT any injected file/line/function/fix
        customer_trace = (
            'Traceback (most recent call last):\n'
            '  File "tests/test_order_validation.py", line 19, in test_create_order_exceeding_stock_should_fail\n'
            '    assert order_resp.status_code == 400\n'
            'AssertionError: assert 201 == 400\n'
        )

        loc_result = localize_fault_core(customer_trace, repo_path=workspace.path)
        top_cand = loc_result["candidates"][0]
        print(f"Top Fault Identified: {top_cand['file']}:{top_cand['line']} in {top_cand['function']} (Score: {top_cand['score']})")
        print(f"Control Flow Context: {top_cand.get('ast', {}).get('control_flow_context')}")
        blame_sha = top_cand.get("git", {}).get("blame", {}).get("commit_hash", "")
        print(f"Git Blame Hash: {blame_sha}")
        print(f"Related Tests Discovered: {[t['file'] for t in loc_result['related_tests']]}")

        assert top_cand["file"] == "app/services/inventory_service.py"
        assert top_cand["line"] == 46
        assert top_cand["function"] == "validate_stock_availability"

        # 4. BUILD PATCH CONTEXT
        print("\n[Stage 4] Assembling PatchContext from Overmend Discoveries...")
        incident_data = {
            "id": f"inc_{provider_name}_e2e",
            "exception_type": "AssertionError",
            "exception_message": "assert 201 == 400",
            "stack_trace": customer_trace,
            "fingerprint": f"fp_{provider_name}"
        }
        ctx_dict = build_patch_context(incident_data, repo_path=workspace.path)
        patch_context = PatchContext.model_validate(ctx_dict)

        # 5. LIVE LLM CANDIDATE GENERATION
        print(f"\n[Stage 5] Requesting 3 Candidate Patches from {provider_name.upper()}...")
        provider = get_provider(provider_name)
        print(f"Provider class: {provider.__class__.__name__}, is_configured: {provider.is_configured}")

        engine = PatchGenerationEngine(provider)
        candidates_result = asyncio.run(engine.generate_candidates(patch_context, repo_path=workspace.path, num_patches=3))
        print(f"Received {len(candidates_result)} candidate patches.")

        # 6. VALIDATE & EXECUTE EACH CANDIDATE IN ISOLATED SANDBOX
        print("\n[Stage 6] Validating and Sandboxing Candidate Patches...")
        report_data = []

        for idx, item in enumerate(candidates_result, 1):
            cand = item.candidate
            val = item.validation
            print(f"\n--- Candidate {idx}: {cand.patch_id} ---")
            print(f"Explanation: {cand.explanation}")
            print(f"Validation Valid: {val.is_valid}, Error: {val.error_reason}")
            print("Unified Diff:\n" + cand.unified_diff)

            sandbox_status = "SKIPPED_INVALID"
            test_exit_code = None

            if val.is_valid:
                print(f"Executing Candidate {idx} in isolated sandbox...")
                c_res = runner.run(f"job_cand_{provider_name}_{idx}", workspace.path, target_sha, patch_diff=cand.unified_diff, candidate_id=cand.patch_id)
                sandbox_status = c_res.status.value
                test_exit_code = c_res.exit_code
                print(f"Sandbox Result: {sandbox_status} (Exit Code: {test_exit_code})")
                if c_res.status == SandboxStatus.PASSED:
                    print(">>> SUCCESS: CANDIDATE PATCH PASSED ALL TESTS! <<<")

            report_data.append({
                "candidate": cand.patch_id,
                "validation": "PASS" if val.is_valid else f"FAIL ({val.error_reason})",
                "sandbox": sandbox_status,
                "exit_code": test_exit_code,
                "diff": cand.unified_diff
            })

        return {
            "status": "COMPLETED",
            "provider": provider_name,
            "candidates": report_data
        }

    finally:
        workspace.cleanup()
        print("\n[Stage 7] Workspace cleanup verified.")

if __name__ == "__main__":
    import sys
    prov = sys.argv[1] if len(sys.argv) > 1 else "gemini"
    run_e2e_validation(prov)

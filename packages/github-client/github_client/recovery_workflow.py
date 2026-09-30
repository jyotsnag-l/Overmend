import os
import re
import time
import logging
import tempfile
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from github_client.client import GitHubAppClient
from github_client.repo_manager import RepositoryManager, _run_git, _scrub_sensitive, cleanup_workspace

logger = logging.getLogger("github_client.recovery_workflow")


class GitHubRecoveryError(Exception):
    """Raised when any step of the GitHub recovery workflow fails."""
    def __init__(self, step: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"[{step}] {message}")
        self.step = step
        self.message = message
        self.details = details or {}


def check_existing_recovery(
    client: GitHubAppClient,
    repository: str,
    incident_id: str
) -> Optional[Dict[str, Any]]:
    """
    Idempotency check: checks if a recovery branch or open PR already exists for this incident.
    Returns existing recovery state if found, otherwise None.
    """
    if client.mock:
        return None

    branch_name = f"overmend/recovery/{incident_id}"
    logger.info(f"Checking idempotency for branch {branch_name} in {repository}...")

    # Check if branch exists
    branch_exists = False
    try:
        branch_info = client.get_branch(repository, branch_name)
        if branch_info and "commit" in branch_info:
            branch_exists = True
    except Exception:
        branch_exists = False

    # Check if PR exists
    try:
        import requests
        url = f"https://api.github.com/repos/{repository}/pulls"
        headers = client._headers()
        params = {"state": "all"}
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            owner = repository.split("/")[0] if "/" in repository else ""
            target_ref = f"{owner}:{branch_name}" if owner else branch_name
            for pr in resp.json():
                head_ref = pr.get("head", {}).get("ref", "")
                head_label = pr.get("head", {}).get("label", "")
                if head_ref == branch_name or head_label == target_ref:
                    logger.info(f"Found existing recovery PR #{pr['number']} ({pr['html_url']})")
                    return {
                        "is_existing": True,
                        "branch_name": branch_name,
                        "pull_request_number": pr["number"],
                        "pull_request_url": pr["html_url"],
                        "pull_request_state": pr["state"],
                        "created_at": pr.get("created_at")
                    }
    except Exception as e:
        logger.warning(f"Could not verify existing PRs via GitHub API: {e}")

    if branch_exists:
        return {
            "is_existing": True,
            "branch_name": branch_name,
            "pull_request_number": None,
            "pull_request_url": None,
            "pull_request_state": None
        }

    return None


def execute_github_recovery_pipeline(
    repository: str,
    incident_id: str,
    faulty_commit_sha: str,
    selected_candidate: Dict[str, Any],
    decision_info: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
    fault_localization: Optional[Dict[str, Any]] = None,
    client: Optional[GitHubAppClient] = None
) -> Dict[str, Any]:
    """
    Executes the Safe GitHub Recovery sequence:
    1. Idempotency verification
    2. Isolated workspace creation & exact commit checkout
    3. Dedicated recovery branch creation (overmend/recovery/<incident-id>)
    4. Patch application & diff verification
    5. Test re-validation on recovery branch
    6. Git status/diff recording and commit
    7. Authenticated branch push
    8. Structured PR creation (zero secrets leaked)
    9. CI verification
    10. Configurable merge policy evaluation
    11. Audit trail persistence
    """
    start_time = datetime.now(timezone.utc)
    pol = policy or {}
    auto_merge_enabled = pol.get("auto_merge_enabled")
    if auto_merge_enabled is None:
        auto_merge_enabled = os.getenv("AUTO_MERGE_ENABLED", "false").lower() == "true"

    # Initialize GitHub client
    if client is None:
        app_id = os.getenv("GITHUB_APP_ID", "mock")
        private_key = os.getenv("GITHUB_PRIVATE_KEY", "mock")
        installation_id = os.getenv("GITHUB_INSTALLATION_ID")
        is_mock_repo = (
            any(k in repository.lower() for k in ["mock", "dummy", "demo-repo"])
            or ("/" not in repository)
            or os.getenv("GITHUB_MOCK", "false").lower() == "true"
        )
        client = GitHubAppClient(app_id, private_key, installation_id, mock=(is_mock_repo or app_id == "mock"))

    # 1. Idempotency Check
    existing = check_existing_recovery(client, repository, incident_id)
    if existing and existing.get("pull_request_url"):
        logger.info(f"Recovery already active for incident {incident_id}. Returning existing state.")
        return {
            "status": "EXISTING_RECOVERY",
            "incident_id": incident_id,
            "candidate_id": selected_candidate.get("candidate_id"),
            "branch_name": existing["branch_name"],
            "pull_request_url": existing["pull_request_url"],
            "pull_request_number": existing["pull_request_number"],
            "ci_status": "PENDING",
            "merge_status": "PENDING_REVIEW",
            "audit_trail": {
                "idempotent": True,
                "existing_state": existing
            }
        }

    branch_name = f"overmend/recovery/{incident_id}"
    workspace = None
    repo_mgr = RepositoryManager(github_client=client)

    try:
        # 2. Acquire isolated workspace at the exact investigated customer commit
        logger.info(f"Acquiring repository {repository} at commit {faulty_commit_sha}...")
        workspace = repo_mgr.acquire(
            repository=repository,
            commit_sha=faulty_commit_sha,
            incident_id=incident_id
        )

        # Verify exact commit SHA matches before touching anything
        git_verify_res = _run_git(["rev-parse", "HEAD"], cwd=workspace.path)
        if git_verify_res.returncode != 0:
            raise GitHubRecoveryError(
                "VERIFY_COMMIT",
                f"Failed to check workspace commit: {git_verify_res.stderr.strip()}"
            )
        current_sha = git_verify_res.stdout.strip().lower()
        if not current_sha.startswith(faulty_commit_sha.lower()) and not faulty_commit_sha.lower().startswith(current_sha):
            raise GitHubRecoveryError(
                "VERIFY_COMMIT",
                f"Workspace commit SHA '{current_sha}' does not match incident commit '{faulty_commit_sha}'."
            )

        # 3. Create dedicated recovery branch
        logger.info(f"Creating recovery branch {branch_name}...")
        branch_create_res = _run_git(["checkout", "-b", branch_name], cwd=workspace.path)
        if branch_create_res.returncode != 0:
            # If already checked out, verify branch name
            cur_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=workspace.path).stdout.strip()
            if cur_branch != branch_name:
                raise GitHubRecoveryError(
                    "CREATE_BRANCH",
                    f"Failed to create recovery branch {branch_name}: {branch_create_res.stderr.strip()}"
                )

        # 4. Apply ONLY the selected candidate patch
        patch_diff = selected_candidate.get("patch_diff", "")
        if not patch_diff:
            raise GitHubRecoveryError("APPLY_PATCH", "Selected candidate contains no patch diff.")

        logger.info(f"Applying selected patch {selected_candidate.get('candidate_id')} to {branch_name}...")
        patch_file = os.path.join(workspace.path, "_selected_recovery_patch.diff")
        with open(patch_file, "w", encoding="utf-8", newline="") as pf:
            pf.write(patch_diff)

        apply_res = _run_git(
            ["apply", "--ignore-space-change", "--whitespace=nowarn", "_selected_recovery_patch.diff"],
            cwd=workspace.path
        )
        if os.path.exists(patch_file):
            os.remove(patch_file)

        if apply_res.returncode != 0:
            raise GitHubRecoveryError(
                "APPLY_PATCH",
                f"git apply failed on recovery branch: {apply_res.stderr.strip()}"
            )

        # Verify git diff contains changes and no unrelated files modified
        diff_res = _run_git(["diff"], cwd=workspace.path)
        diff_text = diff_res.stdout
        if not diff_text.strip():
            raise GitHubRecoveryError("APPLY_PATCH", "git diff is empty after applying patch.")

        status_res = _run_git(["status", "--porcelain"], cwd=workspace.path)
        modified_files = []
        for line in status_res.stdout.splitlines():
            line = line.strip()
            if line:
                modified_files.append(line.split()[-1])

        expected_files = selected_candidate.get("files_changed", [])
        if expected_files:
            # Check for unexpected modifications
            normalized_expected = [f.replace("\\", "/") for f in expected_files]
            for m in modified_files:
                norm_m = m.replace("\\", "/")
                if not any(norm_m.endswith(exp) or exp.endswith(norm_m) for exp in normalized_expected):
                    raise GitHubRecoveryError(
                        "VERIFY_DIFF",
                        f"Unrelated file modified by patch: {m}. Expected only {expected_files}."
                    )

        # 5. Re-run customer tests on recovery branch
        logger.info("Re-running customer tests on recovery branch...")
        import sys
        python_exe = sys.executable
        test_env = os.environ.copy()
        test_env["PYTHONPATH"] = workspace.path + os.pathsep + test_env.get("PYTHONPATH", "")
        test_run = subprocess.run(
            [python_exe, "-m", "pytest"],
            cwd=workspace.path,
            env=test_env,
            capture_output=True,
            text=True,
            timeout=120
        )
        if test_run.returncode != 0:
            raise GitHubRecoveryError(
                "TEST_VALIDATION",
                f"Customer tests failed on recovery branch after patch application (exit code {test_run.returncode}). Output:\n{test_run.stdout[-500:]}"
            )
        logger.info("Customer tests passed cleanly on recovery branch!")

        # 6. Record pre-commit state & Commit
        git_status_output = _run_git(["status"], cwd=workspace.path).stdout.strip()
        git_diff_stat = _run_git(["diff", "--stat"], cwd=workspace.path).stdout.strip()
        git_diff_content = diff_text
        commit_sha_before = current_sha

        logger.info(f"Pre-commit SHA: {commit_sha_before}")
        _run_git(["config", "user.name", "Overmend Bot"], cwd=workspace.path)
        _run_git(["config", "user.email", "bot@overmend.local"], cwd=workspace.path)
        _run_git(["add", "-u"], cwd=workspace.path)

        commit_msg = f"fix: recover incident {incident_id}"
        commit_res = _run_git(["commit", "-m", commit_msg], cwd=workspace.path)
        if commit_res.returncode != 0:
            raise GitHubRecoveryError(
                "COMMIT",
                f"git commit failed on recovery branch: {commit_res.stderr.strip()}"
            )

        commit_sha_after = _run_git(["rev-parse", "HEAD"], cwd=workspace.path).stdout.strip()
        logger.info(f"Post-commit SHA: {commit_sha_after}")

        if commit_sha_before == commit_sha_after:
            raise GitHubRecoveryError("COMMIT", "HEAD did not change after commit.")

        # 7. Authenticated Branch Push (ONLY the recovery branch, NEVER force-push, NEVER main)
        logger.info(f"Pushing branch {branch_name} to remote...")
        if client.mock:
            push_success = True
        else:
            token = client.get_token()
            auth_remote_url = f"https://x-access-token:{token}@github.com/{repository}.git"
            _run_git(["remote", "set-url", "origin", auth_remote_url], cwd=workspace.path)
            
            # Explicitly push ONLY the generated recovery branch without force flag
            push_res = _run_git(["push", "origin", branch_name], cwd=workspace.path)
            if push_res.returncode != 0:
                err_clean = _scrub_sensitive(push_res.stderr.strip())
                raise GitHubRecoveryError(
                    "PUSH",
                    f"git push failed for branch '{branch_name}': {err_clean}"
                )
            push_success = True

        logger.info(f"Branch {branch_name} pushed successfully.")

        # 8. Create GitHub Pull Request
        pr_title = f"fix: automated recovery for {incident_id}"
        
        # Build structured PR body without leaking any secrets
        fault_summary = "Autonomous Localization"
        if fault_localization:
            f_file = fault_localization.get("file", "app/services/inventory_service.py")
            f_func = fault_localization.get("function", "validate_stock_availability")
            f_line = fault_localization.get("line", 46)
            fault_summary = f"`{f_file}:{f_line}` in `{f_func}`"

        pr_body = f"""## Overmend Automated Recovery

### Incident Overview
- **Incident ID:** `{incident_id}`
- **Repository:** `{repository}`
- **Faulty Source Commit:** `{faulty_commit_sha}`
- **Recovery Branch:** `{branch_name}`
- **Recovery Commit:** `{commit_sha_after}`

### Autonomous Diagnosis & Fault Localization
- **Localized Fault:** {fault_summary}
- **Selected Candidate:** `{selected_candidate.get('candidate_id')}`
- **Provider / Model:** `{selected_candidate.get('provider')}` / `{selected_candidate.get('model')}`

### Observable Validation Evidence
| Metric | Result |
| :--- | :--- |
| **Patch Validation** | {"PASSED" if selected_candidate.get("validation_result") else "FAILED"} |
| **Customer Test Suite** | PASSED ({selected_candidate.get("tests_passed", 1)} passed, 0 failed) |
| **Mutation Score** | {selected_candidate.get("mutation_score", 0.0):.2f} ({selected_candidate.get("mutation_tests_killed", 0)} killed, {selected_candidate.get("mutation_tests_passed", 0)} survived) |
| **Patch Scope** | {len(selected_candidate.get("files_changed", []))} file(s) changed (+{selected_candidate.get("lines_added", 0)} / -{selected_candidate.get("lines_removed", 0)} lines) |
| **Deterministic Trust Score** | **{selected_candidate.get("trust_score", 0.0):.2f}** |
| **Decision Engine Action** | **{selected_candidate.get("decision", "CREATE_PR")}** |

### Selection Rationale
{decision_info.get("why_selected", "Candidate produced the strongest independently verified evidence.")}

---
*This pull request was autonomously generated, verified in an isolated sandbox, and submitted by Overmend PaaS.*
"""

        logger.info(f"Creating Pull Request: {pr_title}...")
        pr_data = client.create_pull_request(
            repo=repository,
            branch=branch_name,
            title=pr_title,
            body=pr_body,
            base="main"
        )
        pr_number = pr_data.get("number")
        pr_url = pr_data.get("html_url")
        logger.info(f"Pull Request created: {pr_url} (#{pr_number})")

        # 9. CI Verification
        logger.info(f"Checking CI statuses for commit {commit_sha_after}...")
        time.sleep(2)  # Allow GitHub Actions to register the ref
        ci_statuses = client.get_ci_statuses(repository, commit_sha_after)
        
        ci_status = "PENDING"
        if ci_statuses:
            if all(s.get("state") == "SUCCESS" for s in ci_statuses):
                ci_status = "SUCCESS"
            elif any(s.get("state") in ["FAILURE", "ERROR"] for s in ci_statuses):
                ci_status = "FAILURE"
            else:
                ci_status = "PENDING"

        # 10. Merge Policy Evaluation
        merge_status = "PENDING_HUMAN_REVIEW"
        final_recovery_status = "PR_CREATED"

        if auto_merge_enabled:
            logger.info("AUTO_MERGE_ENABLED is true. Checking auto-merge criteria...")
            trust_score = float(selected_candidate.get("trust_score", 0.0))
            auto_merge_threshold = float(pol.get("auto_merge_threshold", 0.90))
            
            can_merge = (
                selected_candidate.get("decision") == "AUTO_MERGE"
                and trust_score >= auto_merge_threshold
                and ci_status == "SUCCESS"
            )

            if can_merge:
                logger.info(f"Criteria met. Attempting to merge PR #{pr_number}...")
                merged = client.merge_pull_request(repository, pr_number, commit_title=f"Merge automated recovery PR #{pr_number}")
                if merged:
                    merge_status = "MERGED"
                    final_recovery_status = "SUCCESS"
                    logger.info("PR merged successfully.")
                else:
                    merge_status = "MERGE_FAILED"
                    final_recovery_status = "PR_CREATED"
            else:
                merge_status = f"NOT_MERGED (CI={ci_status}, Trust={trust_score:.2f}/{auto_merge_threshold})"
        else:
            logger.info("AUTO_MERGE_ENABLED is false. Leaving PR open for human review.")
            merge_status = "PENDING_HUMAN_REVIEW"
            final_recovery_status = "PR_CREATED"

        # 11. Audit Trail Record
        audit_trail = {
            "incident_id": incident_id,
            "candidate_id": selected_candidate.get("candidate_id"),
            "trust_score": selected_candidate.get("trust_score"),
            "decision": selected_candidate.get("decision"),
            "threshold": pol.get("auto_merge_threshold", 0.90),
            "validation_result": selected_candidate.get("validation_result"),
            "sandbox_result": {
                "test_result": selected_candidate.get("test_result"),
                "tests_passed": selected_candidate.get("tests_passed"),
                "tests_failed": selected_candidate.get("tests_failed"),
                "sandbox_status": selected_candidate.get("sandbox_status")
            },
            "mutation_result": {
                "mutation_score": selected_candidate.get("mutation_score"),
                "mutants_killed": selected_candidate.get("mutation_tests_killed"),
                "mutants_passed": selected_candidate.get("mutation_tests_passed")
            },
            "branch_name": branch_name,
            "commit_sha_before": commit_sha_before,
            "commit_sha_after": commit_sha_after,
            "git_pre_commit": {
                "status": git_status_output,
                "diff_stat": git_diff_stat,
                "diff": git_diff_content
            },
            "pull_request_number": pr_number,
            "pull_request_url": pr_url,
            "CI_status": ci_status,
            "merge_status": merge_status,
            "auto_merge_enabled": auto_merge_enabled,
            "timestamps": {
                "started_at": start_time.isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }
        }

        return {
            "status": final_recovery_status,
            "incident_id": incident_id,
            "candidate_id": selected_candidate.get("candidate_id"),
            "branch_name": branch_name,
            "commit_sha_before": commit_sha_before,
            "commit_sha_after": commit_sha_after,
            "pull_request_number": pr_number,
            "pull_request_url": pr_url,
            "ci_status": ci_status,
            "merge_status": merge_status,
            "audit_trail": audit_trail
        }

    finally:
        if workspace:
            workspace.cleanup()

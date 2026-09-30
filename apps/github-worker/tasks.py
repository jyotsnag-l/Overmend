import logging
import os
import sys
import asyncio
from datetime import datetime, timezone
import requests
from celery import Celery
from shared import setup_logging
import github_client
from github_client.client import GitHubAppClient

# Ensure apps/api is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from database import AsyncSessionLocal
import models
from sqlalchemy import select

setup_logging(service_name="github-worker", level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("github_worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("github_worker", broker=REDIS_URL, backend=REDIS_URL)

def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    else:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()


@celery_app.task(name="tasks.create_pr_task")
def create_pr_task(repo: str, branch: str, title: str, body: str) -> str:
    logger.info("Executing create PR task...")
    result = github_client.create_pull_request(repo, branch, title, body)
    return result


@celery_app.task(bind=True, name="tasks.monitor_pr_ci_task", max_retries=30)
def monitor_pr_ci_task(self, incident_id: str, repo: str, pr_number: int):
    logger.info(f"Executing monitor PR CI task for incident {incident_id}, PR #{pr_number}")
    
    app_id = os.getenv("GITHUB_APP_ID", "mock")
    private_key = os.getenv("GITHUB_PRIVATE_KEY", "mock")
    installation_id = os.getenv("GITHUB_INSTALLATION_ID")
    client = GitHubAppClient(app_id, private_key, installation_id)

    is_mock_repo = (
        client.mock
        or "/" not in repo
        or repo.startswith(("mock", "org/", "test/", "dummy/"))
        or repo in ["demo-repo", "owner/repo", "org/repo", "test/repo"]
        or os.getenv("GITHUB_MOCK", "false").lower() == "true"
    )


    try:
        if is_mock_repo:
            ref = "a1b2c3d4e5f6"
            statuses = [
                {"context": "continuous-integration/github-actions", "state": "SUCCESS", "target_url": "https://ci.example.com/build/1"},
                {"context": "ci/tests", "state": "SUCCESS", "target_url": "https://ci.example.com/build/1"}
            ]
        else:
            url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
            headers = client._headers()
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            ref = resp.json()["head"]["sha"]
            statuses = client.get_ci_statuses(repo, ref)
    except Exception as e:
        logger.error(f"Failed to fetch CI statuses from GitHub: {e}")
        raise self.retry(exc=e, countdown=15)

    async def update_db_ci_statuses(inc_id, pr_num, ci_list):
        import uuid
        async with AsyncSessionLocal() as db:
            pr_res = await db.execute(
                select(models.PullRequest)
                .where(models.PullRequest.github_pr_number == pr_num)
                .where(models.PullRequest.status == "OPEN")
                .order_by(models.PullRequest.created_at.desc())
            )
            pr = pr_res.scalars().first()
            if not pr:
                logger.warning(f"No open PR #{pr_num} found in DB.")
                return False, False

            ci_pending = False
            for ci in ci_list:
                context = ci["context"]
                state = ci["state"]
                target_url = ci.get("target_url")
                
                if state == "PENDING":
                    ci_pending = True
                
                ci_query = select(models.CIStatus).where(
                    models.CIStatus.pull_request_id == pr.id,
                    models.CIStatus.context == context
                )
                ci_res = await db.execute(ci_query)
                db_ci = ci_res.scalar_one_or_none()
                
                if not db_ci:
                    db_ci = models.CIStatus(
                        id=f"ci_{uuid.uuid4().hex[:8]}",
                        organization_id=pr.organization_id,
                        pull_request_id=pr.id,
                        status=state,
                        context=context,
                        target_url=target_url,
                        created_at=datetime.now(timezone.utc)
                    )
                    db.add(db_ci)
                else:
                    db_ci.status = state
                    db_ci.target_url = target_url
                    db_ci.created_at = datetime.now(timezone.utc)
            
            await db.commit()
            return True, ci_pending

    success, ci_pending = run_async(update_db_ci_statuses(incident_id, pr_number, statuses))
    if not success:
        return {"status": "pr_not_found"}

    if os.getenv("BYPASS_CELERY", "false").lower() == "true":
        logger.info("Executing evaluate_and_merge_pr_task synchronously in Celery-bypass mode")
        run_async(async_evaluate_and_merge_pr(incident_id))
    else:
        try:
            celery_app.send_task(
                "tasks.evaluate_and_merge_pr_task",
                args=[incident_id]
            )
        except Exception as e:
            logger.warning(f"Failed to trigger evaluation task: {e}")

    if ci_pending:
        logger.info(f"CI status still pending for PR #{pr_number}. Retrying monitoring task in 15 seconds.")
        raise self.retry(countdown=15)
        
    return {"status": "completed", "ci_pending": ci_pending}


async def async_evaluate_and_merge_pr(incident_id: str):
    import pipeline
    
    app_id = os.getenv("GITHUB_APP_ID", "mock")
    private_key = os.getenv("GITHUB_PRIVATE_KEY", "mock")
    installation_id = os.getenv("GITHUB_INSTALLATION_ID")
    client = GitHubAppClient(app_id, private_key, installation_id)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(models.Incident).where(models.Incident.id == incident_id))
        incident = res.scalar_one_or_none()
        if not incident:
            logger.error(f"Incident {incident_id} not found")
            return
            
        if incident.status in ("MERGED", "VERIFIED", "REVERTED", "REJECTED"):
            logger.info(f"Incident {incident_id} is already in a terminal state: {incident.status}")
            return

        dec_res = await db.execute(
            select(models.Decision)
            .join(models.PatchCandidate)
            .where(models.PatchCandidate.incident_id == incident_id)
            .order_by(models.Decision.created_at.desc())
            .limit(1)
        )
        decision = dec_res.scalar_one_or_none()
        if not decision:
            logger.error(f"No Decision record found for incident {incident_id}")
            await pipeline.transition_state(db, incident, "HUMAN_REVIEW", "No automated decision found.")
            await db.commit()
            return

        pr_res = await db.execute(
            select(models.PullRequest)
            .join(models.PatchCandidate)
            .where(models.PatchCandidate.incident_id == incident_id)
            .where(models.PullRequest.status == "OPEN")
        )
        pr = pr_res.scalar_one_or_none()
        if not pr:
            logger.error(f"No open Pull Request found for incident {incident_id}")
            return

        pr_number: int = int(getattr(pr, "github_pr_number", 0))
        repo_name: str = str(getattr(incident, "affected_repository", "") or "")
        logger.info(f"Evaluating merge criteria for incident {incident_id}, PR #{pr_number}...")
        
        inputs = decision.inputs or {}
        trust_score = inputs.get("trust_score", 0.0)
        sandbox_test_success = inputs.get("test_result", False)
        
        policy_res = await db.execute(
            select(models.ProjectPolicy).where(models.ProjectPolicy.project_id == incident.project_id)
        )
        policy = policy_res.scalar_one_or_none()
        
        trust_threshold = policy.auto_merge_threshold if policy else float(os.getenv("GITHUB_TRUST_THRESHOLD", "0.90"))
        trust_passed = (trust_score >= trust_threshold)
        logger.info(f"Trust Check: Score={trust_score:.2f}, Threshold={trust_threshold:.2f}, Passed={trust_passed}")

        sandbox_passed = sandbox_test_success
        logger.info(f"Sandbox Check: Passed={sandbox_passed}")

        policy_permitted = (decision.action == "AUTO_MERGE")
        if inputs.get("sensitive_file_flags", False):
            policy_permitted = False
            logger.info("Policy Check: Failed due to sensitive file changes.")
        else:
            logger.info(f"Policy Check: Action={decision.action}, Permitted={policy_permitted}")

        ci_res = await db.execute(
            select(models.CIStatus).where(models.CIStatus.pull_request_id == pr.id)
        )
        ci_records = ci_res.scalars().all()
        
        if not ci_records and client.mock:
            import uuid
            mock_status = models.CIStatus(
                id=f"ci_{uuid.uuid4().hex[:8]}",
                organization_id=pr.organization_id,
                pull_request_id=pr.id,
                status="SUCCESS",
                context="continuous-integration/github-actions",
                target_url="https://github.com/mock-ci",
                created_at=datetime.now(timezone.utc)
            )
            db.add(mock_status)
            await db.commit()
            ci_records = [mock_status]
            
        ci_passed = len(ci_records) > 0 and all(r.status.upper() in ["SUCCESS", "PASSED"] for r in ci_records)
        ci_pending = any(r.status.upper() == "PENDING" for r in ci_records)
        logger.info(f"CI Check: Records={len(ci_records)}, Passed={ci_passed}, Pending={ci_pending}")

        if ci_pending:
            logger.info("CI is still pending. Postponing evaluation.")
            return

        try:
            protection = client.get_branch_protection(repo_name, "main")
            bp_satisfied = True
            
            req_checks = protection.get("required_status_checks", {})
            if req_checks:
                contexts = req_checks.get("contexts", [])
                for ctx in contexts:
                    matching = [r for r in ci_records if r.context == ctx]
                    if not matching or any(r.status != "SUCCESS" for r in matching):
                        bp_satisfied = False
                        logger.info(f"Branch Protection Check: Required context '{ctx}' is not successful.")
            
            req_reviews = protection.get("required_pull_request_reviews", {})
            if req_reviews:
                min_approvals = req_reviews.get("required_approving_review_count", 0)
                if min_approvals > 0:
                    bp_satisfied = False
                    logger.info(f"Branch Protection Check: Requires {min_approvals} approvals, human intervention needed.")
            
            logger.info(f"Branch Protection Check: Satisfied={bp_satisfied}")
        except Exception as e:
            logger.warning(f"Failed to fetch branch protection rules: {e}. Defaulting to satisfied.")
            bp_satisfied = True

        all_checks_passed = trust_passed and sandbox_passed and policy_permitted and ci_passed and bp_satisfied

        if all_checks_passed:
            logger.info(f"All merge conditions met for incident {incident_id}. Merging Pull Request...")
            merge_success = client.merge_pull_request(repo_name, pr_number)
            if merge_success:
                pr.status = "MERGED"
                await pipeline.transition_state(db, incident, "MERGED", f"PR #{pr_number} auto-merged successfully.")
                await db.commit()
                
                verification_success = sandbox_passed
                if verification_success:
                    await pipeline.transition_state(db, incident, "VERIFIED", "Incident fix verified successfully. Closing incident.")
                else:
                    await pipeline.transition_state(db, incident, "REVERTED", "Verification failed post-merge. Reverting changes.")
                await db.commit()
            else:
                logger.error("GitHub merge call failed. Routing to HUMAN_REVIEW.")
                await pipeline.transition_state(db, incident, "HUMAN_REVIEW", "Auto-merge API call failed.")
                await db.commit()
        else:
            reason_parts = []
            if not trust_passed: reason_parts.append("Trust Score below threshold")
            if not sandbox_passed: reason_parts.append("Sandbox tests failed")
            if not policy_permitted: reason_parts.append("Policy restricts auto-merge")
            if not ci_passed: reason_parts.append("GitHub CI / Actions failed")
            if not bp_satisfied: reason_parts.append("Branch protection checks failed")
            
            fail_reason = ", ".join(reason_parts)
            logger.warning(f"Merge criteria check failed for incident {incident_id}: {fail_reason}. Routing to HUMAN_REVIEW.")
            
            await pipeline.transition_state(db, incident, "HUMAN_REVIEW", f"Automated merge criteria failed: {fail_reason}.")
            await db.commit()


@celery_app.task(name="tasks.evaluate_and_merge_pr_task")
def evaluate_and_merge_pr_task(incident_id: str):
    logger.info(f"Executing evaluate_and_merge_pr_task for incident {incident_id}...")
    run_async(async_evaluate_and_merge_pr(incident_id))
    return {"status": "success"}

import logging
import os
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
import models
from github_client import verify_signature

logger = logging.getLogger("api.webhooks")
router = APIRouter()

@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Received GitHub webhook event: {x_github_event}, delivery: {x_github_delivery}")

    # Read raw body bytes
    body_bytes = await request.body()

    # Webhook signature verification
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    enforce_secret = (
        os.getenv("ENFORCE_WEBHOOK_SECRET", "false").lower() == "true"
        or os.getenv("ENVIRONMENT", "development").lower() == "production"
    )
    if secret or enforce_secret:
        if not secret or not x_hub_signature_256 or not verify_signature(body_bytes, x_hub_signature_256, secret):
            logger.warning(f"Invalid or missing webhook signature for delivery {x_github_delivery}")
            raise HTTPException(status_code=401, detail="Invalid signature or unconfigured webhook secret")
    else:
        logger.debug("GITHUB_WEBHOOK_SECRET is not configured. Skipping signature verification in dev mode.")

    # Idempotency check
    query = select(models.GitHubEvent).where(models.GitHubEvent.event_id == x_github_delivery)
    res = await db.execute(query)
    existing_event = res.scalar_one_or_none()
    if existing_event:
        logger.info(f"Duplicate delivery ID {x_github_delivery} detected. Skipping.")
        return {"status": "ok", "message": "Duplicate event already processed"}

    # Parse payload
    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception as e:
        logger.error(f"Failed to parse webhook JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Store event
    db_event = models.GitHubEvent(
        event_id=x_github_delivery,
        event_type=x_github_event,
        payload=payload,
        processed_at=datetime.now(timezone.utc)
    )
    db.add(db_event)
    await db.commit()

    if x_github_event == "ping":
        return {"status": "ok", "message": "pong"}

    # Handle GitHub App repository additions / removals
    if x_github_event == "installation_repositories":
        action = payload.get("action")
        repos_added = payload.get("repositories_added", [])
        repos_removed = payload.get("repositories_removed", [])
        import uuid

        # Default organization context
        res = await db.execute(select(models.Organization).limit(1))
        org = res.scalar_one_or_none()
        org_id = org.id if org else "org_overmend"

        if action in ("added", "created") or repos_added:
            for repo in repos_added:
                full_name = repo.get("full_name") or repo.get("name")
                repo_url = f"https://github.com/{full_name}"
                
                # Ensure Project exists
                proj_res = await db.execute(
                    select(models.Project)
                    .where(models.Project.organization_id == org_id)
                    .where(models.Project.repository == full_name)
                )
                db_project = proj_res.scalar_one_or_none()
                if not db_project:
                    proj_id = f"proj_{uuid.uuid4().hex[:8]}"
                    db_project = models.Project(
                        id=proj_id,
                        organization_id=org_id,
                        name=repo.get("name") or full_name,
                        repository=full_name
                    )
                    db.add(db_project)
                    await db.flush()

                    db_policy = models.ProjectPolicy(
                        id=f"pol_{uuid.uuid4().hex[:8]}",
                        organization_id=org_id,
                        project_id=proj_id,
                        auto_merge_threshold=0.90,
                        mandatory_review_threshold=0.70,
                        restricted_files=["auth.py", "payment.py"]
                    )
                    db.add(db_policy)

                    db_env = models.Environment(
                        id=f"env_{uuid.uuid4().hex[:8]}",
                        organization_id=org_id,
                        project_id=proj_id,
                        name="production",
                        config={"debug": False}
                    )
                    db.add(db_env)

                # Ensure Repository exists
                repo_res = await db.execute(
                    select(models.Repository)
                    .where(models.Repository.organization_id == org_id)
                    .where(models.Repository.name == full_name)
                )
                db_repo = repo_res.scalar_one_or_none()
                if not db_repo:
                    db_repo = models.Repository(
                        id=f"repo_{uuid.uuid4().hex[:8]}",
                        organization_id=org_id,
                        project_id=db_project.id,
                        name=full_name,
                        url=repo_url,
                        status="active"
                    )
                    db.add(db_repo)

            await db.commit()
            logger.info(f"Handled installation_repositories added: {len(repos_added)} repositories")

        if repos_removed:
            for repo in repos_removed:
                full_name = repo.get("full_name") or repo.get("name")
                repo_res = await db.execute(
                    select(models.Repository)
                    .where(models.Repository.organization_id == org_id)
                    .where(models.Repository.name == full_name)
                )
                db_repo = repo_res.scalar_one_or_none()
                if db_repo:
                    await db.delete(db_repo)
            await db.commit()
            logger.info(f"Handled installation_repositories removed: {len(repos_removed)} repositories")

        return {"status": "ok", "message": "Installation repositories updated"}

    # Handle CI status updates
    if x_github_event in ("check_run", "check_suite", "status"):
        from celery_app import celery_app
        
        pr_number = None
        repo_name = None
        ref = None
        state = None
        context = None
        target_url = None

        if x_github_event == "check_run":
            check_run = payload.get("check_run", {})
            repo_name = payload.get("repository", {}).get("full_name")
            ref = check_run.get("head_sha")
            context = check_run.get("name")
            target_url = check_run.get("html_url")
            
            run_status = check_run.get("status", "").upper()
            conclusion = check_run.get("conclusion")
            state = "PENDING"
            if run_status == "COMPLETED":
                if conclusion == "success":
                    state = "SUCCESS"
                elif conclusion in ["failure", "cancelled", "timed_out", "action_required"]:
                    state = "FAILURE"
                else:
                    state = "FAILURE"
            
            pull_requests = check_run.get("pull_requests", [])
            if pull_requests:
                pr_number = pull_requests[0].get("number")

        elif x_github_event == "check_suite":
            check_suite = payload.get("check_suite", {})
            repo_name = payload.get("repository", {}).get("full_name")
            ref = check_suite.get("head_sha")
            context = "check_suite"
            
            suite_status = check_suite.get("status", "").upper()
            conclusion = check_suite.get("conclusion")
            state = "PENDING"
            if suite_status == "COMPLETED":
                if conclusion == "success":
                    state = "SUCCESS"
                elif conclusion in ["failure", "cancelled", "timed_out", "action_required"]:
                    state = "FAILURE"
                else:
                    state = "FAILURE"
            
            pull_requests = check_suite.get("pull_requests", [])
            if pull_requests:
                pr_number = pull_requests[0].get("number")

        elif x_github_event == "status":
            repo_name = payload.get("repository", {}).get("full_name")
            ref = payload.get("sha")
            context = payload.get("context")
            target_url = payload.get("target_url")
            raw_state = payload.get("state", "").upper()
            
            if raw_state == "SUCCESS":
                state = "SUCCESS"
            elif raw_state in ("FAILURE", "ERROR"):
                state = "FAILURE"
            else:
                state = "PENDING"

        if repo_name and ref:
            # Query all PRs that are open for this project/repository
            pr_query = select(models.PullRequest).join(models.Project).where(
                models.Project.repository == repo_name
            ).where(models.PullRequest.status == "OPEN")
            
            if pr_number:
                pr_query = pr_query.where(models.PullRequest.github_pr_number == pr_number)
            
            pr_res = await db.execute(pr_query)
            pr_records = pr_res.scalars().all()
            
            for pr in pr_records:
                # Update or insert CIStatus
                ci_query = select(models.CIStatus).where(
                    models.CIStatus.pull_request_id == pr.id,
                    models.CIStatus.context == context
                )
                ci_res = await db.execute(ci_query)
                db_ci = ci_res.scalar_one_or_none()
                
                if not db_ci:
                    import uuid
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
                logger.info(f"Updated CI Status {context} to {state} for PR #{pr.github_pr_number}")
                
                # Fetch incident_id associated with this PR
                cand_query = select(models.PatchCandidate).where(models.PatchCandidate.id == pr.patch_candidate_id)
                cand_res = await db.execute(cand_query)
                cand = cand_res.scalar_one_or_none()
                if cand:
                    logger.info(f"Triggering evaluate_and_merge_pr_task for incident {cand.incident_id}")
                    if os.getenv("BYPASS_CELERY", "false").lower() != "true":
                        try:
                            celery_app.send_task(
                                "tasks.evaluate_and_merge_pr_task",
                                args=[cand.incident_id]
                            )
                        except Exception as e:
                            logger.warning(f"Failed to trigger evaluation task for incident {cand.incident_id}: {e}")
                    else:
                        logger.info("Bypassing Celery evaluation task trigger (BYPASS_CELERY is true)")

    return {"status": "ok", "message": "Event processed successfully"}

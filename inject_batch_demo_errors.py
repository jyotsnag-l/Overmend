import os
import sys
import time
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure project paths are in sys.path
root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, "apps", "api"))
sys.path.insert(0, os.path.join(root_dir, "apps", "recovery-worker"))
sys.path.insert(0, os.path.join(root_dir, "packages", "shared"))
sys.path.insert(0, os.path.join(root_dir, "packages", "core"))

import logging
logging.getLogger().setLevel(logging.CRITICAL)
for l_name in ["recovery_worker", "sandbox_worker", "github_worker", "api", "api.pipeline", "sandbox_manager", "core.decision_engine"]:
    logging.getLogger(l_name).setLevel(logging.CRITICAL)

from database import AsyncSessionLocal, engine, Base
import models
from sqlalchemy import select

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

BATCH_INCIDENTS = [
    # 4 AUTO-MERGE INCIDENTS
    {
        "type": "NameError",
        "message": "name 'profile_db' is not defined",
        "file": "users.py",
        "line": 5,
        "func": "get_user_profile",
        "mode": "AUTO_MERGE",
        "status": "VERIFIED",
        "trust_score": 0.95,
        "mutation_score": 1.0,
        "diff": """--- a/users.py
+++ b/users.py
@@ -2,4 +2,6 @@ def get_user_profile(user_id: int) -> dict:
     if user_id < 0:
         raise ValueError("Invalid user_id: must be non-negative")
-    return profile_db[user_id]
+    _profiles = {1: {"name": "Alice", "role": "admin"}, 2: {"name": "Bob", "role": "user"}}
+    return _profiles.get(user_id, {"id": user_id, "name": "Guest"})
"""
    },
    {
        "type": "TypeError",
        "message": "unsupported operand type(s) for +: 'NoneType' and 'int'",
        "file": "analytics/counter.py",
        "line": 28,
        "func": "increment_event_count",
        "mode": "AUTO_MERGE",
        "status": "VERIFIED",
        "trust_score": 0.92,
        "mutation_score": 1.0,
        "diff": """--- a/analytics/counter.py
+++ b/analytics/counter.py
@@ -26,4 +26,4 @@ def increment_event_count(metrics: dict, event_name: str, step: int = 1):
-    current = metrics.get(event_name)
-    metrics[event_name] = current + step
+    current = metrics.get(event_name) or 0
+    metrics[event_name] = current + step
     return metrics
"""
    },
    {
        "type": "KeyError",
        "message": "'EXPIRED_CODE'",
        "file": "orders.py",
        "line": 14,
        "func": "calculate_order_total",
        "mode": "AUTO_MERGE",
        "status": "VERIFIED",
        "trust_score": 0.94,
        "mutation_score": 1.0,
        "diff": """--- a/orders.py
+++ b/orders.py
@@ -12,4 +12,4 @@ def calculate_order_total(items: list[dict], discount_code: str | None = None):
     if discount_code:
         discount_table = {"SUMMER20": 0.20, "VIP10": 0.10}
-        total -= total * discount_table[discount_code]
+        total -= total * discount_table.get(discount_code, 0.0)
     return round(total, 2)
"""
    },
    {
        "type": "IndexError",
        "message": "list index out of range in chunk iterator",
        "file": "utils/formatter.py",
        "line": 33,
        "func": "extract_header_token",
        "mode": "AUTO_MERGE",
        "status": "VERIFIED",
        "trust_score": 0.89,
        "mutation_score": 1.0,
        "diff": """--- a/utils/formatter.py
+++ b/utils/formatter.py
@@ -31,3 +31,5 @@ def extract_header_token(auth_header: str) -> str:
     parts = auth_header.strip().split()
-    return parts[1]
+    if len(parts) >= 2:
+        return parts[1]
+    return ""
"""
    },

    # 2 MANUAL REVIEW / HUMAN_REVIEW INCIDENTS
    {
        "type": "ZeroDivisionError",
        "message": "division by zero in refund ratio",
        "file": "payments.py",
        "line": 4,
        "func": "calculate_refund",
        "mode": "HUMAN_REVIEW",
        "status": "HUMAN_REVIEW",
        "trust_score": 0.88,
        "mutation_score": 0.90,
        "policy_reason": "Downgraded from AUTO_MERGE to HUMAN_REVIEW because restricted payment file was touched: payments.py",
        "diff": """--- a/payments.py
+++ b/payments.py
@@ -2,4 +2,4 @@ def calculate_refund(amount: float, refund_ratio: float) -> float:
     if refund_ratio == 0:
-        return amount / 0
+        return 0.0
     return amount * refund_ratio
"""
    },
    {
        "type": "ValueError",
        "message": "Invalid HMAC authentication secret format",
        "file": "auth/jwt_validator.py",
        "line": 18,
        "func": "verify_jwt_token",
        "mode": "HUMAN_REVIEW",
        "status": "HUMAN_REVIEW",
        "trust_score": 0.86,
        "mutation_score": 0.85,
        "policy_reason": "Downgraded to HUMAN_REVIEW because security sensitive authentication file was modified: auth/jwt_validator.py",
        "diff": """--- a/auth/jwt_validator.py
+++ b/auth/jwt_validator.py
@@ -16,4 +16,6 @@ def verify_jwt_token(token: str, secret_key: str):
-    if not secret_key.startswith("sec_"):
-        raise ValueError("Invalid HMAC authentication secret format")
+    if not secret_key:
+        raise ValueError("Secret key cannot be null")
     return jwt.decode(token, secret_key, algorithms=["HS256"])
"""
    }
]

async def seed_organizations_and_users(db):
    for org_id, org_name in [("org_seed", "Seed Enterprise Org"), ("org_demo", "Demo Organization")]:
        org_res = await db.execute(select(models.Organization).where(models.Organization.id == org_id))
        org = org_res.scalar_one_or_none()
        if not org:
            org = models.Organization(id=org_id, name=org_name)
            db.add(org)

        proj_res = await db.execute(select(models.Project).where(models.Project.organization_id == org_id))
        project = proj_res.scalars().first()
        if not project:
            project = models.Project(
                id=f"proj_{org_id[4:]}_main",
                organization_id=org_id,
                name="Production Core API",
                repository="seed-org/seed-repo" if "seed" in org_id else "demo-repo"
            )
            db.add(project)

        repo_res = await db.execute(select(models.Repository).where(models.Repository.organization_id == org_id))
        repo = repo_res.scalars().first()
        if not repo:
            repo = models.Repository(
                id=f"repo_{org_id[4:]}_1",
                organization_id=org_id,
                project_id=project.id,
                name="seed-org/seed-repo" if "seed" in org_id else "demo-repo",
                url="https://github.com/seed-org/seed-repo"
            )
            db.add(repo)

        # Seed Owner User & Membership
        user_res = await db.execute(select(models.User).where(models.User.id == "usr_seed"))
        user = user_res.scalar_one_or_none()
        if not user:
            user = models.User(id="usr_seed", email="seed_user@example.com", name="Seed Owner")
            db.add(user)

        mem_res = await db.execute(select(models.Membership).where(models.Membership.organization_id == org_id, models.Membership.user_id == "usr_seed"))
        mem = mem_res.scalar_one_or_none()
        if not mem:
            mem = models.Membership(
                id=f"mem_{org_id[4:]}_owner",
                organization_id=org_id,
                user_id="usr_seed",
                role="OWNER"
            )
            db.add(mem)

        pol_res = await db.execute(select(models.ProjectPolicy).where(models.ProjectPolicy.organization_id == org_id))
        pol = pol_res.scalars().first()
        if not pol:
            pol = models.ProjectPolicy(
                id=f"pol_{org_id[4:]}",
                organization_id=org_id,
                project_id=project.id,
                auto_merge_threshold=0.85,
                mandatory_review_threshold=0.60,
                restricted_files=["payments.py", "auth/jwt_validator.py"],
                anomaly_frequency_threshold=1,
                anomaly_zscore_threshold=3.0,
                anomaly_ewma_threshold=5.0,
                severity_rules={}
            )
            db.add(pol)

    await db.commit()

async def inject_batch():
    t_start = time.perf_counter()
    async with AsyncSessionLocal() as db:
        await seed_organizations_and_users(db)

        # Retrieve active projects for org_seed and org_demo
        proj_seed_res = await db.execute(select(models.Project).where(models.Project.organization_id == "org_seed"))
        proj_seed = proj_seed_res.scalars().first()

        proj_demo_res = await db.execute(select(models.Project).where(models.Project.organization_id == "org_demo"))
        proj_demo = proj_demo_res.scalars().first()

        created_incidents = []

        now = datetime.now(timezone.utc)

        print("\n" + "="*80)
        print(f"{Colors.BOLD}{Colors.HEADER} FAST BATCH INGESTION: 6 INCIDENTS (4 AUTO-MERGE, 2 MANUAL REVIEW){Colors.RESET}")
        print("="*80)

        for idx, inc_meta in enumerate(BATCH_INCIDENTS, start=1):
            inc_id = f"inc_{uuid.uuid4().hex[:8]}"
            pr_num = 140 + idx
            time_offset = timedelta(minutes=(6 - idx) * 3)
            inc_time = now - time_offset

            # Attach to both orgs or primary org_seed for frontend visibility
            org_id = "org_seed"
            project_id = proj_seed.id
            repo_name = proj_seed.repository

            # 1. Create Incident record
            db_incident = models.Incident(
                id=inc_id,
                organization_id=org_id,
                project_id=project_id,
                exception_type=inc_meta["type"],
                exception_message=inc_meta["message"],
                stack_trace=f'Traceback (most recent call last):\n  File "{inc_meta["file"]}", line {inc_meta["line"]}, in {inc_meta["func"]}\n{inc_meta["type"]}: {inc_meta["message"]}',
                status=inc_meta["status"],
                fingerprint=uuid.uuid4().hex,
                context={"repository": repo_name, "module": inc_meta["file"]},
                occurrence_count=1,
                first_seen=inc_time,
                last_seen=inc_time,
                environment="production",
                affected_repository=repo_name,
                affected_project=proj_seed.name,
                severity="CRITICAL" if "Zero" in inc_meta["type"] or "Value" in inc_meta["type"] else "HIGH",
                is_anomaly=True,
                stack_frames={"frames": [{"file": inc_meta["file"], "line": inc_meta["line"], "function": inc_meta["func"], "code": ""}]},
                rolling_metrics={},
                recovery_job_enqueued=True
            )
            db.add(db_incident)

            # 2. Create Fault Location record (Stage 2)
            fl_rec = models.FaultLocation(
                id=f"fl_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                incident_id=inc_id,
                file_path=inc_meta["file"],
                line_number=inc_meta["line"],
                function_name=inc_meta["func"],
                confidence=0.96,
                created_at=inc_time
            )
            db.add(fl_rec)

            # 3. Create 3 Distinct Candidate Patch records (Patch A, Patch B, Patch C)
            pc_pass_id = f"pc_{uuid.uuid4().hex[:8]}"
            pc_pass = models.PatchCandidate(
                id=pc_pass_id,
                organization_id=org_id,
                incident_id=inc_id,
                diff=inc_meta["diff"],
                explanation=f"Candidate Patch A (Primary AST Fix): Automated safe fallback for {inc_meta['type']} in {inc_meta['file']}:{inc_meta['line']}",
                patch_id=f"patch_{idx}_a",
                affected_files=[inc_meta["file"]],
                reasoning_summary=f"Primary AST patch with null guard for {inc_meta['type']}",
                is_valid=True,
                created_at=inc_time
            )
            db.add(pc_pass)

            # Candidate Patch B (Defensive Exception Guard)
            pc_b_id = f"pc_{uuid.uuid4().hex[:8]}"
            pc_b_diff = inc_meta["diff"].replace("or 0", "if metrics.get(event_name) is not None else 0").replace("get(user_id", "get(int(user_id)")
            pc_b = models.PatchCandidate(
                id=pc_b_id,
                organization_id=org_id,
                incident_id=inc_id,
                diff=pc_b_diff if pc_b_diff != inc_meta["diff"] else inc_meta["diff"] + "\n# Alternative boundary check added",
                explanation=f"Candidate Patch B (Defensive Guard): Type cast & boundary check for {inc_meta['file']}",
                patch_id=f"patch_{idx}_b",
                affected_files=[inc_meta["file"]],
                reasoning_summary=f"Defensive exception handler guard",
                is_valid=True,
                created_at=inc_time + timedelta(seconds=1)
            )
            db.add(pc_b)

            # Candidate Patch C (Schema Default Value)
            pc_c_id = f"pc_{uuid.uuid4().hex[:8]}"
            pc_c = models.PatchCandidate(
                id=pc_c_id,
                organization_id=org_id,
                incident_id=inc_id,
                diff=inc_meta["diff"].replace("+", "+ # Schema fallback\n+"),
                explanation=f"Candidate Patch C (Schema Fallback): Strict fallback return value for {inc_meta['file']}",
                patch_id=f"patch_{idx}_c",
                affected_files=[inc_meta["file"]],
                reasoning_summary=f"Fallback schema return value",
                is_valid=True,
                created_at=inc_time + timedelta(seconds=2)
            )
            db.add(pc_c)

            # 4. Create Sandbox Executions for candidates
            sj_id = f"job_{uuid.uuid4().hex[:8]}"
            db_job = models.SandboxJob(
                id=sj_id,
                organization_id=org_id,
                project_id=project_id,
                patch_candidate_id=pc_pass_id,
                status="SUCCESS",
                config={"test_command": "pytest", "image": "python:3.11-slim"},
                created_at=inc_time
            )
            db.add(db_job)

            db_exec = models.SandboxExecution(
                id=f"exec_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                sandbox_job_id=sj_id,
                exit_code=0,
                stdout="======================== 12 passed in 0.42s ========================",
                stderr="",
                duration=0.42,
                created_at=inc_time
            )
            db.add(db_exec)

            # 5. Create Trust Evaluation & Mutation records (Stage 5) for all 3 patch candidates
            te_id = f"te_{uuid.uuid4().hex[:8]}"
            te_rec = models.TrustEvaluation(
                id=te_id,
                organization_id=org_id,
                patch_candidate_id=pc_pass_id,
                trust_score=inc_meta["trust_score"],
                mutation_score=inc_meta["mutation_score"],
                evidence={"recommendation": "AUTO_MERGE" if inc_meta["mode"] == "AUTO_MERGE" else "HUMAN_REVIEW", "test_pass": True, "mutants_total": 10, "mutants_killed": int(inc_meta["mutation_score"] * 10)},
                created_at=inc_time
            )
            db.add(te_rec)

            # Trust Eval for Candidate B
            te_b_rec = models.TrustEvaluation(
                id=f"te_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                patch_candidate_id=pc_b_id,
                trust_score=round(max(0.60, inc_meta["trust_score"] - 0.08), 2),
                mutation_score=0.80,
                evidence={"recommendation": "HUMAN_REVIEW", "test_pass": True, "mutants_total": 10, "mutants_killed": 8},
                created_at=inc_time + timedelta(seconds=1)
            )
            db.add(te_b_rec)

            # Trust Eval for Candidate C
            te_c_rec = models.TrustEvaluation(
                id=f"te_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                patch_candidate_id=pc_c_id,
                trust_score=round(max(0.55, inc_meta["trust_score"] - 0.14), 2),
                mutation_score=0.70,
                evidence={"recommendation": "HUMAN_REVIEW", "test_pass": True, "mutants_total": 10, "mutants_killed": 7},
                created_at=inc_time + timedelta(seconds=2)
            )
            db.add(te_c_rec)

            mut_rec = models.Mutation(
                id=f"mut_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                trust_evaluation_id=te_id,
                file_path=inc_meta["file"],
                line_number=inc_meta["line"],
                original_operator="==",
                mutated_operator="!=",
                status="KILLED",
                created_at=inc_time
            )
            db.add(mut_rec)

            # 6. Create Decision record (Stage 6)
            is_auto = (inc_meta["mode"] == "AUTO_MERGE")
            dec_id = f"dec_{uuid.uuid4().hex[:8]}"
            dec_rec = models.Decision(
                id=dec_id,
                organization_id=org_id,
                patch_candidate_id=pc_pass_id,
                status="APPROVED" if is_auto else "PENDING",
                action="AUTO_MERGE" if is_auto else "HUMAN_REVIEW",
                reason="Auto-merged: High trust score >= threshold." if is_auto else inc_meta.get("policy_reason", "Review required"),
                decided_by="system:decision_engine" if is_auto else None,
                policy_version="v1.0",
                created_at=inc_time
            )
            db.add(dec_rec)

            # 7. Create Pull Request record (Stage 7)
            pr_rec = models.PullRequest(
                id=f"pr_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                project_id=project_id,
                patch_candidate_id=pc_pass_id,
                github_pr_number=pr_num,
                github_pr_url=f"https://github.com/seed-org/seed-repo/pull/{pr_num}",
                status="MERGED" if is_auto else "OPEN",
                created_at=inc_time
            )
            db.add(pr_rec)

            # 8. Create History records for timeline stages (Stage 1 -> Stage 8 or 6)
            stages = ["DETECTED", "LOCALIZED", "PATCH_GENERATED", "SANDBOX_RUNNING", "TESTED", "TRUST_EVALUATED"]
            if is_auto:
                stages.extend(["DECISION", "PR_CREATED", "VERIFIED"])
            else:
                stages.extend(["HUMAN_REVIEW"])

            for s_idx, st in enumerate(stages):
                db_hist = models.IncidentHistory(
                    id=f"hist_{uuid.uuid4().hex[:8]}",
                    organization_id=org_id,
                    incident_id=inc_id,
                    from_state=stages[s_idx - 1] if s_idx > 0 else None,
                    to_state=st,
                    reason=f"Transitioned to {st}",
                    timestamp=inc_time + timedelta(seconds=s_idx * 2),
                    metadata_info={}
                )
                db.add(db_hist)

            created_incidents.append({
                "num": idx,
                "id": inc_id,
                "type": inc_meta["type"],
                "file": inc_meta["file"],
                "mode": inc_meta["mode"],
                "status": inc_meta["status"],
                "pr": f"#{pr_num}"
            })

        await db.commit()

    dur = time.perf_counter() - t_start
    print(f"\n{Colors.BOLD}⚡ Injected 6 Incidents across all 8 stages in {dur:.2f} seconds!{Colors.RESET}\n")

    print(f"{Colors.BOLD}{Colors.GREEN}--- 4 AUTO-MERGED INCIDENTS (RESOLVED -> STAGE 8 VERIFIED) ---{Colors.RESET}")
    for item in created_incidents[:4]:
        print(f" [{item['num']}] {Colors.CYAN}{item['id']}{Colors.RESET} | {item['type']} in {item['file']} -> {Colors.GREEN}AUTO_MERGED ({item['pr']}){Colors.RESET} -> {Colors.BOLD}VERIFIED{Colors.RESET}")

    print(f"\n{Colors.BOLD}{Colors.YELLOW}--- 2 MANUAL MERGE INCIDENTS (AWAITING SRE APPROVAL IN REVIEW QUEUE) ---{Colors.RESET}")
    for item in created_incidents[4:]:
        print(f" [{item['num']}] {Colors.CYAN}{item['id']}{Colors.RESET} | {item['type']} in {item['file']} -> {Colors.YELLOW}HUMAN_REVIEW ({item['pr']}){Colors.RESET} -> {Colors.BOLD}Awaiting Approval{Colors.RESET}")

    print("\n" + "="*80)
    print(f" {Colors.BOLD}👉 Open React Dashboard:{Colors.RESET}  {Colors.CYAN}http://localhost:3000{Colors.RESET}")
    print(f" {Colors.BOLD}👉 Click 'Incidents' tab:{Colors.RESET}  See all 6 incidents & live timeline graphs")
    print(f" {Colors.BOLD}👉 Click 'Review Queue':{Colors.RESET}  Inspect & manually approve/reject the 2 pending patches!")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(inject_batch())

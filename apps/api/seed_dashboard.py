import asyncio
import uuid
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, delete
from database import AsyncSessionLocal, engine, Base
import models
from seed import seed_data
import retrieval

async def seed_dashboard_data():
    # 1. Run base seeding first
    await seed_data()

    print("Seeding rich 8-step incident recovery data with 3 candidate patches across dual repositories...")
    async with AsyncSessionLocal() as session:
        # Clean existing mock incident data to ensure fresh 8-step progression
        for model_cls in [
            models.CIStatus,
            models.PullRequest,
            models.Decision,
            models.Mutation,
            models.TrustEvaluation,
            models.SandboxJobTransition,
            models.SandboxExecution,
            models.SandboxJob,
            models.PatchCandidate,
            models.FaultLocation,
            models.IncidentHistory,
            models.IncidentEvent,
            models.HistoricalRecoveryRecord,
            models.Incident
        ]:
            try:
                await session.execute(delete(model_cls))
            except Exception:
                pass
        await session.commit()

        org_id = "org_seed"
        proj_gateway = "proj_seed"
        proj_payments = "proj_payments"
        repo_gateway = "seed-org/seed-repo"
        repo_payments = "seed-org/payment-service"
        user_id = "usr_seed"

        # =========================================================================
        # 6 REALISTIC INCIDENTS DEFINITION
        # 4 AUTO-MERGED (Auto-Fixed) + 2 HUMAN REVIEW (Manual Merge)
        # Each Incident has 3 Candidate Patches Generated (Patch A, Patch B, Patch C)
        # =========================================================================
        incidents_data: List[Dict[str, Any]] = [
            # 1. AUTO-FIXED: ZeroDivisionError in refund calculation (payments)
            {
                "id": "inc_payment_zero",
                "project_id": proj_payments,
                "repo": repo_payments,
                "project_name": "Payment & Checkout Service",
                "exc_type": "ZeroDivisionError",
                "exc_msg": "division by zero in calculate_refund_rate()",
                "stack_trace": """Traceback (most recent call last):
  File "payments/service.py", line 184, in calculate_refund_rate
    return amount / total_splits
ZeroDivisionError: division by zero""",
                "status": "MERGED",
                "decision": "AUTO_MERGE",
                "severity": "HIGH",
                "is_anomaly": False,
                "error_rate": 0.045,
                "count": 48,
                "age_hours": 18,
                "file": "payments/service.py",
                "line": 184,
                "func": "calculate_refund_rate",
                "patches": [
                    {
                        "letter": "A",
                        "diff": """--- payments/service.py
+++ payments/service.py
@@ -184,3 +184,3 @@
-    return amount / total_splits
+    return amount / total_splits if total_splits > 0 else 0.0""",
                        "explanation": "Candidate Patch A (Primary AST Guard): Add zero-guard to total_splits denominator to prevent ZeroDivisionError during empty refund batches.",
                        "trust_score": 0.96,
                        "mutation_score": 0.94,
                        "exit_code": 0,
                        "is_winning": True
                    },
                    {
                        "letter": "B",
                        "diff": """--- payments/service.py
+++ payments/service.py
@@ -184,3 +184,5 @@
-    return amount / total_splits
+    try:
+        return amount / total_splits
+    except ZeroDivisionError:
+        return 0.0""",
                        "explanation": "Candidate Patch B (Defensive Try/Except): Wrap arithmetic division in localized ZeroDivisionError handler.",
                        "trust_score": 0.86,
                        "mutation_score": 0.82,
                        "exit_code": 0,
                        "is_winning": False
                    },
                    {
                        "letter": "C",
                        "diff": """--- payments/service.py
+++ payments/service.py
@@ -184,3 +184,4 @@
-    return amount / total_splits
+    splits = max(1, total_splits)
+    return amount / splits""",
                        "explanation": "Candidate Patch C (Clamped Denominator): Clamp denominator total_splits to minimum 1 to avoid zero division.",
                        "trust_score": 0.73,
                        "mutation_score": 0.68,
                        "exit_code": 0,
                        "is_winning": False
                    }
                ],
                "pr_num": 101,
                "pr_url": f"https://github.com/{repo_payments}/pull/101",
                "pr_status": "MERGED",
                "risk_flags": [],
                "reason": "High trust score (0.96) and 100% test pass. Safe arithmetic defensive guard with zero blast radius."
            },
            # 2. AUTO-FIXED: AttributeError NoneType in API Gateway rate limiter
            {
                "id": "inc_null_deref",
                "project_id": proj_gateway,
                "repo": repo_gateway,
                "project_name": "API Gateway & Core Services",
                "exc_type": "AttributeError",
                "exc_msg": "'NoneType' object has no attribute 'get_rate_limit'",
                "stack_trace": """Traceback (most recent call last):
  File "gateway/rate_limiter.py", line 92, in check_rate_limit
    tier_limit = tenant_config.get_rate_limit()
AttributeError: 'NoneType' object has no attribute 'get_rate_limit'""",
                "status": "MERGED",
                "decision": "AUTO_MERGE",
                "severity": "CRITICAL",
                "is_anomaly": True,
                "error_rate": 0.082,
                "count": 142,
                "age_hours": 12,
                "file": "gateway/rate_limiter.py",
                "line": 92,
                "func": "check_rate_limit",
                "patches": [
                    {
                        "letter": "A",
                        "diff": """--- gateway/rate_limiter.py
+++ gateway/rate_limiter.py
@@ -92,3 +92,3 @@
-    tier_limit = tenant_config.get_rate_limit()
+    tier_limit = tenant_config.get_rate_limit() if tenant_config is not None else DEFAULT_RATE_LIMIT""",
                        "explanation": "Candidate Patch A (Primary AST Guard): Provide fallback to DEFAULT_RATE_LIMIT when tenant_config resolution returns None.",
                        "trust_score": 0.95,
                        "mutation_score": 0.92,
                        "exit_code": 0,
                        "is_winning": True
                    },
                    {
                        "letter": "B",
                        "diff": """--- gateway/rate_limiter.py
+++ gateway/rate_limiter.py
@@ -92,3 +92,3 @@
-    tier_limit = tenant_config.get_rate_limit()
+    tier_limit = getattr(tenant_config, 'get_rate_limit', lambda: DEFAULT_RATE_LIMIT)()""",
                        "explanation": "Candidate Patch B (Reflective Helper): Use getattr with fallback lambda for rate limit extraction.",
                        "trust_score": 0.84,
                        "mutation_score": 0.80,
                        "exit_code": 0,
                        "is_winning": False
                    },
                    {
                        "letter": "C",
                        "diff": """--- gateway/rate_limiter.py
+++ gateway/rate_limiter.py
@@ -92,3 +92,5 @@
-    tier_limit = tenant_config.get_rate_limit()
+    try:
+        tier_limit = tenant_config.get_rate_limit()
+    except AttributeError:
+        tier_limit = DEFAULT_RATE_LIMIT""",
                        "explanation": "Candidate Patch C (Exception Wrapper): Wrap method resolution in AttributeError handler.",
                        "trust_score": 0.74,
                        "mutation_score": 0.70,
                        "exit_code": 0,
                        "is_winning": False
                    }
                ],
                "pr_num": 102,
                "pr_url": f"https://github.com/{repo_gateway}/pull/102",
                "pr_status": "MERGED",
                "risk_flags": [],
                "reason": "Defensive NoneType fallback verified in sandbox. Trust score 0.95 satisfies auto-merge threshold."
            },
            # 3. AUTO-FIXED: IndexError out of bounds in order processor (payments)
            {
                "id": "inc_order_index",
                "project_id": proj_payments,
                "repo": repo_payments,
                "project_name": "Payment & Checkout Service",
                "exc_type": "IndexError",
                "exc_msg": "list index out of range in process_batch_items()",
                "stack_trace": """Traceback (most recent call last):
  File "order/processor.py", line 203, in process_batch_items
    primary_item = items[0]
IndexError: list index out of range""",
                "status": "MERGED",
                "decision": "AUTO_MERGE",
                "severity": "MEDIUM",
                "is_anomaly": False,
                "error_rate": 0.018,
                "count": 19,
                "age_hours": 8,
                "file": "order/processor.py",
                "line": 203,
                "func": "process_batch_items",
                "patches": [
                    {
                        "letter": "A",
                        "diff": """--- order/processor.py
+++ order/processor.py
@@ -203,3 +203,3 @@
-    primary_item = items[0]
+    if not items:
+        return BatchResult(processed=0, status="EMPTY")
+    primary_item = items[0]""",
                        "explanation": "Candidate Patch A (Primary Early Return): Add early return for empty batch lists before indexing the primary item.",
                        "trust_score": 0.97,
                        "mutation_score": 0.95,
                        "exit_code": 0,
                        "is_winning": True
                    },
                    {
                        "letter": "B",
                        "diff": """--- order/processor.py
+++ order/processor.py
@@ -203,3 +203,4 @@
-    primary_item = items[0]
+    primary_item = next(iter(items), None)
+    if primary_item is None:
+        return BatchResult(processed=0, status="EMPTY")""",
                        "explanation": "Candidate Patch B (Safe Iterator): Use next(iter(items), None) for safe initial item access.",
                        "trust_score": 0.85,
                        "mutation_score": 0.82,
                        "exit_code": 0,
                        "is_winning": False
                    },
                    {
                        "letter": "C",
                        "diff": """--- order/processor.py
+++ order/processor.py
@@ -203,3 +203,3 @@
-    primary_item = items[0]
+    primary_item = items[0] if len(items) > 0 else Item.empty()""",
                        "explanation": "Candidate Patch C (Ternary Fallback): Ternary fallback to Item.empty() on index bound error.",
                        "trust_score": 0.72,
                        "mutation_score": 0.65,
                        "exit_code": 0,
                        "is_winning": False
                    }
                ],
                "pr_num": 103,
                "pr_url": f"https://github.com/{repo_payments}/pull/103",
                "pr_status": "MERGED",
                "risk_flags": [],
                "reason": "Boundary condition check passed mutation testing with 95% kill rate. Auto-merged safely."
            },
            # 4. AUTO-FIXED: JSONDecodeError invalid webhook formatting (gateway)
            {
                "id": "inc_json_payload",
                "project_id": proj_gateway,
                "repo": repo_gateway,
                "project_name": "API Gateway & Core Services",
                "exc_type": "JSONDecodeError",
                "exc_msg": "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
                "stack_trace": """Traceback (most recent call last):
  File "webhooks/parser.py", line 67, in parse_incoming_event
    return json.loads(raw_body)
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes""",
                "status": "MERGED",
                "decision": "AUTO_MERGE",
                "severity": "MEDIUM",
                "is_anomaly": False,
                "error_rate": 0.024,
                "count": 31,
                "age_hours": 5,
                "file": "webhooks/parser.py",
                "line": 67,
                "func": "parse_incoming_event",
                "patches": [
                    {
                        "letter": "A",
                        "diff": """--- webhooks/parser.py
+++ webhooks/parser.py
@@ -67,3 +67,5 @@
-    return json.loads(raw_body)
+    try:
+        return json.loads(raw_body)
+    except (json.JSONDecodeError, TypeError):
+        return {"raw": raw_body, "parse_error": True}""",
                        "explanation": "Candidate Patch A (Graceful Exception Wrapper): Wrap json.loads in exception handler to prevent unhandled 500 crashes on malformed incoming webhook payloads.",
                        "trust_score": 0.94,
                        "mutation_score": 0.91,
                        "exit_code": 0,
                        "is_winning": True
                    },
                    {
                        "letter": "B",
                        "diff": """--- webhooks/parser.py
+++ webhooks/parser.py
@@ -67,3 +67,5 @@
-    return json.loads(raw_body)
+    if not raw_body or not isinstance(raw_body, (str, bytes)):
+        return {"parse_error": True, "reason": "empty_payload"}
+    return json.loads(raw_body)""",
                        "explanation": "Candidate Patch B (Pre-Validation Guard): Validate payload type and non-empty state before JSON parsing.",
                        "trust_score": 0.83,
                        "mutation_score": 0.79,
                        "exit_code": 0,
                        "is_winning": False
                    },
                    {
                        "letter": "C",
                        "diff": """--- webhooks/parser.py
+++ webhooks/parser.py
@@ -67,3 +67,5 @@
-    return json.loads(raw_body)
+    clean_body = raw_body.strip() if hasattr(raw_body, 'strip') else "{}"
+    return json.loads(clean_body) if clean_body else {}""",
                        "explanation": "Candidate Patch C (Sanitizer Guard): Sanitize string whitespace and fallback to empty dict.",
                        "trust_score": 0.71,
                        "mutation_score": 0.66,
                        "exit_code": 0,
                        "is_winning": False
                    }
                ],
                "pr_num": 104,
                "pr_url": f"https://github.com/{repo_gateway}/pull/104",
                "pr_status": "MERGED",
                "risk_flags": [],
                "reason": "Standard JSON parsing exception safety wrapper. Trust score 0.94 satisfies auto-merge policy."
            },
            # 5. HUMAN REVIEW (Manual Merge): KeyError in webhook signature verification (gateway)
            {
                "id": "inc_auth_key",
                "project_id": proj_gateway,
                "repo": repo_gateway,
                "project_name": "API Gateway & Core Services",
                "exc_type": "KeyError",
                "exc_msg": "'stripe_signature' header not found in request payload",
                "stack_trace": """Traceback (most recent call last):
  File "auth/verification.py", line 42, in verify_webhook_signature
    signature = request.headers['stripe_signature']
KeyError: 'stripe_signature'""",
                "status": "HUMAN_REVIEW",
                "decision": "HUMAN_REVIEW",
                "severity": "CRITICAL",
                "is_anomaly": True,
                "error_rate": 0.115,
                "count": 184,
                "age_hours": 3,
                "file": "auth/verification.py",
                "line": 42,
                "func": "verify_webhook_signature",
                "patches": [
                    {
                        "letter": "A",
                        "diff": """--- auth/verification.py
+++ auth/verification.py
@@ -42,3 +42,3 @@
-    signature = request.headers['stripe_signature']
+    signature = request.headers.get('stripe_signature')
+    if not signature:
+        raise AuthenticationError("Missing required stripe_signature header")""",
                        "explanation": "Candidate Patch A (Explicit Auth Guard): Use dict.get() for header access and raise an explicit AuthenticationError instead of unhandled KeyError.",
                        "trust_score": 0.95,
                        "mutation_score": 0.90,
                        "exit_code": 0,
                        "is_winning": True
                    },
                    {
                        "letter": "B",
                        "diff": """--- auth/verification.py
+++ auth/verification.py
@@ -42,3 +42,4 @@
-    signature = request.headers['stripe_signature']
+    headers_lower = {k.lower(): v for k, v in request.headers.items()}
+    signature = headers_lower.get('stripe-signature') or headers_lower.get('stripe_signature')
+    if not signature:
+        raise AuthenticationError("Stripe signature header absent")""",
                        "explanation": "Candidate Patch B (Case-Insensitive Match): Lowercase header dictionary normalization.",
                        "trust_score": 0.88,
                        "mutation_score": 0.84,
                        "exit_code": 0,
                        "is_winning": False
                    },
                    {
                        "letter": "C",
                        "diff": """--- auth/verification.py
+++ auth/verification.py
@@ -42,3 +42,3 @@
-    signature = request.headers['stripe_signature']
+    signature = request.headers.get('stripe_signature', '')""",
                        "explanation": "Candidate Patch C (Default Empty String): Default signature to empty string to avoid unhandled KeyError.",
                        "trust_score": 0.69,
                        "mutation_score": 0.61,
                        "exit_code": 0,
                        "is_winning": False
                    }
                ],
                "pr_num": 105,
                "pr_url": f"https://github.com/{repo_gateway}/pull/105",
                "pr_status": "OPEN",
                "risk_flags": ["AUTHENTICATION_MODIFIED"],
                "reason": "Downgraded from AUTO_MERGE to HUMAN_REVIEW because hard restrictions were triggered: authentication logic modified in auth/verification.py."
            },
            # 6. HUMAN REVIEW (Manual Merge): OperationalError DB Pool Exhaustion (payments)
            {
                "id": "inc_db_pool_timeout",
                "project_id": proj_payments,
                "repo": repo_payments,
                "project_name": "Payment & Checkout Service",
                "exc_type": "OperationalError",
                "exc_msg": "TimeoutError: QueuePool limit of size 20 overflow 10 reached, connection timed out",
                "stack_trace": """Traceback (most recent call last):
  File "core/db/pool.py", line 118, in acquire_connection
    conn = pool.get_connection(timeout=5.0)
psycopg2.OperationalError: QueuePool limit reached, connection timed out""",
                "status": "HUMAN_REVIEW",
                "decision": "HUMAN_REVIEW",
                "severity": "CRITICAL",
                "is_anomaly": True,
                "error_rate": 0.092,
                "count": 96,
                "age_hours": 1,
                "file": "core/db/pool.py",
                "line": 118,
                "func": "acquire_connection",
                "patches": [
                    {
                        "letter": "A",
                        "diff": """--- core/db/pool.py
+++ core/db/pool.py
@@ -118,3 +118,4 @@
-    conn = pool.get_connection(timeout=5.0)
+    pool.recycle_stale_connections(max_age_seconds=60)
+    conn = pool.get_connection(timeout=10.0)""",
                        "explanation": "Candidate Patch A (Recycle & Extended Timeout): Recycle stale leaked connections before acquiring new handles and extend pool acquisition timeout from 5s to 10s.",
                        "trust_score": 0.76,
                        "mutation_score": 0.72,
                        "exit_code": 0,
                        "is_winning": True
                    },
                    {
                        "letter": "B",
                        "diff": """--- core/db/pool.py
+++ core/db/pool.py
@@ -118,3 +118,5 @@
-    conn = pool.get_connection(timeout=5.0)
+    for attempt in range(3):
+        try:
+            return pool.get_connection(timeout=3.0 * (attempt + 1))
+        except TimeoutError:
+            if attempt == 2: raise""",
                        "explanation": "Candidate Patch B (Exponential Retry): Retry connection acquisition 3 times with progressive backoff.",
                        "trust_score": 0.74,
                        "mutation_score": 0.68,
                        "exit_code": 0,
                        "is_winning": False
                    },
                    {
                        "letter": "C",
                        "diff": """--- core/db/pool.py
+++ core/db/pool.py
@@ -118,3 +118,4 @@
-    conn = pool.get_connection(timeout=5.0)
+    pool.expand_max_overflow(increment=5)
+    conn = pool.get_connection(timeout=8.0)""",
                        "explanation": "Candidate Patch C (Dynamic Overflow Expansion): Dynamically increase pool overflow capacity.",
                        "trust_score": 0.65,
                        "mutation_score": 0.59,
                        "exit_code": 0,
                        "is_winning": False
                    }
                ],
                "pr_num": 106,
                "pr_url": f"https://github.com/{repo_payments}/pull/106",
                "pr_status": "OPEN",
                "risk_flags": ["HIGH_BLAST_RADIUS", "DATABASE_MODIFIED"],
                "reason": "Downgraded to HUMAN_REVIEW due to database connection infrastructure modification with high blast radius (0.35)."
            }
        ]

        # Process and seed each of the 6 incidents with complete 8-step lifecycle & 3 candidate patches
        for item in incidents_data:
            inc_id: str = str(item["id"])
            age_hours: float = float(item["age_hours"])
            created_time = datetime.now(timezone.utc) - timedelta(hours=age_hours)

            # 1. Incident Record
            incident = models.Incident(
                id=inc_id,
                organization_id=org_id,
                project_id=str(item["project_id"]),
                exception_type=str(item["exc_type"]),
                exception_message=str(item["exc_msg"]),
                stack_trace=str(item["stack_trace"]),
                status=str(item["status"]),
                fingerprint=f"fp_{uuid.uuid4().hex[:12]}",
                context={"ip": "10.0.4.12", "service": str(item["project_name"]), "env": "production"},
                created_at=created_time,
                occurrence_count=int(item["count"]),
                first_seen=created_time - timedelta(hours=2),
                last_seen=created_time + timedelta(minutes=15),
                error_rate=float(item["error_rate"]),
                environment="production",
                affected_repository=str(item["repo"]),
                affected_project=str(item["project_name"]),
                severity=str(item["severity"]),
                is_anomaly=bool(item["is_anomaly"]),
                recovery_job_enqueued=True
            )
            session.add(incident)

            # 2. Complete 8-Step Timeline Transitions
            steps = [
                ("DETECTED", "LOCALIZED", f"Fault localized via AST callstack analysis to {item['file']}:{item['line']} in {item['func']}().", 0.15),
                ("LOCALIZED", "PATCH_GENERATED", "Synthesized 3 candidate patches (Patch A, Patch B, Patch C) with semantic AST validation.", 0.28),
                ("PATCH_GENERATED", "SANDBOX_RUNNING", "Spawned isolated ephemeral Docker container test environment for all candidates.", 0.38),
                ("SANDBOX_RUNNING", "TRUST_EVALUATED", f"Executed pytest suite in container (Exit Code: 0). Trust Engine evaluated mutant kill matrix.", 0.55),
                ("TRUST_EVALUATED", "DECISION", f"Decision Engine evaluated policy: {item['decision']}. {item['reason']}", 0.65)
            ]
            if item["decision"] == "AUTO_MERGE":
                steps.append(("DECISION", "PR_CREATED", f"GitHub App Pull Request #{item['pr_num']} created with automated recovery manifest.", 0.75))
                steps.append(("PR_CREATED", "VERIFIED", f"GitHub Actions CI checks passed (100% green). Pull Request #{item['pr_num']} auto-merged into main.", 0.90))
            else:
                steps.append(("DECISION", "HUMAN_REVIEW", f"Automated merge paused. Incident queued for SRE manual review due to: {item['reason']}", 0.75))

            for from_s, to_s, reason_txt, offset_sec in steps:
                step_hist = models.IncidentHistory(
                    id=f"hist_{uuid.uuid4().hex[:8]}",
                    organization_id=org_id,
                    incident_id=inc_id,
                    from_state=from_s,
                    to_state=to_s,
                    reason=reason_txt,
                    transitioned_by=user_id if "HUMAN" in to_s else None,
                    metadata_info={"duration_sec": offset_sec, "repo": str(item["repo"])},
                    timestamp=created_time + timedelta(seconds=offset_sec)
                )
                session.add(step_hist)

                step_event = models.IncidentEvent(
                    id=f"ev_{uuid.uuid4().hex[:8]}",
                    organization_id=org_id,
                    incident_id=inc_id,
                    event_type="STATE_CHANGE",
                    payload={"from_state": from_s, "to_state": to_s, "reason": reason_txt},
                    timestamp=created_time + timedelta(seconds=offset_sec)
                )
                session.add(step_event)

            # 3. Fault Location Record
            loc = models.FaultLocation(
                id=f"loc_{inc_id}",
                organization_id=org_id,
                incident_id=inc_id,
                file_path=str(item["file"]),
                line_number=int(item["line"]),
                function_name=str(item["func"]),
                confidence=0.96
            )
            session.add(loc)

            # 4. Generate all 3 Patch Candidates, Sandbox Executions & Trust Evaluations
            winning_pc_id = None
            patches_list: List[Dict[str, Any]] = item["patches"]  # type: ignore
            for p_idx, p_data in enumerate(patches_list):
                letter_str = str(p_data["letter"])
                pc_id = f"pc_{inc_id}_{letter_str.lower()}"
                is_winning = bool(p_data.get("is_winning", False))
                if is_winning:
                    winning_pc_id = pc_id

                patch_cand = models.PatchCandidate(
                    id=pc_id,
                    organization_id=org_id,
                    incident_id=inc_id,
                    diff=str(p_data["diff"]),
                    explanation=str(p_data["explanation"]),
                    patch_id=f"patch_{inc_id}_{letter_str.lower()}",
                    affected_files=[str(item["file"])],
                    estimated_change_scope="1 file, +2 lines, -1 line",
                    reasoning_summary=str(p_data["explanation"]),
                    is_valid=True,
                    created_at=created_time + timedelta(seconds=p_idx * 2)
                )
                session.add(patch_cand)

                # Sandbox Job & Executions
                job_id = f"job_{inc_id}_{letter_str.lower()}"
                sbox_job = models.SandboxJob(
                    id=job_id,
                    organization_id=org_id,
                    project_id=str(item["project_id"]),
                    patch_candidate_id=pc_id,
                    status="COMPLETED",
                    config={"image": "python:3.11-slim", "timeout": 300, "cpu_limit": 0.5, "memory_limit": "512m"},
                    created_at=created_time + timedelta(seconds=p_idx * 2)
                )
                session.add(sbox_job)

                # Sandbox Execution with full pytest output and telemetry
                sbox_exec = models.SandboxExecution(
                    id=f"exec_{inc_id}_{letter_str.lower()}",
                    organization_id=org_id,
                    sandbox_job_id=job_id,
                    stdout=f"""============================= test session starts =============================
platform linux -- Python 3.11.8, pytest-7.4.4
rootdir: /sandbox/workspace/{item['repo']}
collected 4 items

tests/test_verification.py::test_reproduction_before_patch PASSED       [ 25%]
tests/test_verification.py::test_candidate_fix_applied PASSED            [ 50%]
tests/test_verification.py::test_edge_cases_boundary PASSED              [ 75%]
tests/test_verification.py::test_regression_suite PASSED                 [100%]

============================== 4 passed in 0.04s ==============================""",
                    stderr="",
                    exit_code=int(p_data.get("exit_code", 0)),
                    duration=0.04,
                    resource_usage={
                        "max_memory_mb": 64.0,
                        "avg_cpu_percent": 14.5,
                        "cpu_usage_pct": [6.0, 14.5, 28.0, 18.0, 8.0],
                        "memory_mb": [52.0, 58.0, 64.0, 64.0, 64.0]
                    },
                    created_at=created_time + timedelta(seconds=p_idx * 2 + 1)
                )
                session.add(sbox_exec)

                # 5 Sandbox Stage Transitions for smooth live streaming
                stages_seq = [
                    ("PENDING", "CLONING", f"Cloning git repository {item['repo']} into ephemeral sandbox container...", 0.05),
                    ("CLONING", "INSTALLING_DEPS", "Installing Python virtual environment and dependencies (pytest, hypothesis)...", 0.15),
                    ("INSTALLING_DEPS", "PATCHING", f"Applying Candidate Patch {letter_str} to target AST node...", 0.25),
                    ("PATCHING", "TEST_RUNNING", "Running pytest validation test suite in container...", 0.35),
                    ("TEST_RUNNING", "COMPLETED", "All 4 test assertions passed (Exit Code 0). Emitting hardware telemetry.", 0.45)
                ]
                for from_st, to_st, det, off in stages_seq:
                    session.add(models.SandboxJobTransition(
                        id=f"sbtr_{inc_id}_{letter_str.lower()}_{to_st.lower()}",
                        organization_id=org_id,
                        sandbox_job_id=job_id,
                        from_state=from_st,
                        to_state=to_st,
                        details=det,
                        metadata_info={"duration": off, "letter": letter_str},
                        timestamp=created_time + timedelta(seconds=off)
                    ))

                # Trust Evaluation & Mutants
                eval_id = f"eval_{inc_id}_{letter_str.lower()}"
                p_mut_score = float(p_data.get("mutation_score", 0.9))
                p_trust_score = float(p_data.get("trust_score", 0.95))
                killed = int(10 * p_mut_score)
                survived = 10 - killed
                trust_eval = models.TrustEvaluation(
                    id=eval_id,
                    organization_id=org_id,
                    patch_candidate_id=pc_id,
                    trust_score=p_trust_score,
                    mutation_score=p_mut_score,
                    evidence={
                        "test_pass": True,
                        "mutants_total": 10,
                        "mutants_killed": killed,
                        "mutants_survived": survived,
                        "recommendation": "AUTO_MERGE" if p_trust_score >= 0.90 and not item["risk_flags"] else "HUMAN_REVIEW",
                        "risk_flags": item["risk_flags"] if is_winning else []
                    },
                    created_at=created_time + timedelta(seconds=p_idx * 2 + 1)
                )
                session.add(trust_eval)

                # Add mutation record
                session.add(models.Mutation(
                    id=f"mut_{inc_id}_{letter_str.lower()}",
                    organization_id=org_id,
                    trust_evaluation_id=eval_id,
                    file_path=str(item["file"]),
                    line_number=int(item["line"]),
                    original_operator="DEFAULT_LOOKUP",
                    mutated_operator="NULL_FALLBACK",
                    status="KILLED"
                ))

            # 5. Primary Decision Record (Linked to Winning Patch)
            winning_patch: Dict[str, Any] = patches_list[0]
            winning_trust: float = float(winning_patch.get("trust_score", 0.95))
            decision_rec = models.Decision(
                id=f"dec_{inc_id}",
                organization_id=org_id,
                patch_candidate_id=winning_pc_id,
                status="APPROVED" if item["decision"] == "AUTO_MERGE" else "PENDING_REVIEW",
                action=str(item["decision"]),
                reason=str(item["reason"]),
                decided_by=user_id if item["decision"] != "AUTO_MERGE" else None,
                policy_version="v2.1",
                actor_system="AutonomousDecisionEngine/Core",
                policy_checks=[
                    {"check": "test_suite_passed", "passed": True, "description": "Container pytest suite passed (100%)"},
                    {"check": "ci_status_passed", "passed": True, "description": "GitHub Actions CI workflow validation passed"},
                    {"check": "blast_radius_limit", "passed": True, "description": "Blast radius within configured policy limits"},
                    {"check": "no_authentication_changes", "passed": "AUTHENTICATION_MODIFIED" not in item["risk_flags"], "description": "Authentication boundary protection"},
                    {"check": "no_database_migration_changes", "passed": "DATABASE_MODIFIED" not in item["risk_flags"], "description": "Database migration boundary protection"},
                    {"check": "auto_merge_threshold_check", "passed": winning_trust >= 0.90, "description": f"Trust score {winning_trust} satisfies policy threshold 0.90"}
                ],
                risk_flags=item["risk_flags"]  # type: ignore
            )
            session.add(decision_rec)

            # 6. Pull Request & CI Status
            pr_rec = models.PullRequest(
                id=f"pr_{inc_id}",
                organization_id=org_id,
                project_id=item["project_id"],
                patch_candidate_id=winning_pc_id,
                github_pr_number=item["pr_num"],
                github_pr_url=item["pr_url"],
                status=item["pr_status"]
            )
            session.add(pr_rec)

            ci_rec = models.CIStatus(
                id=f"ci_{inc_id}",
                organization_id=org_id,
                pull_request_id=pr_rec.id,
                status="SUCCESS",
                context="continuous-integration/github-actions",
                target_url=f"{item['pr_url']}/checks"
            )
            session.add(ci_rec)

            # 7. Historical Recovery Record for Semantic Retrieval
            embedding = retrieval.get_deterministic_mock_embedding(f"{item['exc_type']}: {item['exc_msg']}")
            hist_rec = models.HistoricalRecoveryRecord(
                id=f"rec_{inc_id}",
                organization_id=org_id,
                incident_id=inc_id,
                incident={"id": inc_id, "type": item["exc_type"], "message": item["exc_msg"], "repo": item["repo"]},
                stack_trace=item["stack_trace"],
                fault_location={"file": item["file"], "line": item["line"], "function": item["func"]},
                patch=winning_patch["diff"],
                outcome="SUCCESS" if item["status"] == "MERGED" else "PENDING_REVIEW",
                trust_score=winning_patch["trust_score"],
                human_decision="AUTO_APPROVED" if item["decision"] == "AUTO_MERGE" else "PENDING_HUMAN_REVIEW",
                final_result=item["status"],
                embedding=embedding
            )
            session.add(hist_rec)

        await session.commit()
        print("All 6 incidents seeded with complete 8-step lifecycle, 3 candidate patches each, and sandbox telemetry!")

if __name__ == "__main__":
    asyncio.run(seed_dashboard_data())

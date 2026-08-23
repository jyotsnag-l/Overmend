import logging
import fnmatch
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("core.decision_engine")

DEFAULT_AUTO_MERGE_THRESHOLD = 0.90
DEFAULT_HUMAN_REVIEW_THRESHOLD = 0.70
DEFAULT_MAX_PATCH_SIZE = 100
DEFAULT_MAX_FILES_CHANGED = 10
DEFAULT_MAX_BLAST_RADIUS = 0.3

# Patterns to match filenames against restriction categories
RESTRICTION_PATTERNS = {
    "authentication": [
        "*auth*", "*login*", "*signup*", "*session*", "*token*", "*jwt*", "*oauth*", "*credential*", "*password*", "*signin*", "*signout*"
    ],
    "authorization": [
        "*permission*", "*role*", "*acl*", "*policy*", "*access*", "*rbac*"
    ],
    "payment logic": [
        "*pay*", "*stripe*", "*billing*", "*checkout*", "*card*", "*transaction*", "*invoice*", "*wallet*", "*refund*", "*subscription*", "*ledger*"
    ],
    "database migrations": [
        "*migration*", "*alembic*", "*flyway*", "*schema*", "*db_version*", "*.sql", "*ddl*", "*changelog*"
    ],
    "secrets": [
        "*secret*", "*key*", "*cert*", "*private_key*", "*.env"
    ],
    "infrastructure": [
        "*docker*", "*kubernetes*", "*terraform*", "*k8s*", "*helm*", "*ansible*", "*deploy*", "Dockerfile", "*.yaml", "*.yml", "docker-compose*"
    ],
    "security policies": [
        "*security*", "*policy*", "*cors*", "*csp*", "*firewall*", "*waf*"
    ]
}

class DecisionEngine:
    def __init__(self, policy_version: str = "v1"):
        self.policy_version = policy_version

    def evaluate(
        self,
        trust_score: float,
        mutation_score: float,
        test_result: bool,
        patch_size: int,
        files_changed: List[str],
        sensitive_file_flags: Any,
        blast_radius: float,
        repository_policy: Optional[Dict[str, Any]] = None,
        ci_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates a candidate patch based on trust/mutation scores and hard restrictions.
        
        Returns:
            Dict containing decision (AUTO_MERGE, HUMAN_REVIEW, REJECT), reason, policy_checks, and risk_flags.
        """
        logger.info(f"Evaluating decision with trust_score={trust_score}, mutation_score={mutation_score}, test_result={test_result}")

        # Resolve policy overrides or defaults
        policy = repository_policy or {}
        auto_merge_threshold = policy.get("auto_merge_threshold")
        if auto_merge_threshold is None:
            auto_merge_threshold = policy.get("auto_merge")
        if auto_merge_threshold is None:
            auto_merge_threshold = DEFAULT_AUTO_MERGE_THRESHOLD

        human_review_threshold = policy.get("human_review_threshold")
        if human_review_threshold is None:
            human_review_threshold = policy.get("mandatory_review_threshold")
        if human_review_threshold is None:
            human_review_threshold = policy.get("human_review")
        if human_review_threshold is None:
            human_review_threshold = DEFAULT_HUMAN_REVIEW_THRESHOLD

        max_patch_size = policy.get("max_patch_size", DEFAULT_MAX_PATCH_SIZE)
        max_files_changed = policy.get("max_files_changed", DEFAULT_MAX_FILES_CHANGED)
        max_blast_radius = policy.get("max_blast_radius", DEFAULT_MAX_BLAST_RADIUS)
        require_ci_success = policy.get("require_ci_success", True)
        restricted_files_policy = policy.get("restricted_files", [])

        # 1. Evaluate policy checks & hard restrictions
        policy_checks = []
        risk_flags = []
        triggered_restrictions = []

        # Helper to log and append check
        def add_check(name: str, passed: bool, desc: str):
            policy_checks.append({
                "check": name,
                "passed": passed,
                "description": desc
            })

        # Check Test result
        add_check("test_suite_passed", test_result, "Local test suite execution success status")
        if not test_result:
            risk_flags.append("TEST_SUITE_FAILED")
            triggered_restrictions.append("failed local tests")

        # Check CI status if required
        if require_ci_success and ci_status is not None:
            ci_passed = ci_status.upper() == "SUCCESS"
            add_check("ci_status_passed", ci_passed, f"CI pipeline status validation (status: {ci_status})")
            if not ci_passed:
                risk_flags.append("CI_PIPELINE_FAILED")
                triggered_restrictions.append(f"CI status is {ci_status}")
        else:
            add_check("ci_status_passed", True, "CI status check skipped (no status provided or not required)")

        # Check blast radius
        blast_passed = blast_radius <= max_blast_radius
        add_check(
            "blast_radius_limit",
            blast_passed,
            f"Blast radius {blast_radius} check against limit {max_blast_radius}"
        )
        if not blast_passed:
            risk_flags.append("HIGH_BLAST_RADIUS")
            triggered_restrictions.append(f"blast radius {blast_radius} exceeds {max_blast_radius}")

        # Check sensitive file flags
        # If sensitive_file_flags is boolean True, or if it is a dictionary with any True value
        sensitive_flag_triggered = False
        if isinstance(sensitive_file_flags, bool):
            sensitive_flag_triggered = sensitive_file_flags
        elif isinstance(sensitive_file_flags, dict):
            sensitive_flag_triggered = any(sensitive_file_flags.values())

        # Match files against patterns and build categorization checks
        category_matches = {cat: [] for cat in RESTRICTION_PATTERNS}
        for file in files_changed:
            normalized_file = file.replace("\\", "/").lower()
            for category, patterns in RESTRICTION_PATTERNS.items():
                for pattern in patterns:
                    if fnmatch.fnmatch(normalized_file, pattern):
                        category_matches[category].append(file)
                        break

        # Match files against configured restricted files
        configured_restricted_matches = []
        for file in files_changed:
            normalized_file = file.replace("\\", "/").lower()
            for pattern in restricted_files_policy:
                if fnmatch.fnmatch(normalized_file, pattern.lower()):
                    configured_restricted_matches.append(file)
                    break

        # Check authentication files
        auth_passed = len(category_matches["authentication"]) == 0
        if isinstance(sensitive_file_flags, dict) and (sensitive_file_flags.get("authentication") or sensitive_file_flags.get("auth")):
            auth_passed = False
        add_check("no_authentication_changes", auth_passed, "No modifications involving authentication logic")
        if not auth_passed:
            triggered_restrictions.append("authentication changes")
            risk_flags.append("AUTHENTICATION_MODIFIED")

        # Check authorization files
        authz_passed = len(category_matches["authorization"]) == 0
        if isinstance(sensitive_file_flags, dict) and sensitive_file_flags.get("authorization"):
            authz_passed = False
        add_check("no_authorization_changes", authz_passed, "No modifications involving authorization logic")
        if not authz_passed:
            triggered_restrictions.append("authorization changes")
            risk_flags.append("AUTHORIZATION_MODIFIED")

        # Check payment logic files
        payment_passed = len(category_matches["payment logic"]) == 0
        if isinstance(sensitive_file_flags, dict) and (sensitive_file_flags.get("payment logic") or sensitive_file_flags.get("payment") or sensitive_file_flags.get("billing")):
            payment_passed = False
        add_check("no_payment_logic_changes", payment_passed, "No modifications involving payment / billing logic")
        if not payment_passed:
            triggered_restrictions.append("payment logic changes")
            risk_flags.append("PAYMENT_LOGIC_MODIFIED")

        # Check database migration files
        migration_passed = len(category_matches["database migrations"]) == 0
        if isinstance(sensitive_file_flags, dict) and (sensitive_file_flags.get("database migrations") or sensitive_file_flags.get("migration") or sensitive_file_flags.get("database")):
            migration_passed = False
        add_check("no_database_migration_changes", migration_passed, "No modifications involving database schema migrations")
        if not migration_passed:
            triggered_restrictions.append("database migrations changes")
            risk_flags.append("DATABASE_MIGRATION_MODIFIED")

        # Check secrets
        secrets_passed = len(category_matches["secrets"]) == 0
        if isinstance(sensitive_file_flags, dict) and (sensitive_file_flags.get("secrets") or sensitive_file_flags.get("secret")):
            secrets_passed = False
        add_check("no_secrets_changes", secrets_passed, "No modifications involving passwords, credentials, or keys")
        if not secrets_passed:
            triggered_restrictions.append("secrets changes")
            risk_flags.append("SECRETS_MODIFIED")

        # Check infrastructure files
        infra_passed = len(category_matches["infrastructure"]) == 0
        if isinstance(sensitive_file_flags, dict) and (sensitive_file_flags.get("infrastructure") or sensitive_file_flags.get("infra")):
            infra_passed = False
        add_check("no_infrastructure_changes", infra_passed, "No modifications involving infrastructure configuration")
        if not infra_passed:
            triggered_restrictions.append("infrastructure changes")
            risk_flags.append("INFRASTRUCTURE_MODIFIED")

        # Check security policies files
        sec_policies_passed = len(category_matches["security policies"]) == 0
        if isinstance(sensitive_file_flags, dict) and sensitive_file_flags.get("security policies"):
            sec_policies_passed = False
        add_check("no_security_policy_changes", sec_policies_passed, "No modifications involving security policies")
        if not sec_policies_passed:
            triggered_restrictions.append("security policies changes")
            risk_flags.append("SECURITY_POLICIES_MODIFIED")

        # Check large refactors
        refactor_passed = (patch_size <= max_patch_size) and (len(files_changed) <= max_files_changed)
        add_check(
            "no_large_refactors",
            refactor_passed,
            f"Patch size {patch_size} lines and {len(files_changed)} files changed within limits (max patch size: {max_patch_size}, max files: {max_files_changed})"
        )
        if not refactor_passed:
            triggered_restrictions.append("large refactor")
            risk_flags.append("LARGE_REFACTOR")

        # Check configured restricted files
        restricted_files_passed = len(configured_restricted_matches) == 0
        add_check(
            "no_configured_restricted_files",
            restricted_files_passed,
            f"No modifications to files configured as restricted: {restricted_files_policy}"
        )
        if not restricted_files_passed:
            triggered_restrictions.append(f"restricted files changed: {configured_restricted_matches}")
            risk_flags.append("RESTRICTED_FILES_MODIFIED")

        # General sensitive file check (boolean flag)
        sensitive_passed = not sensitive_flag_triggered
        add_check("no_sensitive_file_flagged", sensitive_passed, "No general sensitive file flag was set")
        if not sensitive_passed:
            triggered_restrictions.append("general sensitive file flagged")
            risk_flags.append("SENSITIVE_FILE_MODIFIED")

        # 2. Determine raw decision based on Trust Score / Confidence
        # Threshold checks
        add_check(
            "auto_merge_threshold_check",
            trust_score >= auto_merge_threshold,
            f"Trust score {trust_score} satisfies auto-merge threshold {auto_merge_threshold}"
        )
        add_check(
            "human_review_threshold_check",
            trust_score >= human_review_threshold,
            f"Trust score {trust_score} satisfies human review threshold {human_review_threshold}"
        )

        if trust_score >= auto_merge_threshold:
            confidence = "HIGH"
            raw_decision = "AUTO_MERGE"
        elif trust_score >= human_review_threshold:
            confidence = "MEDIUM"
            raw_decision = "HUMAN_REVIEW"
        else:
            confidence = "LOW"
            raw_decision = "REJECT"

        # 3. Handle Overrides
        # Any restriction failure forces a downgrade
        has_restriction_failures = len(triggered_restrictions) > 0
        
        decision = raw_decision
        reason_parts = []

        if raw_decision == "AUTO_MERGE":
            if has_restriction_failures:
                # Override AUTO_MERGE based on hard restrictions
                # Determine whether it should be HUMAN_REVIEW or REJECT
                # Failed tests or failed CI status should force REJECT. Security or policy overrides force HUMAN_REVIEW.
                if not test_result or (require_ci_success and ci_status == "FAILURE"):
                    decision = "REJECT"
                    reason_parts.append(
                        f"Downgraded from AUTO_MERGE to REJECT because hard restrictions were triggered: {', '.join(triggered_restrictions)}."
                    )
                else:
                    decision = "HUMAN_REVIEW"
                    reason_parts.append(
                        f"Downgraded from AUTO_MERGE to HUMAN_REVIEW because hard restrictions were triggered: {', '.join(triggered_restrictions)}."
                    )
            else:
                reason_parts.append(
                    f"Approved for AUTO_MERGE: Trust score {trust_score} >= auto-merge threshold {auto_merge_threshold} with no hard restriction violations."
                )
        elif raw_decision == "HUMAN_REVIEW":
            if not test_result or (require_ci_success and ci_status == "FAILURE"):
                decision = "REJECT"
                reason_parts.append(
                    f"Downgraded from HUMAN_REVIEW to REJECT because of critical failures: {', '.join(triggered_restrictions)}."
                )
            else:
                reason_parts.append(
                    f"Recommending HUMAN_REVIEW: Trust score {trust_score} is in review range [{human_review_threshold}, {auto_merge_threshold})."
                )
                if has_restriction_failures:
                    reason_parts.append(f"Hard restrictions triggered: {', '.join(triggered_restrictions)}.")
        else:
            # Already REJECT
            reason_parts.append(
                f"Rejected: Trust score {trust_score} is below human review threshold {human_review_threshold}."
            )
            if has_restriction_failures:
                reason_parts.append(f"Hard restrictions triggered: {', '.join(triggered_restrictions)}.")

        reason = " ".join(reason_parts)

        logger.info(f"Final Decision: {decision}, Reason: {reason}")

        return {
            "decision": decision,
            "reason": reason,
            "policy_checks": policy_checks,
            "risk_flags": risk_flags
        }

import os
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

from trust_engine_core.scorer import TrustScorer
from core.decision_engine import DecisionEngine, RESTRICTION_PATTERNS

logger = logging.getLogger("core.patch_selector")


def get_configured_thresholds(policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Returns configurable threshold and policy settings.
    Priority: policy dictionary > environment variables > defaults.
    """
    pol = policy or {}
    
    auto_merge_th = pol.get("auto_merge_threshold")
    if auto_merge_th is None:
        auto_merge_th = pol.get("auto_merge")
    if auto_merge_th is None:
        auto_merge_th = float(os.getenv("PATCH_AUTO_MERGE_THRESHOLD", "0.90"))

    pr_th = pol.get("pr_threshold")
    if pr_th is None:
        pr_th = pol.get("human_review_threshold")
    if pr_th is None:
        pr_th = pol.get("mandatory_review_threshold")
    if pr_th is None:
        pr_th = float(os.getenv("PATCH_PR_THRESHOLD", "0.70"))

    auto_merge_enabled = pol.get("auto_merge_enabled")
    if auto_merge_enabled is None:
        auto_merge_enabled = os.getenv("AUTO_MERGE_ENABLED", "false").lower() == "true"

    max_patch_size = pol.get("max_patch_size", int(os.getenv("PATCH_MAX_SIZE", "100")))
    max_files_changed = pol.get("max_files_changed", int(os.getenv("PATCH_MAX_FILES", "10")))
    max_blast_radius = pol.get("max_blast_radius", float(os.getenv("PATCH_MAX_BLAST_RADIUS", "0.3")))
    restricted_files = pol.get("restricted_files", [])

    return {
        "auto_merge_threshold": float(auto_merge_th),
        "pr_threshold": float(pr_th),
        "auto_merge_enabled": bool(auto_merge_enabled),
        "max_patch_size": int(max_patch_size),
        "max_files_changed": int(max_files_changed),
        "max_blast_radius": float(max_blast_radius),
        "restricted_files": restricted_files
    }


def parse_diff_metrics(diff_text: str) -> Dict[str, Any]:
    """
    Extracts lines added, lines removed, files changed, and patch size from unified diff.
    """
    lines_added = 0
    lines_removed = 0
    files_changed = []

    if not diff_text:
        return {
            "lines_added": 0,
            "lines_removed": 0,
            "patch_size": 0,
            "files_changed": []
        }

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            files_changed.append(line[6:].strip())
        elif line.startswith("+++ ") and not line.startswith("+++ /dev/null"):
            files_changed.append(line[4:].strip())
        elif line.startswith("+") and not line.startswith("+++"):
            lines_added += 1
        elif line.startswith("-") and not line.startswith("---"):
            lines_removed += 1

    unique_files = list(dict.fromkeys(files_changed))
    return {
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "patch_size": lines_added + lines_removed,
        "files_changed": unique_files
    }


@dataclass
class CandidateEvidence:
    candidate_id: str
    provider: str
    model: str
    patch_diff: str
    validation_result: bool = False
    validation_error: Optional[str] = None
    patch_application_result: bool = False
    test_result: bool = False
    tests_passed: int = 0
    tests_failed: int = 0
    mutation_score: float = 0.0
    mutation_tests_passed: int = 0
    mutation_tests_killed: int = 0
    regression_result: bool = True
    security_policy_validation: bool = True
    security_policy_violations: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    duplicate_status: bool = False
    duplicate_of: Optional[str] = None
    sandbox_status: str = "PENDING"
    execution_errors: Optional[str] = None
    trust_score: float = 0.0
    scorer_evidence: Dict[str, Any] = field(default_factory=dict)
    decision: str = "REJECT"
    decision_reason: str = ""
    disqualified: bool = False
    disqualification_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PatchSelectionResult:
    status: str  # "SELECTED" or "NO_SAFE_PATCH"
    selected_candidate: Optional[CandidateEvidence]
    why_selected: str
    candidates: List[CandidateEvidence]
    policy_used: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "selected_candidate": self.selected_candidate.to_dict() if self.selected_candidate else None,
            "why_selected": self.why_selected,
            "candidates": [c.to_dict() for c in self.candidates],
            "policy_used": self.policy_used
        }


class PatchSelector:
    """
    Evaluates candidate patches against structured observable validation evidence,
    calculates deterministic trust scores, and selects a candidate according to explicit policy.
    """

    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        self.policy = get_configured_thresholds(policy)
        self.scorer_config = {
            "version": "v1",
            "weights": {
                "test_pass_result": 0.40,
                "mutation_score": 0.30,
                "patch_locality": 0.10,
                "patch_size_score": 0.10,
                "files_changed_score": 0.05,
                "historical_success": 0.05,
            },
            "penalties": {
                "sensitive_file": 0.15,
                "blast_radius": 0.10,
            },
            "thresholds": {
                "auto_merge": self.policy["auto_merge_threshold"],
                "human_review": self.policy["pr_threshold"]
            }
        }
        self.trust_scorer = TrustScorer(self.scorer_config)
        self.decision_engine = DecisionEngine(policy_version="v1")

    def score_candidate(self, evidence: CandidateEvidence, blast_radius: float = 0.0) -> CandidateEvidence:
        """
        Calculates deterministic Trust Score and evaluates Decision Engine for a single candidate.
        Enforces strict safety rules:
        - A patch that fails the customer test MUST NOT be selected.
        - A patch that fails patch validation MUST NOT be selected.
        - A patch that cannot be applied MUST NOT be selected.
        - A patch with sandbox timeout/error MUST NOT be treated as successful.
        """
        # 1. Check Hard Disqualifications
        disqualifications = []
        if not evidence.validation_result:
            disqualifications.append(f"Patch validation failed: {evidence.validation_error or 'invalid unified diff'}")
        if not evidence.patch_application_result:
            disqualifications.append("Patch cannot be applied cleanly to repository")
        if not evidence.test_result:
            disqualifications.append(f"Customer test failed (exit code non-zero, passed={evidence.tests_passed}, failed={evidence.tests_failed})")
        if evidence.sandbox_status in ["TIMEOUT", "ERROR"]:
            disqualifications.append(f"Sandbox failure ({evidence.sandbox_status}): {evidence.execution_errors or 'error'}")
        if not evidence.security_policy_validation:
            disqualifications.append(f"Security/policy violations: {', '.join(evidence.security_policy_violations)}")

        if disqualifications:
            evidence.disqualified = True
            evidence.disqualification_reason = "; ".join(disqualifications)
            evidence.trust_score = 0.0
            evidence.decision = "REJECT"
            evidence.decision_reason = f"Disqualified: {evidence.disqualification_reason}"
            return evidence

        # 2. Evidence Metrics Mapping for TrustScorer
        patch_size = evidence.lines_added + evidence.lines_removed
        files_count = len(evidence.files_changed) if evidence.files_changed else 1

        scorer_inputs = {
            "test_pass_result": evidence.test_result,
            "mutation_score": float(evidence.mutation_score),
            "patch_locality": 1.0,
            "patch_size": patch_size,
            "files_changed": files_count,
            "sensitive_file_flag": not evidence.security_policy_validation,
            "blast_radius": float(blast_radius),
            "historical_success": 1.0
        }

        # Apply duplicate penalty if marked duplicate
        if evidence.duplicate_status:
            scorer_inputs["historical_success"] = 0.5

        trust_result = self.trust_scorer.calculate_score(scorer_inputs)
        evidence.trust_score = float(trust_result["trust_score"])
        evidence.scorer_evidence = trust_result.get("evidence", {})

        # 3. Decision Engine Evaluation
        repo_policy = {
            "auto_merge_threshold": self.policy["auto_merge_threshold"],
            "human_review_threshold": self.policy["pr_threshold"],
            "max_patch_size": self.policy["max_patch_size"],
            "max_files_changed": self.policy["max_files_changed"],
            "max_blast_radius": self.policy["max_blast_radius"],
            "restricted_files": self.policy["restricted_files"]
        }

        engine_res = self.decision_engine.evaluate(
            trust_score=evidence.trust_score,
            mutation_score=evidence.mutation_score,
            test_result=evidence.test_result,
            patch_size=patch_size,
            files_changed=evidence.files_changed,
            sensitive_file_flags=not evidence.security_policy_validation,
            blast_radius=blast_radius,
            repository_policy=repo_policy,
            ci_status="SUCCESS" if evidence.test_result else "FAILURE"
        )

        raw_decision = engine_res.get("decision", "REJECT")
        # Map HUMAN_REVIEW to CREATE_PR for clear GitHub semantics
        if raw_decision == "HUMAN_REVIEW":
            evidence.decision = "CREATE_PR"
        elif raw_decision == "AUTO_MERGE":
            evidence.decision = "AUTO_MERGE"
        else:
            evidence.decision = "REJECT"

        evidence.decision_reason = engine_res.get("reason", "")
        return evidence

    def select_candidate(
        self,
        candidates_evidence: List[CandidateEvidence],
        blast_radius: float = 0.0
    ) -> PatchSelectionResult:
        """
        Evaluates all candidates and selects the candidate with the strongest valid evidence
        according to configured policy.

        Returns:
            PatchSelectionResult with status SELECTED or NO_SAFE_PATCH.
        """
        scored_candidates: List[CandidateEvidence] = []
        for cand in candidates_evidence:
            scored = self.score_candidate(cand, blast_radius=blast_radius)
            scored_candidates.append(scored)

        # Filter out disqualified candidates
        eligible = [c for c in scored_candidates if not c.disqualified and c.decision in ["AUTO_MERGE", "CREATE_PR"]]

        if not eligible:
            reasons = [f"Candidate {c.candidate_id}: {c.disqualification_reason or c.decision_reason}" for c in scored_candidates]
            explanation = "No candidate satisfied safety rules and policy thresholds. " + " | ".join(reasons)
            logger.warning(f"No safe patch found: {explanation}")
            return PatchSelectionResult(
                status="NO_SAFE_PATCH",
                selected_candidate=None,
                why_selected=explanation,
                candidates=scored_candidates,
                policy_used=self.policy
            )

        # Sort eligible candidates deterministically by evidence:
        # 1. Decision priority (AUTO_MERGE > CREATE_PR)
        # 2. Trust Score (highest)
        # 3. Mutation Score (highest)
        # 4. Non-duplicate priority
        # 5. Patch size (smallest)
        # 6. Files changed (fewest)
        def sort_key(c: CandidateEvidence):
            decision_rank = 2 if c.decision == "AUTO_MERGE" else 1
            duplicate_penalty = 0 if c.duplicate_status else 1
            patch_size = c.lines_added + c.lines_removed
            files_count = len(c.files_changed)
            return (
                decision_rank,
                c.trust_score,
                c.mutation_score,
                duplicate_penalty,
                -patch_size,
                -files_count
            )

        sorted_eligible = sorted(eligible, key=sort_key, reverse=True)
        winner = sorted_eligible[0]

        # Construct evidence-based selection explanation
        why_parts = [
            f"Candidate '{winner.candidate_id}' produced the strongest independently verified evidence.",
            f"Customer tests passed cleanly ({winner.tests_passed} passed, 0 failed).",
            f"Mutation score is {winner.mutation_score:.2f} ({winner.mutation_tests_killed} mutants killed, {winner.mutation_tests_passed} survived).",
            f"Minimal blast radius modifying {len(winner.files_changed)} file(s) (+{winner.lines_added}/-{winner.lines_removed} lines).",
            f"Calculated Trust Score: {winner.trust_score:.2f} (PR Threshold: {self.policy['pr_threshold']}, Auto-Merge Threshold: {self.policy['auto_merge_threshold']}).",
            f"Decision Engine verdict: {winner.decision}."
        ]

        # Mention why others were not chosen
        other_notes = []
        for other in scored_candidates:
            if other.candidate_id == winner.candidate_id:
                continue
            if other.disqualified:
                other_notes.append(f"Candidate '{other.candidate_id}' disqualified ({other.disqualification_reason}).")
            elif other.trust_score < winner.trust_score:
                other_notes.append(f"Candidate '{other.candidate_id}' had lower trust score ({other.trust_score:.2f} vs {winner.trust_score:.2f}).")
            elif other.mutation_score < winner.mutation_score:
                other_notes.append(f"Candidate '{other.candidate_id}' had lower mutation score ({other.mutation_score:.2f} vs {winner.mutation_score:.2f}).")

        if other_notes:
            why_parts.append("Comparison with other candidates: " + " ".join(other_notes))

        why_selected = " ".join(why_parts)

        return PatchSelectionResult(
            status="SELECTED",
            selected_candidate=winner,
            why_selected=why_selected,
            candidates=scored_candidates,
            policy_used=self.policy
        )

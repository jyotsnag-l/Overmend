from typing import Dict, Any, List

DEFAULT_SCORER_CONFIG = {
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
        "auto_merge": 0.85,
        "human_review": 0.50
    }
}

class TrustScorer:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEFAULT_SCORER_CONFIG

    def calculate_score(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates a deterministic trust score based on inputs and configured weights/penalties.
        
        Inputs should look like:
        {
            "test_pass_result": True,
            "mutation_score": 0.916,
            "patch_locality": 1.0,
            "patch_size": 15,
            "files_changed": 1,
            "sensitive_file_flag": False,
            "blast_radius": 0.1,
            "historical_success": 0.95
        }
        """
        weights = self.config["weights"]
        penalties = self.config["penalties"]
        thresholds = self.config["thresholds"]
        version = self.config.get("version", "unknown")

        # Extract/Map inputs to 0.0 - 1.0 scores
        test_pass_result = bool(inputs.get("test_pass_result", False))
        test_pass_score = 1.0 if test_pass_result else 0.0

        mutation_score = float(inputs.get("mutation_score", 0.0))

        patch_locality = float(inputs.get("patch_locality", 1.0))

        # Size mapping: smaller is better/more trustworthy
        patch_size = int(inputs.get("patch_size", 0))
        if patch_size <= 10:
            patch_size_score = 1.0
        elif patch_size <= 50:
            patch_size_score = 0.8
        elif patch_size <= 100:
            patch_size_score = 0.5
        else:
            patch_size_score = 0.2

        # Files changed mapping: fewer is better
        files_changed = int(inputs.get("files_changed", 1))
        if files_changed <= 1:
            files_changed_score = 1.0
        elif files_changed <= 2:
            files_changed_score = 0.8
        elif files_changed <= 5:
            files_changed_score = 0.5
        else:
            files_changed_score = 0.2

        historical_success = float(inputs.get("historical_success", 1.0))

        # Calculate weighted contributions
        contributions = {
            "test_pass_result": test_pass_score * weights["test_pass_result"],
            "mutation_score": mutation_score * weights["mutation_score"],
            "patch_locality": patch_locality * weights["patch_locality"],
            "patch_size_score": patch_size_score * weights["patch_size_score"],
            "files_changed_score": files_changed_score * weights["files_changed_score"],
            "historical_success": historical_success * weights["historical_success"],
        }

        base_score = sum(contributions.values())

        # Apply penalties
        penalty_deductions = {}
        
        sensitive_file_flag = bool(inputs.get("sensitive_file_flag", False))
        if sensitive_file_flag:
            penalty_deductions["sensitive_file"] = penalties["sensitive_file"]
        else:
            penalty_deductions["sensitive_file"] = 0.0

        blast_radius = float(inputs.get("blast_radius", 0.0))
        penalty_deductions["blast_radius"] = blast_radius * penalties["blast_radius"]

        final_score = base_score - sum(penalty_deductions.values())
        final_score = max(0.0, min(1.0, final_score)) # Clamp between 0.0 and 1.0

        # Recommendation determination
        if not test_pass_result:
            recommendation = "REJECT"
        elif final_score >= thresholds["auto_merge"]:
            recommendation = "AUTO_MERGE"
        elif final_score >= thresholds["human_review"]:
            recommendation = "HUMAN_REVIEW"
        else:
            recommendation = "REJECT"

        # Risk flags
        risk_flags = []
        if sensitive_file_flag:
            risk_flags.append("SENSITIVE_FILE_MODIFIED")
        if blast_radius > 0.3:
            risk_flags.append("HIGH_BLAST_RADIUS")
        if mutation_score < 0.6:
            risk_flags.append("LOW_MUTATION_SCORE")
        if not test_pass_result:
            risk_flags.append("TEST_SUITE_FAILED")

        # Compile evidence
        evidence = {
            "scorer_version": version,
            "disclaimer": "These weights are heuristic config-driven values for triage and are not scientifically optimal.",
            "inputs": {
                "test_pass_result": test_pass_result,
                "mutation_score": mutation_score,
                "patch_locality": patch_locality,
                "patch_size": patch_size,
                "files_changed": files_changed,
                "sensitive_file_flag": sensitive_file_flag,
                "blast_radius": blast_radius,
                "historical_success": historical_success
            },
            "metric_scores": {
                "test_pass_score": test_pass_score,
                "mutation_score": mutation_score,
                "patch_locality": patch_locality,
                "patch_size_score": patch_size_score,
                "files_changed_score": files_changed_score,
                "historical_success": historical_success
            },
            "config_weights": weights,
            "weighted_contributions": contributions,
            "config_penalties": penalties,
            "penalty_deductions": penalty_deductions,
            "base_score": round(base_score, 4),
            "final_score": round(final_score, 4),
            "thresholds": thresholds
        }

        # Confidence is heavily influenced by the test suite strength (mutation score)
        # and basic test success
        confidence = mutation_score if test_pass_result else 0.0

        return {
            "trust_score": round(final_score, 4),
            "mutation_score": round(mutation_score, 4),
            "confidence": round(confidence, 4),
            "evidence": evidence,
            "risk_flags": risk_flags,
            "recommendation": recommendation
        }

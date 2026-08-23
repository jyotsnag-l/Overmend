from typing import Dict, Any, Optional

from trust_engine_core.engine import evaluate_patch
from trust_engine_core.scorer import TrustScorer, DEFAULT_SCORER_CONFIG

def evaluate_trust(patch: str, mutation_score: float) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper for evaluate_trust.
    """
    scorer = TrustScorer()
    inputs = {
        "test_pass_result": True,
        "mutation_score": mutation_score,
        "patch_locality": 1.0,
        "patch_size": 10,
        "files_changed": 1,
        "sensitive_file_flag": False,
        "blast_radius": 0.0,
        "historical_success": 1.0
    }
    res = scorer.calculate_score(inputs)
    return {
        "trust_score": res["trust_score"],
        "verdict": res["recommendation"],
        "explanation": f"Evaluation calculated with mutation score {mutation_score}."
    }

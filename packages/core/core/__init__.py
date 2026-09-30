from core.decision_engine import DecisionEngine
from core.patch_selector import (
    PatchSelector,
    CandidateEvidence,
    PatchSelectionResult,
    get_configured_thresholds,
    parse_diff_metrics
)

def get_version() -> str:
    return "0.1.0"


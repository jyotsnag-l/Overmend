import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from .schemas import PatchContext, CandidatePatchLLMOutput, PatchValidationReport
from .providers import LLMProvider
from .validator import validate_patch

logger = logging.getLogger("patch_engine.engine")

def normalize_diff(diff_text: str) -> str:
    """
    Normalizes unified diff text for duplicate detection by stripping
    surrounding markdown code fences, normalizing line endings, and
    trimming trailing whitespace per line and overall.
    """
    if not diff_text:
        return ""
    cleaned = diff_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Normalize line endings and whitespace per line
    norm_lines = [line.rstrip() for line in cleaned.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    return "\n".join(norm_lines).strip()

class PatchCandidateResult(BaseModel):
    candidate: CandidatePatchLLMOutput
    validation: PatchValidationReport

class PatchGenerationEngine:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_candidates(
        self,
        context: PatchContext,
        repo_path: str,
        policy: Optional[dict] = None,
        num_patches: int = 3
    ) -> List[PatchCandidateResult]:
        """
        Coordinates generating candidate patches from the LLM provider,
        performing duplicate detection, and running validation checks on each patch.
        """
        if not self.provider:
            raise RuntimeError("No patch-generation provider configured.")

        logger.info(f"Generating {num_patches} candidate patches using provider {self.provider.__class__.__name__}")

        # 1. Generate candidates from LLM provider
        try:
            candidates = await self.provider.generate_patches(context, num_patches=num_patches)
        except Exception as e:
            logger.error(f"Failed to generate patches from LLM provider: {e}", exc_info=True)
            raise RuntimeError(f"Patch generation LLM error: {str(e)}")

        if not candidates or len(candidates) == 0:
            raise RuntimeError("LLM provider returned 0 candidate patches.")

        results = []
        seen_diffs: Dict[str, str] = {}  # normalized_diff -> first candidate's patch_id

        # 2. Deduplicate and validate each candidate
        for candidate in candidates:
            norm_diff = normalize_diff(candidate.unified_diff)

            if norm_diff in seen_diffs:
                first_patch_id = seen_diffs[norm_diff]
                logger.warning(
                    f"Duplicate patch candidate detected: {candidate.patch_id} is identical to {first_patch_id}."
                )
                candidate.is_duplicate = True
                candidate.duplicate_of = first_patch_id
                report = PatchValidationReport(
                    is_valid=False,
                    error_reason=f"Duplicate patch candidate skipped: identical normalized diff to {first_patch_id}."
                )
                results.append(PatchCandidateResult(
                    candidate=candidate,
                    validation=report
                ))
            else:
                seen_diffs[norm_diff] = candidate.patch_id
                logger.info(f"Validating candidate patch {candidate.patch_id}")
                try:
                    report = validate_patch(
                        patch_text=candidate.unified_diff,
                        repo_path=repo_path,
                        context=context,
                        policy=policy
                    )
                except Exception as e:
                    logger.error(f"Unexpected error running validator on patch {candidate.patch_id}: {e}", exc_info=True)
                    report = PatchValidationReport(
                        is_valid=False,
                        error_reason=f"Validator internal error: {str(e)}"
                    )

                results.append(PatchCandidateResult(
                    candidate=candidate,
                    validation=report
                ))

        return results

import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from .schemas import PatchContext, CandidatePatchLLMOutput, PatchValidationReport
from .providers import LLMProvider
from .validator import validate_patch

logger = logging.getLogger("patch_engine.engine")

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
        Coordinates generating candidate patches from the LLM provider
        and running validation checks on each generated patch.
        """
        logger.info(f"Generating {num_patches} candidate patches using provider {self.provider.__class__.__name__}")
        
        try:
            # 1. Generate candidates from LLM
            candidates = await self.provider.generate_patches(context, num_patches=num_patches)
        except Exception as e:
            logger.error(f"Failed to generate patches from LLM provider: {e}", exc_info=True)
            raise RuntimeError(f"Patch generation LLM error: {str(e)}")

        results = []
        
        # 2. Validate each candidate
        for candidate in candidates:
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

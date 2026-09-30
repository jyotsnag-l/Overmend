import os
import asyncio
from .schemas import (
    PatchContext, IncidentData, FaultLocation, SourceContext,
    FunctionSignature, SurroundingLines, CallingFunction, RelatedTest,
    GitHistoryItem, HistoricalFix, CandidatePatchLLMOutput,
    LLMPatchesResponse, PatchValidationReport
)
from .providers import (
    LLMProvider, OpenAIAdapter, AnthropicAdapter, GeminiAdapter, GrokAdapter,
    ProviderConfigurationError, get_provider
)
from .validator import validate_patch, apply_patch_to_text
from .engine import PatchGenerationEngine, PatchCandidateResult, normalize_diff

def generate_patch(fault_info: dict, repo_path: str = ".") -> str:
    """
    Backward-compatible synchronous wrapper for patch generation.
    Requires a configured real LLM provider (OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY).
    Fails clearly if no real provider is configured.
    """
    provider_name = os.getenv("PATCH_PROVIDER", "openai").lower().strip()
    provider = get_provider(provider_name)


    incident = IncidentData(
        exception_type="ValueError",
        exception_message="Legacy fallback error",
        stack_trace="Traceback..."
    )
    fault_location = FaultLocation(
        file=fault_info.get("file", "main.py"),
        line=fault_info.get("line", 1),
        function=fault_info.get("function", "main")
    )
    source_context = SourceContext(
        faulting_file=fault_location.file
    )
    context = PatchContext(
        incident=incident,
        fault_location=fault_location,
        source_context=source_context
    )

    engine = PatchGenerationEngine(provider)

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            results = loop.run_until_complete(
                engine.generate_candidates(context, repo_path=repo_path, num_patches=1)
            )
        else:
            results = asyncio.run(
                engine.generate_candidates(context, repo_path=repo_path, num_patches=1)
            )
    except Exception as e:
        raise RuntimeError(f"Patch generation failed: {str(e)}")

    if results and results[0].validation.is_valid:
        return results[0].candidate.unified_diff
    raise RuntimeError("No valid patch could be generated.")

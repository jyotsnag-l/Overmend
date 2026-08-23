import asyncio
from .schemas import (
    PatchContext, IncidentData, FaultLocation, SourceContext,
    FunctionSignature, SurroundingLines, CallingFunction, RelatedTest,
    GitHistoryItem, HistoricalFix, CandidatePatchLLMOutput,
    LLMPatchesResponse, PatchValidationReport
)
from .providers import LLMProvider, OpenAIAdapter, AnthropicAdapter
from .validator import validate_patch, apply_patch_to_text
from .engine import PatchGenerationEngine, PatchCandidateResult

def generate_patch(fault_info: dict) -> str:
    """
    Backward-compatible synchronous wrapper that generates a mock patch
    for a localized fault.
    """
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
    
    provider = OpenAIAdapter(api_key="mock")
    engine = PatchGenerationEngine(provider)
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        # Fallback if loop is already running
        import nest_asyncio
        nest_asyncio.apply()
        results = loop.run_until_complete(
            engine.generate_candidates(context, repo_path=".", num_patches=1)
        )
    else:
        results = loop.run_until_complete(
            engine.generate_candidates(context, repo_path=".", num_patches=1)
        )
    
    if results:
        return results[0].candidate.unified_diff
    return f"diff --git a/{fault_location.file} b/{fault_location.file}\n"

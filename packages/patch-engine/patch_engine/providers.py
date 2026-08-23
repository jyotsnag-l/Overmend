import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .schemas import PatchContext, CandidatePatchLLMOutput, LLMPatchesResponse

logger = logging.getLogger("patch_engine.providers")

def extract_json_block(text: str) -> dict:
    """
    Extracts the first JSON block from text, parsing it into a dictionary.
    Handles raw JSON or JSON enclosed in markdown code blocks.
    """
    # Try finding JSON block in markdown
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1).strip()
    else:
        # Fallback: Find the first '{' and last '}'
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx + 1].strip()
        else:
            json_str = text.strip()
            
    # Parse JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from text: {e}. Text: {text}")
        raise ValueError(f"LLM output could not be parsed as JSON: {str(e)}")

def build_system_prompt() -> str:
    return (
        "You are an expert automated software healing agent. Your role is to generate precise, correct "
        "unified diff patches and metadata to fix code incidents.\n\n"
        "You must generate exactly 3 distinct candidate patches by default. Each patch should have a different "
        "approach or rationale (e.g., conservative fix, robust input validation, refactoring/alternative logic).\n\n"
        "You must ONLY respond with a valid JSON object matching the requested schema. Do not include any "
        "conversational text or explanation outside the JSON structure. Write the JSON object inside a single markdown "
        "code block like this:\n"
        "```json\n"
        "{\n"
        '  "patches": [\n'
        "    {\n"
        '      "patch_id": "patch_1",\n'
        '      "unified_diff": "diff --git a/filename.py b/filename.py...",\n'
        '      "explanation": "...",\n'
        '      "affected_files": ["filename.py"],\n'
        '      "estimated_change_scope": "SMALL",\n'
        '      "reasoning_summary": "..."\n'
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n"
        "```\n\n"
        "CRITICAL RULES for unified diffs:\n"
        "1. The unified_diff must start with 'diff --git a/file b/file' and contain standard header lines '--- a/file' and '+++ b/file'.\n"
        "2. Include hunk headers '@@ -start,len +start,len @@' and context lines starting with spaces.\n"
        "3. Ensure line counts, line additions (+), and line deletions (-) match the original file contents precisely.\n"
        "4. Do not perform full-file rewrites unless absolutely necessary (i.e. replacing the entire file contents is heavily discouraged; modify only the fault location).\n"
        "5. Modify ONLY the files that are directly related to the localized bug."
    )

def build_user_prompt(context: PatchContext, num_patches: int) -> str:
    # Build related tests representation
    tests_str = "\n".join([f"- File: {t.file}, Function: {t.function or 'all'}" for t in context.related_tests]) or "None"
    
    # Build git history representation
    git_str = ""
    for item in context.git_history:
        if item.type == "blame":
            git_str += f"- Blame for {item.file}:{item.line} -> {json.dumps(item.info)}\n"
        else:
            git_str += f"- Commit: {item.commit_hash[:8] if item.commit_hash else 'unknown'} | Author: {item.author} | Summary: {item.summary}\n"
    if not git_str:
        git_str = "None"
        
    # Build historical context representation
    hist_str = ""
    for i, inc in enumerate(context.historical_context):
        hist_str += f"- Incident {inc.get('id', 'unknown')}: Type: {inc.get('exception_type')}, Message: {inc.get('exception_message')}, Status: {inc.get('status')}\n"
    for fix in context.historical_fixes:
        hist_str += f"- Fix: Incident {fix.incident_id} | Patch ID: {fix.patch_id} | Diff:\n{fix.unified_diff}\n"
    if not hist_str:
        hist_str = "None"

    # Build source context details
    src_ctx = context.source_context
    faulting_file = src_ctx.faulting_file or "unknown"
    
    faulting_func_code = "None"
    if src_ctx.faulting_function:
        faulting_func_code = f"Lines {src_ctx.faulting_function.start_line}-{src_ctx.faulting_function.end_line}:\n{src_ctx.faulting_function.code}"
        
    surrounding_code = "None"
    if src_ctx.surrounding_lines:
        surrounding_code = f"Lines {src_ctx.surrounding_lines.start_line}-{src_ctx.surrounding_lines.end_line}:\n{src_ctx.surrounding_lines.code}"
        
    calling_func_code = "None"
    if src_ctx.calling_function:
        calling_func_code = f"File: {src_ctx.calling_function.file}, Function: {src_ctx.calling_function.function}, Lines {src_ctx.calling_function.start_line}-{src_ctx.calling_function.end_line}:\n{src_ctx.calling_function.code}"

    return (
        f"Generate exactly {num_patches} candidate patches for the following incident:\n\n"
        f"### Incident details:\n"
        f"- Exception Type: {context.incident.exception_type}\n"
        f"- Exception Message: {context.incident.exception_message}\n"
        f"- Stack Trace:\n{context.incident.stack_trace}\n\n"
        f"### Fault Location:\n"
        f"- File: {context.fault_location.file}\n"
        f"- Line: {context.fault_location.line}\n"
        f"- Function: {context.fault_location.function}\n"
        f"- Class: {context.fault_location.class_name}\n"
        f"- Evidence: {context.fault_location.evidence}\n\n"
        f"### Source Code Context of Faulting File ({faulting_file}):\n"
        f"**Faulting Function**:\n{faulting_func_code}\n\n"
        f"**Surrounding Code Context**:\n{surrounding_code}\n\n"
        f"**Calling Function Context**:\n{calling_func_code}\n\n"
        f"### Imports in Faulting File:\n"
        f"{', '.join(context.imports) if context.imports else 'None'}\n\n"
        f"### Related Test Cases:\n"
        f"{tests_str}\n\n"
        f"### Git History / Blame:\n"
        f"{git_str}\n\n"
        f"### Historical Fixes / Similar Incidents:\n"
        f"{hist_str}\n\n"
        f"### Repository Metadata:\n"
        f"{json.dumps(context.repository_context)}\n\n"
        f"Please output a JSON object containing the patches list according to the schema specified."
    )

class LLMProvider(ABC):
    @abstractmethod
    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        """
        Generates candidate patches based on the given context.
        """
        pass

class OpenAIAdapter(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "mock")
        self.model = model
        self.base_url = base_url
        
        # Instantiate client when not in mock mode or if packages are installed
        if self.api_key != "mock":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError:
                self.client = None
        else:
            self.client = None

    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context, num_patches)
        
        if self.api_key == "mock" or not self.client:
            logger.info("Using mock OpenAI response")
            # Return a default mock structure
            return self._get_mock_response(context, num_patches)
            
        try:
            # We call in executor or async if available, but since standard client is sync, we run in executor
            import asyncio
            loop = asyncio.get_event_loop()
            
            def make_call():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                )
                
            response = await loop.run_in_executor(None, make_call)
            text_content = response.choices[0].message.content
            
            # Parse JSON response
            parsed_data = extract_json_block(text_content)
            validated_response = LLMPatchesResponse.model_validate(parsed_data)
            return validated_response.patches
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI Patch Generation failed: {str(e)}")

    def _get_mock_response(self, context: PatchContext, num_patches: int) -> List[CandidatePatchLLMOutput]:
        # Generate mock patches matching the schema
        fault_file = context.fault_location.file or "main.py"
        
        if "users.py" in fault_file:
            return [
                CandidatePatchLLMOutput(
                    patch_id="patch_1",
                    unified_diff=(
                        "diff --git a/users.py b/users.py\n"
                        "--- a/users.py\n"
                        "+++ b/users.py\n"
                        "@@ -4,2 +4,2 @@\n"
                        "     # Intentional bug: profile_db is not defined, which raises NameError at runtime\n"
                        "-    return profile_db[user_id]\n"
                        "+    return profile_db[user_id] syntax_error_here\n"
                    ),
                    explanation="Mock explanation for invalid syntax patch A.",
                    affected_files=["users.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Syntax error patch."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_2",
                    unified_diff=(
                        "diff --git a/users.py b/users.py\n"
                        "--- a/users.py\n"
                        "+++ b/users.py\n"
                        "@@ -4,2 +4,3 @@\n"
                        "     # Intentional bug: profile_db is not defined, which raises NameError at runtime\n"
                        "-    return profile_db[user_id]\n"
                        "+    profile_db = {1: {'name': 'Alice'}}\n"
                        "+    return profile_db.get(user_id, {})\n"
                    ),
                    explanation="Mock explanation for logic-only patch B.",
                    affected_files=["users.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Logic-only patch without updating tests."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_3",
                    unified_diff=(
                        "diff --git a/users.py b/users.py\n"
                        "--- a/users.py\n"
                        "+++ b/users.py\n"
                        "@@ -4,2 +4,3 @@\n"
                        "     # Intentional bug: profile_db is not defined, which raises NameError at runtime\n"
                        "-    return profile_db[user_id]\n"
                        "+    profile_db = {1: {'name': 'Alice'}}\n"
                        "+    return profile_db.get(user_id, {})\n"
                        "diff --git a/tests/test_users.py b/tests/test_users.py\n"
                        "--- a/tests/test_users.py\n"
                        "+++ b/tests/test_users.py\n"
                        "@@ -1,14 +1,11 @@\n"
                        "-import pytest\n"
                        "-from users import get_user_profile\n"
                        "-\n"
                        "-def test_get_user_profile_name_error() -> None:\n"
                        "-    # Assert that accessing a profile raises NameError due to the bug\n"
                        "-    with pytest.raises(NameError) as exc_info:\n"
                        "-        get_user_profile(1)\n"
                        "-    assert \"profile_db\" in str(exc_info.value)\n"
                        "-\n"
                        "-def test_get_user_profile_invalid_id() -> None:\n"
                        "-    # Assert that negative IDs raise ValueError\n"
                        "-    with pytest.raises(ValueError) as exc_info:\n"
                        "-        get_user_profile(-1)\n"
                        "-    assert \"Invalid user_id\" in str(exc_info.value)\n"
                        "+import pytest\n"
                        "+from users import get_user_profile\n"
                        "+\n"
                        "+def test_get_user_profile_name_error() -> None:\n"
                        "+    assert get_user_profile(1) == {'name': 'Alice'}\n"
                        "+\n"
                        "+def test_get_user_profile_invalid_id() -> None:\n"
                        "+    # Assert that negative IDs raise ValueError\n"
                        "+    with pytest.raises(ValueError) as exc_info:\n"
                        "+        get_user_profile(-1)\n"
                        "+    assert \"Invalid user_id\" in str(exc_info.value)\n"
                    ),
                    explanation="Mock explanation for logic and test patch C.",
                    affected_files=["users.py", "tests/test_users.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Complete fix for logic and tests."
                )
            ][:num_patches]
        elif "payments.py" in fault_file:
            return [
                CandidatePatchLLMOutput(
                    patch_id="patch_1",
                    unified_diff=(
                        "diff --git a/payments.py b/payments.py\n"
                        "--- a/payments.py\n"
                        "+++ b/payments.py\n"
                        "@@ -3,3 +3,3 @@\n"
                        "     if refund_ratio == 0:\n"
                        "-        return amount / 0  # Intentionally raise ZeroDivisionError\n"
                        "+        return amount / 0 syntax_error_here\n"
                        "     return amount * refund_ratio\n"
                    ),
                    explanation="Mock explanation for invalid syntax patch A.",
                    affected_files=["payments.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Syntax error patch."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_2",
                    unified_diff=(
                        "diff --git a/payments.py b/payments.py\n"
                        "--- a/payments.py\n"
                        "+++ b/payments.py\n"
                        "@@ -3,3 +3,3 @@\n"
                        "     if refund_ratio == 0:\n"
                        "-        return amount / 0  # Intentionally raise ZeroDivisionError\n"
                        "+        return 0.0\n"
                        "     return amount * refund_ratio\n"
                    ),
                    explanation="Mock explanation for logic-only patch B.",
                    affected_files=["payments.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Logic-only patch without updating tests."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_3",
                    unified_diff=(
                        "diff --git a/payments.py b/payments.py\n"
                        "--- a/payments.py\n"
                        "+++ b/payments.py\n"
                        "@@ -3,3 +3,3 @@\n"
                        "     if refund_ratio == 0:\n"
                        "-        return amount / 0  # Intentionally raise ZeroDivisionError\n"
                        "+        return 0.0\n"
                        "     return amount * refund_ratio\n"
                        "diff --git a/tests/test_payments.py b/tests/test_payments.py\n"
                        "--- a/tests/test_payments.py\n"
                        "+++ b/tests/test_payments.py\n"
                        "@@ -7,4 +7,2 @@\n"
                        " def test_calculate_refund_zero_ratio() -> None:\n"
                        "-    # This will raise ZeroDivisionError which serves as the error-recovery trigger\n"
                        "-    with pytest.raises(ZeroDivisionError):\n"
                        "-        calculate_refund(100.0, 0.0)\n"
                        "+    assert calculate_refund(100.0, 0.0) == 0.0\n"
                    ),
                    explanation="Mock explanation for logic and test patch C.",
                    affected_files=["payments.py", "tests/test_payments.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Complete fix for logic and tests."
                )
            ][:num_patches]

        patches = []
        for i in range(1, num_patches + 1):
            patches.append(CandidatePatchLLMOutput(
                patch_id=f"patch_{i}",
                unified_diff=(
                    f"diff --git a/{fault_file} b/{fault_file}\n"
                    f"--- a/{fault_file}\n"
                    f"+++ b/{fault_file}\n"
                    f"@@ -1,2 +1,2 @@\n"
                    f" def div(x):\n"
                    f"-    return x / 0\n"
                    f"+    return x / {i}\n"
                ),
                explanation=f"Mock explanation for approach {i}.",
                affected_files=[fault_file],
                estimated_change_scope="SMALL",
                reasoning_summary=f"Mock reasoning for approach {i}."
            ))
        return patches

class AnthropicAdapter(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "mock")
        self.model = model
        self.base_url = base_url
        
        if self.api_key != "mock":
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key, base_url=self.base_url)
            except ImportError:
                self.client = None
        else:
            self.client = None

    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context, num_patches)
        
        if self.api_key == "mock" or not self.client:
            logger.info("Using mock Anthropic response")
            return self._get_mock_response(context, num_patches)
            
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            def make_call():
                return self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.2
                )
                
            response = await loop.run_in_executor(None, make_call)
            text_content = response.content[0].text
            
            parsed_data = extract_json_block(text_content)
            validated_response = LLMPatchesResponse.model_validate(parsed_data)
            return validated_response.patches
            
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}", exc_info=True)
            raise RuntimeError(f"Anthropic Patch Generation failed: {str(e)}")

    def _get_mock_response(self, context: PatchContext, num_patches: int) -> List[CandidatePatchLLMOutput]:
        # Generate mock patches matching the schema
        fault_file = context.fault_location.file or "main.py"
        
        if "users.py" in fault_file:
            return [
                CandidatePatchLLMOutput(
                    patch_id="patch_anthropic_1",
                    unified_diff=(
                        "diff --git a/users.py b/users.py\n"
                        "--- a/users.py\n"
                        "+++ b/users.py\n"
                        "@@ -4,2 +4,2 @@\n"
                        "     # Intentional bug: profile_db is not defined, which raises NameError at runtime\n"
                        "-    return profile_db[user_id]\n"
                        "+    return profile_db[user_id] syntax_error_here\n"
                    ),
                    explanation="Mock explanation for invalid syntax patch A.",
                    affected_files=["users.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Syntax error patch."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_anthropic_2",
                    unified_diff=(
                        "diff --git a/users.py b/users.py\n"
                        "--- a/users.py\n"
                        "+++ b/users.py\n"
                        "@@ -4,2 +4,3 @@\n"
                        "     # Intentional bug: profile_db is not defined, which raises NameError at runtime\n"
                        "-    return profile_db[user_id]\n"
                        "+    profile_db = {1: {'name': 'Alice'}}\n"
                        "+    return profile_db.get(user_id, {})\n"
                    ),
                    explanation="Mock explanation for logic-only patch B.",
                    affected_files=["users.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Logic-only patch without updating tests."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_anthropic_3",
                    unified_diff=(
                        "diff --git a/users.py b/users.py\n"
                        "--- a/users.py\n"
                        "+++ b/users.py\n"
                        "@@ -4,2 +4,3 @@\n"
                        "     # Intentional bug: profile_db is not defined, which raises NameError at runtime\n"
                        "-    return profile_db[user_id]\n"
                        "+    profile_db = {1: {'name': 'Alice'}}\n"
                        "+    return profile_db.get(user_id, {})\n"
                        "diff --git a/tests/test_users.py b/tests/test_users.py\n"
                        "--- a/tests/test_users.py\n"
                        "+++ b/tests/test_users.py\n"
                        "@@ -1,14 +1,11 @@\n"
                        "-import pytest\n"
                        "-from users import get_user_profile\n"
                        "-\n"
                        "-def test_get_user_profile_name_error() -> None:\n"
                        "-    # Assert that accessing a profile raises NameError due to the bug\n"
                        "-    with pytest.raises(NameError) as exc_info:\n"
                        "-        get_user_profile(1)\n"
                        "-    assert \"profile_db\" in str(exc_info.value)\n"
                        "-\n"
                        "-def test_get_user_profile_invalid_id() -> None:\n"
                        "-    # Assert that negative IDs raise ValueError\n"
                        "-    with pytest.raises(ValueError) as exc_info:\n"
                        "-        get_user_profile(-1)\n"
                        "-    assert \"Invalid user_id\" in str(exc_info.value)\n"
                        "+import pytest\n"
                        "+from users import get_user_profile\n"
                        "+\n"
                        "+def test_get_user_profile_name_error() -> None:\n"
                        "+    assert get_user_profile(1) == {'name': 'Alice'}\n"
                        "+\n"
                        "+def test_get_user_profile_invalid_id() -> None:\n"
                        "+    # Assert that negative IDs raise ValueError\n"
                        "+    with pytest.raises(ValueError) as exc_info:\n"
                        "+        get_user_profile(-1)\n"
                        "+    assert \"Invalid user_id\" in str(exc_info.value)\n"
                    ),
                    explanation="Mock explanation for logic and test patch C.",
                    affected_files=["users.py", "tests/test_users.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Complete fix for logic and tests."
                )
            ][:num_patches]
        elif "payments.py" in fault_file:
            return [
                CandidatePatchLLMOutput(
                    patch_id="patch_anthropic_1",
                    unified_diff=(
                        "diff --git a/payments.py b/payments.py\n"
                        "--- a/payments.py\n"
                        "+++ b/payments.py\n"
                        "@@ -3,3 +3,3 @@\n"
                        "     if refund_ratio == 0:\n"
                        "-        return amount / 0  # Intentionally raise ZeroDivisionError\n"
                        "+        return amount / 0 syntax_error_here\n"
                        "     return amount * refund_ratio\n"
                    ),
                    explanation="Mock explanation for invalid syntax patch A.",
                    affected_files=["payments.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Syntax error patch."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_anthropic_2",
                    unified_diff=(
                        "diff --git a/payments.py b/payments.py\n"
                        "--- a/payments.py\n"
                        "+++ b/payments.py\n"
                        "@@ -3,3 +3,3 @@\n"
                        "     if refund_ratio == 0:\n"
                        "-        return amount / 0  # Intentionally raise ZeroDivisionError\n"
                        "+        return 0.0\n"
                        "     return amount * refund_ratio\n"
                    ),
                    explanation="Mock explanation for logic-only patch B.",
                    affected_files=["payments.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Logic-only patch without updating tests."
                ),
                CandidatePatchLLMOutput(
                    patch_id="patch_anthropic_3",
                    unified_diff=(
                        "diff --git a/payments.py b/payments.py\n"
                        "--- a/payments.py\n"
                        "+++ b/payments.py\n"
                        "@@ -3,3 +3,3 @@\n"
                        "     if refund_ratio == 0:\n"
                        "-        return amount / 0  # Intentionally raise ZeroDivisionError\n"
                        "+        return 0.0\n"
                        "     return amount * refund_ratio\n"
                        "diff --git a/tests/test_payments.py b/tests/test_payments.py\n"
                        "--- a/tests/test_payments.py\n"
                        "+++ b/tests/test_payments.py\n"
                        "@@ -7,4 +7,2 @@\n"
                        " def test_calculate_refund_zero_ratio() -> None:\n"
                        "-    # This will raise ZeroDivisionError which serves as the error-recovery trigger\n"
                        "-    with pytest.raises(ZeroDivisionError):\n"
                        "-        calculate_refund(100.0, 0.0)\n"
                        "+    assert calculate_refund(100.0, 0.0) == 0.0\n"
                    ),
                    explanation="Mock explanation for logic and test patch C.",
                    affected_files=["payments.py", "tests/test_payments.py"],
                    estimated_change_scope="SMALL",
                    reasoning_summary="Complete fix for logic and tests."
                )
            ][:num_patches]
        
        patches = []
        for i in range(1, num_patches + 1):
            patches.append(CandidatePatchLLMOutput(
                patch_id=f"patch_anthropic_{i}",
                unified_diff=(
                    f"diff --git a/{fault_file} b/{fault_file}\n"
                    f"--- a/{fault_file}\n"
                    f"+++ b/{fault_file}\n"
                    f"@@ -1,2 +1,2 @@\n"
                    f" def div(x):\n"
                    f"-    return x / 0\n"
                    f"+    return x / {i * 10}\n"
                ),
                explanation=f"Mock Anthropic explanation for approach {i}.",
                affected_files=[fault_file],
                estimated_change_scope="SMALL",
                reasoning_summary=f"Mock Anthropic reasoning for approach {i}."
            ))
        return patches

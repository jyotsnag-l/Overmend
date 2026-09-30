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
    if not text or not text.strip():
        raise ValueError("LLM output is empty or whitespace.")

    # Try finding JSON block in markdown
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1).strip()
    else:
        # Fallback: Find the outermost '{' and '}'
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
        logger.error(f"Failed to parse JSON from text: {e}. Raw text snippet: {text[:200]}")
        raise ValueError(f"LLM output could not be parsed as JSON: {str(e)}")

def build_system_prompt() -> str:
    return (
        "You are an expert automated software healing agent. Your role is to generate precise, correct "
        "unified diff patches and metadata to fix code incidents.\n\n"
        "You must generate distinct candidate patches according to the requested count. Each patch should have a different "
        "approach or rationale (e.g., conservative fix, robust input validation, refactoring/alternative logic).\n\n"
        "You must ONLY respond with a valid JSON object matching the requested schema. Do not include any "
        "conversational text or explanation outside the JSON structure. Write the JSON object inside a single markdown "
        "code block like this:\n"
        "```json\n"
        "{\n"
        '  "patches": [\n'
        "    {\n"
        '      "patch_id": "patch_1",\n'
        '      "unified_diff": "diff --git a/filename.py b/filename.py\\n--- a/filename.py\\n+++ b/filename.py\\n@@ -10,3 +10,3 @@\\n context\\n-old\\n+new\\n context",\n'
        '      "explanation": "...",\n'
        '      "affected_files": ["filename.py"],\n'
        '      "estimated_change_scope": "SMALL",\n'
        '      "reasoning_summary": "..."\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "```\n\n"
        "CRITICAL RULES for unified diffs:\n"
        "1. The unified_diff must start with 'diff --git a/file b/file' and contain standard header lines '--- a/file' and '+++ b/file'.\n"
        "2. Include hunk headers '@@ -start,len +start,len @@' and context lines starting with a space.\n"
        "3. Ensure line numbers, context lines, additions (+), and deletions (-) match the original file contents precisely.\n"
        "4. Do NOT perform full-file rewrites unless strictly necessary (modify only the fault location).\n"
        "5. Modify ONLY the files that are directly related to the localized bug.\n"
        "6. Do NOT modify tests just to make them pass unless the incident evidence explicitly indicates that the test itself is defective.\n"
        "7. Do NOT modify configuration or dependencies unless strictly justified by the incident evidence.\n"
        "8. All candidate patches must be distinct. Do NOT duplicate patches."
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
    for inc in context.historical_context:
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

class ProviderConfigurationError(RuntimeError):
    """Raised when an LLM provider is not configured or missing required API keys."""
    pass

class LLMProvider(ABC):
    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider is fully configured with required credentials."""
        pass

    @abstractmethod
    def validate_configuration(self) -> None:
        """Validates configuration, raising ProviderConfigurationError if not configured."""
        pass

    @abstractmethod
    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        """
        Generates candidate patches based on the given context.
        """
        pass

class OpenAIAdapter(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.client = None

        if self.api_key and self.api_key.strip() and self.api_key.lower() != "mock":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception:
                self.client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key.lower() != "mock" and self.client is not None)

    def validate_configuration(self) -> None:
        if not self.api_key or not self.api_key.strip() or self.api_key.lower() == "mock":
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "OpenAI API key (OPENAI_API_KEY) is missing or not configured."
            )
        if self.client is None:
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "OpenAI client could not be initialized or openai package is not installed."
            )

    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        self.validate_configuration()

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context, num_patches)

        try:
            import asyncio
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def make_call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
            )

        try:
            if loop and loop.is_running():
                response = await loop.run_in_executor(None, make_call)
            else:
                response = make_call()

            text_content = response.choices[0].message.content
            parsed_data = extract_json_block(text_content)
            validated_response = LLMPatchesResponse.model_validate(parsed_data)
            return validated_response.patches

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
            raise RuntimeError(f"OpenAI Patch Generation failed: {str(e)}")

class AnthropicAdapter(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")
        self.client = None

        if self.api_key and self.api_key.strip() and self.api_key.lower() != "mock":
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key, base_url=self.base_url)
            except Exception:
                self.client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key.lower() != "mock" and self.client is not None)

    def validate_configuration(self) -> None:
        if not self.api_key or not self.api_key.strip() or self.api_key.lower() == "mock":
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "Anthropic API key (ANTHROPIC_API_KEY) is missing or not configured."
            )
        if self.client is None:
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "Anthropic client could not be initialized or anthropic package is not installed."
            )

    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        self.validate_configuration()

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context, num_patches)

        try:
            import asyncio
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

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

        try:
            if loop and loop.is_running():
                response = await loop.run_in_executor(None, make_call)
            else:
                response = make_call()

            text_content = response.content[0].text
            parsed_data = extract_json_block(text_content)
            validated_response = LLMPatchesResponse.model_validate(parsed_data)
            return validated_response.patches

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}", exc_info=True)
            raise RuntimeError(f"Anthropic Patch Generation failed: {str(e)}")

class GeminiAdapter(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.client = None

        if self.api_key and self.api_key.strip() and self.api_key.lower() != "mock":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key.lower() != "mock" and self.client is not None)

    def validate_configuration(self) -> None:
        if not self.api_key or not self.api_key.strip() or self.api_key.lower() == "mock":
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "Google Gemini API key (GOOGLE_API_KEY) is missing or not configured."
            )
        if self.client is None:
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "Gemini client could not be initialized or google-genai package is not installed."
            )

    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        self.validate_configuration()

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context, num_patches)

        try:
            import asyncio
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def make_call():
            from google.genai import types
            return self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                )
            )

        try:
            if loop and loop.is_running():
                response = await loop.run_in_executor(None, make_call)
            else:
                response = make_call()

            text_content = response.text
            parsed_data = extract_json_block(text_content)
            validated_response = LLMPatchesResponse.model_validate(parsed_data)
            return validated_response.patches

        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}", exc_info=True)
            raise RuntimeError(f"Gemini Patch Generation failed: {str(e)}")

class GrokAdapter(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        raw_key = api_key if api_key is not None else (os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY"))
        self.api_key = raw_key.strip() if raw_key else None

        is_groq = bool(self.api_key and self.api_key.startswith("gsk_"))
        default_base = "https://api.groq.com/openai/v1" if is_groq else "https://api.x.ai/v1"
        default_model = "qwen/qwen3.8-27b" if is_groq else "grok-2-latest"

        self.base_url = base_url or os.getenv("GROK_BASE_URL") or default_base
        self.model = model or os.getenv("GROK_MODEL") or default_model
        self.client = None

        if self.api_key and self.api_key.strip() and self.api_key.lower() != "mock":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception:
                self.client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() and self.api_key.lower() != "mock" and self.client is not None)

    def validate_configuration(self) -> None:
        if not self.api_key or not self.api_key.strip() or self.api_key.lower() == "mock":
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "Grok / xAI API key (XAI_API_KEY) is missing or not configured."
            )
        if self.client is None:
            raise ProviderConfigurationError(
                "PROVIDER_NOT_CONFIGURED: No real patch-generation provider is configured. "
                "Grok client could not be initialized or openai package is not installed."
            )

    async def generate_patches(self, context: PatchContext, num_patches: int = 3) -> List[CandidatePatchLLMOutput]:
        self.validate_configuration()

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(context, num_patches)

        try:
            import asyncio
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        def make_call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
            )

        try:
            if loop and loop.is_running():
                response = await loop.run_in_executor(None, make_call)
            else:
                response = make_call()

            text_content = response.choices[0].message.content
            parsed_data = extract_json_block(text_content)
            validated_response = LLMPatchesResponse.model_validate(parsed_data)
            return validated_response.patches

        except Exception as e:
            logger.error(f"Error calling Grok/xAI API: {e}", exc_info=True)
            raise RuntimeError(f"Grok Patch Generation failed: {str(e)}")

def get_provider(provider_name: Optional[str] = None, **kwargs) -> LLMProvider:
    """
    Factory to resolve and instantiate the configured LLMProvider.
    Supported providers: 'openai', 'grok' (or 'xai'), 'gemini', 'anthropic'.
    Does not silently fall back to other providers.
    """
    name = (provider_name or os.getenv("PATCH_PROVIDER", "openai")).lower().strip()
    if name == "openai":
        return OpenAIAdapter(**kwargs)
    elif name in ("grok", "xai"):
        return GrokAdapter(**kwargs)
    elif name == "gemini":
        return GeminiAdapter(**kwargs)
    elif name == "anthropic":
        return AnthropicAdapter(**kwargs)
    else:
        raise ProviderConfigurationError(
            f"Unsupported PATCH_PROVIDER: '{name}'. Supported providers: openai, grok, gemini, anthropic"
        )


from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

class IncidentData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    id: Optional[str] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    stack_trace: Optional[str] = None
    fingerprint: Optional[str] = None

class FaultLocation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    file: Optional[str] = None
    line: Optional[int] = None
    function: Optional[str] = None
    class_name: Optional[str] = Field(None, alias="class")
    stack_frame: Optional[Dict[str, Any]] = None
    recent_change: Optional[bool] = None
    evidence: Optional[List[str]] = None

class FunctionSignature(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    code: Optional[str] = None

class SurroundingLines(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    code: Optional[str] = None

class CallingFunction(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    file: Optional[str] = None
    function: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    code: Optional[str] = None

class SourceContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    faulting_file: Optional[str] = None
    faulting_function: Optional[FunctionSignature] = None
    surrounding_lines: Optional[SurroundingLines] = None
    calling_function: Optional[CallingFunction] = None

class RelatedTest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    file: str
    function: Optional[str] = None
    code: Optional[str] = None

class GitHistoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    type: str  # blame or commit
    file: Optional[str] = None
    line: Optional[int] = None
    info: Optional[Dict[str, Any]] = None
    commit_hash: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    message: Optional[str] = None
    changed_files: Optional[List[str]] = None

class HistoricalFix(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    incident_id: Optional[str] = None
    patch_id: Optional[str] = None
    unified_diff: Optional[str] = None
    explanation: Optional[str] = None

class PatchContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    incident: IncidentData
    fault_location: FaultLocation
    source_context: SourceContext
    imports: List[str] = Field(default_factory=list)
    related_tests: List[RelatedTest] = Field(default_factory=list)
    git_history: List[GitHistoryItem] = Field(default_factory=list)
    historical_context: List[Dict[str, Any]] = Field(default_factory=list)
    historical_fixes: List[HistoricalFix] = Field(default_factory=list)
    repository_context: Dict[str, Any] = Field(default_factory=dict)

class CandidatePatchLLMOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    patch_id: str = Field(..., description="Unique string identifier for the patch, e.g. patch_1")
    unified_diff: str = Field(..., description="The unified diff of the changes to be applied. Must be a valid unified diff format starting with 'diff --git ...'")
    explanation: str = Field(..., description="A detailed description of the changes made and the fix rationale")
    affected_files: List[str] = Field(..., description="List of file paths modified by this patch")
    estimated_change_scope: str = Field(..., description="Description of the size and impact of the patch (e.g. 'SMALL', 'MEDIUM', 'LARGE')")
    reasoning_summary: str = Field(..., description="A short summary of the reasoning behind this fix")
    is_duplicate: Optional[bool] = Field(default=False, description="Whether this patch was identified as a duplicate")
    duplicate_of: Optional[str] = Field(default=None, description="The patch_id of the original candidate if duplicate")

class LLMPatchesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    patches: List[CandidatePatchLLMOutput] = Field(..., description="List of generated candidate patches, exactly 3 by default")

class PatchValidationReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    is_valid: bool
    error_reason: Optional[str] = None
    patch_size: int = 0  # lines changed (additions + deletions)
    files_changed: int = 0
    affected_paths: List[str] = Field(default_factory=list)
    hunks_matched: Optional[bool] = Field(default=None, description="Whether all diff hunks matched repository source")
    syntax_valid: Optional[bool] = Field(default=None, description="Whether patched code passed syntax/AST validation")

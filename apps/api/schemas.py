from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

# Organization Schemas
class OrganizationBase(BaseModel):
    name: str = Field(..., description="Name of the organization")

class OrganizationCreate(OrganizationBase):
    id: str = Field(..., description="Unique organization identifier, e.g., org_123")

class OrganizationResponse(OrganizationBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# User Schemas
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Membership Schemas
class MembershipCreate(BaseModel):
    user_id: str
    role: str = Field(..., description="Role of the user in the org: OWNER, ADMIN, ENGINEER, REVIEWER, VIEWER")
    team_id: Optional[str] = None

class MembershipResponse(BaseModel):
    id: str
    organization_id: str
    user_id: str
    team_id: Optional[str]
    role: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Project Schemas
class ProjectBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the project")
    repository: str = Field(..., max_length=255, description="Git repository path, e.g. company/repo")

class ProjectCreate(ProjectBase):
    id: str = Field(..., description="Unique project identifier, e.g. proj_123")
    organization_id: Optional[str] = Field(None, description="Organization ID. If not supplied, inferred from header.")

class ProjectResponse(ProjectBase):
    id: str
    organization_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Incident Schemas
class IncidentBase(BaseModel):
    exception_type: str = Field(..., description="The type of exception raised")
    exception_message: str = Field(..., description="The message detailing the exception")
    stack_trace: str = Field(..., description="The full traceback of the exception")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional contextual info")

class IncidentCreate(IncidentBase):
    project_id: str = Field(..., description="ID of the project reporting this exception")

class IncidentResponse(IncidentBase):
    id: str
    project_id: str
    organization_id: str
    status: str
    fingerprint: str
    created_at: datetime
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime
    error_rate: float
    environment: str
    affected_repository: Optional[str] = None
    affected_project: Optional[str] = None
    stack_frames: Optional[Dict[str, Any]] = None
    severity: str
    is_anomaly: bool
    model_config = ConfigDict(from_attributes=True)

# Incident Event (Ingestion) Schemas
class EventCreate(BaseModel):
    event_id: Optional[str] = Field(default=None, description="Unique event identifier for idempotency")
    project_id: str = Field(..., description="ID of the project reporting this event")
    exception_type: str = Field(..., description="The type of exception raised")
    exception_message: str = Field(..., description="The message detailing the exception")
    stack_trace: str = Field(..., description="The full traceback of the exception")
    file: Optional[str] = Field(default=None, description="The file path where exception occurred")
    line: Optional[int] = Field(default=None, description="The line number where exception occurred")
    function: Optional[str] = Field(default=None, description="The function name where exception occurred")
    git_commit: Optional[str] = Field(default=None, description="The Git commit hash")
    runtime_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about the runtime environment")
    environment: str = Field(default="production", description="The environment e.g. production, staging, development")
    request_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Safe HTTP request metadata")
    sdk_version: Dict[str, Any] = Field(default_factory=dict, description="SDK version metadata")

# Patch & Decision Schemas
class PatchCandidateResponse(BaseModel):
    id: str
    organization_id: str
    incident_id: str
    diff: str
    explanation: str
    created_at: datetime
    patch_id: Optional[str] = None
    affected_files: Optional[List[str]] = None
    estimated_change_scope: Optional[str] = None
    reasoning_summary: Optional[str] = None
    is_valid: Optional[bool] = None
    validation_error: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class DecisionCreate(BaseModel):
    patch_candidate_id: str
    status: str = Field(..., description="APPROVED or REJECTED")
    reason: str = Field(..., description="Reason for this decision")

class DecisionResponse(BaseModel):
    id: str
    organization_id: str
    patch_candidate_id: str
    status: str
    action: str
    reason: str
    decided_by: Optional[str]
    created_at: datetime
    policy_version: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    actor_system: Optional[str] = None
    policy_checks: Optional[List[Dict[str, Any]]] = None
    risk_flags: Optional[List[str]] = None
    model_config = ConfigDict(from_attributes=True)

# Audit Log Schemas
class AuditLogResponse(BaseModel):
    id: str
    organization_id: str
    user_id: Optional[str]
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Sandbox Schemas
class SandboxConfig(BaseModel):
    cpu_limit: float = Field(default=0.5, description="CPU limit (e.g. number of CPUs)")
    memory_limit: str = Field(default="512m", description="Memory limit (e.g. 512m)")
    timeout: int = Field(default=300, description="Execution timeout in seconds")
    network_mode: str = Field(default="none", description="Network mode (e.g. none, bridge)")
    test_command: str = Field(default="pytest", description="Test command to run")
    working_directory: str = Field(default="/workspace", description="Working directory inside container")
    environment_allowlist: List[str] = Field(default_factory=list, description="Allowed environment variable keys")
    image: str = Field(default="python:3.11-slim", description="Docker image to run the sandbox in")

class SandboxJobCreate(BaseModel):
    patch_candidate_id: str
    config: Optional[SandboxConfig] = None

class SandboxJobResponse(BaseModel):
    id: str
    organization_id: str
    project_id: str
    patch_candidate_id: str
    status: str
    config: Dict[str, Any]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SandboxExecutionResponse(BaseModel):
    id: str
    organization_id: str
    sandbox_job_id: str
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    stdout_url: Optional[str] = None
    stderr_url: Optional[str] = None
    exit_code: Optional[int] = None
    duration: Optional[float] = None
    resource_usage: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SandboxTransitionResponse(BaseModel):
    id: str
    organization_id: str
    sandbox_job_id: str
    from_state: Optional[str] = None
    to_state: str
    timestamp: datetime
    details: Optional[str] = None
    metadata_info: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)

class DecisionEvaluateRequest(BaseModel):
    patch_candidate_id: str
    trust_score: float
    mutation_score: float
    test_result: bool
    patch_size: int
    files_changed: List[str]
    sensitive_file_flags: Any
    blast_radius: float
    repository_policy: Optional[Dict[str, Any]] = None
    ci_status: Optional[str] = None


# Historical Recovery Schemas
class HistoricalRecoveryRecordCreate(BaseModel):
    incident: Dict[str, Any]
    stack_trace: str
    fault_location: Dict[str, Any]
    patch: str
    outcome: str
    trust_score: float
    human_decision: str
    final_result: str

class HistoricalRecoveryRecordResponse(BaseModel):
    id: str
    organization_id: str
    incident: Dict[str, Any]
    stack_trace: str
    fault_location: Dict[str, Any]
    patch: str
    outcome: str
    trust_score: float
    human_decision: str
    final_result: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class HistoricalSimilarityResult(BaseModel):
    similarity_score: float
    incident_id: str
    previous_fault_location: Dict[str, Any]
    previous_patch: str
    outcome: str
    trust_score: float
    human_decision: str


from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    String, Text, DateTime, JSON, ForeignKey, Integer, Float, Boolean, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.compiler import compiles
from database import Base

# Setup custom pgvector compile fallback for SQLite
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy.types import UserDefinedType
    class Vector(UserDefinedType):
        def __init__(self, dim):
            self.dim = dim

@compiles(Vector, "sqlite")
def compile_vector_sqlite(element, compiler, **kw):
    return "TEXT"

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="decided_by_user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan")
    memberships = relationship("Membership", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    repositories = relationship("Repository", back_populates="organization", cascade="all, delete-orphan")
    environments = relationship("Environment", back_populates="organization", cascade="all, delete-orphan")
    project_policies = relationship("ProjectPolicy", back_populates="organization", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="organization", cascade="all, delete-orphan")
    incident_events = relationship("IncidentEvent", back_populates="organization", cascade="all, delete-orphan")
    fault_locations = relationship("FaultLocation", back_populates="organization", cascade="all, delete-orphan")
    patch_candidates = relationship("PatchCandidate", back_populates="organization", cascade="all, delete-orphan")
    sandbox_jobs = relationship("SandboxJob", back_populates="organization", cascade="all, delete-orphan")
    sandbox_executions = relationship("SandboxExecution", back_populates="organization", cascade="all, delete-orphan")
    test_runs = relationship("TestRun", back_populates="organization", cascade="all, delete-orphan")
    mutations = relationship("Mutation", back_populates="organization", cascade="all, delete-orphan")
    trust_evaluations = relationship("TrustEvaluation", back_populates="organization", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="organization", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="organization", cascade="all, delete-orphan")
    ci_statuses = relationship("CIStatus", back_populates="organization", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="organization", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="organization", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="teams")
    memberships = relationship("Membership", back_populates="team")


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    team_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("teams.id"), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # OWNER, ADMIN, ENGINEER, REVIEWER, VIEWER
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")
    team = relationship("Team", back_populates="memberships")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repository: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="projects")
    repositories = relationship("Repository", back_populates="project", cascade="all, delete-orphan")
    environments = relationship("Environment", back_populates="project", cascade="all, delete-orphan")
    policies = relationship("ProjectPolicy", back_populates="project", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="project", cascade="all, delete-orphan")
    sandbox_jobs = relationship("SandboxJob", back_populates="project", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="project", cascade="all, delete-orphan")


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_synced_commit: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    organization = relationship("Organization", back_populates="repositories")
    project = relationship("Project", back_populates="repositories")


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # production, staging, dev
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="environments")
    project = relationship("Project", back_populates="environments")


class ProjectPolicy(Base):
    __tablename__ = "project_policies"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    auto_merge_threshold: Mapped[float] = mapped_column(Float, default=0.90)
    mandatory_review_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    restricted_files: Mapped[list] = mapped_column(JSON, default=list)  # e.g., ["auth.py", "payment.py"]
    anomaly_frequency_threshold: Mapped[int] = mapped_column(Integer, default=10)
    anomaly_zscore_threshold: Mapped[float] = mapped_column(Float, default=3.0)
    anomaly_ewma_threshold: Mapped[float] = mapped_column(Float, default=5.0)
    severity_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="project_policies")
    project = relationship("Project", back_populates="policies")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    exception_type: Mapped[str] = mapped_column(String(255), nullable=False)
    exception_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DETECTED", index=True)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True) # pgvector support

    # New tracking fields
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    environment: Mapped[str] = mapped_column(String(50), default="production", index=True)
    affected_repository: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    affected_project: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stack_frames: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="MEDIUM", index=True)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    rolling_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    recovery_job_enqueued: Mapped[bool] = mapped_column(Boolean, default=False)

    organization = relationship("Organization", back_populates="incidents")
    project = relationship("Project", back_populates="incidents")
    events = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")
    fault_locations = relationship("FaultLocation", back_populates="incident", cascade="all, delete-orphan")
    patch_candidates = relationship("PatchCandidate", back_populates="incident", cascade="all, delete-orphan")


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(50), ForeignKey("incidents.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    organization = relationship("Organization", back_populates="incident_events")
    incident = relationship("Incident", back_populates="events")


class FaultLocation(Base):
    __tablename__ = "fault_locations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(50), ForeignKey("incidents.id"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    function_name: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="fault_locations")
    incident = relationship("Incident", back_populates="fault_locations")


class PatchCandidate(Base):
    __tablename__ = "patch_candidates"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(50), ForeignKey("incidents.id"), nullable=False, index=True)
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Metadata fields for LLM Patch Generation Engine
    patch_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    affected_files: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    estimated_change_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reasoning_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_valid: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    validation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="patch_candidates")
    incident = relationship("Incident", back_populates="patch_candidates")
    sandbox_jobs = relationship("SandboxJob", back_populates="patch_candidate", cascade="all, delete-orphan")
    trust_evaluations = relationship("TrustEvaluation", back_populates="patch_candidate", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="patch_candidate", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="patch_candidate", cascade="all, delete-orphan")


class SandboxJob(Base):
    __tablename__ = "sandbox_jobs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    patch_candidate_id: Mapped[str] = mapped_column(String(50), ForeignKey("patch_candidates.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="QUEUED", index=True)  # QUEUED, CREATING, CLONING, etc.
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # Stores SandboxConfig
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="sandbox_jobs")
    project = relationship("Project", back_populates="sandbox_jobs")
    patch_candidate = relationship("PatchCandidate", back_populates="sandbox_jobs")
    executions = relationship("SandboxExecution", back_populates="sandbox_job", cascade="all, delete-orphan")
    transitions = relationship("SandboxJobTransition", back_populates="sandbox_job", cascade="all, delete-orphan")


class SandboxJobTransition(Base):
    __tablename__ = "sandbox_job_transitions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    sandbox_job_id: Mapped[str] = mapped_column(String(50), ForeignKey("sandbox_jobs.id"), nullable=False, index=True)
    from_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_info: Mapped[dict] = mapped_column(JSON, default=dict)

    organization = relationship("Organization")
    sandbox_job = relationship("SandboxJob", back_populates="transitions")


class SandboxExecution(Base):
    __tablename__ = "sandbox_executions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    sandbox_job_id: Mapped[str] = mapped_column(String(50), ForeignKey("sandbox_jobs.id"), nullable=False, index=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stdout_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    stderr_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resource_usage: Mapped[dict] = mapped_column(JSON, default=dict)  # CPU, memory stats
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    organization = relationship("Organization", back_populates="sandbox_executions")
    sandbox_job = relationship("SandboxJob", back_populates="executions")
    test_runs = relationship("TestRun", back_populates="sandbox_execution", cascade="all, delete-orphan")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    sandbox_execution_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("sandbox_executions.id"), nullable=True, index=True)
    test_suite_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_failed: Mapped[int] = mapped_column(Integer, default=0)
    logs: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="test_runs")
    sandbox_execution = relationship("SandboxExecution", back_populates="test_runs")


class TrustEvaluation(Base):
    __tablename__ = "trust_evaluations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=True, index=True)
    patch_candidate_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("patch_candidates.id"), nullable=True, index=True)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    mutation_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="trust_evaluations")
    patch_candidate = relationship("PatchCandidate", back_populates="trust_evaluations")
    mutations = relationship("Mutation", back_populates="trust_evaluation", cascade="all, delete-orphan")


class Mutation(Base):
    __tablename__ = "mutations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=True, index=True)
    trust_evaluation_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("trust_evaluations.id"), nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_operator: Mapped[str] = mapped_column(String(100), nullable=False)
    mutated_operator: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # KILLED, SURVIVED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="mutations")
    trust_evaluation = relationship("TrustEvaluation", back_populates="mutations")


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    patch_candidate_id: Mapped[str] = mapped_column(String(50), ForeignKey("patch_candidates.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # APPROVED, REJECTED, PENDING_REVIEW
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # AUTO_MERGE, HUMAN_REVIEW, REJECT
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Decision Engine fields
    policy_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    inputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    actor_system: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    policy_checks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    risk_flags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    organization = relationship("Organization", back_populates="decisions")
    patch_candidate = relationship("PatchCandidate", back_populates="decisions")
    decided_by_user = relationship("User", back_populates="decisions")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(50), ForeignKey("projects.id"), nullable=False, index=True)
    patch_candidate_id: Mapped[str] = mapped_column(String(50), ForeignKey("patch_candidates.id"), nullable=False, index=True)
    github_pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    github_pr_url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="OPEN")  # OPEN, MERGED, CLOSED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="pull_requests")
    project = relationship("Project", back_populates="pull_requests")
    patch_candidate = relationship("PatchCandidate", back_populates="pull_requests")
    ci_statuses = relationship("CIStatus", back_populates="pull_request", cascade="all, delete-orphan")


class CIStatus(Base):
    __tablename__ = "ci_statuses"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    pull_request_id: Mapped[str] = mapped_column(String(50), ForeignKey("pull_requests.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # PENDING, SUCCESS, FAILURE
    context: Mapped[str] = mapped_column(String(255), nullable=False)
    target_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="ci_statuses")
    pull_request = relationship("PullRequest", back_populates="ci_statuses")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., CREATE_PROJECT, APPROVE_PATCH
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., Project, PatchCandidate
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    organization = relationship("Organization", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(50), ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)  # EMAIL, SLACK
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, SENT, FAILED
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="notifications")
    user = relationship("User", back_populates="notifications")


class IncidentHistory(Base):
    __tablename__ = "incident_histories"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(50), ForeignKey("incidents.id"), nullable=False, index=True)
    from_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_state: Mapped[str] = mapped_column(String(50), nullable=False)
    transitioned_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("users.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    metadata_info: Mapped[dict] = mapped_column(JSON, default=dict)

    organization = relationship("Organization")
    incident = relationship("Incident")


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(50), ForeignKey("incidents.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    incident = relationship("Incident")


class GitHubEvent(Base):
    __tablename__ = "github_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class HistoricalRecoveryRecord(Base):
    __tablename__ = "historical_recovery_records"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(50), ForeignKey("organizations.id"), nullable=False, index=True)
    incident_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    incident: Mapped[dict] = mapped_column(JSON, default=dict)
    stack_trace: Mapped[str] = mapped_column(Text, nullable=False)
    fault_location: Mapped[dict] = mapped_column(JSON, default=dict)
    patch: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(String(100), nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False)
    human_decision: Mapped[str] = mapped_column(String(100), nullable=False)
    final_result: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index(
            "historical_recovery_records_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
    )



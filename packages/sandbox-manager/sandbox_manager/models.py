from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SandboxStatus(str, Enum):
    PASSED = "PASSED"
    TEST_FAILURE = "TEST_FAILURE"
    PATCH_APPLY_ERROR = "PATCH_APPLY_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    TIMEOUT = "TIMEOUT"
    SANDBOX_ERROR = "SANDBOX_ERROR"


class SandboxResult(BaseModel):
    """
    Structured result returned by SandboxRunner execution.
    Supports both attribute access and dict-style indexing for backwards compatibility.
    """
    candidate_id: Optional[str] = None
    status: SandboxStatus = SandboxStatus.SANDBOX_ERROR
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    test_command: str = ""
    tests_total: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    tests_skipped: Optional[int] = None
    workspace_info: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    resource_usage: Dict[str, Any] = Field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Backwards compatibility alias for duration_seconds."""
        return self.duration_seconds

    def __getitem__(self, item: str) -> Any:
        if item == "duration":
            return self.duration_seconds
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        if item == "duration":
            return self.duration_seconds
        if hasattr(self, item):
            val = getattr(self, item)
            return val if val is not None else default
        return default

    def __contains__(self, item: str) -> bool:
        return item == "duration" or hasattr(self, item)

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["duration"] = self.duration_seconds
        d["status"] = self.status.value if isinstance(self.status, SandboxStatus) else str(self.status)
        return d

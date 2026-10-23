"""Data models for Permission Modes, Action Requests, Approval Decisions, and Audit Logs."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PermissionMode(str, Enum):
    """The 3 primary security modes defined in Pheonix spec."""
    ALWAYS_ASK = "always_ask"
    ASK_ON_CHANGES = "ask_on_changes"
    AUTO_REVIEW = "auto_review"


class ActionCategory(str, Enum):
    READ = "read"
    MUTATION = "mutation"
    EXECUTION = "execution"
    ADMIN = "admin"


class ActionType(str, Enum):
    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    FS_DELETE = "fs_delete"
    EXEC_CODE = "exec_code"
    EXEC_COMMAND = "exec_command"
    NET_REQUEST = "net_request"
    SECRET_ACCESS = "secret_access"
    CANVAS_EDIT = "canvas_edit"
    TOOL_INVOKE = "tool_invoke"

    @property
    def category(self) -> ActionCategory:
        if self in (ActionType.FS_READ,):
            return ActionCategory.READ
        elif self in (ActionType.FS_WRITE, ActionType.FS_DELETE, ActionType.CANVAS_EDIT):
            return ActionCategory.MUTATION
        elif self in (ActionType.EXEC_CODE, ActionType.EXEC_COMMAND, ActionType.TOOL_INVOKE):
            return ActionCategory.EXECUTION
        elif self in (ActionType.SECRET_ACCESS,):
            return ActionCategory.ADMIN
        return ActionCategory.MUTATION


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ActionRequest(BaseModel):
    """A privileged action requested by an agent, tool, or user."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    project_id: str = "default"
    actor_id: str = "agent"
    action_type: ActionType
    resource: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    created_at: datetime = Field(default_factory=utc_now)


class ApprovalDecision(BaseModel):
    """The final outcome for an ActionRequest."""
    model_config = ConfigDict(extra="ignore")

    request_id: str
    tenant_id: str = "default"
    status: ApprovalStatus
    decided_by: str = "system"
    reason: Optional[str] = None
    decided_at: datetime = Field(default_factory=utc_now)


class AuditEntry(BaseModel):
    """Immutable audit ledger record of a permission evaluation and decision."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    project_id: str = "default"
    mode: PermissionMode
    actor_id: str
    action_type: str
    resource: str
    status: ApprovalStatus
    decided_by: str
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)

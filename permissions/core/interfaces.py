"""Abstract interfaces for Permission Policies, Risk Scoring, Approval Queue, and Audit Store."""

from abc import ABC, abstractmethod
from typing import List, Optional
from .models import (
    ActionRequest,
    ApprovalDecision,
    AuditEntry,
    PermissionMode,
    RiskLevel,
)


class BaseRiskScorer(ABC):
    """Evaluates the risk magnitude of an action request."""

    @abstractmethod
    def score(self, request: ActionRequest) -> RiskLevel:
        """Assigns LOW, MEDIUM, HIGH, or CRITICAL risk."""
        pass


class BasePermissionPolicy(ABC):
    """Evaluates action requests against security policies and active mode."""

    @abstractmethod
    def evaluate(self, request: ActionRequest, mode: PermissionMode) -> ApprovalDecision:
        """Determines if the action is AUTO_APPROVED or requires PENDING approval."""
        pass


class BaseApprovalQueue(ABC):
    """Manages pending human-in-the-loop approval requests."""

    @abstractmethod
    def enqueue(self, request: ActionRequest, timeout_seconds: float = 60.0) -> ActionRequest:
        """Pushes an action request to the pending approval queue."""
        pass

    @abstractmethod
    def approve(self, request_id: str, approver: str = "human", reason: Optional[str] = None) -> ApprovalDecision:
        """Approves a pending request."""
        pass

    @abstractmethod
    def reject(self, request_id: str, approver: str = "human", reason: Optional[str] = None) -> ApprovalDecision:
        """Rejects a pending request."""
        pass

    @abstractmethod
    def get_pending(self, project_id: Optional[str] = None) -> List[ActionRequest]:
        """Lists active pending requests awaiting decision."""
        pass


class BaseAuditStore(ABC):
    """Append-only audit ledger for permission evaluations and decisions."""

    @abstractmethod
    def log(self, entry: AuditEntry) -> None:
        """Appends an immutable audit entry."""
        pass

    @abstractmethod
    def query(self, project_id: Optional[str] = None, limit: int = 50) -> List[AuditEntry]:
        """Queries recorded audit entries."""
        pass

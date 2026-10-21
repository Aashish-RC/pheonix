"""Permission Service: Unified facade integrating PolicyEngine, RiskScorer, ApprovalQueue, and AuditStore."""

from typing import List, Optional
from .core.models import (
    ActionRequest,
    ApprovalDecision,
    ApprovalStatus,
    AuditEntry,
    PermissionMode,
    RiskLevel,
    utc_now,
)
from .engine.policy_engine import PolicyEngine
from .engine.risk_scorer import RiskScorer
from .queue.approval_queue import ApprovalQueue
from .storage.sqlite_audit import SQLiteAuditStore


class PermissionService:
    """Unified controller governing permission modes, approvals, and audit trails."""

    def __init__(
        self,
        default_mode: PermissionMode = PermissionMode.ASK_ON_CHANGES,
        db_path: str = "./permissions.db",
        queue_timeout: float = 60.0,
    ):
        self.mode = default_mode
        self.risk_scorer = RiskScorer()
        self.policy_engine = PolicyEngine(self.risk_scorer)
        self.queue = ApprovalQueue(default_timeout=queue_timeout)
        self.audit_store = SQLiteAuditStore(db_path)

    def set_mode(self, new_mode: PermissionMode) -> None:
        """Dynamically switch between ALWAYS_ASK, ASK_ON_CHANGES, and AUTO_REVIEW."""
        self.mode = new_mode

    def request_action(
        self,
        request: ActionRequest,
        override_mode: Optional[PermissionMode] = None,
        timeout_seconds: Optional[float] = None,
    ) -> ApprovalDecision:
        """Evaluates an action request under the active mode, queuing if approval is required."""
        active_mode = override_mode or self.mode
        decision = self.policy_engine.evaluate(request, active_mode)

        if decision.status == ApprovalStatus.PENDING:
            self.queue.enqueue(request, timeout_seconds=timeout_seconds)

        # Record evaluation audit entry
        self.audit_store.log(
            AuditEntry(
                project_id=request.project_id,
                mode=active_mode,
                actor_id=request.actor_id,
                action_type=request.action_type,
                resource=request.resource,
                status=decision.status,
                decided_by=decision.decided_by,
                reason=decision.reason,
                timestamp=utc_now(),
            )
        )
        return decision

    def approve_action(
        self,
        request_id: str,
        approver: str = "human",
        reason: Optional[str] = None,
        project_id: str = "default",
    ) -> ApprovalDecision:
        """Explicitly approves a pending request in the queue and records audit log."""
        decision = self.queue.approve(request_id, approver=approver, reason=reason)
        self.audit_store.log(
            AuditEntry(
                project_id=project_id,
                mode=self.mode,
                actor_id=approver,
                action_type=decision.request_id,  # or request_id reference
                resource=f"Request {request_id}",
                status=decision.status,
                decided_by=approver,
                reason=decision.reason,
                timestamp=utc_now(),
            )
        )
        return decision

    def reject_action(
        self,
        request_id: str,
        approver: str = "human",
        reason: Optional[str] = None,
        project_id: str = "default",
    ) -> ApprovalDecision:
        """Explicitly rejects a pending request in the queue and records audit log."""
        decision = self.queue.reject(request_id, approver=approver, reason=reason)
        self.audit_store.log(
            AuditEntry(
                project_id=project_id,
                mode=self.mode,
                actor_id=approver,
                action_type=decision.request_id,
                resource=f"Request {request_id}",
                status=decision.status,
                decided_by=approver,
                reason=decision.reason,
                timestamp=utc_now(),
            )
        )
        return decision

    def get_pending_requests(self, project_id: Optional[str] = None) -> List[ActionRequest]:
        """Returns all actions awaiting human-in-the-loop sign-off."""
        return self.queue.get_pending(project_id)

    def get_audit_trail(self, project_id: Optional[str] = None, limit: int = 50) -> List[AuditEntry]:
        """Retrieves tamper-resistant audit logs."""
        return self.audit_store.query(project_id=project_id, limit=limit)

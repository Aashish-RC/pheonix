"""Permission Service: Unified facade integrating PolicyEngine, RiskScorer, ApprovalQueue, and AuditStore."""

from typing import Any, Dict, List, Optional, Union
from .core.models import (
    ActionRequest,
    ActionType,
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

    def check_permission(
        self,
        action_type: Union[ActionType, str],
        resource: str = "",
        project_id: str = "default",
        actor_id: str = "agent",
        payload: Optional[Dict[str, Any]] = None,
        override_mode: Optional[PermissionMode] = None,
    ) -> ApprovalDecision:
        """Convenience method to check permission directly without constructing ActionRequest."""
        if isinstance(action_type, str):
            try:
                action_type_enum = ActionType(action_type)
            except ValueError:
                action_type_enum = (
                    ActionType.EXEC_COMMAND
                    if "exec" in action_type.lower() or "cmd" in action_type.lower()
                    else ActionType.FS_WRITE
                )
        else:
            action_type_enum = action_type

        req = ActionRequest(
            project_id=project_id,
            actor_id=actor_id,
            action_type=action_type_enum,
            resource=resource,
            payload=payload or {},
        )
        return self.request_action(req, override_mode=override_mode)

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
                tenant_id=getattr(request, "tenant_id", "default"),
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
        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="permissions",
                action="evaluate_request",
                tenant_id=getattr(request, "tenant_id", "default"),
                project_id=request.project_id,
                user_id=request.actor_id,
                role="agent" if request.actor_id == "agent" else "user",
                resource=request.resource,
                status=decision.status.value if hasattr(decision.status, "value") else str(decision.status),
                details={
                    "request_id": request.id,
                    "action_type": request.action_type.value if hasattr(request.action_type, "value") else str(request.action_type),
                    "reason": decision.reason,
                },
            )
        except Exception:
            pass
        return decision

    def approve_action(
        self,
        request_id: str,
        approver: str = "human",
        reason: Optional[str] = None,
        project_id: str = "default",
        tenant_id: str = "default",
    ) -> ApprovalDecision:
        """Explicitly approves a pending request in the queue and records audit log."""
        decision = self.queue.approve(request_id, approver=approver, reason=reason)
        self.audit_store.log(
            AuditEntry(
                tenant_id=tenant_id,
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
        tenant_id: str = "default",
    ) -> ApprovalDecision:
        """Explicitly rejects a pending request in the queue and records audit log."""
        decision = self.queue.reject(request_id, approver=approver, reason=reason)
        self.audit_store.log(
            AuditEntry(
                tenant_id=tenant_id,
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

    def get_audit_trail(
        self,
        project_id: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> List[AuditEntry]:
        """Retrieves tamper-resistant audit logs."""
        return self.audit_store.query(project_id=project_id, limit=limit, tenant_id=tenant_id)

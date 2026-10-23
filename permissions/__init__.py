"""Pheonix Permission Modes & Access Governance Engine."""

from .core.models import (
    PermissionMode,
    ActionCategory,
    ActionType,
    RiskLevel,
    ApprovalStatus,
    ActionRequest,
    ApprovalDecision,
    AuditEntry,
)
from .core.interfaces import (
    BaseRiskScorer,
    BasePermissionPolicy,
    BaseApprovalQueue,
    BaseAuditStore,
)
from typing import Any, Dict, Optional, Union
from .engine.risk_scorer import RiskScorer
from .engine.policy_engine import PolicyEngine
from .queue.approval_queue import ApprovalQueue
from .storage.sqlite_audit import SQLiteAuditStore
from .service import PermissionService

_default_permission_service: Optional[PermissionService] = None


def get_permission_service() -> PermissionService:
    global _default_permission_service
    if _default_permission_service is None:
        _default_permission_service = PermissionService()
    return _default_permission_service


def check_permission(
    action_type: Union[ActionType, str],
    resource: str = "",
    project_id: str = "default",
    actor_id: str = "agent",
    payload: Optional[Dict[str, Any]] = None,
    override_mode: Optional[PermissionMode] = None,
    service: Optional[PermissionService] = None,
) -> ApprovalDecision:
    """Module-level permission check interceptor for Sandboxes and Agent tools."""
    svc = service or get_permission_service()
    return svc.check_permission(
        action_type=action_type,
        resource=resource,
        project_id=project_id,
        actor_id=actor_id,
        payload=payload,
        override_mode=override_mode,
    )


__all__ = [
    "PermissionMode",
    "ActionCategory",
    "ActionType",
    "RiskLevel",
    "ApprovalStatus",
    "ActionRequest",
    "ApprovalDecision",
    "AuditEntry",
    "BaseRiskScorer",
    "BasePermissionPolicy",
    "BaseApprovalQueue",
    "BaseAuditStore",
    "RiskScorer",
    "PolicyEngine",
    "ApprovalQueue",
    "SQLiteAuditStore",
    "PermissionService",
    "get_permission_service",
    "check_permission",
]

"""Policy Engine: Evaluates ActionRequests against active PermissionMode and risk scores."""

from typing import Optional
from ..core.interfaces import BasePermissionPolicy, BaseRiskScorer
from ..core.models import (
    ActionCategory,
    ActionRequest,
    ApprovalDecision,
    ApprovalStatus,
    PermissionMode,
    RiskLevel,
    utc_now,
)
from .risk_scorer import RiskScorer


class PolicyEngine(BasePermissionPolicy):
    """Core governor deciding if actions are auto-permitted or queued for human approval."""

    def __init__(self, risk_scorer: Optional[BaseRiskScorer] = None):
        self.risk_scorer = risk_scorer or RiskScorer()

    def evaluate(self, request: ActionRequest, mode: PermissionMode) -> ApprovalDecision:
        # Score risk if not already assigned
        if request.risk_level == RiskLevel.LOW:
            request.risk_level = self.risk_scorer.score(request)

        now = utc_now()

        # MODE 1: ALWAYS_ASK (Require explicit approval for everything)
        if mode == PermissionMode.ALWAYS_ASK:
            return ApprovalDecision(
                request_id=request.id,
                status=ApprovalStatus.PENDING,
                decided_by="policy_engine",
                reason="ALWAYS_ASK mode gates all actions for human approval",
                decided_at=now,
            )

        # MODE 2: ASK_ON_CHANGES (Permit read-only, gate mutations and executions)
        elif mode == PermissionMode.ASK_ON_CHANGES:
            category = request.action_type.category
            if category == ActionCategory.READ and request.risk_level != RiskLevel.CRITICAL:
                return ApprovalDecision(
                    request_id=request.id,
                    status=ApprovalStatus.AUTO_APPROVED,
                    decided_by="policy_engine",
                    reason="ASK_ON_CHANGES auto-permits non-destructive read actions",
                    decided_at=now,
                )
            else:
                return ApprovalDecision(
                    request_id=request.id,
                    status=ApprovalStatus.PENDING,
                    decided_by="policy_engine",
                    reason=f"ASK_ON_CHANGES gates state changes and execution ({request.action_type.value})",
                    decided_at=now,
                )

        # MODE 3: AUTO_REVIEW (Permit low/medium risk autonomously, gate high/critical risk)
        elif mode == PermissionMode.AUTO_REVIEW:
            if request.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return ApprovalDecision(
                    request_id=request.id,
                    status=ApprovalStatus.PENDING,
                    decided_by="policy_engine",
                    reason=f"AUTO_REVIEW gates high-risk action ({request.risk_level.value})",
                    decided_at=now,
                )
            else:
                return ApprovalDecision(
                    request_id=request.id,
                    status=ApprovalStatus.AUTO_APPROVED,
                    decided_by="policy_engine",
                    reason=f"AUTO_REVIEW auto-permits safe {request.risk_level.value}-risk action",
                    decided_at=now,
                )

        # Fallback safe default
        return ApprovalDecision(
            request_id=request.id,
            status=ApprovalStatus.PENDING,
            decided_by="policy_engine",
            reason="Unrecognized mode; default to safe gating",
            decided_at=now,
        )

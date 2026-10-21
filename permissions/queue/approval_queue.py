"""Approval Queue: Thread-safe pending action approval queue with expiration handling."""

from datetime import datetime
import threading
import time
from typing import Callable, Dict, List, Optional
from ..core.interfaces import BaseApprovalQueue
from ..core.models import (
    ActionRequest,
    ApprovalDecision,
    ApprovalStatus,
    utc_now,
)


class ApprovalQueue(BaseApprovalQueue):
    """Thread-safe queue managing human-in-the-loop pending approval requests."""

    def __init__(self, default_timeout: float = 60.0):
        self.default_timeout = default_timeout
        self._lock = threading.Lock()
        self._pending: Dict[str, ActionRequest] = {}
        self._deadlines: Dict[str, float] = {}
        self._decisions: Dict[str, ApprovalDecision] = {}
        self._callbacks: List[Callable[[ApprovalDecision], None]] = []

    def register_callback(self, callback: Callable[[ApprovalDecision], None]) -> None:
        """Register a notification callback triggered on any decision."""
        with self._lock:
            self._callbacks.append(callback)

    def _purge_expired(self) -> None:
        now_ts = time.time()
        expired_ids = []
        for req_id, deadline in list(self._deadlines.items()):
            if now_ts > deadline:
                expired_ids.append(req_id)

        for req_id in expired_ids:
            self._pending.pop(req_id, None)
            self._deadlines.pop(req_id, None)
            decision = ApprovalDecision(
                request_id=req_id,
                status=ApprovalStatus.EXPIRED,
                decided_by="system_timeout",
                reason="Request timed out waiting for human approval",
                decided_at=utc_now(),
            )
            self._decisions[req_id] = decision
            for cb in self._callbacks:
                try:
                    cb(decision)
                except Exception:
                    pass

    def enqueue(self, request: ActionRequest, timeout_seconds: Optional[float] = None) -> ActionRequest:
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout
        deadline = time.time() + timeout
        with self._lock:
            self._purge_expired()
            self._pending[request.id] = request
            self._deadlines[request.id] = deadline
        return request

    def approve(self, request_id: str, approver: str = "human", reason: Optional[str] = None) -> ApprovalDecision:
        with self._lock:
            self._purge_expired()
            if request_id not in self._pending:
                # Check if already decided
                if request_id in self._decisions:
                    return self._decisions[request_id]
                raise ValueError(f"Approval request {request_id} not found or expired")

            self._pending.pop(request_id)
            self._deadlines.pop(request_id, None)
            decision = ApprovalDecision(
                request_id=request_id,
                status=ApprovalStatus.APPROVED,
                decided_by=approver,
                reason=reason or "Approved by operator",
                decided_at=utc_now(),
            )
            self._decisions[request_id] = decision

        for cb in self._callbacks:
            try:
                cb(decision)
            except Exception:
                pass
        return decision

    def reject(self, request_id: str, approver: str = "human", reason: Optional[str] = None) -> ApprovalDecision:
        with self._lock:
            self._purge_expired()
            if request_id not in self._pending:
                if request_id in self._decisions:
                    return self._decisions[request_id]
                raise ValueError(f"Approval request {request_id} not found or expired")

            self._pending.pop(request_id)
            self._deadlines.pop(request_id, None)
            decision = ApprovalDecision(
                request_id=request_id,
                status=ApprovalStatus.REJECTED,
                decided_by=approver,
                reason=reason or "Rejected by operator",
                decided_at=utc_now(),
            )
            self._decisions[request_id] = decision

        for cb in self._callbacks:
            try:
                cb(decision)
            except Exception:
                pass
        return decision

    def get_pending(self, project_id: Optional[str] = None) -> List[ActionRequest]:
        with self._lock:
            self._purge_expired()
            requests = list(self._pending.values())
            if project_id:
                requests = [r for r in requests if r.project_id == project_id]
            return requests

    def get_decision(self, request_id: str) -> Optional[ApprovalDecision]:
        with self._lock:
            self._purge_expired()
            return self._decisions.get(request_id)

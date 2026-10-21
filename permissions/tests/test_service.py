"""Unit tests for PermissionService unified facade."""

import pytest
from permissions.core.models import (
    ActionRequest,
    ActionType,
    ApprovalStatus,
    PermissionMode,
)
from permissions.service import PermissionService


@pytest.fixture
def service():
    return PermissionService(
        default_mode=PermissionMode.ASK_ON_CHANGES,
        db_path=":memory:",
        queue_timeout=5.0,
    )


def test_service_workflow(service):
    # 1. Read action in ASK_ON_CHANGES -> Auto-approved
    req_read = ActionRequest(action_type=ActionType.FS_READ, resource="readme.md")
    d1 = service.request_action(req_read)
    assert d1.status == ApprovalStatus.AUTO_APPROVED

    # 2. Write action in ASK_ON_CHANGES -> Pending, Enqueued
    req_write = ActionRequest(action_type=ActionType.FS_WRITE, resource="secret.key")
    d2 = service.request_action(req_write)
    assert d2.status == ApprovalStatus.PENDING

    pending = service.get_pending_requests()
    assert len(pending) == 1
    assert pending[0].id == req_write.id

    # 3. Approve the pending write
    d_approved = service.approve_action(req_write.id, approver="lead_dev", reason="Authorized fix")
    assert d_approved.status == ApprovalStatus.APPROVED
    assert len(service.get_pending_requests()) == 0

    # 4. Switch mode to ALWAYS_ASK
    service.set_mode(PermissionMode.ALWAYS_ASK)
    d3 = service.request_action(req_read)
    assert d3.status == ApprovalStatus.PENDING

    # 5. Reject the pending read in ALWAYS_ASK
    d_rejected = service.reject_action(req_read.id, approver="security", reason="Lockdown active")
    assert d_rejected.status == ApprovalStatus.REJECTED

    # 6. Verify audit trail has recorded all events
    trail = service.get_audit_trail()
    assert len(trail) >= 5

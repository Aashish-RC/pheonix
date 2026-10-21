"""Unit tests for ApprovalQueue: enqueuing, decisions, callbacks, and expiration."""

import time
import pytest
from permissions.core.models import (
    ActionRequest,
    ActionType,
    ApprovalStatus,
    RiskLevel,
)
from permissions.queue.approval_queue import ApprovalQueue


@pytest.fixture
def queue():
    return ApprovalQueue(default_timeout=2.0)


def test_enqueue_and_list_pending(queue):
    req1 = ActionRequest(project_id="proj-1", action_type=ActionType.FS_WRITE, resource="a.py")
    req2 = ActionRequest(project_id="proj-2", action_type=ActionType.EXEC_CODE, resource="b.py")

    queue.enqueue(req1)
    queue.enqueue(req2)

    all_pending = queue.get_pending()
    assert len(all_pending) == 2

    p1_pending = queue.get_pending(project_id="proj-1")
    assert len(p1_pending) == 1
    assert p1_pending[0].id == req1.id


def test_approve_flow_and_callback(queue):
    req = ActionRequest(action_type=ActionType.SECRET_ACCESS, resource="stripe_key")
    queue.enqueue(req)

    callback_events = []
    queue.register_callback(lambda dec: callback_events.append(dec))

    dec = queue.approve(req.id, approver="alice@admin", reason="Verified ticket #402")
    assert dec.status == ApprovalStatus.APPROVED
    assert dec.decided_by == "alice@admin"
    assert dec.reason == "Verified ticket #402"

    # Queue should be empty now
    assert len(queue.get_pending()) == 0

    # Callback was triggered
    assert len(callback_events) == 1
    assert callback_events[0].status == ApprovalStatus.APPROVED


def test_reject_flow(queue):
    req = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="curl http://malicious.io")
    queue.enqueue(req)

    dec = queue.reject(req.id, approver="bob@security", reason="Disallowed domain")
    assert dec.status == ApprovalStatus.REJECTED
    assert dec.decided_by == "bob@security"
    assert dec.reason == "Disallowed domain"

    assert len(queue.get_pending()) == 0


def test_request_expiration(queue):
    # Enqueue with very short timeout
    req = ActionRequest(action_type=ActionType.FS_DELETE, resource="records.csv")
    queue.enqueue(req, timeout_seconds=0.1)

    assert len(queue.get_pending()) == 1
    time.sleep(0.2)

    # After deadline, queue should consider it expired
    assert len(queue.get_pending()) == 0

    dec = queue.get_decision(req.id)
    assert dec is not None
    assert dec.status == ApprovalStatus.EXPIRED

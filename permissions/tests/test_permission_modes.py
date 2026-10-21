"""Unit tests verifying that each PermissionMode changes what asks for approval."""

import pytest
from permissions.core.models import (
    ActionRequest,
    ActionType,
    ApprovalStatus,
    PermissionMode,
    RiskLevel,
)
from permissions.engine.policy_engine import PolicyEngine
from permissions.engine.risk_scorer import RiskScorer


@pytest.fixture
def engine():
    return PolicyEngine(RiskScorer())


def test_always_ask_mode_gates_everything(engine):
    """In ALWAYS_ASK, every privileged operation must require human approval."""
    mode = PermissionMode.ALWAYS_ASK

    # Benign read request
    read_req = ActionRequest(action_type=ActionType.FS_READ, resource="README.md")
    d1 = engine.evaluate(read_req, mode)
    assert d1.status == ApprovalStatus.PENDING
    assert "ALWAYS_ASK" in d1.reason

    # Benign web request
    net_req = ActionRequest(action_type=ActionType.NET_REQUEST, resource="https://example.com")
    d2 = engine.evaluate(net_req, mode)
    assert d2.status == ApprovalStatus.PENDING

    # Write request
    write_req = ActionRequest(action_type=ActionType.FS_WRITE, resource="data.txt")
    d3 = engine.evaluate(write_req, mode)
    assert d3.status == ApprovalStatus.PENDING

    # Code execution
    exec_req = ActionRequest(action_type=ActionType.EXEC_CODE, payload={"code": "print(1)"})
    d4 = engine.evaluate(exec_req, mode)
    assert d4.status == ApprovalStatus.PENDING


def test_ask_on_changes_mode_splits_reads_and_mutations(engine):
    """In ASK_ON_CHANGES, read-only requests are auto-approved; mutations require approval."""
    mode = PermissionMode.ASK_ON_CHANGES

    # Read action -> AUTO_APPROVED
    read_req = ActionRequest(action_type=ActionType.FS_READ, resource="config.json")
    d_read = engine.evaluate(read_req, mode)
    assert d_read.status == ApprovalStatus.AUTO_APPROVED

    # File write -> PENDING
    write_req = ActionRequest(action_type=ActionType.FS_WRITE, resource="config.json")
    d_write = engine.evaluate(write_req, mode)
    assert d_write.status == ApprovalStatus.PENDING
    assert "gates state changes" in d_write.reason

    # File delete -> PENDING
    del_req = ActionRequest(action_type=ActionType.FS_DELETE, resource="temp.log")
    d_del = engine.evaluate(del_req, mode)
    assert d_del.status == ApprovalStatus.PENDING

    # Execution -> PENDING
    exec_req = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="npm test")
    d_exec = engine.evaluate(exec_req, mode)
    assert d_exec.status == ApprovalStatus.PENDING


def test_auto_review_mode_permits_safe_and_gates_high_risk(engine):
    """In AUTO_REVIEW, low and medium risk actions are auto-permitted; high/critical risk is gated."""
    mode = PermissionMode.AUTO_REVIEW

    # Read action -> AUTO_APPROVED
    read_req = ActionRequest(action_type=ActionType.FS_READ, resource="main.py")
    d_read = engine.evaluate(read_req, mode)
    assert d_read.status == ApprovalStatus.AUTO_APPROVED

    # Standard benign file write -> AUTO_APPROVED (Medium risk)
    write_req = ActionRequest(action_type=ActionType.FS_WRITE, resource="output.json")
    d_write = engine.evaluate(write_req, mode)
    assert d_write.status == ApprovalStatus.AUTO_APPROVED

    # Benign python code -> AUTO_APPROVED (Medium risk)
    code_req = ActionRequest(action_type=ActionType.EXEC_CODE, payload={"code": "x = 10"})
    d_code = engine.evaluate(code_req, mode)
    assert d_code.status == ApprovalStatus.AUTO_APPROVED

    # High-risk action (Secret access) -> PENDING
    sec_req = ActionRequest(action_type=ActionType.SECRET_ACCESS, resource="master_key")
    d_sec = engine.evaluate(sec_req, mode)
    assert d_sec.status == ApprovalStatus.PENDING
    assert "gates high-risk" in d_sec.reason

    # Critical risk action (Destructive command) -> PENDING
    crit_req = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="rm -rf /")
    d_crit = engine.evaluate(crit_req, mode)
    assert d_crit.status == ApprovalStatus.PENDING
    assert d_crit.decided_by == "policy_engine"

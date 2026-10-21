"""Unit tests for RiskScorer static and heuristic risk analysis."""

import pytest
from permissions.core.models import ActionRequest, ActionType, RiskLevel
from permissions.engine.risk_scorer import RiskScorer


@pytest.fixture
def scorer():
    return RiskScorer()


def test_baseline_risk_classification(scorer):
    assert scorer.score(ActionRequest(action_type=ActionType.FS_READ, resource="file.txt")) == RiskLevel.LOW
    assert scorer.score(ActionRequest(action_type=ActionType.TOOL_INVOKE, resource="calculator")) == RiskLevel.LOW
    assert scorer.score(ActionRequest(action_type=ActionType.FS_WRITE, resource="test.py")) == RiskLevel.MEDIUM
    assert scorer.score(ActionRequest(action_type=ActionType.EXEC_CODE, payload={"code": "1+1"})) == RiskLevel.MEDIUM
    assert scorer.score(ActionRequest(action_type=ActionType.FS_DELETE, resource="temp.tmp")) == RiskLevel.HIGH
    assert scorer.score(ActionRequest(action_type=ActionType.SECRET_ACCESS, resource="api_token")) == RiskLevel.HIGH


def test_critical_command_detection(scorer):
    # Destructive unix rm -rf /
    r1 = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="rm -rf /")
    assert scorer.score(r1) == RiskLevel.CRITICAL

    # Windows destructive rmdir /s /q
    r2 = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="rmdir /s /q C:\\Windows")
    assert scorer.score(r2) == RiskLevel.CRITICAL

    # Disk format
    r3 = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="format D:")
    assert scorer.score(r3) == RiskLevel.CRITICAL

    # SQL Drop database
    r4 = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="DROP DATABASE production;")
    assert scorer.score(r4) == RiskLevel.CRITICAL

    # System shutdown
    r5 = ActionRequest(action_type=ActionType.EXEC_COMMAND, resource="shutdown -h now")
    assert scorer.score(r5) == RiskLevel.CRITICAL


def test_sensitive_path_detection(scorer):
    # .env write
    r1 = ActionRequest(action_type=ActionType.FS_WRITE, resource=".env")
    assert scorer.score(r1) == RiskLevel.CRITICAL

    # .env read
    r2 = ActionRequest(action_type=ActionType.FS_READ, resource="d:/project/.env")
    assert scorer.score(r2) == RiskLevel.HIGH

    # SSH private key
    r3 = ActionRequest(action_type=ActionType.FS_READ, resource="~/.ssh/id_rsa")
    assert scorer.score(r3) == RiskLevel.HIGH

    # System shadow file
    r4 = ActionRequest(action_type=ActionType.FS_READ, resource="/etc/shadow")
    assert scorer.score(r4) == RiskLevel.HIGH

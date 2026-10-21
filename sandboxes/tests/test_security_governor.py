"""Unit tests for SecurityGovernor: pattern blocking, network gating, and env sanitization."""

import pytest
from sandboxes.core.models import ExecutionRequest, ResourceLimits
from sandboxes.governor.security_governor import SecurityGovernor


@pytest.fixture
def governor():
    return SecurityGovernor()


def test_block_prohibited_libraries(governor):
    req = ExecutionRequest(code="import ctypes\nctypes.windll.kernel32")
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "ctypes" in err


def test_block_sensitive_file_access(governor):
    req = ExecutionRequest(code="with open('/etc/shadow') as f: data = f.read()")
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "shadow" in err


def test_network_access_gating(governor):
    # Network disabled by default
    req_no_net = ExecutionRequest(
        code="import socket\ns = socket.socket()",
        limits=ResourceLimits(network_access=False),
    )
    is_valid, err = governor.validate_request(req_no_net)
    assert not is_valid
    assert "Network access is disabled" in err

    # Network explicitly allowed
    req_with_net = ExecutionRequest(
        code="import socket\ns = socket.socket()",
        limits=ResourceLimits(network_access=True),
    )
    is_valid, err = governor.validate_request(req_with_net)
    assert is_valid
    assert err is None


def test_path_traversal_detection(governor):
    req = ExecutionRequest(
        code="print('ok')",
        files={"../../escaped.txt": "evil content"},
    )
    is_valid, err = governor.validate_request(req)
    assert not is_valid
    assert "Path traversal attempt" in err


def test_environment_sanitization(governor):
    allowed = ["PATH", "SYSTEMROOT"]
    custom = {"USER_SETTING": "123", "SAFE_VAR": "hello"}
    env = governor.sanitize_environment(allowed, custom)

    assert "PATH" in env or "SYSTEMROOT" in env
    assert env.get("USER_SETTING") == "123"
    assert env.get("SAFE_VAR") == "hello"

    # Verify no leaked secret keys
    for k in env.keys():
        assert "SECRET" not in k.upper() or k in custom

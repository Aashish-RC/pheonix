"""Unit tests for ToolDispatcher: execution of builtins, custom tools, and error handling."""

import pytest
from tools_mcp.core.models import ToolInvocation
from tools_mcp.runner.dispatcher import ToolDispatcher


@pytest.fixture
def dispatcher():
    return ToolDispatcher()


def test_builtin_calculator(dispatcher):
    inv = ToolInvocation(
        tool_name="calculator",
        arguments={"expression": "15 * 4 + 2"},
    )
    res = dispatcher.dispatch(inv)
    assert res.success is True
    assert res.output == "62"
    assert res.duration_ms >= 0


def test_builtin_string_transform(dispatcher):
    inv1 = ToolInvocation(
        tool_name="string_transform",
        arguments={"text": "hello pheonix", "operation": "upper"},
    )
    res1 = dispatcher.dispatch(inv1)
    assert res1.success is True
    assert res1.output == "HELLO PHEONIX"

    inv2 = ToolInvocation(
        tool_name="string_transform",
        arguments={"text": "radar", "operation": "reverse"},
    )
    res2 = dispatcher.dispatch(inv2)
    assert res2.output == "radar"


def test_builtin_json_query(dispatcher):
    inv = ToolInvocation(
        tool_name="json_query",
        arguments={"json_str": '{"status": "ok", "code": 200}', "key": "status"},
    )
    res = dispatcher.dispatch(inv)
    assert res.success is True
    assert res.output == "ok"


def test_builtin_hash_generator(dispatcher):
    inv = ToolInvocation(
        tool_name="hash_generator",
        arguments={"text": "pheonix", "algorithm": "sha256"},
    )
    res = dispatcher.dispatch(inv)
    assert res.success is True
    assert len(res.output) == 64


def test_unknown_tool_error(dispatcher):
    inv = ToolInvocation(tool_name="imaginary_tool_404", arguments={})
    res = dispatcher.dispatch(inv)
    assert res.success is False
    assert "not registered" in res.error

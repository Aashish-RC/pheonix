"""Integration test for the wired pipeline:
orchestrator -> agent -> tools_mcp -> web_search/browser_automation
"""

import pytest
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.core.models import PlanDAG, PlanNode, TaskStatus
from tools_mcp.runner.dispatcher import ToolDispatcher
from tools_mcp.core.models import ToolInvocation


def test_tools_mcp_to_web_search():
    """Verify tools_mcp dispatches to web_search provider."""
    dispatcher = ToolDispatcher()
    inv = ToolInvocation(tool_name="web_search", arguments={"query": "quantum computing", "num_results": 3})
    res = dispatcher.dispatch(inv)

    assert res.success is True
    assert res.output is not None
    assert len(res.output) >= 1
    assert "title" in res.output[0]
    assert "url" in res.output[0]


def test_tools_mcp_to_browser_automation():
    """Verify tools_mcp dispatches to browser_automation."""
    dispatcher = ToolDispatcher()
    inv = ToolInvocation(
        tool_name="browser_automation",
        arguments={"url": "https://example.com", "task": "Check landing page"},
    )
    res = dispatcher.dispatch(inv)

    assert res.success is True
    assert res.output is not None
    assert "success" in res.output
    assert res.output["success"] is True


def test_orchestrator_to_agent_pipeline():
    """Verify orchestrator runs agent node which executes with tools."""
    runner = ParallelDAGRunner()

    step = PlanNode(
        id="step-1",
        title="Research AI Architecture",
        action="agent:researcher",
        params={
            "prompt": "Find recent advances in distributed systems",
            "max_steps": 2,
        },
    )
    dag = PlanDAG(
        project_id="test_proj",
        nodes={"step-1": step},
    )

    report = runner.run_plan(dag)

    assert report.total_nodes == 1
    assert report.completed_nodes == 1
    assert report.failed_nodes == 0
    assert dag.nodes["step-1"].status == TaskStatus.COMPLETED
    assert dag.nodes["step-1"].output is not None

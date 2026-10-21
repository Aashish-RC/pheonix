"""Tests for OrchestratorBridge."""

import pytest
from workflow_builder.core.models import (
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowNodeType,
)
from workflow_builder.runtime.orchestrator_bridge import OrchestratorBridge


def test_orchestrator_bridge_topological_execution():
    bridge = OrchestratorBridge()

    nodes = {
        "start": WorkflowNode(
            node_id="start",
            node_type=WorkflowNodeType.TRIGGER,
            label="Start Trigger",
            action_name="init_trigger",
        ),
        "fanout": WorkflowNode(
            node_id="fanout",
            node_type=WorkflowNodeType.PARALLEL_FANOUT,
            label="Fanout",
            action_name="parallel_split",
            upstream_dependencies=["start"],
        ),
        "agent_a": WorkflowNode(
            node_id="agent_a",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="Agent A",
            action_name="agent_task_a",
            upstream_dependencies=["fanout"],
        ),
        "agent_b": WorkflowNode(
            node_id="agent_b",
            node_type=WorkflowNodeType.AGENT_STEP,
            label="Agent B",
            action_name="agent_task_b",
            upstream_dependencies=["fanout"],
        ),
        "fanin": WorkflowNode(
            node_id="fanin",
            node_type=WorkflowNodeType.AGGREGATE_FANIN,
            label="Barrier",
            action_name="barrier_join",
            upstream_dependencies=["agent_a", "agent_b"],
        ),
    }

    graph = WorkflowGraph(name="Test Topo", description="Testing", nodes=nodes)
    report = bridge.execute_workflow(graph, "test_input")

    assert report.success is True
    assert len(report.nodes_executed) == 5
    # Order: start before fanout, fanout before agents, agents before fanin
    start_idx = report.nodes_executed.index("start")
    fanout_idx = report.nodes_executed.index("fanout")
    fanin_idx = report.nodes_executed.index("fanin")
    assert start_idx < fanout_idx < fanin_idx
    assert report.parallel_branches_executed == 2

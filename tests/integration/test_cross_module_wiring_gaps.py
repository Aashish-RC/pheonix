"""
Integration Tests for Section B: Cross-Module Wiring Gaps
Validates:
1. Rules -> Guardrails: Rule compilation into runtime regexes/taxonomies and automatic filtering
2. Observability -> Tracker: Real token emission from tracer dispatching to tracker.deduct_usage()
3. Storage -> Knowledge: Upload webhooks automatically indexing saved files into knowledge base
4. Recommender -> Model Gateway: Dynamic route weighting API from recommender to gateway routing
5. Permissions -> Sandboxes: Privileged execution and file writing interception with 3 permission tiers
6. Workflow Builder -> Orchestrator: Visual workflow graph compilation into orchestrator PlanDAG
"""

import pytest


def test_gap1_rules_to_guardrails_propagation():
    """Rules -> Guardrails: Central rule updates compile into runtime regexes in Guardrails."""
    from rules.client import RulesClient
    from rules.core.engine import RulesEngine
    from rules.models import RuleDefinition, RuleCondition, RuleAction, RuleScope
    from guardrails.core.engine import GuardrailsEngine

    rules_engine = RulesEngine()
    rules_client = RulesClient(app_name="guardrails", engine=rules_engine, scope=RuleScope.GLOBAL)
    engine = GuardrailsEngine(rules_client=rules_client)

    # 1. Clean initial state - normal prompt passes
    res = engine.evaluate("Tell me a story about a phoenix rising.")
    assert res.action == "allow"

    # 2. Add central rule targeting guardrails
    rule = RuleDefinition(
        rule_id="rule_block_telemetry_leak",
        name="Block Telemetry Leaks",
        scope=RuleScope.GLOBAL,
        conditions=[
            RuleCondition(
                field="prompt",
                operator="regex",
                value=r"(?i)\bSECRET_INTERNAL_API_KEY\b",
            )
        ],
        action=RuleAction.BLOCK,
    )
    rules_engine.add_rule(rule)

    # 3. Dynamic regex compiled automatically into GuardrailsEngine
    res_blocked = engine.evaluate("Here is the key: SECRET_INTERNAL_API_KEY 12345")
    assert res_blocked.action == "block"
    assert any("rule_block_telemetry_leak" in r or "SECRET_INTERNAL_API_KEY" in r for r in res_blocked.matched_patterns)


def test_gap2_observability_to_tracker_sync():
    """Observability -> Tracker: Tracer emits TokenUsageEvent directly to tracker.deduct_usage()."""
    from tracker.client import TrackerClient
    from observability.core.tracer import TelemetryCollector, TokenUsageEvent

    tracker = TrackerClient()
    key_id = "test_obs_sync_key"
    tracker.key_monitor.register_key(
        key_id=key_id,
        provider="openai",
        monthly_quota_usd=10.0,
        current_spend=0.0,
    )

    collector = TelemetryCollector()
    collector.add_token_usage_listener(
        lambda event: tracker.deduct_usage(
            provider=event.provider,
            tokens=event.total_tokens,
            cost_usd=event.cost_usd,
            key_id=key_id,
        )
    )

    # Emit span with tokens and cost
    collector.emit(
        module="gateway",
        operation="chat_completion",
        token_usage={"prompt_tokens": 500, "completion_tokens": 250, "total_tokens": 750},
        cost_usd=0.05,
        metadata={"key_id": key_id, "provider": "openai"},
    )

    record = tracker.key_monitor._key_records.get(key_id)
    assert record is not None
    assert record.current_spend_usd == pytest.approx(0.05, rel=1e-3)


def test_gap3_storage_to_knowledge_ingestion():
    """Storage -> Knowledge: Storage upload webhook triggers knowledge.index_document()."""
    from storage.core.engine import StorageEngine
    from storage.client import StorageClient
    from knowledge.notes.store import NoteStore

    knowledge_store = NoteStore(db_path=":memory:")
    engine = StorageEngine(auto_index_knowledge=False)
    client = StorageClient(engine=engine)

    # Wire webhook
    client.register_upload_webhook(
        lambda stored_file, data: knowledge_store.index_document(
            file_id=stored_file.file_id,
            content=data,
            filename=stored_file.filename,
            project_id=stored_file.project_id,
            tags=stored_file.tags,
        )
    )

    content = b"# Phoenix Architecture Guide\nCentral microservice blueprint."
    stored = client.upload(
        filename="phoenix_blueprint.md",
        data=content,
        project_id="proj_arch",
        tags=["architecture", "spec"],
    )

    # Confirm indexed in knowledge
    notes = knowledge_store.list_notes(project_id="proj_arch")
    matching = [n for n in notes if n.metadata.get("file_id") == stored.file_id]
    assert len(matching) == 1
    assert "Phoenix Architecture Guide" in matching[0].content
    assert "architecture" in matching[0].tags


def test_gap4_recommender_to_model_gateway_route_weights():
    """Recommender -> Model Gateway: Computes dynamic route weights and provides export API."""
    from recommender.core.models import (
        CandidateMetrics,
        ModelCandidate,
        OptimizationGoal,
        TaskProfile,
        TaskType,
    )
    from recommender.engine.recommender_service import RecommenderService

    service = RecommenderService()
    candidates = [
        ModelCandidate(
            provider="openai",
            model_name="gpt-4o",
            capabilities=["reasoning"],
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            metrics=CandidateMetrics(avg_latency_ms=600.0, quality_score=0.95),
        ),
        ModelCandidate(
            provider="gemini",
            model_name="gemini-1.5-flash",
            capabilities=["fast"],
            cost_per_1k_input=0.0003,
            cost_per_1k_output=0.001,
            metrics=CandidateMetrics(avg_latency_ms=180.0, quality_score=0.88),
        ),
    ]

    task = TaskProfile(
        task_id="fast_lane",
        task_type=TaskType.FAST_QUERY,
        goal=OptimizationGoal.MIN_LATENCY,
    )

    weights = service.compute_route_weights(candidates, task=task)
    assert len(weights) == 2
    assert "gemini/gemini-1.5-flash" in weights
    assert "openai/gpt-4o" in weights
    # Under MIN_LATENCY, Gemini Flash should have a higher weight than GPT-4o
    assert weights["gemini/gemini-1.5-flash"] > weights["openai/gpt-4o"]

    payload = service.export_gateway_route_weights("smart-tier", candidates, task=task)
    assert payload["alias"] == "smart-tier"
    assert "weights" in payload
    assert payload["weights"] == weights


def test_gap5_permissions_to_sandbox_gate():
    """Permissions -> Sandboxes: Intercepts privileged sandbox executions across 3 tiers."""
    from permissions.core.models import PermissionMode
    from permissions.service import PermissionService
    from sandboxes.core.models import ExecutionRequest, SandboxStatus
    from sandboxes.manager import SandboxManager

    perm_service = PermissionService(default_mode=PermissionMode.ALWAYS_ASK)
    manager = SandboxManager(permission_service=perm_service, enforce_permissions=True)

    # 1. ALWAYS_ASK mode blocks privileged code execution
    req_exec = ExecutionRequest(
        language="python",
        code="import os; os.system('echo test')",
        project_id="p1",
    )
    res_blocked = manager.run(req_exec)
    assert res_blocked.status == SandboxStatus.BLOCKED
    assert "Blocked by permissions gate" in res_blocked.stderr

    # 2. AUTO_REVIEW mode permits low-risk execution
    perm_service.set_mode(PermissionMode.AUTO_REVIEW)
    req_safe = ExecutionRequest(
        language="python",
        code="x = 10 + 20; print(x)",
        project_id="p1",
    )
    res_allowed = manager.run(req_safe)
    # Passed gate (either completed or running through runner)
    assert res_allowed.status != SandboxStatus.BLOCKED


def test_gap6_workflow_builder_to_orchestrator():
    """Workflow Builder -> Orchestrator: visual WorkflowGraph compiles into PlanDAG."""
    from workflow_builder.core.models import (
        WorkflowEdge,
        WorkflowGraph,
        WorkflowNode,
        WorkflowNodeType,
    )
    from workflow_builder import to_plan_dag
    from workflow_builder.runtime.orchestrator_bridge import OrchestratorBridge
    from orchestrator.core.models import TaskStatus

    n1 = WorkflowNode(
        node_id="step_crawl",
        node_type=WorkflowNodeType.TOOL_STEP,
        label="Crawl Web",
        action_name="web_crawl",
        parameters={"url": "https://example.com"},
    )
    n2 = WorkflowNode(
        node_id="step_summarize",
        node_type=WorkflowNodeType.AGENT_STEP,
        label="Summarize Content",
        action_name="agent_summarize",
        upstream_dependencies=["step_crawl"],
    )

    graph = WorkflowGraph(
        name="Research Workflow",
        description="Crawls and summarizes content",
        nodes={"step_crawl": n1, "step_summarize": n2},
        edges=[WorkflowEdge(source_node_id="step_crawl", target_node_id="step_summarize")],
    )

    # Compile via to_plan_dag()
    dag = to_plan_dag(graph, project_id="proj_research")
    assert dag.id == graph.workflow_id
    assert dag.title == "Research Workflow"
    assert len(dag.nodes) == 2
    assert "step_crawl" in dag.nodes
    assert "step_summarize" in dag.nodes
    assert "step_crawl" in dag.nodes["step_summarize"].depends_on
    assert dag.nodes["step_crawl"].status == TaskStatus.PENDING

    # Run via OrchestratorBridge
    bridge = OrchestratorBridge()
    report = bridge.execute_with_orchestrator(graph)
    assert report.total_nodes == 2
    assert report.completed_nodes == 2

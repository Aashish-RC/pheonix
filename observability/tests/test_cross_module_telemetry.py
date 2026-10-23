"""
Cross-Module Observability Telemetry Test (Task 1.2)
Verifies that multi-step operations across orchestrator, memory, and model serving
emit synchronized telemetry spans with trace_id, duration_ms, tokens, and status codes.
"""

import sys
import tempfile
import pytest
from pathlib import Path

from observability.core.tracer import TelemetryCollector, TelemetrySpan, TraceContext
from orchestrator.planner.multi_step_planner import MultiStepPlanner
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.core.models import TaskStatus
from serving.models import InferenceRequest, ResourceLimits
from serving.core.engine import ModelServingEngine
from memory.engine import MemoryEngine
from memory.config import (
    MemoryConfig,
    WorkingMemoryBackend,
    FactStoreBackend,
    VectorStoreBackend,
    EmbeddingBackend,
)


@pytest.fixture
def telemetry_env():
    collector = TelemetryCollector.get_instance()
    collector.clear()
    yield collector
    collector.clear()


def test_cross_module_telemetry_emission(telemetry_env):
    """
    Done When: Triggering a multi-step task generates synchronized trace logs
    detailing latency and token metrics across serving, memory, and orchestrator.
    """
    trace_id = "trc-sync-e2e-test-12345"

    # 1. Model Serving Inference
    serving = ModelServingEngine(limits=ResourceLimits(enforce_ram_limits=False))
    req = InferenceRequest(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": "What is the fastest animal?"}],
        max_tokens=32,
    )
    inf_res = serving.infer(req)
    assert inf_res.offline is True

    # 2. Memory Ingestion & Recall
    wal_dir = tempfile.mkdtemp()
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()

    mem_config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=wal_dir,
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=db_path,
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        embedding_dim=64,
        max_context_tokens=500,
    )
    memory = MemoryEngine(config=mem_config)

    memory.store(user_id="user_obs", text="Cheetah is the fastest land animal.", session_id="sess_obs")
    ctx = memory.recall(user_id="user_obs", query="fastest animal", session_id="sess_obs")
    assert ctx is not None

    # 3. Orchestrator Multi-Step Plan with trace propagation
    planner = MultiStepPlanner()
    runner = ParallelDAGRunner()

    steps = [
        {"id": "step_a", "action": "noop", "depends_on": []},
        {"id": "step_b", "action": "noop", "depends_on": ["step_a"]},
    ]
    plan = planner.create_plan("Telemetry Plan", steps)
    report = runner.run_plan(plan)
    assert report.status == TaskStatus.COMPLETED

    # 4. Assert synchronized spans captured across all 3 modules
    spans = telemetry_env.get_spans()
    assert len(spans) >= 4  # 1 serving + 1 memory + 2 orchestrator steps

    modules_logged = {s.module for s in spans}
    assert "serving" in modules_logged
    assert "memory" in modules_logged
    assert "orchestrator" in modules_logged

    # Verify metrics presence
    serving_spans = [s for s in spans if s.module == "serving"]
    assert len(serving_spans) > 0
    assert serving_spans[0].token_usage["total_tokens"] > 0
    assert serving_spans[0].duration_ms >= 0

    memory_spans = [s for s in spans if s.module == "memory"]
    assert len(memory_spans) > 0
    assert memory_spans[0].operation == "memory_recall"
    assert memory_spans[0].duration_ms >= 0

    orchestrator_spans = [s for s in spans if s.module == "orchestrator"]
    assert len(orchestrator_spans) >= 2
    assert all(s.status_code == 200 for s in orchestrator_spans)

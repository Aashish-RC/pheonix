"""End-to-End Core Integration Test (Task W14)
Chains the complete core workflow:
1. .env configuration loaded
2. Auth registration and device login (backed by Vault key-lease engine)
3. Secret stored in Vault
4. Provider activated and verified
5. Model routing executed via serving engine
6. Memory engine writes turn and retrieves relevant context
7. Orchestrator executes a 2-step DAG plan (Step 1: sandbox code execution, Step 2: MCP tool dispatch)
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

# 1. Auth & Vault
from auth.core.manager import AuthManager
from vault.core.manager import KeyStoreManager

# 2. Providers
from providers import (
    ProviderActivationManager,
    ProviderCatalog,
    ProviderDescriptor,
    PingResult,
)

# 3. Model Serving
from serving.models import InferenceRequest, ResourceLimits
from serving.core.engine import ModelServingEngine

import sys
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR / "memory") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "memory"))

# 4. Memory
from engine import MemoryEngine
from config import (
    MemoryConfig,
    WorkingMemoryBackend,
    FactStoreBackend,
    VectorStoreBackend,
    EmbeddingBackend,
)

# 5. Orchestrator, Sandboxes, and Tools
from orchestrator.planner.multi_step_planner import MultiStepPlanner
from orchestrator.engine.dag_runner import ParallelDAGRunner
from orchestrator.core.models import TaskStatus
from sandboxes.manager import SandboxManager
from tools_mcp.runner.dispatcher import ToolDispatcher


@pytest.fixture
def test_env_setup(tmp_path):
    """Set up temporary directory paths for isolated end-to-end testing."""
    vault_file = tmp_path / "e2e_vault.enc"
    wal_dir = tmp_path / "wal"
    wal_dir.mkdir(parents=True, exist_ok=True)
    sqlite_db = tmp_path / "e2e_memory.db"

    yield {
        "vault_file": vault_file,
        "wal_dir": str(wal_dir),
        "sqlite_db": str(sqlite_db),
    }

    shutil.rmtree(wal_dir, ignore_errors=True)
    if sqlite_db.exists():
        try:
            sqlite_db.unlink()
        except OSError:
            pass


def mock_successful_probe(desc: ProviderDescriptor, secret: str) -> PingResult:
    return PingResult(
        success=True,
        latency_ms=25.0,
        status_code=200,
        error_message=None,
    )


def test_e2e_full_core_pipeline(test_env_setup):
    """
    W14: Comprehensive verification chaining all core layers from
    initial credentials to autonomous multi-step execution.
    """
    # -------------------------------------------------------------
    # Step 1: Configuration & Environment Verification
    # -------------------------------------------------------------
    root_env_example = Path(__file__).resolve().parent.parent.parent / ".env.example"
    assert root_env_example.exists(), ".env.example must exist at repository root"
    with open(root_env_example, "r", encoding="utf-8") as f:
        env_content = f.read()
    assert "PHEONIX_SECRET_KEY" in env_content
    assert "VAULT_PASSPHRASE" in env_content
    assert "QDRANT_HOST" in env_content

    # -------------------------------------------------------------
    # Step 2: Vault Initialization & Secret Storage
    # -------------------------------------------------------------
    vault_path = test_env_setup["vault_file"]
    vault = KeyStoreManager(vault_path)
    vault.initialize("master-passphrase-e2e-12345")
    assert vault.is_initialized()

    # Store provider secret in vault
    raw_api_key = "sk-live-mock-openai-key-998877"
    vault.put_secret(
        key_id="openai_prod",
        secret=raw_api_key,
        tags=["provider", "llm", "openai"],
    )
    leased = vault.get_lease("openai_prod")
    assert leased.get_plaintext() == raw_api_key
    leased.release()

    # -------------------------------------------------------------
    # Step 3: Auth Registration & Session Creation (W3: Auth -> Vault)
    # -------------------------------------------------------------
    auth_mgr = AuthManager(vault_manager=vault)
    user = auth_mgr.register_initial_user("alice", "SuperSecurePassword123!")
    assert user.username == "alice"

    session = auth_mgr.authenticate(
        username="alice",
        password="SuperSecurePassword123!",
        device_id="dev_workstation",
        device_name="Alice Workstation",
        platform="windows",
    )
    assert session.token_string is not None
    verified = auth_mgr.validate_session(session.token_string)
    assert verified["uid"] == user.user_id

    # -------------------------------------------------------------
    # Step 4: Provider Activation (W4: Providers -> Capability Matrix)
    # -------------------------------------------------------------
    prov_mgr = ProviderActivationManager(vault_manager=vault)
    success, prov_record, ping = prov_mgr.activate_provider(
        provider_id="openai",
        secret=raw_api_key,
        probe_fn=mock_successful_probe,
    )
    assert success is True
    assert ping.success is True
    assert prov_record.status.value == "active"

    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # Step 5: Model Routing & Serving Generation
    # -------------------------------------------------------------
    serving_engine = ModelServingEngine(limits=ResourceLimits(enforce_ram_limits=False))
    inf_req = InferenceRequest(
        model="llama3.2:1b",
        messages=[{"role": "user", "content": "What is the capital of France?"}],
        max_tokens=64,
    )
    inf_res = serving_engine.infer(inf_req)
    assert inf_res.offline is True
    assert len(inf_res.content) > 0

    # -------------------------------------------------------------
    # Step 6: Memory Write-back & Context Retrieval (W5 & O1)
    # -------------------------------------------------------------
    mem_config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=test_env_setup["wal_dir"],
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=test_env_setup["sqlite_db"],
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=":memory:",
        embedding_backend=EmbeddingBackend.LOCAL,
        embedding_dim=64,
        max_context_tokens=500,
    )
    memory_engine = MemoryEngine(config=mem_config)

    # Store the conversation exchange
    mem_entry = memory_engine.remember(
        user_id=user.username,
        text=f"User: {inf_req.messages[0]['content']}\nAssistant: {inf_res.content}",
        session_id=session.session_id,
    )
    assert mem_entry["user_id"] == user.username

    # Retrieve context to verify persistence
    context_pkg = memory_engine.recall(user_id=user.username, query="capital of France", session_id=session.session_id)
    assert context_pkg is not None
    assert context_pkg.user_id == user.username

    # -------------------------------------------------------------
    # Step 7: Orchestrator DAG Execution (W6, W7, W12, W13)
    # -------------------------------------------------------------
    planner = MultiStepPlanner()
    runner = ParallelDAGRunner(
        sandbox_manager=SandboxManager(),
        tool_dispatcher=ToolDispatcher(),
    )

    steps = [
        # Step 1: Code execution in isolated sandbox (W6)
        {
            "id": "step_compute",
            "title": "Compute squares in sandbox",
            "action": "code",
            "params": {
                "language": "python",
                "code": "print('SANDBOX_OK:' + str(sum(i*i for i in range(1, 5))))",
            },
            "depends_on": [],
        },
        # Step 2: Built-in tool dispatch via MCP registry (W7)
        {
            "id": "step_calc",
            "title": "Compute final multiplier via calculator tool",
            "action": "tool:calculator",
            "params": {
                "expression": "30 * 2 + 5",
            },
            "depends_on": ["step_compute"],
        },
    ]

    plan = planner.create_plan(
        title="E2E Validation Plan",
        steps_spec=steps,
        project_id="e2e_core",
    )
    report = runner.run_plan(plan)

    assert report.status == TaskStatus.COMPLETED
    assert report.completed_nodes == 2
    assert report.failed_nodes == 0
    # 1^2 + 2^2 + 3^2 + 4^2 = 1 + 4 + 9 + 16 = 30
    assert "SANDBOX_OK:30" in report.node_results["step_compute"].output
    # 30 * 2 + 5 = 65
    assert report.node_results["step_calc"].output == "65"

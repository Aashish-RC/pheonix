"""
Tests for Schema Migrations and Multi-Tenancy Isolation across all 10 modules.
"""

from datetime import datetime, timezone
import os
import sqlite3
import tempfile
import uuid
import pytest

from storage.migrations import SchemaMigrator, Migration, add_column_if_missing, table_columns


def _safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def test_schema_migrator_idempotency_and_version_tracking():
    """Verify SchemaMigrator tracks applied migrations in schema_version and executes each once."""
    conn = sqlite3.connect(":memory:")
    migrator = SchemaMigrator(conn)

    # Initial migration state
    assert migrator.get_applied_versions() == []

    # Migration 1: create a legacy table
    def _v1(c: sqlite3.Connection):
        c.execute("CREATE TABLE test_table (id TEXT PRIMARY KEY, name TEXT NOT NULL)")

    # Migration 2: alter table to add tenant_id
    def _v2(c: sqlite3.Connection):
        add_column_if_missing(c, "test_table", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
        c.execute("CREATE INDEX idx_test_tenant ON test_table(tenant_id)")

    migrator.apply_all([
        Migration(version=1, name="create_test_table", up=_v1),
        Migration(version=2, name="add_tenant_id", up=_v2),
    ])

    assert migrator.get_applied_versions() == [1, 2]
    assert "tenant_id" in table_columns(conn, "test_table")

    # Re-running migrations should be no-op
    applied = migrator.apply_all([
        Migration(version=1, name="create_test_table", up=_v1),
        Migration(version=2, name="add_tenant_id", up=_v2),
    ])
    assert applied == 0


def test_legacy_database_migration_without_data_loss():
    """Simulate an older DB created without tenant_id or schema_version table."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Pre-seed older schema without tenant_id
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE permission_audit (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL DEFAULT 'default',
                mode TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                resource TEXT NOT NULL,
                status TEXT NOT NULL,
                decided_by TEXT NOT NULL,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO permission_audit VALUES (
                'audit_1', 'proj_alpha', 'always_ask', 'user_1', 'EXECUTE',
                'tool:shell', 'approved', 'admin', 'ok', '2026-01-01T00:00:00Z'
            )
        """)
        conn.commit()
        conn.close()

        # Connect with SQLiteAuditStore
        from permissions.storage.sqlite_audit import SQLiteAuditStore
        store = SQLiteAuditStore(db_path=db_path)

        # Confirm old record migrated cleanly and has tenant_id default
        records = store.query(project_id="proj_alpha")
        assert len(records) == 1
        assert records[0].id == "audit_1"
        assert getattr(records[0], "tenant_id", None) == "default"

        # Check schema_version in the DB
        conn2 = sqlite3.connect(db_path)
        versions = [r[0] for r in conn2.execute("SELECT version FROM schema_version").fetchall()]
        assert 1 in versions
        assert 2 in versions
        conn2.close()
    finally:
        _safe_remove(db_path)


# ==============================================================================
# Module 1: tracker tenancy
# ==============================================================================
def test_tracker_tenancy():
    from tracker.models import SubscriptionPlan, KeyQuotaStatus, ProviderRenewal
    from tracker.core.plans import PlanRegistry
    from tracker.core.key_monitor import KeyMonitor
    from tracker.client import TrackerClient

    plans = PlanRegistry()
    plans.register_plan(SubscriptionPlan(
        plan_id="custom-plan-tenant-a",
        tenant_id="tenant_a",
        provider="custom_ai",
        name="Custom AI Plan A",
        monthly_quota_usd=100.0,
    ))
    plans.register_plan(SubscriptionPlan(
        plan_id="custom-plan-tenant-b",
        tenant_id="tenant_b",
        provider="custom_ai",
        name="Custom AI Plan B",
        monthly_quota_usd=500.0,
    ))

    monitor = KeyMonitor(plan_registry=plans)
    k_a = monitor.register_key("key-a", "custom_ai", current_spend=20.0, tenant_id="tenant_a")
    k_b = monitor.register_key("key-b", "custom_ai", current_spend=50.0, tenant_id="tenant_b")

    assert k_a.tenant_id == "tenant_a"
    assert k_a.monthly_quota_usd == 100.0
    assert k_b.tenant_id == "tenant_b"
    assert k_b.monthly_quota_usd == 500.0

    # Tenant filtering
    tenant_a_keys = monitor.list_keys(tenant_id="tenant_a")
    assert len(tenant_a_keys) == 1
    assert tenant_a_keys[0].key_id == "key-a"

    # Client level
    client = TrackerClient(plan_registry=plans, key_monitor=monitor)
    assert len(client.list_all_keys(tenant_id="tenant_b")) == 1


# ==============================================================================
# Module 2: registry tenancy
# ==============================================================================
def test_registry_tenancy():
    from registry.models import ComponentManifest
    from registry.core.engine import ComponentRegistry

    reg = ComponentRegistry()
    m_a = ComponentManifest(name="tool_a", version="1.0.0", description="Tool A", tenant_id="tenant_alpha")
    m_b = ComponentManifest(name="tool_b", version="1.0.0", description="Tool B", tenant_id="tenant_beta")

    reg.register_component(m_a)
    reg.register_component(m_b)

    assert reg.get_component("tool_a", tenant_id="tenant_alpha") is not None
    assert reg.get_component("tool_a", tenant_id="tenant_beta") is None
    assert len(reg.list_components(tenant_id="tenant_alpha")) == 1


# ==============================================================================
# Module 3: providers tenancy
# ==============================================================================
def test_providers_tenancy():
    from providers.models import ProviderDescriptor, ActivatedProvider, PingResult, ProviderStatus
    from providers.core.manager import ProviderActivationManager

    mgr = ProviderActivationManager()
    dummy_ping = lambda desc, secret: PingResult(success=True, latency_ms=12.0)

    _, rec_a, _ = mgr.activate_provider("openai", secret="sk-mock-a", probe_fn=dummy_ping, tenant_id="tenant_x")
    assert rec_a.tenant_id == "tenant_x"

    providers_x = mgr.list_activated_providers(tenant_id="tenant_x")
    assert len(providers_x) == 1
    assert providers_x[0].tenant_id == "tenant_x"

    providers_y = mgr.list_activated_providers(tenant_id="tenant_y")
    assert len(providers_y) == 0


# ==============================================================================
# Module 4: observability tenancy & migration
# ==============================================================================
def test_observability_tenancy_and_storage():
    from observability.core.store import ObservabilityStore
    from observability.core.logger import UsageCostLogger
    from observability.client import ObservabilityClient

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        client = ObservabilityClient(db_path=db_path)
        client.log_inference(
            request_id="req_1",
            model="gpt-4o",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            tenant_id="tenant_blue",
        )
        client.log_inference(
            request_id="req_2",
            model="gpt-4o",
            provider="openai",
            prompt_tokens=200,
            completion_tokens=100,
            tenant_id="tenant_green",
        )

        view_blue = client.get_personal_view(tenant_id="tenant_blue")
        assert view_blue.total_requests == 1
        assert view_blue.total_tokens == 150
        assert view_blue.tenant_id == "tenant_blue"

        view_green = client.get_personal_view(tenant_id="tenant_green")
        assert view_green.total_requests == 1
        assert view_green.total_tokens == 300
    finally:
        _safe_remove(db_path)


# ==============================================================================
# Module 5: canvas tenancy & migration
# ==============================================================================
def test_canvas_tenancy_and_storage():
    from canvas.core.models import CanvasBoard, ArtifactType
    from canvas.storage.sqlite_canvas import SQLiteCanvasStore
    from canvas.artifacts.manager import SQLiteArtifactManager

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = SQLiteCanvasStore(db_path=db_path)
        b_a = CanvasBoard(name="Board A", tenant_id="tenant_1", project_id="proj_1")
        b_b = CanvasBoard(name="Board B", tenant_id="tenant_2", project_id="proj_1")
        store.save_board(b_a)
        store.save_board(b_b)

        assert len(store.list_boards(project_id="proj_1", tenant_id="tenant_1")) == 1
        assert len(store.list_boards(project_id="proj_1", tenant_id="tenant_2")) == 1

        # Artifacts
        art_mgr = SQLiteArtifactManager(db_path=db_path)
        art = art_mgr.create_artifact(
            project_id="proj_1",
            title="Design.md",
            artifact_type=ArtifactType.MARKDOWN,
            initial_content="# Design",
            tenant_id="tenant_1",
        )
        assert art.tenant_id == "tenant_1"
        assert len(art_mgr.list_artifacts(project_id="proj_1", tenant_id="tenant_1")) == 1
        assert len(art_mgr.list_artifacts(project_id="proj_1", tenant_id="tenant_2")) == 0
    finally:
        _safe_remove(db_path)


# ==============================================================================
# Module 6: sync_engine tenancy
# ==============================================================================
def test_sync_engine_tenancy():
    from sync_engine.core.models import EntityType, MutationType
    from sync_engine.core.delta_tracker import DeltaChangeTracker
    from sync_engine.core.protocol import SyncProtocol

    tracker = DeltaChangeTracker(node_id="node_1")
    mut_a = tracker.record_mutation("ent_1", EntityType.CHAT, MutationType.INSERT, {"msg": "hi"}, tenant_id="tenant_alpha")
    mut_b = tracker.record_mutation("ent_2", EntityType.CHAT, MutationType.INSERT, {"msg": "bye"}, tenant_id="tenant_beta")

    assert mut_a.tenant_id == "tenant_alpha"
    assert mut_b.tenant_id == "tenant_beta"
    assert len(tracker.get_deltas_since(0.0, tenant_id="tenant_alpha")) == 1

    protocol = SyncProtocol()
    packet = protocol.create_packet("node_1", "node_2", [mut_a], tenant_id="tenant_alpha")
    assert packet.tenant_id == "tenant_alpha"

    store = {}
    protocol.ingest_packet(packet, store)
    assert store["ent_1"].tenant_id == "tenant_alpha"


# ==============================================================================
# Module 7: notifications tenancy
# ==============================================================================
def test_notifications_tenancy():
    from notifications.core.models import NotificationItem, NotificationRule
    from notifications.storage.inbox_store import InboxStore

    inbox = InboxStore()
    n_a = NotificationItem(title="Alert A", body="Body A", tenant_id="org_a", user_id="u1")
    n_b = NotificationItem(title="Alert B", body="Body B", tenant_id="org_b", user_id="u1")

    inbox.save_notification(n_a)
    inbox.save_notification(n_b)

    assert len(inbox.list_notifications(user_id="u1", tenant_id="org_a")) == 1
    assert len(inbox.list_notifications(user_id="u1", tenant_id="org_b")) == 1
    assert inbox.list_notifications(user_id="u1", tenant_id="org_a")[0].title == "Alert A"


# ==============================================================================
# Module 8: recommender tenancy
# ==============================================================================
def test_recommender_tenancy():
    from recommender.core.models import TaskProfile, ModelCandidate
    from recommender.engine.recommender_service import RecommenderService

    service = RecommenderService()
    task = TaskProfile(task_id="task_1", tenant_id="corp_x")
    candidates = [
        ModelCandidate(provider="openai", model_name="gpt-4o-mini"),
        ModelCandidate(provider="anthropic", model_name="claude-3-haiku"),
    ]
    decision = service.recommend_model(task, candidates)
    assert decision.tenant_id == "corp_x"


# ==============================================================================
# Module 9: release_finishing tenancy
# ==============================================================================
def test_release_finishing_tenancy():
    from release_finishing.core.models import ReleasePackage, SystemHealthReport

    pkg = ReleasePackage(
        version="1.2.0",
        sha256_bundle_checksum="abc12345",
        tenant_id="tenant_release",
    )
    assert pkg.tenant_id == "tenant_release"

    report = SystemHealthReport(
        overall_healthy=True,
        health_score=1.0,
        tenant_id="tenant_release",
    )
    assert report.tenant_id == "tenant_release"


# ==============================================================================
# Module 10: orchestrator tenancy & migration
# ==============================================================================
def test_orchestrator_tenancy_and_storage():
    from orchestrator.core.models import PlanDAG, PlanNode
    from orchestrator.storage.sqlite_plan_store import SQLitePlanStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        store = SQLitePlanStore(db_path=db_path)
        plan_1 = PlanDAG(title="Pipeline 1", tenant_id="tenant_p1", project_id="proj_1")
        plan_2 = PlanDAG(title="Pipeline 2", tenant_id="tenant_p2", project_id="proj_1")

        store.save_plan(plan_1)
        store.save_plan(plan_2)

        fetched = store.get_plan(plan_1.id, tenant_id="tenant_p1")
        assert fetched is not None
        assert fetched.tenant_id == "tenant_p1"

        # Cross-tenant query isolation
        assert store.get_plan(plan_1.id, tenant_id="tenant_p2") is None
        assert len(store.list_plans(tenant_id="tenant_p1")) == 1
        assert len(store.list_plans(tenant_id="tenant_p2")) == 1
    finally:
        _safe_remove(db_path)

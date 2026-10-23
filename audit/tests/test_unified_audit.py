"""
Tests for Unified Cross-Module Audit Log and Cryptographic Hash Chaining.
"""

import pytest
import sqlite3
from audit.models import UnifiedAuditEntry, AuditSeverity, UserRole
from audit.ledger import UnifiedAuditLedger
from audit.client import AuditLogger, set_audit_logger


@pytest.fixture
def memory_ledger():
    return UnifiedAuditLedger(db_path=":memory:")


def test_audit_entry_creation_and_defaults():
    entry = UnifiedAuditEntry(
        module="vault",
        action="secret_read",
        resource="openai_api_key",
        role=UserRole.ADMIN.value,
        tenant_id="tenant_alpha",
        user_id="user_123",
    )
    assert entry.module == "vault"
    assert entry.action == "secret_read"
    assert entry.role == "admin"
    assert entry.tenant_id == "tenant_alpha"
    assert entry.severity == AuditSeverity.INFO
    assert entry.status == "success"


def test_ledger_append_and_query(memory_ledger):
    e1 = UnifiedAuditEntry(
        tenant_id="t1",
        user_id="u1",
        role=UserRole.OWNER.value,
        module="auth",
        action="login",
        resource="device_phone",
    )
    e2 = UnifiedAuditEntry(
        tenant_id="t1",
        user_id="u2",
        role=UserRole.AGENT.value,
        module="permissions",
        action="evaluate_request",
        resource="fs_write:/etc/hosts",
        status="denied",
        severity=AuditSeverity.WARNING,
    )
    e3 = UnifiedAuditEntry(
        tenant_id="t2",
        user_id="u3",
        role=UserRole.MEMBER.value,
        module="vault",
        action="get_secret",
        resource="db_url",
    )

    hash1 = memory_ledger.log(e1)
    hash2 = memory_ledger.log(e2)
    hash3 = memory_ledger.log(e3)

    assert hash1 is not None and len(hash1) == 64
    assert hash2 != hash1
    assert hash3 != hash2

    # Query tenant t1
    t1_entries = memory_ledger.query(tenant_id="t1")
    assert len(t1_entries) == 2
    # Verify latest first
    assert t1_entries[0].action == "evaluate_request"
    assert t1_entries[1].action == "login"

    # Query role agent
    agent_entries = memory_ledger.query(role="agent")
    assert len(agent_entries) == 1
    assert agent_entries[0].user_id == "u2"

    # Query module vault
    vault_entries = memory_ledger.query(module="vault")
    assert len(vault_entries) == 1
    assert vault_entries[0].tenant_id == "t2"


def test_ledger_tamper_evident_integrity(memory_ledger):
    for i in range(5):
        entry = UnifiedAuditEntry(
            tenant_id="tenant_prod",
            user_id=f"user_{i}",
            role=UserRole.USER.value,
            module="sandboxes",
            action="execute_code",
            resource=f"snippet_{i}.py",
            details={"cpu_ms": 12.5 + i},
        )
        memory_ledger.log(entry)

    # Initial verification must pass
    assert memory_ledger.verify_integrity() is True

    # Artificially tamper with a row in the database
    conn = memory_ledger._get_connection()
    conn.execute("UPDATE unified_audit_log SET action = 'tampered_action' WHERE seq = 3")
    conn.commit()

    # Verification must now fail
    assert memory_ledger.verify_integrity() is False


def test_audit_logger_singleton_and_recording():
    ledger = UnifiedAuditLedger(db_path=":memory:")
    logger = AuditLogger(ledger=ledger)
    set_audit_logger(logger)

    h = logger.record(
        module="storage",
        action="upload_blob",
        tenant_id="tenant_omega",
        user_id="user_admin",
        role=UserRole.ADMIN,
        resource="s3://bucket/dataset.parquet",
        status="success",
    )
    assert len(h) == 64

    results = logger.query(tenant_id="tenant_omega")
    assert len(results) == 1
    assert results[0].module == "storage"
    assert results[0].resource == "s3://bucket/dataset.parquet"
    assert logger.verify_integrity() is True

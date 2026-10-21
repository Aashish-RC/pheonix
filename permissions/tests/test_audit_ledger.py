"""Unit tests for SQLiteAuditStore append-only ledger."""

import pytest
from permissions.core.models import (
    ActionType,
    ApprovalStatus,
    AuditEntry,
    PermissionMode,
)
from permissions.storage.sqlite_audit import SQLiteAuditStore


@pytest.fixture
def audit_store():
    return SQLiteAuditStore(db_path=":memory:")


def test_audit_logging_and_querying(audit_store):
    e1 = AuditEntry(
        project_id="proj-alpha",
        mode=PermissionMode.ALWAYS_ASK,
        actor_id="agent-007",
        action_type=ActionType.FS_WRITE.value,
        resource="main.py",
        status=ApprovalStatus.PENDING,
        decided_by="policy_engine",
        reason="ALWAYS_ASK requires approval",
    )
    e2 = AuditEntry(
        project_id="proj-alpha",
        mode=PermissionMode.ALWAYS_ASK,
        actor_id="operator",
        action_type=ActionType.FS_WRITE.value,
        resource="main.py",
        status=ApprovalStatus.APPROVED,
        decided_by="operator",
        reason="Approved code patch",
    )
    e3 = AuditEntry(
        project_id="proj-beta",
        mode=PermissionMode.AUTO_REVIEW,
        actor_id="agent-008",
        action_type=ActionType.FS_READ.value,
        resource="notes.md",
        status=ApprovalStatus.AUTO_APPROVED,
        decided_by="policy_engine",
    )

    audit_store.log(e1)
    audit_store.log(e2)
    audit_store.log(e3)

    all_entries = audit_store.query(limit=10)
    assert len(all_entries) == 3

    alpha_entries = audit_store.query(project_id="proj-alpha", limit=10)
    assert len(alpha_entries) == 2
    assert alpha_entries[0].project_id == "proj-alpha"

    beta_entries = audit_store.query(project_id="proj-beta", limit=10)
    assert len(beta_entries) == 1
    assert beta_entries[0].status == ApprovalStatus.AUTO_APPROVED

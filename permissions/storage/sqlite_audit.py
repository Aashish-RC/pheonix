"""SQLite Audit Store: Append-only persistent ledger for permission decisions."""

from datetime import datetime
from pathlib import Path
import sqlite3
import threading
from typing import List, Optional
from ..core.interfaces import BaseAuditStore
from ..core.models import (
    ActionType,
    ApprovalStatus,
    AuditEntry,
    PermissionMode,
)


class SQLiteAuditStore(BaseAuditStore):
    """Append-only audit ledger storing permission evaluations and approval events."""

    def __init__(self, db_path: str = "./permissions_audit.db"):
        self._db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row

        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        from storage.migrations import SchemaMigrator, Migration, add_column_if_missing
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS permission_audit (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    mode TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decided_by TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                );
            """)

            def _migrate_v1(c: sqlite3.Connection):
                add_column_if_missing(c, "permission_audit", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_tenant
                    ON permission_audit(tenant_id);
                """)

            def _migrate_v2(c: sqlite3.Connection):
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_project
                    ON permission_audit(project_id);
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON permission_audit(timestamp DESC);
                """)

            migrator = SchemaMigrator(conn)
            migrator.apply_all([
                Migration(version=1, name="permission_audit_tenant_id", up=_migrate_v1),
                Migration(version=2, name="permission_audit_indexes", up=_migrate_v2),
            ])
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def log(self, entry: AuditEntry) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO permission_audit (
                        id, tenant_id, project_id, mode, actor_id, action_type, resource, status, decided_by, reason, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        getattr(entry, "tenant_id", "default"),
                        entry.project_id,
                        entry.mode.value if hasattr(entry.mode, "value") else str(entry.mode),
                        entry.actor_id,
                        entry.action_type.value if hasattr(entry.action_type, "value") else str(entry.action_type),
                        entry.resource,
                        entry.status.value if hasattr(entry.status, "value") else str(entry.status),
                        entry.decided_by,
                        entry.reason,
                        entry.timestamp.isoformat(),
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

    def query(
        self,
        project_id: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> List[AuditEntry]:
        conditions = []
        params: list = []
        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        
        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        query_sql = f"SELECT * FROM permission_audit{where_clause} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query_sql, params)
                rows = cur.fetchall()
                entries = []
                for r in rows:
                    row_keys = r.keys()
                    entries.append(
                        AuditEntry(
                            id=r["id"],
                            tenant_id=r["tenant_id"] if "tenant_id" in row_keys else "default",
                            project_id=r["project_id"],
                            mode=PermissionMode(r["mode"]),
                            actor_id=r["actor_id"],
                            action_type=r["action_type"],
                            resource=r["resource"],
                            status=ApprovalStatus(r["status"]),
                            decided_by=r["decided_by"],
                            reason=r["reason"],
                            timestamp=datetime.fromisoformat(r["timestamp"]),
                        )
                    )
                return entries
            finally:
                if self._memory_conn is None:
                    conn.close()

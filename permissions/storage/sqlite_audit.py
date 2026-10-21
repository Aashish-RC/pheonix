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
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS permission_audit (
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
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_project
                ON permission_audit(project_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON permission_audit(timestamp DESC);
            """)
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
                        id, project_id, mode, actor_id, action_type, resource, status, decided_by, reason, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
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

    def query(self, project_id: Optional[str] = None, limit: int = 50) -> List[AuditEntry]:
        query_sql = "SELECT * FROM permission_audit"
        params: list = []
        if project_id:
            query_sql += " WHERE project_id = ?"
            params.append(project_id)
        query_sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query_sql, params)
                rows = cur.fetchall()
                entries = []
                for r in rows:
                    entries.append(
                        AuditEntry(
                            id=r["id"],
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

"""
Pheonix Observability Storage Engine
Append-only transactional SQLite ledger for persisting model usage and cost metrics.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional
from ..models import UsageRecord


class ObservabilityStore:
    """
    Local, append-only SQLite store for usage and metering records.
    Ensures zero external network dependencies and absolute data integrity.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".pheonix" / "observability.db"
        if isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes the database schema if not present with migration support."""
        from storage.migrations import SchemaMigrator, Migration, add_column_if_missing
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_ledger (
                    record_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    cached INTEGER NOT NULL,
                    status_code INTEGER NOT NULL
                )
            """)

            def _migrate_v1_indexes(c: sqlite3.Connection):
                c.execute("CREATE INDEX IF NOT EXISTS idx_actor ON usage_ledger(actor)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_model ON usage_ledger(model)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON usage_ledger(timestamp)")

            def _migrate_v2_tenant(c: sqlite3.Connection):
                add_column_if_missing(c, "usage_ledger", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("CREATE INDEX IF NOT EXISTS idx_ledger_tenant ON usage_ledger(tenant_id)")

            migrator = SchemaMigrator(conn)
            migrator.apply_all([
                Migration(version=1, name="initial_usage_ledger_indexes", up=_migrate_v1_indexes),
                Migration(version=2, name="usage_ledger_tenant_id", up=_migrate_v2_tenant),
            ])
            conn.commit()

    def insert_record(self, record: UsageRecord) -> None:
        """Appends a new usage record into the immutable ledger."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO usage_ledger (
                    record_id, request_id, tenant_id, timestamp, actor, model, provider,
                    prompt_tokens, completion_tokens, total_tokens, cost_usd,
                    latency_ms, cached, status_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.record_id,
                record.request_id,
                getattr(record, "tenant_id", "default") or "default",
                record.timestamp,
                record.actor,
                record.model,
                record.provider,
                record.prompt_tokens,
                record.completion_tokens,
                record.total_tokens,
                record.cost_usd,
                record.latency_ms,
                1 if record.cached else 0,
                record.status_code
            ))
            conn.commit()

    def get_records(
        self,
        actor: Optional[str] = None,
        model: Optional[str] = None,
        since_timestamp: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[UsageRecord]:
        """Queries stored records with optional filtering."""
        query = "SELECT * FROM usage_ledger WHERE 1=1"
        params = []

        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if actor:
            query += " AND actor = ?"
            params.append(actor)
        if model:
            query += " AND model = ?"
            params.append(model)
        if since_timestamp:
            query += " AND timestamp >= ?"
            params.append(since_timestamp)

        query += " ORDER BY timestamp ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                UsageRecord(
                    record_id=r["record_id"],
                    request_id=r["request_id"],
                    tenant_id=r["tenant_id"] if "tenant_id" in r.keys() else "default",
                    timestamp=r["timestamp"],
                    actor=r["actor"],
                    model=r["model"],
                    provider=r["provider"],
                    prompt_tokens=r["prompt_tokens"],
                    completion_tokens=r["completion_tokens"],
                    total_tokens=r["total_tokens"],
                    cost_usd=r["cost_usd"],
                    latency_ms=r["latency_ms"],
                    cached=bool(r["cached"]),
                    status_code=r["status_code"]
                )
                for r in rows
            ]

    def count_records(self, tenant_id: Optional[str] = None) -> int:
        with self._get_connection() as conn:
            if tenant_id:
                row = conn.execute("SELECT COUNT(*) FROM usage_ledger WHERE tenant_id = ?", (tenant_id,)).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM usage_ledger").fetchone()
            return row[0] if row else 0

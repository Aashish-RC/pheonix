"""
Pheonix Database Migration Engine
Provides schema-version tracking and auto-migration for SQLite databases.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Callable, List, Optional, Union


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Migration:
    version: int
    name: str
    up: Union[str, List[str], Callable[[sqlite3.Connection], None]]


class SchemaMigrator:
    """
    Manages and applies versioned migrations to an SQLite database.
    Creates and maintains a schema version tracking table.
    """

    def __init__(self, conn: sqlite3.Connection, table_name: str = "schema_version"):
        self.conn = conn
        self.table_name = table_name
        self._ensure_version_table()

    def _ensure_version_table(self) -> None:
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def get_applied_versions(self) -> List[int]:
        cur = self.conn.execute(f"SELECT version FROM {self.table_name} ORDER BY version ASC")
        return [row[0] for row in cur.fetchall()]

    def is_applied(self, version: int) -> bool:
        cur = self.conn.execute(f"SELECT 1 FROM {self.table_name} WHERE version = ?", (version,))
        return cur.fetchone() is not None

    def apply_migration(self, migration: Migration) -> bool:
        if self.is_applied(migration.version):
            return False

        if callable(migration.up):
            migration.up(self.conn)
        elif isinstance(migration.up, str):
            self.conn.execute(migration.up)
        elif isinstance(migration.up, list):
            for statement in migration.up:
                self.conn.execute(statement)

        self.conn.execute(
            f"INSERT INTO {self.table_name} (version, name, applied_at) VALUES (?, ?, ?)",
            (migration.version, migration.name, utc_now_iso()),
        )
        self.conn.commit()
        return True

    def apply_all(self, migrations: List[Migration]) -> int:
        applied_count = 0
        sorted_migrations = sorted(migrations, key=lambda m: m.version)
        for m in sorted_migrations:
            if self.apply_migration(m):
                applied_count += 1
        return applied_count


def table_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
    """Helper to inspect column names of a table."""
    try:
        cur = conn.execute(f"PRAGMA table_info({table_name})")
        return [r["name"] if isinstance(r, sqlite3.Row) else r[1] for r in cur.fetchall()]
    except Exception:
        return []


def add_column_if_missing(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> bool:
    """Safely adds a column to an existing table if it does not already exist."""
    cols = table_columns(conn, table_name)
    if cols and column_name not in cols:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
        return True
    return False

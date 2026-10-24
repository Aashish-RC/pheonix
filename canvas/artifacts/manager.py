"""Artifact Manager: Versioned live artifacts with time-travel revision snapshots."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading
from typing import List, Optional
from uuid import UUID, uuid4

from ..core.interfaces import BaseArtifactManager
from ..core.models import (
    Artifact,
    ArtifactRevision,
    ArtifactType,
    utc_now,
)
from .diff import ArtifactDiffEngine


class SQLiteArtifactManager(BaseArtifactManager):
    """SQLite engine managing versioned live artifacts and time-travel revisions."""

    def __init__(self, db_path: str = "./artifacts.db"):
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
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    artifact_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    current_version INTEGER NOT NULL DEFAULT 1,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            def _migrate_v1_tables_and_indexes(c: sqlite3.Connection):
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_artifacts_project
                    ON artifacts(project_id);
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS artifact_revisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        artifact_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        author TEXT NOT NULL,
                        diff_summary TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE,
                        UNIQUE(artifact_id, version)
                    );
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_revisions_artifact
                    ON artifact_revisions(artifact_id);
                """)

            def _migrate_v2_tenant_id(c: sqlite3.Connection):
                add_column_if_missing(c, "artifacts", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_artifacts_tenant
                    ON artifacts(tenant_id);
                """)

            migrator = SchemaMigrator(conn, table_name="artifacts_schema_version")
            migrator.apply_all([
                Migration(version=1, name="initial_artifact_tables", up=_migrate_v1_tables_and_indexes),
                Migration(version=2, name="artifacts_tenant_id", up=_migrate_v2_tenant_id),
            ])
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def create_artifact(
        self,
        project_id: str,
        title: str,
        artifact_type: ArtifactType,
        initial_content: str,
        author: str = "agent",
        tenant_id: str = "default",
    ) -> Artifact:
        artifact_id = uuid4()
        now = utc_now()

        rev1 = ArtifactRevision(
            version=1,
            content=initial_content,
            author=author,
            diff_summary="Initial version",
            created_at=now,
        )

        artifact = Artifact(
            id=artifact_id,
            tenant_id=tenant_id,
            project_id=project_id,
            artifact_type=artifact_type,
            title=title,
            current_version=1,
            revisions=[rev1],
            metadata={},
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                        id, tenant_id, project_id, artifact_type, title, current_version, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(artifact.id),
                        artifact.tenant_id,
                        artifact.project_id,
                        artifact.artifact_type.value,
                        artifact.title,
                        artifact.current_version,
                        json.dumps(artifact.metadata),
                        artifact.created_at.isoformat(),
                        artifact.updated_at.isoformat(),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO artifact_revisions (
                        artifact_id, version, content, author, diff_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(artifact.id),
                        rev1.version,
                        rev1.content,
                        rev1.author,
                        rev1.diff_summary,
                        rev1.created_at.isoformat(),
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

        return artifact

    def get_artifact(
        self,
        artifact_id: UUID,
        tenant_id: Optional[str] = None,
    ) -> Optional[Artifact]:
        with self._lock:
            conn = self._get_connection()
            try:
                query = "SELECT * FROM artifacts WHERE id = ?"
                params: list = [str(artifact_id)]
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                cur = conn.execute(query, params)
                art_row = cur.fetchone()
                if not art_row:
                    return None

                rev_cur = conn.execute(
                    "SELECT * FROM artifact_revisions WHERE artifact_id = ? ORDER BY version ASC",
                    (str(artifact_id),),
                )
                revisions = [
                    ArtifactRevision(
                        version=r["version"],
                        content=r["content"],
                        author=r["author"],
                        diff_summary=r["diff_summary"],
                        created_at=datetime.fromisoformat(r["created_at"]),
                    )
                    for r in rev_cur.fetchall()
                ]

                return Artifact(
                    id=UUID(art_row["id"]),
                    tenant_id=art_row["tenant_id"] if "tenant_id" in art_row.keys() else "default",
                    project_id=art_row["project_id"],
                    artifact_type=ArtifactType(art_row["artifact_type"]),
                    title=art_row["title"],
                    current_version=int(art_row["current_version"]),
                    revisions=revisions,
                    metadata=json.loads(art_row["metadata"]),
                    created_at=datetime.fromisoformat(art_row["created_at"]),
                    updated_at=datetime.fromisoformat(art_row["updated_at"]),
                )
            finally:
                if self._memory_conn is None:
                    conn.close()

    def list_artifacts(
        self,
        project_id: str = "default",
        tenant_id: Optional[str] = None,
    ) -> List[Artifact]:
        with self._lock:
            conn = self._get_connection()
            try:
                query = "SELECT id FROM artifacts WHERE project_id = ?"
                params: list = [project_id]
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                query += " ORDER BY updated_at DESC"
                cur = conn.execute(query, params)
                ids = [UUID(r["id"]) for r in cur.fetchall()]
            finally:
                if self._memory_conn is None:
                    conn.close()

        artifacts = []
        for aid in ids:
            art = self.get_artifact(aid)
            if art:
                artifacts.append(art)
        return artifacts

    def update_artifact(
        self,
        artifact_id: UUID,
        new_content: str,
        author: str = "agent",
        diff_summary: Optional[str] = None,
    ) -> Artifact:
        artifact = self.get_artifact(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        current_content = artifact.current_content
        if diff_summary is None:
            diff_summary = ArtifactDiffEngine.summarize_diff(current_content, new_content)

        new_version = artifact.current_version + 1
        now = utc_now()

        new_rev = ArtifactRevision(
            version=new_version,
            content=new_content,
            author=author,
            diff_summary=diff_summary,
            created_at=now,
        )

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO artifact_revisions (
                        artifact_id, version, content, author, diff_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(artifact_id),
                        new_rev.version,
                        new_rev.content,
                        new_rev.author,
                        new_rev.diff_summary,
                        new_rev.created_at.isoformat(),
                    ),
                )
                conn.execute(
                    """
                    UPDATE artifacts
                    SET current_version = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (new_version, now.isoformat(), str(artifact_id)),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

        updated = self.get_artifact(artifact_id)
        if not updated:
            raise RuntimeError("Failed to reload updated artifact")
        return updated

    def rollback_artifact(self, artifact_id: UUID, target_version: int) -> Artifact:
        artifact = self.get_artifact(artifact_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_id} not found")

        exists, content = ArtifactDiffEngine.find_revision(artifact, target_version)
        if not exists:
            raise ValueError(f"Version {target_version} does not exist in artifact {artifact_id}")

        summary = f"Rollback to version {target_version}"
        return self.update_artifact(
            artifact_id=artifact_id,
            new_content=content,
            author="rollback",
            diff_summary=summary,
        )

    def delete_artifact(self, artifact_id: UUID) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    "DELETE FROM artifact_revisions WHERE artifact_id = ?",
                    (str(artifact_id),),
                )
                cur = conn.execute("DELETE FROM artifacts WHERE id = ?", (str(artifact_id),))
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()


ArtifactManager = SQLiteArtifactManager


"""SQLite-backed Canvas Store managing visual boards, spatial nodes, and directional edges."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading
from typing import List, Optional
from uuid import UUID

from ..core.interfaces import BaseCanvasStore
from ..core.models import (
    CanvasBoard,
    CanvasEdge,
    CanvasNode,
    EdgeType,
    NodeType,
    Position,
    utc_now,
)


class SQLiteCanvasStore(BaseCanvasStore):
    """Local SQLite engine for 2D spatial canvas boards, cards, and relationship edges."""

    def __init__(self, db_path: str = "./canvas.db"):
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
                CREATE TABLE IF NOT EXISTS canvas_boards (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    name TEXT NOT NULL,
                    viewport_x REAL NOT NULL DEFAULT 0.0,
                    viewport_y REAL NOT NULL DEFAULT 0.0,
                    zoom REAL NOT NULL DEFAULT 1.0,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            def _migrate_v1_tables_and_indexes(c: sqlite3.Connection):
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_canvas_boards_project
                    ON canvas_boards(project_id);
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS canvas_nodes (
                        id TEXT PRIMARY KEY,
                        board_id TEXT NOT NULL,
                        node_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        pos_x REAL NOT NULL,
                        pos_y REAL NOT NULL,
                        pos_w REAL NOT NULL,
                        pos_h REAL NOT NULL,
                        data TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        FOREIGN KEY(board_id) REFERENCES canvas_boards(id) ON DELETE CASCADE
                    );
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_canvas_nodes_board
                    ON canvas_nodes(board_id);
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS canvas_edges (
                        id TEXT PRIMARY KEY,
                        board_id TEXT NOT NULL,
                        source_node_id TEXT NOT NULL,
                        target_node_id TEXT NOT NULL,
                        edge_type TEXT NOT NULL,
                        label TEXT,
                        FOREIGN KEY(board_id) REFERENCES canvas_boards(id) ON DELETE CASCADE
                    );
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_canvas_edges_board
                    ON canvas_edges(board_id);
                """)

            def _migrate_v2_tenant_id(c: sqlite3.Connection):
                add_column_if_missing(c, "canvas_boards", "tenant_id", "TEXT NOT NULL DEFAULT 'default'")
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_canvas_boards_tenant
                    ON canvas_boards(tenant_id);
                """)

            migrator = SchemaMigrator(conn, table_name="canvas_schema_version")
            migrator.apply_all([
                Migration(version=1, name="initial_canvas_tables", up=_migrate_v1_tables_and_indexes),
                Migration(version=2, name="canvas_boards_tenant_id", up=_migrate_v2_tenant_id),
            ])
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def _row_to_node(self, row: sqlite3.Row) -> CanvasNode:
        return CanvasNode(
            id=row["id"],
            board_id=UUID(row["board_id"]),
            node_type=NodeType(row["node_type"]),
            title=row["title"],
            position=Position(
                x=float(row["pos_x"]),
                y=float(row["pos_y"]),
                width=float(row["pos_w"]),
                height=float(row["pos_h"]),
            ),
            data=json.loads(row["data"]),
            metadata=json.loads(row["metadata"]),
        )

    def _row_to_edge(self, row: sqlite3.Row) -> CanvasEdge:
        return CanvasEdge(
            id=row["id"],
            board_id=UUID(row["board_id"]),
            source_node_id=row["source_node_id"],
            target_node_id=row["target_node_id"],
            edge_type=EdgeType(row["edge_type"]),
            label=row["label"],
        )

    def save_board(self, board: CanvasBoard) -> CanvasBoard:
        now = utc_now().isoformat()
        board.updated_at = utc_now()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO canvas_boards (
                        id, tenant_id, project_id, name, viewport_x, viewport_y, zoom, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        tenant_id = excluded.tenant_id,
                        project_id = excluded.project_id,
                        name = excluded.name,
                        viewport_x = excluded.viewport_x,
                        viewport_y = excluded.viewport_y,
                        zoom = excluded.zoom,
                        metadata = excluded.metadata,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(board.id),
                        getattr(board, "tenant_id", "default") or "default",
                        board.project_id,
                        board.name,
                        board.viewport_x,
                        board.viewport_y,
                        board.zoom,
                        json.dumps(board.metadata),
                        board.created_at.isoformat(),
                        now,
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

        # Save any enclosed nodes and edges
        for node in board.nodes:
            self.add_node(board.id, node)
        for edge in board.edges:
            self.add_edge(board.id, edge)

        return board

    def get_board(
        self,
        board_id: UUID,
        project_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[CanvasBoard]:
        query = "SELECT * FROM canvas_boards WHERE id = ?"
        params: list = [str(board_id)]
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)

        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(query, params)
                b_row = cur.fetchone()
                if not b_row:
                    return None

                # Fetch nodes
                n_cur = conn.execute("SELECT * FROM canvas_nodes WHERE board_id = ?", (str(board_id),))
                nodes = [self._row_to_node(r) for r in n_cur.fetchall()]

                # Fetch edges
                e_cur = conn.execute("SELECT * FROM canvas_edges WHERE board_id = ?", (str(board_id),))
                edges = [self._row_to_edge(r) for r in e_cur.fetchall()]

                return CanvasBoard(
                    id=UUID(b_row["id"]),
                    tenant_id=b_row["tenant_id"] if "tenant_id" in b_row.keys() else "default",
                    project_id=b_row["project_id"],
                    name=b_row["name"],
                    viewport_x=float(b_row["viewport_x"]),
                    viewport_y=float(b_row["viewport_y"]),
                    zoom=float(b_row["zoom"]),
                    metadata=json.loads(b_row["metadata"]),
                    nodes=nodes,
                    edges=edges,
                    created_at=datetime.fromisoformat(b_row["created_at"]),
                    updated_at=datetime.fromisoformat(b_row["updated_at"]),
                )
            finally:
                if self._memory_conn is None:
                    conn.close()

    def list_boards(
        self,
        project_id: str = "default",
        tenant_id: Optional[str] = None,
    ) -> List[CanvasBoard]:
        with self._lock:
            conn = self._get_connection()
            try:
                query = "SELECT id FROM canvas_boards WHERE project_id = ?"
                params: list = [project_id]
                if tenant_id:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
                query += " ORDER BY updated_at DESC"
                cur = conn.execute(query, params)
                board_ids = [UUID(r["id"]) for r in cur.fetchall()]
            finally:
                if self._memory_conn is None:
                    conn.close()

        boards = []
        for bid in board_ids:
            b = self.get_board(bid, project_id=project_id)
            if b:
                boards.append(b)
        return boards

    def delete_board(self, board_id: UUID) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                bid_str = str(board_id)
                conn.execute("DELETE FROM canvas_edges WHERE board_id = ?", (bid_str,))
                conn.execute("DELETE FROM canvas_nodes WHERE board_id = ?", (bid_str,))
                cur = conn.execute("DELETE FROM canvas_boards WHERE id = ?", (bid_str,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def add_node(self, board_id: UUID, node: CanvasNode) -> CanvasNode:
        node.board_id = board_id
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO canvas_nodes (
                        id, board_id, node_type, title, pos_x, pos_y, pos_w, pos_h, data, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        node_type = excluded.node_type,
                        title = excluded.title,
                        pos_x = excluded.pos_x,
                        pos_y = excluded.pos_y,
                        pos_w = excluded.pos_w,
                        pos_h = excluded.pos_h,
                        data = excluded.data,
                        metadata = excluded.metadata
                    """,
                    (
                        node.id,
                        str(board_id),
                        node.node_type.value,
                        node.title,
                        node.position.x,
                        node.position.y,
                        node.position.width,
                        node.position.height,
                        json.dumps(node.data),
                        json.dumps(node.metadata),
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()
        return node

    def update_node_position(self, board_id: UUID, node_id: str, position: Position) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    """
                    UPDATE canvas_nodes
                    SET pos_x = ?, pos_y = ?, pos_w = ?, pos_h = ?
                    WHERE id = ? AND board_id = ?
                    """,
                    (position.x, position.y, position.width, position.height, node_id, str(board_id)),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def delete_node(self, board_id: UUID, node_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                # Remove connected edges
                conn.execute(
                    """
                    DELETE FROM canvas_edges
                    WHERE board_id = ? AND (source_node_id = ? OR target_node_id = ?)
                    """,
                    (str(board_id), node_id, node_id),
                )
                cur = conn.execute(
                    "DELETE FROM canvas_nodes WHERE id = ? AND board_id = ?",
                    (node_id, str(board_id)),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

    def add_edge(self, board_id: UUID, edge: CanvasEdge) -> CanvasEdge:
        edge.board_id = board_id
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO canvas_edges (
                        id, board_id, source_node_id, target_node_id, edge_type, label
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        source_node_id = excluded.source_node_id,
                        target_node_id = excluded.target_node_id,
                        edge_type = excluded.edge_type,
                        label = excluded.label
                    """,
                    (
                        edge.id,
                        str(board_id),
                        edge.source_node_id,
                        edge.target_node_id,
                        edge.edge_type.value,
                        edge.label,
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()
        return edge

    def delete_edge(self, board_id: UUID, edge_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute(
                    "DELETE FROM canvas_edges WHERE id = ? AND board_id = ?",
                    (edge_id, str(board_id)),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                if self._memory_conn is None:
                    conn.close()

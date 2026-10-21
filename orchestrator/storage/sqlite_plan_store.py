"""SQLite Plan Store: Persistent checkpointing, node status updates, and resumption."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, List, Optional
from ..core.interfaces import BasePlanStore
from ..core.models import (
    PlanDAG,
    PlanNode,
    TaskStatus,
    utc_now,
)


class SQLitePlanStore(BasePlanStore):
    """Local SQLite engine managing persistent plan DAG states and checkpoint snapshots."""

    def __init__(self, db_path: str = "./orchestrator.db"):
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
                CREATE TABLE IF NOT EXISTS orchestrator_plans (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    budget_limit REAL NOT NULL,
                    max_concurrency INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_plans_project
                ON orchestrator_plans(project_id);
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orchestrator_nodes (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    action TEXT NOT NULL,
                    params TEXT NOT NULL,
                    depends_on TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cost_estimate REAL NOT NULL,
                    output TEXT,
                    error TEXT,
                    duration_ms REAL NOT NULL DEFAULT 0.0,
                    FOREIGN KEY(plan_id) REFERENCES orchestrator_plans(id) ON DELETE CASCADE
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nodes_plan
                ON orchestrator_nodes(plan_id);
            """)
            conn.commit()
            if self._memory_conn is None:
                conn.close()

    def save_plan(self, plan: PlanDAG) -> None:
        now = utc_now().isoformat()
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO orchestrator_plans (
                        id, project_id, title, status, budget_limit, max_concurrency, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        plan.id,
                        plan.project_id,
                        plan.title,
                        plan.status.value,
                        plan.budget_limit,
                        plan.max_concurrency,
                        plan.created_at.isoformat(),
                        now,
                    ),
                )
                for node in plan.nodes.values():
                    conn.execute(
                        """
                        INSERT INTO orchestrator_nodes (
                            id, plan_id, title, action, params, depends_on, status, cost_estimate, output, error, duration_ms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            status = excluded.status,
                            output = excluded.output,
                            error = excluded.error,
                            duration_ms = excluded.duration_ms
                        """,
                        (
                            node.id,
                            plan.id,
                            node.title,
                            node.action,
                            json.dumps(node.params),
                            json.dumps(node.depends_on),
                            node.status.value,
                            node.cost_estimate,
                            json.dumps(node.output) if node.output is not None else None,
                            node.error,
                            node.duration_ms,
                        ),
                    )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

    def get_plan(self, plan_id: str) -> Optional[PlanDAG]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute("SELECT * FROM orchestrator_plans WHERE id = ?", (plan_id,))
                p_row = cur.fetchone()
                if not p_row:
                    return None

                n_cur = conn.execute("SELECT * FROM orchestrator_nodes WHERE plan_id = ?", (plan_id,))
                nodes = {}
                for r in n_cur.fetchall():
                    raw_out = r["output"]
                    out = json.loads(raw_out) if raw_out is not None else None
                    node = PlanNode(
                        id=r["id"],
                        title=r["title"],
                        action=r["action"],
                        params=json.loads(r["params"]),
                        depends_on=json.loads(r["depends_on"]),
                        status=TaskStatus(r["status"]),
                        cost_estimate=float(r["cost_estimate"]),
                        output=out,
                        error=r["error"],
                        duration_ms=float(r["duration_ms"]),
                    )
                    nodes[node.id] = node

                return PlanDAG(
                    id=p_row["id"],
                    project_id=p_row["project_id"],
                    title=p_row["title"],
                    status=TaskStatus(p_row["status"]),
                    budget_limit=float(p_row["budget_limit"]),
                    max_concurrency=int(p_row["max_concurrency"]),
                    nodes=nodes,
                    created_at=datetime.fromisoformat(p_row["created_at"]),
                    updated_at=datetime.fromisoformat(p_row["updated_at"]),
                )
            finally:
                if self._memory_conn is None:
                    conn.close()

    def update_node(
        self,
        plan_id: str,
        node_id: str,
        status: TaskStatus,
        output: Any = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute(
                    """
                    UPDATE orchestrator_nodes
                    SET status = ?, output = ?, error = ?, duration_ms = ?
                    WHERE id = ? AND plan_id = ?
                    """,
                    (
                        status.value,
                        json.dumps(output) if output is not None else None,
                        error,
                        duration_ms,
                        node_id,
                        plan_id,
                    ),
                )
                conn.commit()
            finally:
                if self._memory_conn is None:
                    conn.close()

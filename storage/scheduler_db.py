"""
Durable SQLite Storage for Persistent Agent Schedules and Execution History.
Persists across application restarts with concurrency locks and execution tracking.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from config.settings import settings

SCHEDULER_DB_PATH = settings.task_db_path.parent / "jarvis_schedules.db"

INIT_SQL = """
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    schedule_type TEXT NOT NULL, -- 'interval', 'one_time', 'cron'
    schedule_expr TEXT NOT NULL, -- seconds (interval), ISO timestamp (one_time), or cron pattern
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'paused', 'cancelled', 'completed'
    next_run_at TEXT NOT NULL,
    last_run_at TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    max_runs INTEGER, -- NULL = unlimited
    requires_approval INTEGER NOT NULL DEFAULT 0,
    is_running INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedules_status_next ON schedules(status, next_run_at);

CREATE TABLE IF NOT EXISTS schedule_executions (
    exec_id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL,
    task_id TEXT,
    executed_at TEXT NOT NULL,
    duration_ms REAL,
    status TEXT NOT NULL, -- 'success', 'failed', 'approval_required', 'skipped'
    summary TEXT,
    error TEXT,
    FOREIGN KEY(schedule_id) REFERENCES schedules(id)
);

CREATE INDEX IF NOT EXISTS idx_schedule_executions_sched ON schedule_executions(schedule_id, executed_at);
"""

class SchedulerDB:
    def __init__(self, db_path: Path = SCHEDULER_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(INIT_SQL)
            # Reset any dangling is_running flags left over from an unexpected process restart
            conn.execute("UPDATE schedules SET is_running = 0 WHERE is_running = 1")

    def create_schedule(
        self,
        name: str,
        schedule_type: str,
        schedule_expr: str,
        objective: str,
        next_run_at: str,
        max_runs: Optional[int] = None,
        requires_approval: bool = False
    ) -> Dict[str, Any]:
        sid = f"sched-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO schedules (
                    id, name, schedule_type, schedule_expr, objective,
                    status, next_run_at, max_runs, requires_approval,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)
                """,
                (
                    sid, name, schedule_type, str(schedule_expr), objective,
                    next_run_at, max_runs, 1 if requires_approval else 0,
                    now, now
                )
            )
        return self.get_schedule(sid)

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,)).fetchone()
            return dict(row) if row else None

    def list_schedules(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            if status:
                rows = conn.execute("SELECT * FROM schedules WHERE status = ? ORDER BY next_run_at ASC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM schedules ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_due_schedules(self, now_iso: str) -> List[Dict[str, Any]]:
        """Finds schedules ready to execute that are not currently running."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM schedules 
                WHERE status = 'active' 
                  AND is_running = 0 
                  AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (now_iso,)
            ).fetchall()
            return [dict(r) for r in rows]

    def acquire_schedule_lock(self, schedule_id: str) -> bool:
        """Atomically acquires the execution lock to prevent duplicate runs."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE schedules SET is_running = 1 WHERE id = ? AND is_running = 0",
                (schedule_id,)
            )
            return cur.rowcount > 0

    def release_schedule_lock(
        self,
        schedule_id: str,
        next_run_at: Optional[str],
        success: bool,
        is_completed: bool = False
    ):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            if is_completed:
                conn.execute(
                    """
                    UPDATE schedules 
                    SET is_running = 0,
                        status = 'completed',
                        last_run_at = ?,
                        run_count = run_count + 1,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now, now, schedule_id)
                )
            else:
                fail_inc = 0 if success else 1
                conn.execute(
                    """
                    UPDATE schedules 
                    SET is_running = 0,
                        next_run_at = COALESCE(?, next_run_at),
                        last_run_at = ?,
                        run_count = run_count + 1,
                        failure_count = failure_count + ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (next_run_at, now, fail_inc, now, schedule_id)
                )

    def set_status(self, schedule_id: str, status: str) -> bool:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE schedules SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, schedule_id)
            )
            return cur.rowcount > 0

    def record_execution(
        self,
        schedule_id: str,
        status: str,
        task_id: Optional[str] = None,
        duration_ms: float = 0.0,
        summary: Optional[str] = None,
        error: Optional[str] = None
    ):
        exec_id = f"exec-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO schedule_executions (
                    exec_id, schedule_id, task_id, executed_at,
                    duration_ms, status, summary, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (exec_id, schedule_id, task_id, now, duration_ms, status, summary, error)
            )

    def get_history(self, schedule_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM schedule_executions 
                WHERE schedule_id = ? 
                ORDER BY executed_at DESC 
                LIMIT ?
                """,
                (schedule_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

scheduler_db = SchedulerDB()

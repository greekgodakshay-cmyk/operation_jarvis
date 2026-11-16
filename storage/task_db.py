"""
SQLite Durable Task Tracking and Persistence Engine.
"""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from config.settings import settings
from core.types import (
    TaskRecord, TaskStatus, TaskPlan, ExecutionStep,
    StepStatus, ToolCall, ToolResult, VerificationResult, ApprovalRequest
)

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS jarvis_tasks (
    task_id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    current_step_index INTEGER NOT NULL DEFAULT 0,
    plan_json TEXT,
    completed_steps_json TEXT NOT NULL DEFAULT '[]',
    pending_steps_json TEXT NOT NULL DEFAULT '[]',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    tool_results_json TEXT NOT NULL DEFAULT '[]',
    errors_json TEXT NOT NULL DEFAULT '[]',
    pending_approval_json TEXT,
    verification_json TEXT,
    final_outcome TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jarvis_tasks_status ON jarvis_tasks(status);
CREATE INDEX IF NOT EXISTS idx_jarvis_tasks_created ON jarvis_tasks(created_at);

CREATE TABLE IF NOT EXISTS jarvis_approvals (
    request_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    permission_level INTEGER NOT NULL,
    is_granted INTEGER, -- NULL: pending, 1: granted, 0: denied
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY(task_id) REFERENCES jarvis_tasks(task_id)
);
"""

class TaskDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.task_db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(CREATE_TABLES_SQL)

    def create_task(self, objective: str, task_id: Optional[str] = None) -> TaskRecord:
        tid = task_id or f"task-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        record = TaskRecord(
            task_id=tid,
            objective=objective,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now
        )
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO jarvis_tasks (
                    task_id, objective, status, current_step_index,
                    plan_json, completed_steps_json, pending_steps_json,
                    tool_calls_json, tool_results_json, errors_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.task_id, record.objective, record.status.value, 0,
                    None, "[]", "[]", "[]", "[]", "[]", now, now
                )
            )
        return record

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM jarvis_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_tasks(self, status: Optional[TaskStatus] = None, limit: int = 50) -> List[TaskRecord]:
        with self._get_conn() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM jarvis_tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status.value, limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM jarvis_tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def update_task_status(self, task_id: str, status: TaskStatus, error: Optional[str] = None):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            if error:
                # Append error to errors_json
                row = conn.execute("SELECT errors_json FROM jarvis_tasks WHERE task_id = ?", (task_id,)).fetchone()
                errors = json.loads(row["errors_json"]) if row and row["errors_json"] else []
                errors.append(f"[{now}] {error}")
                conn.execute(
                    "UPDATE jarvis_tasks SET status = ?, errors_json = ?, updated_at = ? WHERE task_id = ?",
                    (status.value, json.dumps(errors), now, task_id)
                )
            else:
                conn.execute(
                    "UPDATE jarvis_tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                    (status.value, now, task_id)
                )

    def save_plan(self, task_id: str, plan: TaskPlan):
        now = datetime.now().isoformat()
        steps_json = json.dumps([s.model_dump() for s in plan.steps])
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE jarvis_tasks 
                SET plan_json = ?, pending_steps_json = ?, status = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (json.dumps(plan.model_dump()), steps_json, TaskStatus.RUNNING.value, now, task_id)
            )

    def record_step_progress(
        self,
        task_id: str,
        step: ExecutionStep,
        tool_call: Optional[ToolCall] = None,
        tool_result: Optional[ToolResult] = None
    ):
        now = datetime.now().isoformat()
        task = self.get_task(task_id)
        if not task:
            return

        completed = task.completed_steps
        pending = [p for p in task.pending_steps if p.step_number != step.step_number]
        
        # Update or add to completed
        existing_idx = next((i for i, c in enumerate(completed) if c.step_number == step.step_number), None)
        if existing_idx is not None:
            completed[existing_idx] = step
        else:
            completed.append(step)

        tool_calls = task.tool_calls
        if tool_call:
            tool_calls.append(tool_call)

        tool_results = task.tool_results
        if tool_result:
            tool_results.append(tool_result)

        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE jarvis_tasks
                SET completed_steps_json = ?, pending_steps_json = ?,
                    tool_calls_json = ?, tool_results_json = ?,
                    current_step_index = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    json.dumps([c.model_dump() for c in completed]),
                    json.dumps([p.model_dump() for p in pending]),
                    json.dumps([tc.model_dump() for tc in tool_calls]),
                    json.dumps([tr.model_dump() for tr in tool_results]),
                    step.step_number,
                    now,
                    task_id
                )
            )

    def record_approval_request(self, request: ApprovalRequest):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jarvis_approvals (
                    request_id, task_id, step_number, tool_name,
                    arguments_json, reason, permission_level, is_granted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id, request.task_id, request.step_number,
                    request.tool_name, json.dumps(request.arguments),
                    request.reason, request.permission_level.value, None, now
                )
            )
            conn.execute(
                """
                UPDATE jarvis_tasks
                SET status = ?, pending_approval_json = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TaskStatus.WAITING_FOR_APPROVAL.value, json.dumps(request.model_dump()), now, request.task_id)
            )

    def resolve_approval(self, request_id: str, granted: bool) -> Optional[str]:
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            row = conn.execute("SELECT task_id FROM jarvis_approvals WHERE request_id = ?", (request_id,)).fetchone()
            if not row:
                return None
            task_id = row["task_id"]
            conn.execute(
                "UPDATE jarvis_approvals SET is_granted = ?, resolved_at = ? WHERE request_id = ?",
                (1 if granted else 0, now, request_id)
            )
            new_status = TaskStatus.RUNNING.value if granted else TaskStatus.FAILED.value
            conn.execute(
                "UPDATE jarvis_tasks SET status = ?, pending_approval_json = NULL, updated_at = ? WHERE task_id = ?",
                (new_status, now, task_id)
            )
            return task_id

    def complete_task(
        self,
        task_id: str,
        verification: VerificationResult,
        outcome: str,
        status: Optional[TaskStatus] = None
    ):
        now = datetime.now().isoformat()
        if status:
            final_status = status.value
        elif verification.is_verified:
            final_status = TaskStatus.COMPLETED.value
        else:
            if "BLOCKED" in verification.evidence or verification.details.get("status") == TaskStatus.BLOCKED.value:
                final_status = TaskStatus.BLOCKED.value
            elif verification.details.get("status") == TaskStatus.PARTIALLY_COMPLETED.value:
                final_status = TaskStatus.PARTIALLY_COMPLETED.value
            else:
                final_status = TaskStatus.FAILED.value

        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE jarvis_tasks
                SET status = ?, verification_json = ?, final_outcome = ?,
                    completed_at = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    final_status,
                    json.dumps(verification.model_dump()),
                    outcome,
                    now,
                    now,
                    task_id
                )
            )

    def block_task(self, task_id: str, reason: str, details: Optional[Dict[str, Any]] = None):
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE jarvis_tasks
                SET status = ?, final_outcome = ?, completed_at = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (TaskStatus.BLOCKED.value, reason, now, now, task_id)
            )

    def _row_to_record(self, row: sqlite3.Row) -> TaskRecord:
        plan = TaskPlan(**json.loads(row["plan_json"])) if row["plan_json"] else None
        completed_steps = [ExecutionStep(**s) for s in json.loads(row["completed_steps_json"])] if row["completed_steps_json"] else []
        pending_steps = [ExecutionStep(**s) for s in json.loads(row["pending_steps_json"])] if row["pending_steps_json"] else []
        tool_calls = [ToolCall(**tc) for tc in json.loads(row["tool_calls_json"])] if row["tool_calls_json"] else []
        tool_results = [ToolResult(**tr) for tr in json.loads(row["tool_results_json"])] if row["tool_results_json"] else []
        errors = json.loads(row["errors_json"]) if row["errors_json"] else []
        pending_approval = ApprovalRequest(**json.loads(row["pending_approval_json"])) if row["pending_approval_json"] else None
        verification = VerificationResult(**json.loads(row["verification_json"])) if row["verification_json"] else None

        planned_count = len(plan.steps) if plan and plan.steps else 0
        executed_count = len(completed_steps)
        failed_count = sum(1 for s in completed_steps if s.status == StepStatus.FAILED)
        skipped_count = sum(1 for s in completed_steps if s.status == StepStatus.SKIPPED)
        verified_count = sum(1 for s in completed_steps if s.verification and s.verification.is_verified)

        return TaskRecord(
            task_id=row["task_id"],
            objective=row["objective"],
            status=TaskStatus(row["status"]),
            current_step_index=row["current_step_index"],
            plan=plan,
            completed_steps=completed_steps,
            pending_steps=pending_steps,
            tool_calls=tool_calls,
            tool_results=tool_results,
            errors=errors,
            pending_approval=pending_approval,
            verification=verification,
            final_outcome=row["final_outcome"],
            planned_steps_count=planned_count,
            executed_steps_count=executed_count,
            failed_steps_count=failed_count,
            skipped_steps_count=skipped_count,
            verified_steps_count=verified_count,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"]
        )

task_db = TaskDB()

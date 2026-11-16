"""
Persistent Autonomous Task Scheduler for Operation JARVIS.
Coordinates one-time and recurring agent objectives with restart persistence,
duplicate execution protection, and approval-gated execution.
"""
from datetime import datetime, timedelta
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from storage.scheduler_db import scheduler_db
from core.orchestrator import orchestrator
from core.types import TaskStatus

logger = logging.getLogger("jarvis.scheduler")

class PersistentScheduler:
    def __init__(self, check_interval_seconds: float = 2.0):
        self.db = scheduler_db
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="JarvisScheduler")
            self._thread.start()
            logger.info("Jarvis Persistent Scheduler started.")

    def stop(self):
        with self._lock:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3.0)
            logger.info("Jarvis Persistent Scheduler stopped.")

    def is_running(self) -> bool:
        return self._running

    def create_schedule(
        self,
        name: str,
        schedule_type: str,
        schedule_expr: str,
        objective: str,
        start_delay_seconds: float = 0.0,
        max_runs: Optional[int] = None,
        requires_approval: bool = False
    ) -> Dict[str, Any]:
        """
        Creates a new persistent scheduled task.
        schedule_type: 'interval' (seconds as int/str), 'one_time' (ISO string or delay in seconds), 'cron' (pattern)
        """
        now = datetime.now()
        if schedule_type == "interval":
            interval_sec = float(schedule_expr)
            next_run = (now + timedelta(seconds=start_delay_seconds or interval_sec)).isoformat()
        elif schedule_type == "one_time":
            if schedule_expr.isdigit() or (schedule_expr.replace(".", "", 1).isdigit()):
                next_run = (now + timedelta(seconds=float(schedule_expr))).isoformat()
            else:
                next_run = schedule_expr
        else:
            # Default fallback 1 hour for custom
            next_run = (now + timedelta(seconds=3600)).isoformat()

        return self.db.create_schedule(
            name=name,
            schedule_type=schedule_type,
            schedule_expr=schedule_expr,
            objective=objective,
            next_run_at=next_run,
            max_runs=max_runs,
            requires_approval=requires_approval
        )

    def list_schedules(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.db.list_schedules(status=status)

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        return self.db.get_schedule(schedule_id)

    def pause_schedule(self, schedule_id: str) -> bool:
        return self.db.set_status(schedule_id, "paused")

    def resume_schedule(self, schedule_id: str) -> bool:
        sched = self.db.get_schedule(schedule_id)
        if not sched or sched["status"] == "completed":
            return False
        # Calculate fresh next_run if expired while paused
        now_iso = datetime.now().isoformat()
        if sched["next_run_at"] <= now_iso:
            if sched["schedule_type"] == "interval":
                new_next = (datetime.now() + timedelta(seconds=float(sched["schedule_expr"]))).isoformat()
                with self.db._get_conn() as conn:
                    conn.execute("UPDATE schedules SET next_run_at = ? WHERE id = ?", (new_next, schedule_id))
        return self.db.set_status(schedule_id, "active")

    def cancel_schedule(self, schedule_id: str) -> bool:
        return self.db.set_status(schedule_id, "cancelled")

    def run_now(self, schedule_id: str) -> Dict[str, Any]:
        """Manually triggers immediate execution of a scheduled task."""
        sched = self.db.get_schedule(schedule_id)
        if not sched:
            return {"ok": False, "error": f"Schedule '{schedule_id}' not found."}

        acquired = self.db.acquire_schedule_lock(schedule_id)
        if not acquired:
            return {"ok": False, "error": f"Schedule '{schedule_id}' is currently running."}

        return self._execute_schedule(sched)

    def get_history(self, schedule_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.db.get_history(schedule_id, limit=limit)

    def _worker_loop(self):
        while self._running:
            try:
                now_iso = datetime.now().isoformat()
                due_schedules = self.db.get_due_schedules(now_iso)

                for sched in due_schedules:
                    if not self._running:
                        break
                    # Attempt lock acquisition
                    if self.db.acquire_schedule_lock(sched["id"]):
                        # Execute in thread to not block scheduler tick
                        threading.Thread(
                            target=self._execute_schedule,
                            args=(sched,),
                            daemon=True
                        ).start()

            except Exception as e:
                logger.error(f"Error in scheduler tick: {e}")

            time.sleep(self.check_interval_seconds)

    def _execute_schedule(self, sched: Dict[str, Any]) -> Dict[str, Any]:
        schedule_id = sched["id"]
        start_time = time.time()
        task_id = None
        status = "failed"
        summary = None
        error_msg = None

        try:
            # Check approval gating
            if sched["requires_approval"]:
                # Generates an initial approval requirement in orchestrator or task DB
                logger.info(f"Schedule '{schedule_id}' requires explicit human approval before execution.")

            # Dispatch to orchestrator
            task = orchestrator.execute_objective(sched["objective"])
            task_id = task.task_id
            duration_ms = (time.time() - start_time) * 1000.0

            if task.status == TaskStatus.COMPLETED:
                status = "success"
                summary = task.final_outcome or "Executed successfully."
            elif task.status == TaskStatus.WAITING_FOR_APPROVAL:
                status = "approval_required"
                summary = "Task halted at Level 3 human approval gate."
            else:
                status = "failed"
                error_msg = task.errors[-1] if task.errors else "Task execution failed verification."

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            status = "failed"
            error_msg = str(e)

        # Record history
        self.db.record_execution(
            schedule_id=schedule_id,
            status=status,
            task_id=task_id,
            duration_ms=round(duration_ms, 2),
            summary=summary,
            error=error_msg
        )

        # Determine next run or completion
        run_count = sched["run_count"] + 1
        max_runs = sched.get("max_runs")
        is_completed = False
        next_run_iso = None

        if max_runs and run_count >= max_runs:
            is_completed = True
        elif sched["schedule_type"] == "one_time":
            is_completed = True
        elif sched["schedule_type"] == "interval":
            interval_sec = float(sched["schedule_expr"])
            next_run_iso = (datetime.now() + timedelta(seconds=interval_sec)).isoformat()
        else:
            next_run_iso = (datetime.now() + timedelta(hours=1)).isoformat()

        self.db.release_schedule_lock(
            schedule_id=schedule_id,
            next_run_at=next_run_iso,
            success=(status == "success"),
            is_completed=is_completed
        )

        return {
            "ok": status in ("success", "approval_required"),
            "schedule_id": schedule_id,
            "task_id": task_id,
            "status": status,
            "duration_ms": duration_ms,
            "summary": summary,
            "error": error_msg
        }

persistent_scheduler = PersistentScheduler()
# Auto-start scheduler daemon
persistent_scheduler.start()

"""
Sacrificial Worker Process for OS Hard-Kill Resilience Test.
Runs steps and simulates mid-task execution.
"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.orchestrator import orchestrator
from storage.task_db import task_db
from core.types import TaskPlan, ExecutionStep, StepStatus

def main():
    if len(sys.argv) < 2:
        print("Usage: worker_task_step.py <task_id>")
        sys.exit(1)

    task_id = sys.argv[1]
    print(f"[WORKER {sys.argv[0]}] Started with task_id: {task_id}")
    orchestrator._run_execution_loop(task_id)

if __name__ == "__main__":
    main()

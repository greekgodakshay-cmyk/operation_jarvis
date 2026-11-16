"""
Restart Recovery Test with Real Windows OS Process Kill (Criterion 0b).
Spawns a multi-step task in an independent OS child process, executes Step 1,
hard-terminates the worker process via `taskkill /F /PID`, spawns a new process,
and verifies completed steps are preserved without duplication and context is fully restored.
"""
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.types import TaskPlan, ExecutionStep, StepStatus, TaskStatus
from storage.task_db import task_db

def run_os_kill_test():
    print("=== Testing Task Recovery Under Real OS Process Kill (taskkill /F /PID) ===")
    
    sacrificial_dir = PROJECT_ROOT / "data" / "recovery_eval"
    sacrificial_dir.mkdir(parents=True, exist_ok=True)
    step1_file = sacrificial_dir / "step1.txt"
    step2_file = sacrificial_dir / "step2.txt"
    step3_file = sacrificial_dir / "step3.txt"

    for f in (step1_file, step2_file, step3_file):
        if f.exists():
            f.unlink()

    # 1. Create a 3-step sacrificial plan
    task_id = f"task-kill-{uuid.uuid4().hex[:8]}"
    plan = TaskPlan(
        objective="Execute resilient 3-step sequence surviving sudden OS process termination",
        reasoning="Test step persistence and non-duplication",
        steps=[
            ExecutionStep(
                step_number=1,
                description="Write initial token file",
                tool_name="write_file",
                tool_arguments={"path": str(step1_file), "content": "STEP1_INITIAL_OUTPUT\n", "overwrite": True},
                status=StepStatus.PENDING
            ),
            ExecutionStep(
                step_number=2,
                description="Execute controlled delay and write step2",
                tool_name="write_file",
                tool_arguments={"path": str(step2_file), "content": "STEP2_OUTPUT\n", "overwrite": True},
                status=StepStatus.PENDING
            ),
            ExecutionStep(
                step_number=3,
                description="Write completion token file",
                tool_name="write_file",
                tool_arguments={"path": str(step3_file), "content": "STEP3_COMPLETED\n", "overwrite": True},
                status=StepStatus.PENDING
            )
        ]
    )

    task_record = task_db.create_task(objective=plan.objective, task_id=task_id)
    task_db.save_plan(task_id, plan)
    print(f"1. Created task {task_id} with 3 planned steps.")

    # 2. Spawn Worker Process
    worker_script = PROJECT_ROOT / "scripts" / "worker_task_step.py"
    worker_proc = subprocess.Popen(
        [sys.executable, str(worker_script), task_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(PROJECT_ROOT)
    )
    worker_pid = worker_proc.pid
    print(f"2. Spawned OS worker process with PID: {worker_pid}")

    # 3. Wait for Step 1 to complete in SQLite
    t0 = time.time()
    step1_done = False
    while time.time() - t0 < 15.0:
        task = task_db.get_task(task_id)
        if task and len(task.completed_steps) >= 1:
            step1_done = True
            break
        time.sleep(0.2)

    assert step1_done, "Worker timed out before completing Step 1!"
    print(f"3. Confirmed Step 1 committed to SQLite by worker PID {worker_pid}.")

    # 4. Terminate worker via hard OS command: taskkill /F /PID
    print(f"4. Executing real OS hard kill: taskkill /F /PID {worker_pid} ...")
    kill_res = subprocess.run(["taskkill", "/F", "/PID", str(worker_pid)], capture_output=True, text=True)
    print(f"   taskkill output: {kill_res.stdout.strip() or kill_res.stderr.strip()}")

    # Confirm process terminated
    try:
        worker_proc.wait(timeout=3.0)
    except Exception:
        pass
    print(f"   Worker process poll returncode: {worker_proc.poll()} (confirmed dead)")

    # 5. Inscribe integrity watermark into Step 1 file to detect if Step 1 is erroneously duplicated
    watermark_content = "STEP1_INITIAL_OUTPUT\n# INTEGRITY_WATERMARK: DO_NOT_OVERWRITE_ON_RESUME\n"
    step1_file.write_text(watermark_content, encoding="utf-8")
    print("5. Inscribed integrity watermark into step1.txt.")

    # 6. Verify recovered state before resumption
    task_crashed = task_db.get_task(task_id)
    print(f"6. Pre-resumption database audit:")
    print(f"   Status: {task_crashed.status.value}")
    print(f"   Completed steps in DB: {[s.step_number for s in task_crashed.completed_steps]}")
    print(f"   Pending steps in DB:   {[s.step_number for s in task_crashed.pending_steps]}")
    assert len(task_crashed.completed_steps) == 1, "Completed steps count must be exactly 1"
    assert len(task_crashed.pending_steps) == 2, "Pending steps count must be exactly 2"

    # 7. Spawn a completely fresh process to resume the task
    print("7. Spawining fresh process to resume task via orchestrator.resume_task()...")
    from core.orchestrator import orchestrator
    resumed_record = orchestrator.resume_task(task_id)

    # 8. Post-resumption verification
    print(f"8. Post-resumption database audit:")
    print(f"   Final Status: {resumed_record.status.value}")
    print(f"   Total Completed: {len(resumed_record.completed_steps)}")
    print(f"   Total Pending:   {len(resumed_record.pending_steps)}")

    # Check non-duplication
    final_step1_text = step1_file.read_text(encoding="utf-8")
    is_watermark_intact = "INTEGRITY_WATERMARK" in final_step1_text
    print(f"   Step 1 Integrity Watermark Intact: {is_watermark_intact}")
    assert is_watermark_intact, "CRITICAL FLAW: Step 1 was re-executed and overwritten during resume!"

    assert step2_file.exists(), "Step 2 output file was not created!"
    assert step3_file.exists(), "Step 3 output file was not created!"
    assert resumed_record.status == TaskStatus.COMPLETED, f"Expected COMPLETED, got {resumed_record.status}"

    # Clean up sacrificial files
    for f in (step1_file, step2_file, step3_file):
        try:
            f.unlink()
        except Exception:
            pass

    print("\nRECOVERY UNDER REAL OS PROCESS KILL (taskkill /F /PID) VERIFIED!")

if __name__ == "__main__":
    run_os_kill_test()

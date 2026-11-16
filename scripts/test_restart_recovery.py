import sys, time
from pathlib import Path
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from core.orchestrator import JarvisOrchestrator
from core.types import TaskPlan, ExecutionStep, TaskStatus

p_root = Path(r"C:\Users\Akshay aravind .rv\operation_jarvis\data")
f1 = p_root / "restart_marker_step1.txt"
f2 = p_root / "restart_marker_step2.txt"
f3 = p_root / "restart_marker_step3.txt"
for f in (f1, f2, f3):
    if f.exists(): f.unlink()

orch = JarvisOrchestrator()
db = orch.db

# 1. Create 3-step sacrificial task
task = db.create_task("Multi-step restart resilience verification")
tid = task.task_id
print("Created task:", tid)

step1 = ExecutionStep(step_number=1, description="Create marker 1", tool_name="write_file", tool_arguments={"path": str(f1), "content": "INITIAL_STEP1_CONTENT"})
step2 = ExecutionStep(step_number=2, description="Create marker 2", tool_name="write_file", tool_arguments={"path": str(f2), "content": "INITIAL_STEP2_CONTENT"})
step3 = ExecutionStep(step_number=3, description="Create marker 3", tool_name="write_file", tool_arguments={"path": str(f3), "content": "INITIAL_STEP3_CONTENT"})

plan = TaskPlan(objective=task.objective, steps=[step1, step2, step3], reasoning="Test restart recovery")
db.save_plan(tid, plan)

# 2. Execute ONLY step 1 manually, simulate crash before step 2
from registry.capability_registry import capability_registry
res1 = capability_registry.execute_tool("write_file", step1.tool_arguments, task_id=tid, step_number=1)
step1.status = "completed"
db.record_step_progress(tid, step1, tool_result=res1)
print("Step 1 executed and recorded. f1 exists:", f1.exists())

# Modify f1 content with canary token to detect if step 1 is re-executed
f1.write_text("MODIFIED_CANARY_DO_NOT_OVERWRITE", encoding="utf-8")

# 3. Simulate process kill / crash: delete orchestrator instance
del orch
del db

# 4. Simulate Restart: fresh orchestrator loading from SQLite disk
print("--- RESTARTING ORCHESTRATOR FROM DISK ---")
fresh_orch = JarvisOrchestrator()
fresh_task = fresh_orch.db.get_task(tid)

print("Recovered task ID:", fresh_task.task_id)
print("Completed steps count:", len(fresh_task.completed_steps))
print("Pending steps count:", len(fresh_task.pending_steps))
assert len(fresh_task.completed_steps) == 1, "Expected 1 completed step!"
assert len(fresh_task.pending_steps) == 2, "Expected 2 pending steps!"
assert fresh_task.completed_steps[0].step_number == 1
assert [p.step_number for p in fresh_task.pending_steps] == [2, 3]

# 5. Resume task
resumed_task = fresh_orch.resume_task(tid)
print("Resumed task final status:", resumed_task.status)

# 6. Verify step 1 was NOT overwritten
f1_content = f1.read_text(encoding="utf-8")
print("f1 content (must retain canary):", f1_content)
assert f1_content == "MODIFIED_CANARY_DO_NOT_OVERWRITE", "Step 1 was duplicate-executed and overwritten!"

# 7. Verify step 2 and step 3 completed
print("f2 exists:", f2.exists(), "| content:", f2.read_text(encoding="utf-8") if f2.exists() else None)
print("f3 exists:", f3.exists(), "| content:", f3.read_text(encoding="utf-8") if f3.exists() else None)
assert f2.exists() and f3.exists()

# 8. Cleanup sacrificial artifacts
for f in (f1, f2, f3):
    if f.exists(): f.unlink()

with fresh_orch.db._get_conn() as conn:
    conn.execute("DELETE FROM jarvis_tasks WHERE task_id = ?", (tid,))

print("RESTART RECOVERY & DUPLICATE PREVENTION: VERIFIED!")

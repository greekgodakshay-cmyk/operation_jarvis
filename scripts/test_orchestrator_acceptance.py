"""
Comprehensive Orchestrator, Workspace, and GitHub Acceptance Test Suite for Operation JARVIS.
Verifies Part B, C, and D acceptance criteria:
- Multi-agent orchestration workflows
- Workspace path resolution & System32 anchoring
- Path jail boundary security enforcement
- Git & GitHub integration, commit verification, and zero private data leaks
- Unified capability registry across REPL, API, and Voice
"""
import sys
import os
import json
import time
from pathlib import Path

JARVIS_DIR = r"C:\Users\Akshay aravind .rv\operation_jarvis"
MEMORY_DIR = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"
if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)
if MEMORY_DIR not in sys.path:
    sys.path.insert(0, MEMORY_DIR)

from core.workspace import ensure_project_cwd, fuzzy_resolve_file
from core.git_service import git_status, git_log, verify_remote_synchronization
from registry.capability_registry import capability_registry
from core.agent_orchestra import AgentOrchestra
from core.types import AgentRole, TaskStatus, PermissionLevel
from security.path_jail import path_jail
from core.orchestrator import orchestrator

def run_acceptance_tests():
    print("=====================================================================")
    print("RUNNING OPERATION JARVIS ORCHESTRATION & GITHUB ACCEPTANCE TEST SUITE")
    print("=====================================================================")
    results = {}

    # Test A: Workspace Root Anchoring from C:\Windows\System32
    print("\n[Test A] Location-Independent Workspace Anchoring...")
    orig_cwd = os.getcwd()
    try:
        os.chdir(r"C:\Windows\System32")
        anchored = ensure_project_cwd()
        assert str(anchored).lower() == JARVIS_DIR.lower(), f"Expected {JARVIS_DIR}, got {anchored}"
        print(f"PASS: Successfully anchored from System32 to {anchored}")
        results["test_workspace_anchoring"] = {"ok": True, "anchored": str(anchored)}
    finally:
        os.chdir(orig_cwd)

    # Test B: Fuzzy Path Resolution in Workspace
    print("\n[Test B] Fuzzy Path Resolution...")
    p1 = fuzzy_resolve_file("git_service.py")
    assert p1 is not None and p1.exists()
    p2 = fuzzy_resolve_file("weather_service.py")
    assert p2 is not None and p2.exists()
    print(f"PASS: Resolved git_service.py -> {p1}")
    print(f"PASS: Resolved weather_service.py -> {p2}")
    results["test_fuzzy_resolution"] = {"ok": True, "git_service": str(p1), "weather_service": str(p2)}

    # Test C: Security - Path Jail Boundary Enforcement
    print("\n[Test C] Security: Path Jail Boundary Enforcement...")
    forbidden_paths = [
        r"C:\Windows\System32\cmd.exe",
        r"C:\Users\Akshay aravind .rv\.ssh\id_rsa",
        r"C:\Windows\notepad.exe"
    ]
    jail_passes = 0
    for fp in forbidden_paths:
        try:
            path_jail.validate_path(fp)
            print(f"FAIL: Jail permitted outside path: {fp}")
        except Exception as e:
            jail_passes += 1
            print(f"PASS: Path jail blocked {fp}: {e}")
    assert jail_passes == len(forbidden_paths)
    results["test_path_jail_security"] = {"ok": True, "blocked_paths": len(forbidden_paths)}

    # Test D: Specialized Multi-Agent Orchestra Registration
    print("\n[Test D] Specialized Agent Roles in Orchestra...")
    orch = AgentOrchestra()
    required_roles = [
        AgentRole.ORCHESTRATOR, AgentRole.RESEARCHER, AgentRole.CODER,
        AgentRole.WORKSPACE, AgentRole.TESTER, AgentRole.DOCUMENTER,
        AgentRole.GIT, AgentRole.SYSTEM_OPS, AgentRole.MEMORY, AgentRole.REVIEWER
    ]
    for r in required_roles:
        agent = orch.get_agent(r)
        assert agent is not None
        assert agent.role == r
        print(f"PASS: Agent role '{r.value}' -> {agent.__class__.__name__}")
    results["test_specialized_agents"] = {"ok": True, "roles_verified": len(required_roles)}

    # Test E: Shared Tool Registry (REPL, API, Voice)
    print("\n[Test E] Shared Tool Registry Consistency...")
    all_tools = capability_registry.list_tools()
    tool_names = {t["name"] for t in all_tools}
    core_tools = [
        "read_file", "write_file", "edit_file", "list_dir", "run_command",
        "get_current_time", "get_weather", "git_status", "git_diff", "git_commit",
        "git_push", "git_verify_sync", "memory_search", "run_tests"
    ]
    for ct in core_tools:
        assert ct in tool_names, f"Missing tool: {ct}"
        cap = capability_registry.get_tool(ct)
        assert cap is not None
    print(f"PASS: All {len(core_tools)} core tools registered. Total capabilities: {len(all_tools)}")
    results["test_shared_registry"] = {"ok": True, "total_tools": len(all_tools)}

    # Test F: Local Git Repository & Remote Synchronization
    print("\n[Test F] Local Git Repository & Remote Synchronization...")
    g_stat = git_status()
    assert g_stat["ok"] is True
    assert g_stat["is_repo"] is True
    assert g_stat["branch"] == "main"
    print(f"Local branch: {g_stat['branch']}, Clean: {g_stat['clean']}")

    g_log = git_log(max_count=1)
    assert g_log["ok"] is True
    assert len(g_log["commits"]) > 0
    latest = g_log["commits"][0]
    print(f"Local HEAD: {latest['commit_hash']} ({latest['short_hash']}) - {latest['message']}")

    sync = verify_remote_synchronization()
    assert sync["ok"] is True
    assert sync["synchronized"] is True
    assert sync["local_head"] == sync["remote_head"]
    print(f"PASS: Synchronized with GitHub remote: Local {sync['local_head'][:7]} == Remote {sync['remote_head'][:7]}")
    results["test_git_synchronization"] = {
        "ok": True,
        "branch": g_stat["branch"],
        "commit_hash": latest["commit_hash"],
        "short_hash": latest["short_hash"],
        "synchronized": sync["synchronized"]
    }

    # Test G: Zero Private Data Leak Verification
    print("\n[Test G] Privacy Verification: Zero Memory/Databases/Secrets in Git...")
    from core.git_service import _run_git
    ls_files = _run_git(["ls-files"], cwd=JARVIS_DIR)
    tracked_files = ls_files["stdout"].splitlines()
    forbidden_tracked = [
        f for f in tracked_files if any(k in f.lower() for k in [
            ".env", "memory.db", "jarvis_tasks.db", "id_rsa", ".token", "chatgpt", "local_ai_memory"
        ]) and not f.endswith(".example")
    ]
    print(f"Total files tracked in Git: {len(tracked_files)}")
    print(f"Forbidden files found: {forbidden_tracked}")
    assert len(forbidden_tracked) == 0, f"Found private data in Git: {forbidden_tracked}"
    print("PASS: Verified 0 private databases, ChatGPT exports, or secret files tracked in Git.")
    results["test_privacy_zero_leaks"] = {"ok": True, "tracked_files_count": len(tracked_files)}

    # Test H: Autonomous Multi-Step Execution with Dependencies
    print("\n[Test H] Autonomous Multi-Step Task Execution...")
    test_obj = "Inspect the project README.md and verify that .gitignore exists."
    t0 = time.perf_counter()
    task = orchestrator.execute_objective(test_obj)
    dur = time.perf_counter() - t0
    assert task.status == TaskStatus.COMPLETED
    assert len(task.completed_steps) >= 2
    print(f"PASS: Task {task.task_id} completed in {dur:.2f}s with {len(task.completed_steps)} verified steps.")
    for s in task.completed_steps:
        print(f" - Step {s.step_number}: {s.description} [Tool: {s.tool_name}] -> Outcome: {s.status.value}")
    results["test_multistep_execution"] = {
        "ok": True,
        "task_id": task.task_id,
        "steps_count": len(task.completed_steps),
        "duration_seconds": round(dur, 2)
    }

    out_file = os.path.join(JARVIS_DIR, "evidence", "orchestrator_acceptance_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nAll Acceptance Tests Completed Successfully! Results saved to {out_file}")

if __name__ == "__main__":
    run_acceptance_tests()

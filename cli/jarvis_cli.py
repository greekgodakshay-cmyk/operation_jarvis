"""
Unified Command Line Interface for Operation Jarvis.
Usage:
  python jarvis_cli.py submit "Objective text"
  python jarvis_cli.py status <task_id>
  python jarvis_cli.py list
  python jarvis_cli.py resume <task_id>
  python jarvis_cli.py approve <task_id> <request_id>
  python jarvis_cli.py health
  python jarvis_cli.py trace <task_id>
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure operation_jarvis root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config.settings import settings
from core.orchestrator import orchestrator
from storage.task_db import task_db
from storage.audit_logger import audit_logger
from core.llm_client import llm_client
from registry.memory_adapter import memory_adapter
from registry.capability_registry import capability_registry
from registry.skill_adapter import skill_registry
from security.policy_engine import policy_engine

def cmd_submit(args):
    print(f"\n[JARVIS] Submitting Objective: {args.objective}\n" + "=" * 60)
    task = orchestrator.execute_objective(objective=args.objective)
    print(f"Task ID: {task.task_id}")
    print(f"Final Status: {task.status.value.upper()}")
    if task.plan:
        print(f"\nExecution Plan ({len(task.plan.steps)} steps):")
        for s in task.plan.steps:
            print(f"  Step {s.step_number}: {s.description} -> [{s.tool_name or 'reasoning'}]")

    if task.completed_steps:
        print(f"\nCompleted Steps ({len(task.completed_steps)}):")
        for s in task.completed_steps:
            verif_str = f" [VERIFIED: {s.verification.evidence}]" if s.verification else ""
            print(f"  ✓ Step {s.step_number}: {s.description}{verif_str}")

    if task.status.value == "waiting_for_approval" and task.pending_approval:
        print(f"\n⚠️ ACTION REQUIRED: Restricted Operation Blocked Pending Approval!")
        print(f"Request ID: {task.pending_approval.request_id}")
        print(f"Tool:       {task.pending_approval.tool_name}")
        print(f"Arguments:  {task.pending_approval.arguments}")
        print(f"Reason:     {task.pending_approval.reason}")
        print(f"\nTo approve, run:")
        print(f"  python jarvis_cli.py approve {task.task_id} {task.pending_approval.request_id}")

    if task.verification:
        print(f"\nFinal Verification: {'SUCCESS' if task.verification.is_verified else 'FAILED'}")
        print(f"Evidence:\n{task.verification.evidence}")

    if task.final_outcome:
        print(f"\nOutcome:\n{task.final_outcome}")

def cmd_status(args):
    task = task_db.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"\nTask ID:     {task.task_id}")
    print(f"Objective:   {task.objective}")
    print(f"Status:      {task.status.value.upper()}")
    print(f"Created:     {task.created_at}")
    print(f"Updated:     {task.updated_at}")
    print(f"Completed:   {task.completed_at or 'In Progress / Pending'}")
    
    if task.pending_approval:
        print(f"\n⚠️ PENDING APPROVAL:")
        print(f"  Request ID: {task.pending_approval.request_id}")
        print(f"  Tool:       {task.pending_approval.tool_name}")
        print(f"  Reason:     {task.pending_approval.reason}")

    if task.verification:
        print(f"\nVerification:")
        print(f"  Verified: {task.verification.is_verified}")
        print(f"  Evidence: {task.verification.evidence}")

def cmd_list(args):
    tasks = task_db.list_tasks(limit=args.limit)
    print(f"\nRecent Jarvis Tasks ({len(tasks)}):\n" + "=" * 70)
    for t in tasks:
        print(f"{t.task_id} | {t.status.value.upper():<16} | {t.created_at[:19]} | {t.objective[:40]}")

def cmd_resume(args):
    print(f"\n[JARVIS] Resuming Task {args.task_id}...")
    task = orchestrator.resume_task(args.task_id, approval_token=args.token)
    print(f"Status: {task.status.value.upper()}")
    if task.final_outcome:
        print(f"Outcome: {task.final_outcome}")

def cmd_approve(args):
    granted = not args.deny
    if granted:
        policy_engine.grant_approval(args.request_id)
    task_db.resolve_approval(args.request_id, granted)
    print(f"Approval for request '{args.request_id}' set to: {'GRANTED' if granted else 'DENIED'}")
    if granted:
        print("Resuming execution...")
        orchestrator.resume_task(args.task_id, approval_token=args.request_id)

def cmd_health(args):
    ollama_ok = llm_client.is_healthy()
    mem_status = memory_adapter.get_status()
    tools = capability_registry.list_tools()
    skills = skill_registry.list_skills()

    print("\n============================================================")
    print("OPERATION JARVIS — SYSTEM HEALTH & CAPABILITY AUDIT")
    print("============================================================")
    print(f"LLM (Ollama):           {'ONLINE' if ollama_ok else 'OFFLINE'} ({settings.primary_model})")
    print(f"Memory DB:              {'HEALTHY' if mem_status.get('healthy') else 'WARNING'} (33.5 GB Budget)")
    print(f"Registered Tools:       {len(tools)} capabilities")
    print(f"Discovered Skills:      {len(skills)} procedural skills")
    print(f"Workspace Path:         {ROOT_DIR}")
    print("============================================================\n")

def cmd_trace(args):
    events = audit_logger.get_task_trace(args.task_id)
    print(f"\nExecution Trace for {args.task_id} ({len(events)} events):\n" + "=" * 70)
    for ev in events:
        print(f"[{ev['timestamp'][:19]}] {ev['event_type'].upper():<20} | hash={ev.get('hash', '')[:8]}...")
        if "details" in ev and ev["details"]:
            print(f"   Details: {json.dumps(ev['details'])[:140]}")

def cmd_emergency_stop(args):
    res = orchestrator.emergency_stop(reason=args.reason or "CLI Emergency Stop")
    print(f"\n🚨 [EMERGENCY STOP INVOKED] 🚨")
    print(f"Status:   {res['policy']['status']}")
    print(f"Message:  {res['message']}")
    print(f"Aborted Tasks: {res['aborted_tasks']}")

def cmd_reset_stop(args):
    res = orchestrator.reset_emergency_stop()
    print(f"\n[EMERGENCY STOP CLEARED]")
    print(f"Status:   {res['status']}")
    print(f"Message:  {res['message']}")

def cmd_web_search(args):
    from registry.internet_gateway import internet_gateway
    print(f"\n[JARVIS INTERNET GATEWAY] Query: {args.query}\n" + "=" * 60)
    res = internet_gateway.unified_search(args.query, max_results=args.limit)
    print(f"Sanitized Query:     {res['query']}")
    print(f"Retrieval Timestamp: {res['retrieved_at']}")
    print(f"Sources Found:       {res['count']}\n")
    for idx, s in enumerate(res['sources'], 1):
        print(f"[{idx}] {s['title']}")
        print(f"    URL:       {s['url']}")
        print(f"    Publisher: {s['publisher']} | Freshness: {s['freshness_category']}")
        print(f"    Date:      {s.get('published_date') or 'Unknown'}")
        print(f"    Summary:   {s.get('snippet', '')[:140]}...\n")

def cmd_research(args):
    from core.research_indexer import research_indexer
    if args.action == "status":
        st = research_indexer.get_status()
        print(json.dumps(st, indent=2))
    elif args.action == "run-cycle":
        print("\nTriggering on-demand public research indexing cycle...")
        res = research_indexer.run_indexing_cycle()
        print(json.dumps(res, indent=2))
    elif args.action == "search":
        hits = research_indexer.db.search_research(args.query, limit=args.limit)
        print(f"\nResearch FTS Search for '{args.query}' ({len(hits)} hits):\n" + "=" * 60)
        for h in hits:
            print(f"• [{h['freshness_category']}] {h['title']}")
            print(f"  URL:  {h['url']}")
            print(f"  Snippet: {h.get('snippet', '')[:120]}...\n")
    elif args.action == "emergency-stop":
        res = research_indexer.emergency_stop()
        print(json.dumps(res, indent=2))

def cmd_telemetry(args):
    from core.inference_queue import inference_queue
    import psutil
    vram = inference_queue.get_vram_status()
    q_health = inference_queue.get_queue_health()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

    print("\n============================================================")
    print("OPERATION JARVIS — HARDWARE & INFERENCE TELEMETRY")
    print("============================================================")
    print(f"Host Hardware:          HP Victus (Intel Core 5 210H, RTX 4050 6GB)")
    print(f"CPU Utilization:        {psutil.cpu_percent(interval=0.1)}%")
    print(f"DDR5 System RAM:        {round(mem.used/(1024**3), 2)} GB used / {round(mem.total/(1024**3), 2)} GB ({mem.percent}%)")
    print(f"GPU VRAM Allocated:     {vram['used_mb']} MB / {vram['total_mb']} MB (Headroom: {vram['headroom_pct']}%)")
    print(f"GPU Utilization:        {vram.get('gpu_util_pct', 0)}%")
    print(f"System Drive (C:):      {round(disk.used/(1024**3), 2)} GB / {round(disk.total/(1024**3), 2)} GB ({disk.percent}%)")
    print("------------------------------------------------------------")
    print(f"Inference Queue State:  {q_health['pending_requests_in_queue']} pending | {q_health['completed_requests']} completed")
    print(f"Avg Inference Latency:  {q_health['avg_latency_sec']}s (Last: {q_health['last_latency_sec']}s)")
    print("============================================================\n")

def cmd_code_map(args):
    from core.code_engine import code_engine
    target = args.path or str(ROOT_DIR)
    print(f"\n[JARVIS CODE ENGINE] Mapping repository: {target}\n" + "=" * 60)
    res = code_engine.map_repository(target, max_depth=args.depth)
    print(f"Primary Language:   {res.get('primary_language', 'unknown')}")
    print(f"Total Source Files: {res.get('total_files', 0)}")
    print(f"Entry Points:       {', '.join(res.get('detected_entry_points', []))}")
    print("\nStructure Summary:")
    print(res.get("structure_summary", ""))

def cmd_test_run(args):
    from core.code_engine import code_engine
    cmd = args.cmd or "pytest -q"
    print(f"\n[JARVIS TEST RUNNER] Executing: {cmd}\n" + "=" * 60)
    res = code_engine.run_test_suite(cmd, working_dir=args.working_dir)
    print(f"Status:             {'PASS' if res['ok'] else 'FAIL'}")
    print(f"Exit Code:          {res.get('exit_code')}")
    if res.get("failures"):
        print(f"\nFailures ({res['failure_count']}):")
        for f in res["failures"]:
            print(f"  ✗ {f}")
    print("\nOutput Tail:")
    print(res.get("output_tail", ""))

def cmd_daily_brief(args):
    from core.assistant import assistant
    print("\n[JARVIS] Generating Operational Daily Briefing...\n" + "=" * 65)
    res = assistant.generate_daily_brief(target_date=args.date)
    print(res["briefing"])
    print("\n" + "=" * 65)
    print(f"Calendar events checked: {res['active_event_count']} | Pending tasks: {res['pending_task_count']}")

def cmd_deep_research(args):
    from core.assistant import assistant
    print(f"\n[JARVIS DEEP RESEARCH] Query: {args.query}\n" + "=" * 65)
    res = assistant.conduct_deep_research(query=args.query, domain=args.domain)
    print(f"Decomposed Subqueries: {res['subqueries']}")
    print(f"Gathered Evidence Items: {res['evidence_count']}\n")
    print(res["synthesis"])
    print("\n" + "=" * 65)
    print(f"Archived in research index: {res['archived_url']} (ID: {res['archived_id']})")

def cmd_youtube_concept(args):
    from core.assistant import assistant
    print(f"\n[JARVIS CONTENT ASSISTANT] Topic: {args.topic}\n" + "=" * 65)
    res = assistant.generate_youtube_concept(topic=args.topic, niche=args.niche)
    print(res["package"])
    print("\n" + "=" * 65)
    print(f"Publish Action Gated: Level 3 Approval Required ({res['requires_approval_for_publish']})")

def cmd_desktop(args):
    from core.desktop_controller import desktop_controller
    action_str = " ".join(args.action) if isinstance(args.action, list) else str(args.action)
    res = desktop_controller.execute_cli_command(action_str)
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_open(args):
    from core.desktop_controller import desktop_controller
    target = " ".join(args.target) if isinstance(args.target, list) else str(args.target)
    res = desktop_controller.execute_cli_command(f"open {target}")
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_close(args):
    from core.desktop_controller import desktop_controller
    target = " ".join(args.target) if isinstance(args.target, list) else str(args.target)
    res = desktop_controller.execute_cli_command(f"close {target}")
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_restart(args):
    from core.desktop_controller import desktop_controller
    target = " ".join(args.target) if isinstance(args.target, list) else str(args.target)
    res = desktop_controller.execute_cli_command(f"restart {target}")
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_focus(args):
    from core.desktop_controller import desktop_controller
    target = " ".join(args.target) if isinstance(args.target, list) else str(args.target)
    res = desktop_controller.execute_cli_command(f"focus {target}")
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_minimize(args):
    from core.desktop_controller import desktop_controller
    target = " ".join(args.target) if isinstance(args.target, list) else str(args.target)
    res = desktop_controller.execute_cli_command(f"minimize {target}")
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_maximize(args):
    from core.desktop_controller import desktop_controller
    target = " ".join(args.target) if isinstance(args.target, list) else str(args.target)
    res = desktop_controller.execute_cli_command(f"maximize {target}")
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_restore(args):
    from core.desktop_controller import desktop_controller
    target = " ".join(args.target) if isinstance(args.target, list) else str(args.target)
    res = desktop_controller.execute_cli_command(f"restore {target}")
    if res.get("output"):
        print(res["output"])
    elif res.get("message"):
        print(res["message"])

def cmd_list_apps(args):
    from core.desktop_controller import desktop_controller
    res = desktop_controller.list_running_apps()
    print(res.get("output", ""))

def cmd_find_apps(args):
    from core.desktop_controller import desktop_controller
    q = " ".join(args.query) if hasattr(args, "query") and isinstance(args.query, list) else ""
    apps = desktop_controller.find_installed_apps(filter_query=q)
    lines = [f"• {a['name']} ({a['path']})" for a in apps[:20]]
    print(f"[SUCCESS] Found {len(apps)} installed applications:\n" + "\n".join(lines))

def cmd_ask(args):
    from core.freshness_router import source_router
    q = args.question
    auth = getattr(args, "reddit", False)
    res = source_router.answer_query(q, reddit_authorized=auth)
    print(f"\n[JARVIS ROUTE: {res['route'].upper()}]\n" + "=" * 60)
    print(res["reply"])
    if res.get("sources"):
        print("\nSources & Citations:")
        for s in res["sources"]:
            print(f"  • {s['title']} -> {s['url']}")
    print("=" * 60)

def cmd_wiki(args):
    from registry.internet_gateway import internet_gateway
    q = args.subject
    sec = getattr(args, "section", None)
    res = internet_gateway.get_wikipedia_article(q, section_title=sec)
    if not res.get("ok"):
        print(f"\n[WIKIPEDIA RETRIEVAL] {res.get('error', 'Article not found.')}")
        return
    print(f"\n[WIKIPEDIA] {res['title']}\n" + "=" * 60)
    print(f"URL: {res['url']}")
    print(f"Date: {res.get('published_date')}\n")
    print(res.get("extract", "")[:1200])
    if res.get("sections"):
        print(f"\nAvailable Sections ({len(res['sections'])}):")
        print(", ".join(res["sections"][:10]))
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Operation Jarvis CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # submit
    p_sub = subparsers.add_parser("submit")
    p_sub.add_argument("objective", type=str, help="Objective to execute")
    p_sub.set_defaults(func=cmd_submit)

    # status
    p_stat = subparsers.add_parser("status")
    p_stat.add_argument("task_id", type=str, help="Task ID")
    p_stat.set_defaults(func=cmd_status)

    # list
    p_list = subparsers.add_parser("list")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    # resume
    p_res = subparsers.add_parser("resume")
    p_res.add_argument("task_id", type=str, help="Task ID to resume")
    p_res.add_argument("--token", type=str, help="Approval token if required")
    p_res.set_defaults(func=cmd_resume)

    # approve
    p_app = subparsers.add_parser("approve")
    p_app.add_argument("task_id", type=str, help="Task ID")
    p_app.add_argument("request_id", type=str, help="Approval Request ID")
    p_app.add_argument("--deny", action="store_true", help="Deny instead of grant")
    p_app.set_defaults(func=cmd_approve)

    # health
    p_health = subparsers.add_parser("health")
    p_health.set_defaults(func=cmd_health)

    # trace
    p_trace = subparsers.add_parser("trace")
    p_trace.add_argument("task_id", type=str, help="Task ID")
    p_trace.set_defaults(func=cmd_trace)

    # emergency-stop
    p_estop = subparsers.add_parser("emergency-stop")
    p_estop.add_argument("--reason", type=str, default="Operator command", help="Reason for emergency stop")
    p_estop.set_defaults(func=cmd_emergency_stop)

    # reset-stop
    p_rstop = subparsers.add_parser("reset-stop")
    p_rstop.set_defaults(func=cmd_reset_stop)

    # web-search
    p_wsearch = subparsers.add_parser("web-search")
    p_wsearch.add_argument("query", type=str, help="Search query")
    p_wsearch.add_argument("--limit", type=int, default=5, help="Result limit")
    p_wsearch.set_defaults(func=cmd_web_search)

    # research
    p_res_cmd = subparsers.add_parser("research")
    p_res_cmd.add_argument("action", choices=["status", "run-cycle", "search", "emergency-stop"], help="Action to execute")
    p_res_cmd.add_argument("--query", type=str, default="", help="Query for search")
    p_res_cmd.add_argument("--limit", type=int, default=5, help="Result limit")
    p_res_cmd.set_defaults(func=cmd_research)

    # telemetry
    p_telem = subparsers.add_parser("telemetry")
    p_telem.set_defaults(func=cmd_telemetry)

    # code-map
    p_cmap = subparsers.add_parser("code-map")
    p_cmap.add_argument("--path", type=str, default=None, help="Target repository path")
    p_cmap.add_argument("--depth", type=int, default=3, help="Max directory depth")
    p_cmap.set_defaults(func=cmd_code_map)

    # test-run
    p_trun = subparsers.add_parser("test-run")
    p_trun.add_argument("--cmd", type=str, default="pytest -q", help="Test command to run")
    p_trun.add_argument("--working-dir", type=str, default=None, help="Working directory")
    p_trun.set_defaults(func=cmd_test_run)

    # daily-brief
    p_brief = subparsers.add_parser("daily-brief")
    p_brief.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD")
    p_brief.set_defaults(func=cmd_daily_brief)

    # deep-research
    p_dres = subparsers.add_parser("deep-research")
    p_dres.add_argument("query", type=str, help="Research topic or query")
    p_dres.add_argument("--domain", type=str, default="technical", help="Research domain")
    p_dres.set_defaults(func=cmd_deep_research)

    # youtube-concept
    p_yt = subparsers.add_parser("youtube-concept")
    p_yt.add_argument("topic", type=str, help="YouTube video topic")
    p_yt.add_argument("--niche", type=str, default="bodybuilding_motivation", help="Content niche")
    p_yt.set_defaults(func=cmd_youtube_concept)

    # desktop
    p_desk = subparsers.add_parser("desktop")
    p_desk.add_argument("action", nargs="*", help="Desktop action or application command")
    p_desk.set_defaults(func=cmd_desktop)

    # open
    p_open = subparsers.add_parser("open")
    p_open.add_argument("target", nargs="+", help="Application or folder to open")
    p_open.set_defaults(func=cmd_open)

    # close
    p_close = subparsers.add_parser("close")
    p_close.add_argument("target", nargs="+", help="Application to close")
    p_close.set_defaults(func=cmd_close)

    # restart
    p_res = subparsers.add_parser("restart")
    p_res.add_argument("target", nargs="+", help="Application to restart")
    p_res.set_defaults(func=cmd_restart)

    # focus
    p_foc = subparsers.add_parser("focus")
    p_foc.add_argument("target", nargs="+", help="Application window to focus")
    p_foc.set_defaults(func=cmd_focus)

    # minimize
    p_min = subparsers.add_parser("minimize")
    p_min.add_argument("target", nargs="+", help="Application window to minimize")
    p_min.set_defaults(func=cmd_minimize)

    # maximize
    p_max = subparsers.add_parser("maximize")
    p_max.add_argument("target", nargs="+", help="Application window to maximize")
    p_max.set_defaults(func=cmd_maximize)

    # restore
    p_rst = subparsers.add_parser("restore")
    p_rst.add_argument("target", nargs="+", help="Application window to restore")
    p_rst.set_defaults(func=cmd_restore)

    # list-apps
    p_lapps = subparsers.add_parser("list-apps")
    p_lapps.set_defaults(func=cmd_list_apps)

    # find-apps
    p_fapps = subparsers.add_parser("find-apps")
    p_fapps.add_argument("query", nargs="*", help="Application name to search")
    p_fapps.set_defaults(func=cmd_find_apps)

    # ask
    p_ask = subparsers.add_parser("ask")
    p_ask.add_argument("question", type=str, help="Question to ask JARVIS")
    p_ask.add_argument("--reddit", action="store_true", help="Authorize Reddit community research")
    p_ask.set_defaults(func=cmd_ask)

    # wiki
    p_wiki = subparsers.add_parser("wiki")
    p_wiki.add_argument("subject", type=str, help="Wikipedia subject or query")
    p_wiki.add_argument("--section", type=str, default=None, help="Specific section title")
    p_wiki.set_defaults(func=cmd_wiki)

    # Direct single-string or natural action command interceptor
    if len(sys.argv) == 2 and any(sys.argv[1].lower().startswith(pfx) for pfx in [
        "open ", "launch ", "start ", "close ", "shut down ", "terminate ", "kill ",
        "restart ", "focus ", "minimize ", "maximize ", "restore ", "list running", "find installed"
    ]):
        from core.desktop_controller import desktop_controller
        res = desktop_controller.execute_cli_command(sys.argv[1])
        if res.get("output"):
            print(res["output"])
        elif res.get("message"):
            print(res["message"])
        return

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

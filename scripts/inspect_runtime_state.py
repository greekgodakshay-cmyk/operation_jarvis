import sys
import os
import json
import sqlite3

JARVIS_DIR = r"C:\Users\Akshay aravind .rv\operation_jarvis"
MEMORY_DIR = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"
if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)
if MEMORY_DIR not in sys.path:
    sys.path.insert(0, MEMORY_DIR)

def inspect_all():
    print("=== 1. CAPABILITY REGISTRY ===")
    from registry.capability_registry import capability_registry
    tools = capability_registry.list_tools()
    print(f"Total tools in capability_registry: {len(tools)}")

    print("\n=== 2. MEMORY DATABASE ===")
    db_path = os.path.join(MEMORY_DIR, "07_MEMORY_INDEX", "memory.db")
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"memory.db exists at: {db_path} (Size: {size_mb:.2f} MB)")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')")
        tables = cursor.fetchall()
        for tbl, ttype in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{tbl}]")
                cnt = cursor.fetchone()[0]
                print(f"  - {tbl} ({ttype}): {cnt} rows")
            except Exception as e:
                print(f"  - {tbl} ({ttype}): error: {e}")
        conn.close()

    print("\n=== 3. TEMPORAL CHECK ===")
    from core.temporal import get_system_temporal_info, get_temporal_context_prompt, tool_get_current_time
    info = get_system_temporal_info()
    print("Host temporal info:", json.dumps(info, indent=2))
    tool_res = tool_get_current_time()
    print("tool_get_current_time:", json.dumps(tool_res, indent=2))

    print("\n=== 4. FRESHNESS CLASSIFIER & GATEWAY ===")
    from core.freshness_router import classify_freshness, fetch_live_intelligence
    test_queries = [
        "Who is the current CEO of NVIDIA?",
        "What is the latest information about the alleged NVIDIA/China spy scandal and Jensen Huang resignation?",
        "Who won the latest Israeli election, and who is currently Prime Minister?",
        "Who was the first Muslim elected in the 2026 US midterm elections?",
        "What is the latest SpaceX Starship news?",
        "Tell me about Python decorators."
    ]
    for q in test_queries:
        is_fresh, route = classify_freshness(q)
        print(f"\nQuery: '{q}'\n  Freshness required: {is_fresh}, Route: {route}")
        if is_fresh:
            intel = fetch_live_intelligence(q, route_type=route)
            print(f"  Result ok: {intel.get('ok')}, Hits: {len(intel.get('evidence', []))}, Latency: {intel.get('latency_ms')}ms")
            for ev in intel.get('evidence', [])[:2]:
                print(f"    - Title: {ev.get('title')}")
                print(f"      Source: {ev.get('source')}")
                print(f"      Date: {ev.get('date')}")
                print(f"      Snippet: {ev.get('snippet')[:100]}...")

    print("\n=== 5. WORKSPACE RESOLVER ===")
    from core.workspace import fuzzy_resolve_file, ensure_project_cwd
    print("ensure_project_cwd:", ensure_project_cwd())
    for f in ["orchestra.py", "qwen_chat.py", "ledger.md", "memory.db"]:
        resolved = fuzzy_resolve_file(f)
        print(f"Fuzzy resolve '{f}' -> {resolved}")

if __name__ == "__main__":
    inspect_all()

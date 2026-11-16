import sys
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from registry.capability_registry import capability_registry

cases = [
    # Coding (10)
    ("Check the git status and uncommitted changes in the repository", "git_status"),
    ("Run the pytest test suite to verify module behavior", "run_tests"),
    ("Extract classes, functions, and symbols from the python module", "code_symbols"),
    ("Apply multi-file atomic edits with rollback to the source files", "multi_file_patch"),
    ("Map the directory structure and entry points of the project", "repo_map"),
    ("Read source file contents to inspect function implementation", "read_file"),
    ("Write new code to a file in the workspace", "write_file"),
    ("Edit specific lines in a code file", "edit_file"),
    ("Search procedural skills for development workflows", "search_skills"),
    ("Read detailed instructions for a specific coding skill", "read_skill"),

    # Browser & Web (8)
    ("Navigate the browser to a website URL", "browser_navigate"),
    ("Take a browser snapshot to inspect DOM and layout", "browser_snapshot"),
    ("Fetch clean text content from a web page URL", "web_fetch"),
    ("Search the live web for technical documentation", "web_search"),
    ("Inspect open pages in the Chrome browser session", "browser_list_pages"),
    ("Check browser session connectivity and status", "browser_status"),
    ("Search Wikipedia articles for technical background", "wikipedia_search"),
    ("Launch persistent Chrome browser instance with remote debugging", "browser_launch_persistent"),

    # Documents & Research (8)
    ("Ingest a PDF research document into the database", "document_ingest"),
    ("Search document chunks for keyword citations", "document_search"),
    ("List all ingested research documents", "document_list"),
    ("Search research index for relevant academic papers", "research_search"),
    ("Inspect status of research index database", "research_status"),
    ("Ingest an excel spreadsheet workbook", "document_ingest"),
    ("Query indexed text chunks for source page citations", "document_search"),
    ("Search latest technology news feeds", "tech_news_search"),

    # System & Windows Ops (8)
    ("Check hardware telemetry including CPU, RAM, and GPU VRAM headroom", "system_telemetry"),
    ("Inspect inference queue state and latency metrics", "inference_health"),
    ("Execute a safe PowerShell command to inspect directory", "run_command"),
    ("Inspect active desktop windows using agent desktop CLI", "desktop"),
    ("List running applications via desktop accessibility tree", "desktop"),
    ("Verify if a file exists on the filesystem", "verify_file_exists"),
    ("Verify file content hash on disk", "verify_file_content"),
    ("Check directory file listing", "list_dir"),

    # Memory & Knowledge (8)
    ("Search personal memory for past project decisions", "memory_search"),
    ("Store a newly verified fact into long-term memory", "memory_store"),
    ("Get project overview and category distribution from memory", "memory_project_overview"),
    ("Inspect memory database status and budget", "memory_status"),
    ("Recall past context regarding the backup project", "memory_search"),
    ("Store notes on the internship tracker project", "memory_store"),
    ("Update an existing memory entry", "memory_update"),
    ("Check status of memory database", "memory_status"),

    # Personal Assistant (8)
    ("Get list of upcoming calendar events", "calendar_get_events"),
    ("Check available time slots on the schedule", "calendar_check_availability"),
    ("Search emails from inbox", "email_search"),
    ("Read the full content of an email", "email_read"),
    ("Create a draft email for review", "email_draft"),
    ("Summarize recent emails from today", "email_summarize"),
    ("Check active schedules and next run times", "schedule_list"),
    ("Suggest open meeting slots for tomorrow", "calendar_suggest_slots")
]

hits = 0
results = []
for obj, expected_tool in cases:
    selected = capability_registry.find_relevant_tools(obj, limit=8)
    names = [s["function"]["name"] for s in selected]
    is_hit = expected_tool in names
    if is_hit:
        hits += 1
        rank = names.index(expected_tool) + 1
    else:
        rank = -1
    results.append({
        "objective": obj,
        "expected": expected_tool,
        "is_hit": is_hit,
        "rank": rank,
        "top_3": names[:3]
    })

accuracy = (hits / len(cases)) * 100.0
print(f"BENCHMARK RESULTS: {hits}/{len(cases)} cases passed ({accuracy:.1f}% accuracy)")

misses = [r for r in results if not r["is_hit"]]
if misses:
    print(f"\nMisses ({len(misses)}):")
    for m in misses:
        print(f"  ✗ '{m['objective']}' -> Expected: {m['expected']}, Selected: {m['top_3']}")
else:
    print("All 50 benchmark cases successfully matched the expected tool in the top 8 set!")

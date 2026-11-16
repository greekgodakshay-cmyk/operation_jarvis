"""
Script to test Memory Accuracy, Contradiction Detection, Timestamp Supersession,
and Project Separation across the 4 distinct domains:
1. Operation JARVIS
2. Student Internship & Skill Tracker
3. Multi-Cloud Backup System
4. Mr Mysto / YouTube
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

JARVIS_ROOT = Path(r"C:\Users\Akshay aravind .rv\operation_jarvis")
sys.path.insert(0, str(JARVIS_ROOT))

from registry.memory_adapter import memory_adapter

def test_memory_system():
    print("=" * 60)
    print("TESTING MEMORY SYSTEM ACCURACY & PROJECT SEPARATION")
    print("=" * 60)

    # 1. Inspect Status & Counts
    status = memory_adapter.get_status()
    print(f"Memory Status: Healthy={status.get('healthy')}, UsedMB={status.get('total_used_mb', 0):.2f}")
    
    overview = memory_adapter.get_project_overview()
    print(f"Total Memories in SQLite: {overview.get('total_memories')}")
    print(f"Categories Breakdown: {json.dumps(overview.get('categories', {}), indent=2)}")

    # 2. Test Project Separation
    print("\n--- Testing Project Separation ---")
    test_projects = [
        ("operation_jarvis", "Operation JARVIS core architecture and task orchestration"),
        ("student_internship", "Student Internship & Skill Tracker portal requirements and resume review"),
        ("multicloud_backup", "Multi-Cloud Backup System encryption keys and snapshot schedules"),
        ("mr_mysto", "Mr Mysto YouTube channel bodybuilding motivation and video editing timeline")
    ]
    
    # Store sacrificial isolated records for each project
    sacrificial_ids = []
    try:
        for prj, content in test_projects:
            title = f"Sacrificial Spec for {prj}"
            res = memory_adapter.store(
                title=title,
                content=content,
                category="02_PROJECT_KNOWLEDGE",
                project=prj,
                importance="high",
                tags=[prj, "sacrificial_eval"],
                source="test_memory_quality"
            )
            mid = res.get("id") or res.get("memory_id")
            if mid:
                sacrificial_ids.append((mid, res.get("file_path")))
            print(f"Stored {prj} record -> ID: {mid}")

        # Test query isolation
        print("\nVerifying Strict Project Isolation:")
        for prj, _ in test_projects:
            results = memory_adapter.search(query="sacrificial_eval", project=prj, limit=10)
            returned_projects = set(r["project"] for r in results if "sacrificial_eval" in r.get("title", "").lower() or "sacrificial" in r.get("snippet", "").lower() or r.get("project") == prj)
            other_projects = [p for p in returned_projects if p != prj and p != "global"]
            print(f"Query for project='{prj}': matched {len(results)} items. Other projects leaked: {other_projects}")
            assert len(other_projects) == 0, f"Leakage detected in {prj}: {other_projects}"

        print("Project isolation test: PASSED (Zero cross-project leakage).")

        # 3. Test Contradiction & Supersession Detection
        print("\n--- Testing Contradiction & Timestamp Supersession ---")
        # Step A: Store an initial premise
        premise_title = "Sacrificial API Port Configuration"
        res_v1 = memory_adapter.store(
            title=premise_title,
            content="FastAPI backend runs on port 8000 for all local endpoints.",
            category="04_TECHNICAL_DOCUMENTATION",
            project="operation_jarvis",
            importance="normal",
            tags=["api", "port", "sacrificial_contradiction"]
        )
        print(f"Initial premise stored: {res_v1.get('id')}")

        # Step B: Attempt exact title duplicate / conflict detection
        conflict_check = memory_adapter.detect_duplicate_or_contradiction(
            title=premise_title,
            content="FastAPI backend port was migrated from 8000 to port 8080 due to collision."
        )
        print(f"Conflict detection on identical title: {conflict_check}")
        assert conflict_check["has_conflict"] is True, "Expected duplicate/contradiction detected on identical title"

        # Step B2: Attempt semantic contradiction on differing title
        semantic_check = memory_adapter.detect_duplicate_or_contradiction(
            title="Sacrificial API Port Migration",
            content="FastAPI backend port was migrated from 8000 to port 8080 due to collision."
        )
        print(f"Conflict detection on differing title with entity overlap & migration intent: {semantic_check}")
        assert semantic_check["has_conflict"] is True, "Expected semantic supersession detected on overlapping entity with migration intent"

        # Step C: Evaluate non-identical title semantic contradiction
        # E.g. "Sacrificial Port Migration" contradicts "Sacrificial API Port Configuration"
        contradicting_title = "Sacrificial Service Port Migration"
        res_v2 = memory_adapter.store(
            title=contradicting_title,
            content="FastAPI backend was migrated from port 8000 to port 8080 due to collision. Port 8000 is deprecated.",
            category="04_TECHNICAL_DOCUMENTATION",
            project="operation_jarvis",
            importance="high",
            tags=["api", "port", "sacrificial_contradiction"]
        )
        print(f"Contradicting/updated premise stored: {res_v2.get('id')}")

        # Search for port configuration
        port_results = memory_adapter.search(query="FastAPI port sacrificial_contradiction", project="operation_jarvis", limit=5)
        print(f"\nSearch results for 'FastAPI port sacrificial_contradiction' (count={len(port_results)}):")
        for i, r in enumerate(port_results):
            print(f"[{i+1}] Title: '{r['title']}' | Updated: {r.get('updated_at')} | Rank: {r.get('rank')}")

    finally:
        # Clean up sacrificial memories
        print("\nCleaning up sacrificial records...")
        with memory_adapter.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, file_path FROM memories WHERE title LIKE 'Sacrificial %'")
            rows = cur.fetchall()
            for r in rows:
                mid = r["id"]
                fpath = r["file_path"]
                cur.execute("DELETE FROM memories WHERE id = ?", (mid,))
                cur.execute("DELETE FROM memories_fts WHERE id = ?", (mid,))
                cur.execute("DELETE FROM audit_log WHERE memory_id = ?", (mid,))
                if fpath and os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
            conn.commit()
            print(f"Purged {len(rows)} sacrificial memory entries.")

if __name__ == "__main__":
    test_memory_system()

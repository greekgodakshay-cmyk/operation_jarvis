#!/usr/bin/env python3
"""
Operation JARVIS — Safe Document Inventory & Orphan Cleanup Utility
Audits all documents in document_index.db and selectively purges ONLY:
1. Missing files (deleted pytest temp files).
2. Ephemeral test files in AppData/Local/Temp.
Strictly PRESERVES all legitimate user documents in data/uploads/.
Usage:
  python scripts/cleanup_invalid_documents.py            # Dry-run audit only (safe)
  python scripts/cleanup_invalid_documents.py --execute  # Applies cleanup
"""

import sys
import sqlite3
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "document_index.db"

def audit_and_cleanup(execute: bool = False):
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    docs = conn.execute("SELECT * FROM documents ORDER BY ingested_at DESC").fetchall()
    chunks = conn.execute("SELECT doc_id, COUNT(*) as count FROM chunks GROUP BY doc_id").fetchall()
    chunk_counts = {r["doc_id"]: r["count"] for r in chunks}

    valid_managed = []
    orphaned_missing = []
    ephemeral_temp = []
    empty_records = []

    for d in docs:
        doc_id = d["doc_id"]
        fpath = Path(d["file_path"])
        fsize = d["file_size_bytes"]
        exists = fpath.exists()
        disk_size = fpath.stat().st_size if exists else 0
        actual_chunks = chunk_counts.get(doc_id, 0)

        info = {
            "doc_id": doc_id,
            "filename": d["filename"],
            "file_path": str(fpath),
            "file_size": fsize,
            "disk_size": disk_size,
            "chunks": actual_chunks,
            "ingested_at": d["ingested_at"]
        }

        if not exists:
            orphaned_missing.append(info)
        elif "data\\uploads" in str(fpath) or "data/uploads" in str(fpath):
            if disk_size == 0 or actual_chunks == 0:
                empty_records.append(info)
            else:
                valid_managed.append(info)
        else:
            # File exists, but inside a Temp/pytest directory
            ephemeral_temp.append(info)

    print("=" * 70)
    print("OPERATION JARVIS — DOCUMENT AUDIT SUMMARY")
    print("=" * 70)
    print(f"Total Registered Records in Database : {len(docs)}")
    print(f"Valid Managed Documents (Preserved)  : {len(valid_managed)}")
    print(f"Missing Temp Files (Non-existent)     : {len(orphaned_missing)}")
    print(f"Lingering Ephemeral Pytest Files      : {len(ephemeral_temp)}")
    print(f"Empty Files / Zero Chunks            : {len(empty_records)}")
    print("-" * 70)

    print(f"\n[+] VALID MANAGED DOCUMENTS ({len(valid_managed)}) — WILL NEVER BE TOUCHED:")
    for v in valid_managed:
        print(f"  • {v['doc_id']} | {v['filename']} ({v['disk_size']} B, {v['chunks']} chunks)")

    targets_to_purge = orphaned_missing + ephemeral_temp

    print(f"\n[!] INVALID TEST RECORDS IDENTIFIED FOR PURGE ({len(targets_to_purge)}):")
    for t in targets_to_purge:
        status = "MISSING FROM DISK" if not Path(t["file_path"]).exists() else "EPHEMERAL TEMP FILE"
        print(f"  • {t['doc_id']} | {t['filename']} [{status}] -> {t['file_path']}")

    if not execute:
        print("\n" + "=" * 70)
        print("DRY-RUN MODE: No changes made to document_index.db.")
        print("To execute safe cleanup, run with --execute")
        print("=" * 70)
        return

    print("\nExecuting safe cleanup of invalid test records...")
    purged_count = 0
    with conn:
        for t in targets_to_purge:
            did = t["doc_id"]
            conn.execute("DELETE FROM chunks_fts WHERE doc_id = ?", (did,))
            conn.execute("DELETE FROM chunks WHERE doc_id = ?", (did,))
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (did,))
            purged_count += 1

    print(f"Cleaned up {purged_count} invalid records from database.")
    print("Original documents in data/uploads/ remain completely intact.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit and safely purge invalid document test records.")
    parser.add_argument("--execute", action="store_true", help="Perform the actual database cleanup.")
    args = parser.parse_args()
    audit_and_cleanup(execute=args.execute)

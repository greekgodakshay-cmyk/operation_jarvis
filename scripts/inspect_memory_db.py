import sys
import os
import sqlite3
import json

MEMORY_DIR = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"
db_path = os.path.join(MEMORY_DIR, "07_MEMORY_INDEX", "memory.db")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== TABLE SCHEMAS ===")
for tbl in ["memories", "chatgpt_provenance", "storage_metrics", "audit_log"]:
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE name = '{tbl}'")
    row = cursor.fetchone()
    print(f"\nSchema for {tbl}:\n{row[0] if row else 'NOT FOUND'}")

print("\n=== MEMORIES SUMMARY ===")
cursor.execute("SELECT project, category, COUNT(*) FROM memories GROUP BY project, category")
for p, c, count in cursor.fetchall():
    print(f"Project: {p:25} | Category: {c:25} | Count: {count}")

print("\n=== CHATGPT PROVENANCE SUMMARY ===")
cursor.execute("SELECT COUNT(*), COUNT(DISTINCT conversation_id), MIN(created_at), MAX(created_at) FROM chatgpt_provenance")
total_prov, dist_conv, min_ts, max_ts = cursor.fetchone()
print(f"Total provenance rows: {total_prov}")
print(f"Distinct ChatGPT conversations: {dist_conv}")
print(f"Timestamp range: {min_ts} to {max_ts}")

print("\n=== CHECKING RAW CONVERSATION ARCHIVES ===")
archive_dir = os.path.join(MEMORY_DIR, "03_CONVERSATION_ARCHIVES")
for root, dirs, files in os.walk(archive_dir):
    for f in files:
        fp = os.path.join(root, f)
        print(f"Archive file: {fp} ({os.path.getsize(fp)} bytes)")

print("\n=== SAMPLE RECORDS FOR SPECIFIC TOPICS ===")
topics = [
    "Student Internship",
    "Multi-Cloud Backup",
    "JARVIS",
    "preference",
    "personality"
]
for t in topics:
    cursor.execute("SELECT id, title, project, category, LENGTH(content) FROM memories WHERE title LIKE ? OR content LIKE ? LIMIT 3", (f"%{t}%", f"%{t}%"))
    rows = cursor.fetchall()
    print(f"\nQuery for '{t}' (hits: {len(rows)}):")
    for r in rows:
        print(f"  [{r[0]}] {r[1]} (Project: {r[2]}, Cat: {r[3]}, Len: {r[4]})")

conn.close()

import sys
import os
import sqlite3

MEMORY_DIR = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"
conn = sqlite3.connect(os.path.join(MEMORY_DIR, "07_MEMORY_INDEX", "memory.db"))
c = conn.cursor()

print("=== Memories matching JARVIS ===")
c.execute("SELECT id, title, project, category, file_path FROM memories WHERE title LIKE '%jarvis%' OR project LIKE '%jarvis%'")
rows = c.fetchall()
print(f"Total matching memories: {len(rows)}")
for r in rows:
    print(r)

print("\n=== Memories matching Preference or Personality ===")
c.execute("SELECT id, title, project, category, file_path FROM memories WHERE category = '01_PERSONAL_PREFERENCES'")
rows = c.fetchall()
for r in rows:
    print(r)

print("\n=== Memories matching Architecture or Decisions ===")
c.execute("SELECT id, title, project, category, file_path FROM memories WHERE title LIKE '%architect%' OR title LIKE '%decision%'")
rows = c.fetchall()
for r in rows:
    print(r)

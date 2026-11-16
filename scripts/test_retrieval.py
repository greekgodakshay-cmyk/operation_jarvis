import sys
import os

MEMORY_DIR = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"
if MEMORY_DIR not in sys.path:
    sys.path.insert(0, MEMORY_DIR)

from engine.db import MemoryDB
from engine.retriever import MemoryRetriever

db_path = os.path.join(MEMORY_DIR, "07_MEMORY_INDEX", "memory.db")
db = MemoryDB(db_path)
retriever = MemoryRetriever(db, MEMORY_DIR)

test_queries = [
    "Student Internship",
    "Multi-Cloud Backup",
    "Operation JARVIS architectural decision",
    "user preferences",
    "tell me about my personality",
    "what did we discuss about Google Drive viva"
]

for q in test_queries:
    print(f"\n==========================================")
    print(f"QUERY: '{q}'")
    intent = retriever.classify_query(q)
    print(f"Intent classified: {intent}")
    results = retriever.search_relevant(q, limit=3)
    print(f"search_relevant hits: {len(results)}")
    for r in results:
        print(f"  - [{r['category']}] {r['title']} (Score: {r.get('composite_score', 0):.2f})")
    
    # Also test raw FTS search across all categories
    all_hits = retriever.search(q, limit=3)
    print(f"raw search (all categories) hits: {len(all_hits)}")
    for r in all_hits:
        print(f"  - [{r['category']} | {r['project']}] {r['title']}")

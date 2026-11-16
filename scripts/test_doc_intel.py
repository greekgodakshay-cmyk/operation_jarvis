import sys
import time
from pathlib import Path

JARVIS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(JARVIS_ROOT))

from core.doc_intelligence import doc_intelligence

test_file = Path("data/doc_test_eval.txt")
test_file.write_text("Operation JARVIS Document Intelligence Test.\nSection 1: Kernel handle architecture.\nSection 2: Security descriptors and DACLs.", encoding="utf-8")

t0 = time.time()
res = doc_intelligence.ingest_document(test_file)
dt = time.time() - t0
print(f"Ingest status: {res['status']} | Chunks: {res['total_chunks']} | Latency: {dt:.4f}s")

search_res = doc_intelligence.search_documents("Security descriptors DACLs", limit=3)
print(f"Search matches: {len(search_res)} | First citation: {search_res[0].get('citation') if search_res else None}")
if search_res:
    print(f"Snippet: {search_res[0].get('snippet')}")

# Clean up
if test_file.exists():
    test_file.unlink()
print("Doc intel test complete.")

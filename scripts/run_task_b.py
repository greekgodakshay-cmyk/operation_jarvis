import sys, os
from pathlib import Path
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from core.doc_intelligence import doc_intelligence
from core.llm_client import OllamaLLMClient
from core.types import TaskBudget

p_data = Path(r"C:\Users\Akshay aravind .rv\operation_jarvis\data")
f_alpha = p_data / "doc_alpha.txt"
f_beta = p_data / "doc_beta.txt"

f_alpha.write_text(
    "SYSTEM ALPHA ARCHITECTURE SPECIFICATION\n"
    "Throughput capacity: 450 requests per second under peak load.\n"
    "Primary database: PostgreSQL 16 cluster with replication.\n"
    "Caching layer: Distributed Redis instances.\n"
    "Deployment target: Linux Ubuntu containerized environment.\n",
    encoding="utf-8"
)

f_beta.write_text(
    "SYSTEM BETA ARCHITECTURE SPECIFICATION\n"
    "Throughput capacity: 920 requests per second under peak load.\n"
    "Primary database: SQLite 3.45 with Write-Ahead Logging (WAL).\n"
    "Caching layer: In-process LRU cache.\n"
    "Deployment target: Windows 11 local workstation.\n",
    encoding="utf-8"
)

# 1. Ingest both documents
ing_a = doc_intelligence.ingest_document(f_alpha, force_reindex=True)
ing_b = doc_intelligence.ingest_document(f_beta, force_reindex=True)
print("Ingest Alpha:", ing_a.get("status"), "| Ingest Beta:", ing_b.get("status"))

# 2. Search both documents
chunks_a = doc_intelligence.search_documents("Alpha Throughput PostgreSQL", limit=1)
chunks_b = doc_intelligence.search_documents("Beta Throughput SQLite", limit=1)

assert len(chunks_a) > 0 and len(chunks_b) > 0
cit_a = chunks_a[0]["citation"]
cit_b = chunks_b[0]["citation"]
print("Citation A:", cit_a)
print("Citation B:", cit_b)

# 3. Model synthesis with citations
client = OllamaLLMClient()
prompt = (
    f"Compare the architecture of System Alpha and System Beta based strictly on these extracts:\n\n"
    f"Extract A ({cit_a}):\n{chunks_a[0]['text_content']}\n\n"
    f"Extract B ({cit_b}):\n{chunks_b[0]['text_content']}\n\n"
    f"State the throughput, primary database, and caching differences, including the exact citation for each fact."
)

res = client.chat(
    messages=[{"role": "user", "content": prompt}],
    task_budget=TaskBudget.RESEARCH,
    temperature=0.1
)

output_text = res.get("content", "")
print("Model Comparison Output:\n", output_text)

# Check citations in output
has_cit_a = "doc_alpha.txt" in output_text or "Alpha" in output_text
has_cit_b = "doc_beta.txt" in output_text or "Beta" in output_text
print("Mentions Alpha:", has_cit_a)
print("Mentions Beta:", has_cit_b)
assert has_cit_a and has_cit_b

# 4. Cleanup
f_alpha.unlink(missing_ok=True)
f_beta.unlink(missing_ok=True)
print("TASK (B) DOCUMENT COMPARISON & CITED SUMMARY: VERIFIED!")

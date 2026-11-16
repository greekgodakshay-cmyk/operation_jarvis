import sys
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from core.llm_client import OllamaLLMClient
from core.types import TaskBudget

client = OllamaLLMClient()
prompt = (
    "Research the technical trade-offs of SQLite Write-Ahead Logging (WAL) mode versus rollback journal mode. "
    "Structure your response strictly under three distinct sections:\n"
    "1. VERIFIED FACTS (Empirical concurrency model, reader/writer non-blocking properties)\n"
    "2. ARCHITECTURAL INFERENCES (Why WAL provides superior throughput in read-heavy applications)\n"
    "3. KNOWN UNCERTAINTIES & SYSTEM CONSTRAINTS (Where WAL fails or degrades, such as NFS/SMB network shares or high write contention)\n"
    "Be direct, objective, and mathematically precise."
)

res = client.chat(
    messages=[{"role": "user", "content": prompt}],
    task_budget=TaskBudget.RESEARCH,
    temperature=0.1
)

content = res.get("content", "")
print("Model Output:\n", content)

has_facts = "VERIFIED FACTS" in content.upper()
has_inferences = "ARCHITECTURAL INFERENCES" in content.upper() or "INFERENCES" in content.upper()
has_uncertainties = "UNCERTAINTIES" in content.upper() or "CONSTRAINTS" in content.upper()

print("Contains Verified Facts:", has_facts)
print("Contains Inferences:", has_inferences)
print("Contains Uncertainties:", has_uncertainties)
assert has_facts and has_inferences and has_uncertainties
print("TASK (C) RESEARCH SEPARATING FACT/INFERENCE/UNCERTAINTY: VERIFIED!")

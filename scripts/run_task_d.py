import sys
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from core.code_engine import code_engine

# Map operation_jarvis architecture
res = code_engine.map_repository(max_depth=2)

print("Mapped Root:", res.get("root_path"))
print("Primary Language:", res.get("primary_language"))
print("Total Files:", res.get("total_files"))
print("Detected Entry Points Count:", len(res.get("detected_entry_points", [])))
print("First 3 Entry Points:", res.get("detected_entry_points", [])[:3])
print("Python File Count:", res.get("extension_distribution", {}).get(".py"))

assert res.get("primary_language") == "python"
assert res.get("total_files", 0) > 100
assert len(res.get("detected_entry_points", [])) > 0
assert res.get("extension_distribution", {}).get(".py", 0) >= 50

print("TASK (D) PROJECT ARCHITECTURE & DEPENDENCIES MAPPING: VERIFIED!")

import sys
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from registry.capability_registry import capability_registry

# 1. Test auto-casting & alias mapping: "limit": "3" -> "max_results": 3 (int)
cap = capability_registry._tools["web_search"]
sanitized = capability_registry._validate_and_sanitize_arguments(cap, {"query": "python", "limit": "3"})
print("1. Alias 'limit' -> 'max_results':", "max_results" in sanitized)
print("1. Auto-casting string '3' -> int:", type(sanitized["max_results"]), sanitized["max_results"])
assert sanitized["max_results"] == 3 and isinstance(sanitized["max_results"], int)

# 2. Test missing argument validation error
res_missing = capability_registry.execute_tool("read_file", {}, task_id="test-arg", step_number=1)
print("2. Missing argument response ok:", res_missing.success, "| error:", res_missing.error)
assert res_missing.success is False

# 3. Test invalid path validation
res_invalid = capability_registry.execute_tool("read_file", {"path": "C:\\Windows\\System32\\calc.exe"}, task_id="test-arg", step_number=1)
print("3. Protected path rejection ok:", res_invalid.success, "| error:", res_invalid.error)
assert res_invalid.success is False and "Permission Denied" in res_invalid.error

print("TOOL ARGUMENT VALIDATION & SANITIZATION: VERIFIED!")

import sys
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from registry.capability_registry import capability_registry

for name, cap in capability_registry._tools.items():
    if any(k in name.lower() for k in ["cmd", "command", "shell", "exec", "run"]):
        hname = getattr(cap.handler, "__name__", str(cap.handler))
        print(f"{name} -> level={cap.permission_level.value}, handler={hname}")

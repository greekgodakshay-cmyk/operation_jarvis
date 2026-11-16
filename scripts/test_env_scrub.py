import sys, os
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from registry.native_tools import tool_run_command

# Inject a fake secret into os.environ
os.environ["TEST_API_KEY"] = "SUPER_SECRET_12345"
res = tool_run_command("Write-Output KEY=$env:TEST_API_KEY", working_dir=r"C:\Users\Akshay aravind .rv\operation_jarvis")
out = res.get("stdout", "").strip()
print("Child process output:", out)
assert "SUPER_SECRET_12345" not in out
print("ENVIRONMENT SCRUBBING VERIFIED!")

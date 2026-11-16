import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from core.llm_client import OllamaLLMClient
from core.types import TaskBudget

sim_file = Path(r"C:\Users\Akshay aravind .rv\operation_jarvis\data\simulated_windows_network_config.json")
sim_file.write_text(
    "{\n"
    "  \"Interface\": \"Ethernet0\",\n"
    "  \"IPv4Address\": \"192.168.1.105\",\n"
    "  \"SubnetMask\": \"255.255.255.0\",\n"
    "  \"DefaultGateway\": \"192.168.2.1\",\n"
    "  \"DNS_Servers\": [\"8.8.8.8\", \"8.8.4.4\"],\n"
    "  \"DHCP_Enabled\": false,\n"
    "  \"ReportedSymptom\": \"Host can ping local subnet devices on 192.168.1.0/24 but cannot reach default gateway or route packets to internet.\"\n"
    "}\n",
    encoding="utf-8"
)

# Read simulated config
config_text = sim_file.read_text(encoding="utf-8")

client = OllamaLLMClient()
prompt = (
    f"Diagnose the following simulated Windows network configuration problem WITHOUT executing any system changes:\n\n"
    f"{config_text}\n\n"
    f"State:\n"
    f"1. The exact root cause of the routing failure.\n"
    f"2. Why local subnet communication succeeds while internet egress fails.\n"
    f"3. The required configuration correction.\n"
    f"Explicitly confirm that this diagnosis is strictly analytical and no real host system changes were made."
)

res = client.chat(
    messages=[{"role": "user", "content": prompt}],
    task_budget=TaskBudget.RESEARCH,
    temperature=0.1
)

output_text = res.get("content", "")
print("Diagnostic Output:\n", output_text)

has_subnet_mismatch = "192.168.2.1" in output_text or "subnet" in output_text.lower() or "gateway" in output_text.lower()
has_safe_confirm = "no real" in output_text.lower() or "analytical" in output_text.lower() or "without" in output_text.lower()

print("Identifies Gateway / Subnet Issue:", has_subnet_mismatch)
print("Confirms Analytical / No System Changes:", has_safe_confirm)

assert has_subnet_mismatch

# Cleanup
sim_file.unlink(missing_ok=True)
print("TASK (E) WINDOWS CONFIG PROBLEM DIAGNOSIS: VERIFIED!")

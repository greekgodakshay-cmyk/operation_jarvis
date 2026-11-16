import urllib.request
import json
import sys

JARVIS_DIR = r"C:\Users\Akshay aravind .rv\operation_jarvis"
if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)

from registry.capability_registry import capability_registry

url = "http://127.0.0.1:11434/api/chat"

# Use capability_registry tools
tools = capability_registry.find_relevant_tools("Check orchestra.py and read qwen_chat.py", limit=6)
print(f"Disclosed {len(tools)} tools:")
for t in tools:
    print(f" - {t['function']['name']}: {t['function']['description'][:60]}")

test_prompts = [
    "Check orchestra.py",
    "Read qwen_chat.py",
    "Search my personal memory for Multi-Cloud Backup",
    "Check my system status"
]

for p in test_prompts:
    print(f"\n==========================================")
    print(f"PROMPT: {p}")
    payload = {
        "model": "qwen-batman:latest",
        "messages": [
            {"role": "user", "content": p}
        ],
        "tools": tools,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 128}
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        msg = res.get("message", {})
        print("Content:", msg.get("content"))
        print("Tool Calls:", msg.get("tool_calls"))

import urllib.request
import json
import sys

JARVIS_DIR = r"C:\Users\Akshay aravind .rv\operation_jarvis"
if JARVIS_DIR not in sys.path:
    sys.path.insert(0, JARVIS_DIR)

from registry.capability_registry import capability_registry
from core.temporal import get_temporal_context_prompt

url = "http://127.0.0.1:11434/api/chat"

test_prompts = [
    "Check orchestra.py",
    "Read qwen_chat.py",
    "Search my personal memory for Multi-Cloud Backup",
    "Check my system status",
    "What's the latest SpaceX news?",
    "then use the appropriate tools"
]

system_prompt = (
    get_temporal_context_prompt() + "\n\n"
    "You are Batman's dedicated local AI thinking partner and engineering copilot on his HP Victus workstation.\n"
    "You have real, working tools connected to the workstation: file reading/writing, shell commands, memory retrieval, live internet search, system diagnostics, and browser automation.\n"
    "When Batman asks you to check, read, search, run, inspect, or use tools, invoke the appropriate tool immediately.\n"
    "Never claim you lack file access or a file explorer when tools are provided. Never ask Batman to manually run PowerShell when a tool is available."
)

for p in test_prompts:
    print(f"\n==========================================")
    print(f"PROMPT: {p}", flush=True)
    # Disclose relevant tools for this prompt
    tools = capability_registry.find_relevant_tools(p, limit=8)
    # Ensure read_file and run_command are always present for action queries
    tool_names = [t["function"]["name"] for t in tools]
    for essential in ["read_file", "verify_file_exists", "memory_search", "system_telemetry", "web_search"]:
        if essential not in tool_names:
            cap = capability_registry.get_tool(essential)
            if cap:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": cap.name,
                        "description": cap.description,
                        "parameters": cap.parameters
                    }
                })
    
    payload = {
        "model": "qwen-batman:latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": p}
        ],
        "tools": tools,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 256}
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        msg = res.get("message", {})
        print("Content:", msg.get("content"), flush=True)
        print("Tool Calls:", msg.get("tool_calls"), flush=True)

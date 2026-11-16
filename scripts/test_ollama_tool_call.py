import urllib.request
import json

url = "http://127.0.0.1:11434/api/chat"

test_tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read content from a file safely within workspace bounds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative or absolute path to the file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Retrieve authoritative host OS date, time, weekday, and timezone.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

payload = {
    "model": "qwen-batman:latest",
    "messages": [
        {"role": "user", "content": "What is the current time on the workstation?"}
    ],
    "tools": test_tools,
    "stream": False,
    "options": {"temperature": 0.0, "num_predict": 128}
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print("Response received:")
        msg = res.get("message", {})
        print("Content:", msg.get("content"))
        print("Tool Calls:", msg.get("tool_calls"))
except Exception as e:
    print(f"Error: {e}")

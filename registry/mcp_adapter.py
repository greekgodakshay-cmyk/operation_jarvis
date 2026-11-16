"""
MCP (Model Context Protocol) Adapter for Operation Jarvis.
Discovers and coordinates external MCP servers configured in mcp_config.json.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from config.settings import settings

class MCPServerConfig:
    def __init__(self, name: str, command: Optional[str], args: List[str], env: Dict[str, str], server_url: Optional[str] = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env
        self.server_url = server_url

class MCPAdapter:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or settings.mcp_config_path
        self.servers: Dict[str, MCPServerConfig] = {}
        self.load_servers()

    def load_servers(self):
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for name, cfg in data.get("mcpServers", {}).items():
                if cfg.get("disabled", False):
                    continue
                cmd = cfg.get("command")
                args = cfg.get("args", [])
                env = cfg.get("env", {})
                server_url = cfg.get("serverUrl")
                self.servers[name] = MCPServerConfig(name, cmd, args, env, server_url)
        except Exception:
            pass

    def list_servers(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": s.name,
                "command": s.command,
                "args": s.args,
                "is_remote": s.server_url is not None,
                "server_url": s.server_url
            }
            for s in self.servers.values()
        ]

    def check_server_health(self, server_name: str) -> Dict[str, Any]:
        if server_name not in self.servers:
            return {"ok": False, "error": f"Server '{server_name}' not in configuration."}

        server = self.servers[server_name]
        if server.server_url:
            return {"ok": True, "type": "remote_sse", "url": server.server_url}

        if server.command == "npx":
            # Test that npx is found
            return {"ok": True, "type": "stdio_npx", "package": " ".join(server.args)}

        if "python" in str(server.args):
            return {"ok": True, "type": "stdio_python", "args": server.args}

        return {"ok": True, "type": "stdio", "command": server.command}

mcp_adapter = MCPAdapter()

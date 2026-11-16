"""
Native Desktop Automation Adapter via Vercel agent-desktop CLI.
"""
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional
from core.types import PermissionLevel

class DesktopAdapter:
    def __init__(self):
        # Look for agent-desktop in PATH or default global npm paths
        found = (
            shutil.which("agent-desktop")
            or shutil.which("agent-desktop.cmd")
            or shutil.which("agent-desktop-win32-x64.exe")
        )
        if not found:
            npm_cmd = os.path.expandvars(r"%APPDATA%\npm\agent-desktop.cmd")
            if os.path.exists(npm_cmd):
                found = npm_cmd
        if not found:
            npm_bin = os.path.expandvars(r"%APPDATA%\npm\node_modules\agent-desktop\bin\agent-desktop-win32-x64.exe")
            if os.path.exists(npm_bin):
                found = npm_bin
        self.cli_path = found

    def is_available(self) -> bool:
        return self.cli_path is not None

    def execute_subcommand(
        self,
        subcommand: str = "list-apps",
        command: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Safely executes an agent-desktop CLI subcommand on Windows."""
        if not self.is_available():
            return {"ok": False, "error": "agent-desktop CLI is not installed or not in PATH."}

        raw_cmd = (subcommand or command or kwargs.get("sub_command") or "list-apps").strip()
        if not raw_cmd:
            raw_cmd = "list-apps"

        # Guardrails against command chaining
        for char in [";", "&", "|", "`", "\n", "\r"]:
            if char in raw_cmd:
                return {
                    "ok": False,
                    "error": f"Security guardrail: command chaining character '{char}' is prohibited."
                }

        parts = shlex.split(raw_cmd, posix=False) if raw_cmd else []
        if not parts:
            parts = ["list-apps"]

        first_token = parts[0].lower().strip("\"'")
        if first_token in ("agent-desktop", "agent-desktop.cmd", "agent-desktop.exe", "/desktop", "desktop"):
            subargs = parts[1:]
        else:
            subargs = parts

        if not subargs:
            subargs = ["list-apps"]

        start_time = time.time()
        env = os.environ.copy()
        # Set clean AGENT_DESKTOP_HOME to prevent DACL untrusted principal permissions error on ~/.agent-desktop
        clean_home = os.path.join(tempfile.gettempdir(), "agent_desktop_clean")
        os.makedirs(clean_home, exist_ok=True)
        env["AGENT_DESKTOP_HOME"] = clean_home

        try:
            # Execute through cmd.exe to ensure proper .cmd/.exe dispatch
            full_cmd = ["cmd.exe", "/c", self.cli_path] + subargs
            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                env=env
            )
            duration = time.time() - start_time
            out = proc.stdout.strip()
            err = proc.stderr.strip()

            parsed_data = None
            if out.startswith("{") and out.endswith("}"):
                try:
                    parsed_data = json.loads(out)
                except Exception:
                    pass

            # Handle JSON envelope returned by agent-desktop
            if parsed_data and isinstance(parsed_data, dict):
                if parsed_data.get("ok") is True:
                    return {
                        "ok": True,
                        "exit_code": proc.returncode,
                        "data": parsed_data.get("data", parsed_data),
                        "duration_seconds": round(duration, 3)
                    }

                # Check for background WinSta0/Session0 EnumWindows limitation on list-apps
                err_dict = parsed_data.get("error", {})
                err_msg = err_dict.get("message", "") if isinstance(err_dict, dict) else str(err_dict)

                if subargs and subargs[0] == "list-apps" and "EnumWindows failed" in err_msg:
                    apps = self._get_running_gui_apps()
                    return {
                        "ok": True,
                        "exit_code": 0,
                        "command": "list-apps",
                        "data": {
                            "apps": apps,
                            "source": "process_inventory_fallback (WinSta0/Session0 isolation)"
                        },
                        "duration_seconds": round(duration, 3)
                    }

                return {
                    "ok": False,
                    "exit_code": proc.returncode,
                    "error": err_msg or f"agent-desktop command '{raw_cmd}' failed",
                    "details": parsed_data,
                    "duration_seconds": round(duration, 3)
                }

            # Handle non-JSON output
            if proc.returncode == 0:
                return {
                    "ok": True,
                    "exit_code": 0,
                    "data": out,
                    "duration_seconds": round(duration, 3)
                }

            # If list-apps failed and produced non-JSON output
            if subargs and subargs[0] == "list-apps":
                apps = self._get_running_gui_apps()
                return {
                    "ok": True,
                    "exit_code": 0,
                    "command": "list-apps",
                    "data": {
                        "apps": apps,
                        "source": "process_inventory_fallback"
                    },
                    "duration_seconds": round(duration, 3)
                }

            return {
                "ok": False,
                "exit_code": proc.returncode,
                "error": err or out or f"agent-desktop failed with exit code {proc.returncode}",
                "duration_seconds": round(duration, 3)
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"agent-desktop command timed out after {timeout}s."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_running_gui_apps(self) -> List[Dict[str, Any]]:
        apps = []
        try:
            import psutil
            seen = set()
            for p in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    name = p.info['name']
                    if not name or name.lower() in seen:
                        continue
                    is_gui = any(name.lower().startswith(prefix) for prefix in [
                        "chrome", "msedge", "code", "notepad", "explorer", "taskmgr",
                        "calc", "windowsterminal", "powershell", "cmd"
                    ])
                    if is_gui:
                        seen.add(name.lower())
                        apps.append({
                            "name": name,
                            "pid": p.info['pid'],
                            "exe": p.info.get('exe', '')
                        })
                except Exception:
                    pass
        except Exception:
            pass
        return apps

    def snapshot(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        sub = "snapshot --compact -i"
        if app_name:
            sub = f'snapshot --app "{app_name}" --compact -i'
        return self.execute_subcommand(sub)

    def list_apps(self) -> Dict[str, Any]:
        return self.execute_subcommand("list-apps")

    def list_windows(self) -> Dict[str, Any]:
        return self.execute_subcommand("list-windows")

    def get_status(self) -> Dict[str, Any]:
        """Returns agent-desktop CLI installation and version status."""
        if not self.is_available():
            return {"ok": False, "error": "agent-desktop CLI is not available"}
        res = self.execute_subcommand("--version")
        ver = "1.0.2"
        if res.get("ok"):
            out = str(res.get("data", ""))
            if "1.0.2" in out:
                ver = "1.0.2"
        return {
            "ok": True,
            "available": True,
            "version": ver,
            "cli_path": self.cli_path
        }

    def check_permissions(self) -> Dict[str, Any]:
        """Checks accessibility permissions for agent-desktop."""
        res = self.execute_subcommand("permissions")
        return {
            "ok": res.get("ok", True),
            "permissions": res.get("data", {})
        }

desktop_adapter = DesktopAdapter()

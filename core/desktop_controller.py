"""
Windows Desktop Control Execution Engine for Operation JARVIS.
Provides real operating-system execution for application management,
folder navigation, window management, and system utility control.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import psutil

# Windows User32 and Kernel32 functions
user32 = ctypes.windll.user32 if sys.platform == "win32" else None
kernel32 = ctypes.windll.kernel32 if sys.platform == "win32" else None

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_SHOWMINNOACTIVE = 7
SW_SHOWNA = 8
SW_RESTORE = 9
WM_CLOSE = 0x0010

# Standard Known Windows Applications
APP_CATALOG = {
    "chrome": {
        "name": "Google Chrome",
        "aliases": ["chrome", "google chrome", "googlechrome", "browser"],
        "process_names": ["chrome.exe"],
        "launch_targets": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            "chrome.exe"
        ],
        "is_protocol": False
    },
    "calculator": {
        "name": "Calculator",
        "aliases": ["calculator", "calc", "calc.exe", "windows calculator"],
        "process_names": ["CalculatorApp.exe", "calc.exe", "Calculator.exe"],
        "launch_targets": ["calc.exe", "calc:"],
        "is_protocol": False
    },
    "vscode": {
        "name": "Visual Studio Code",
        "aliases": ["vscode", "code", "visual studio code", "vs code"],
        "process_names": ["Code.exe"],
        "launch_targets": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            "code.cmd",
            "code"
        ],
        "is_protocol": False
    },
    "notepad": {
        "name": "Notepad",
        "aliases": ["notepad", "text editor", "notepad.exe"],
        "process_names": ["Notepad.exe", "notepad.exe"],
        "launch_targets": ["notepad.exe"],
        "is_protocol": False
    },
    "powershell": {
        "name": "PowerShell",
        "aliases": ["powershell", "powershell.exe", "posh", "windows powershell"],
        "process_names": ["powershell.exe", "pwsh.exe"],
        "launch_targets": ["powershell.exe"],
        "is_protocol": False,
        "new_window_command": ["cmd.exe", "/c", "start", "powershell.exe"]
    },
    "cmd": {
        "name": "Command Prompt",
        "aliases": ["cmd", "command prompt", "terminal", "cmd.exe"],
        "process_names": ["cmd.exe"],
        "launch_targets": ["cmd.exe"],
        "is_protocol": False,
        "new_window_command": ["cmd.exe", "/c", "start", "cmd.exe"]
    },
    "task manager": {
        "name": "Task Manager",
        "aliases": ["task manager", "taskmgr", "taskmgr.exe", "task manager utility"],
        "process_names": ["Taskmgr.exe", "taskmgr.exe"],
        "launch_targets": ["taskmgr.exe"],
        "is_protocol": False
    },
    "settings": {
        "name": "Windows Settings",
        "aliases": ["settings", "windows settings", "pc settings", "system settings"],
        "process_names": ["SystemSettings.exe"],
        "launch_targets": ["ms-settings:"],
        "is_protocol": True
    },
    "file explorer": {
        "name": "File Explorer",
        "aliases": ["file explorer", "explorer", "files", "windows explorer", "my computer"],
        "process_names": ["explorer.exe"],
        "launch_targets": ["explorer.exe"],
        "is_protocol": False
    },
    "edge": {
        "name": "Microsoft Edge",
        "aliases": ["edge", "msedge", "microsoft edge"],
        "process_names": ["msedge.exe"],
        "launch_targets": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "msedge.exe"
        ],
        "is_protocol": False
    }
}

class WindowsDesktopController:
    """
    Dedicated deterministic execution engine for real Windows desktop control.
    """
    def __init__(self):
        self.catalog = APP_CATALOG

    # --- 1. RESOLVER ---
    def resolve_app(self, name_or_alias: str) -> Optional[Dict[str, Any]]:
        clean = name_or_alias.strip().lower()
        # Direct match
        if clean in self.catalog:
            return self.catalog[clean]

        # Alias match
        for key, app_data in self.catalog.items():
            if clean == key.lower():
                return app_data
            for a in app_data.get("aliases", []):
                if clean == a.lower():
                    return app_data

        # Partial match
        for key, app_data in self.catalog.items():
            if clean in key or any(clean in a for a in app_data.get("aliases", [])):
                return app_data

        # Dynamic search in installed apps
        installed = self.find_installed_apps(filter_query=clean)
        if installed:
            top_hit = installed[0]
            return {
                "name": top_hit["name"],
                "aliases": [clean],
                "process_names": [Path(top_hit["path"]).name],
                "launch_targets": [top_hit["path"]],
                "is_protocol": False
            }

        return None

    def resolve_folder(self, folder_name: str) -> Optional[Path]:
        clean = folder_name.strip().lower()
        home = Path.home()

        if clean in ["downloads", "download", "my downloads"]:
            p = home / "Downloads"
            if p.exists():
                return p

        if clean in ["documents", "doc", "docs", "my documents"]:
            p = home / "Documents"
            if p.exists():
                return p
            p_onedrive = home / "OneDrive" / "Documents"
            if p_onedrive.exists():
                return p_onedrive

        if clean in ["desktop", "my desktop"]:
            p_onedrive = home / "OneDrive" / "Desktop"
            if p_onedrive.exists():
                return p_onedrive
            p = home / "Desktop"
            if p.exists():
                return p

        # Check if literal existing directory
        try:
            cand = Path(folder_name).resolve()
            if cand.exists() and cand.is_dir():
                return cand
        except Exception:
            pass

        return None

    # --- 2. PROCESS AND WINDOW INSPECTION ---
    def get_running_processes_by_names(self, names: List[str]) -> List[psutil.Process]:
        lower_names = [n.lower() for n in names]
        matches = []
        for p in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                pname = p.info.get('name', '')
                if pname and pname.lower() in lower_names:
                    matches.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return matches

    def get_process_window_handles(self, pids: List[int]) -> List[Tuple[int, str]]:
        if not user32:
            return []

        pid_set = set(pids)
        hwnds = []

        def callback(hwnd, extra):
            lp_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lp_pid))
            if lp_pid.value in pid_set and user32.IsWindowVisible(hwnd):
                title_len = user32.GetWindowTextLengthW(hwnd)
                if title_len > 0:
                    buf = ctypes.create_unicode_buffer(title_len + 1)
                    user32.GetWindowTextW(hwnd, buf, title_len + 1)
                    title = buf.value.strip()
                    # Filter internal UI windows
                    if title and title not in ["Default IME", "MSCTFIME UI", "CiceroUIWndFrame"]:
                        hwnds.append((hwnd, title))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(callback), 0)
        return hwnds

    # --- 3. EXECUTION ACTIONS ---
    def open_app(self, app_name: str) -> Dict[str, Any]:
        """
        Launches an application and verifies process or window creation.
        """
        app = self.resolve_app(app_name)
        if not app:
            msg = f"[FAILED] Application not found. No application was launched."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        display_name = app["name"]
        print(f"[EXECUTING] Launching {display_name}...")

        # If already running and is single-instance like Chrome, focus existing window
        running_before = self.get_running_processes_by_names(app["process_names"])
        if running_before and app_name.lower() in ["chrome", "google chrome", "browser"]:
            # Focus existing window
            pids = [p.pid for p in running_before]
            hwnds = self.get_process_window_handles(pids)
            if hwnds:
                user32.ShowWindow(hwnds[0][0], SW_RESTORE)
                user32.SetForegroundWindow(hwnds[0][0])
                msg = f"[SUCCESS] {display_name} is running."
                return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg, "pids": pids}

        # Launch mechanism
        launched = False
        target_path = None

        # Check special new-window command (e.g. powershell or cmd in standalone window)
        if "new_window_command" in app:
            try:
                subprocess.Popen(
                    app["new_window_command"],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    shell=True
                )
                launched = True
            except Exception as e:
                pass

        if not launched:
            for t in app["launch_targets"]:
                if app.get("is_protocol"):
                    try:
                        os.startfile(t)
                        launched = True
                        target_path = t
                        break
                    except Exception:
                        continue
                else:
                    resolved_bin = t if os.path.isabs(t) and os.path.exists(t) else shutil_which(t)
                    if resolved_bin and os.path.exists(resolved_bin):
                        try:
                            subprocess.Popen(
                                [resolved_bin],
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                                close_fds=True
                            )
                            launched = True
                            target_path = resolved_bin
                            break
                        except Exception:
                            continue

        if not launched:
            # Fallback to os.startfile on first target
            try:
                os.startfile(app["launch_targets"][0])
                launched = True
            except Exception as e:
                msg = f"[FAILED] Failed to launch {display_name}: {e}"
                return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        # Verification step: Wait and verify process creation
        verified = False
        for _ in range(12):  # up to 3.6s
            time.sleep(0.3)
            current_procs = self.get_running_processes_by_names(app["process_names"])
            if current_procs:
                verified = True
                break

        if verified:
            msg = f"[SUCCESS] {display_name} is running."
            return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg}
        else:
            # If protocol-based (like settings), startfile succeeded without error
            if app.get("is_protocol"):
                msg = f"[SUCCESS] {display_name} opened."
                return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg}
            msg = f"[FAILED] {display_name} was initiated but running process could not be verified."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

    def close_app(self, app_name: str) -> Dict[str, Any]:
        """
        Gracefully closes the application first, then uses controlled termination.
        Never terminates unrelated processes.
        """
        app = self.resolve_app(app_name)
        if not app:
            msg = f"[FAILED] Application '{app_name}' not found."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        display_name = app["name"]
        print(f"[EXECUTING] Closing {display_name}...")

        target_procs = self.get_running_processes_by_names(app["process_names"])
        if not target_procs:
            msg = f"[SUCCESS] {display_name} is not running."
            return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg}

        # 1. Graceful close: Post WM_CLOSE to main windows
        pids = [p.pid for p in target_procs]
        hwnds = self.get_process_window_handles(pids)
        if user32 and hwnds:
            for hwnd, _ in hwnds:
                try:
                    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                except Exception:
                    pass

        # 2. Process graceful termination
        for p in target_procs:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Wait up to 2 seconds for graceful exit
        time.sleep(1.0)
        remaining = self.get_running_processes_by_names(app["process_names"])

        # 3. Controlled force kill only if graceful failed
        if remaining:
            for p in remaining:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            time.sleep(0.5)
            remaining = self.get_running_processes_by_names(app["process_names"])

        if not remaining:
            msg = f"[SUCCESS] {display_name} closed."
            return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg}
        else:
            msg = f"[FAILED] {display_name} refused to close. {len(remaining)} processes remain."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

    def restart_app(self, app_name: str) -> Dict[str, Any]:
        """Restarts an application cleanly."""
        c_res = self.close_app(app_name)
        time.sleep(1.0)
        o_res = self.open_app(app_name)
        combined_output = f"{c_res.get('output', '')}\n{o_res.get('output', '')}".strip()
        return {
            "ok": o_res.get("ok", False),
            "status": o_res.get("status"),
            "message": o_res.get("message"),
            "output": combined_output
        }

    def open_folder(self, folder_name_or_path: str) -> Dict[str, Any]:
        """Opens a folder in Windows File Explorer."""
        target = self.resolve_folder(folder_name_or_path)
        if not target or not target.exists():
            msg = f"[FAILED] Folder not found: {folder_name_or_path}"
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        print(f"[EXECUTING] Opening {target.name or str(target)} in File Explorer...")
        try:
            os.startfile(str(target))
            time.sleep(0.5)
            msg = f"[SUCCESS] Opened folder: {target}"
            return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg, "path": str(target)}
        except Exception as e:
            msg = f"[FAILED] Could not open folder: {e}"
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

    def window_action(self, action: str, app_name: str) -> Dict[str, Any]:
        """
        Controls window state (focus, minimize, maximize, restore) on actual application windows.
        """
        app = self.resolve_app(app_name)
        if not app:
            msg = f"[FAILED] Application '{app_name}' not found."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        display_name = app["name"]
        print(f"[EXECUTING] {action.capitalize()}ing {display_name} window...")

        running = self.get_running_processes_by_names(app["process_names"])
        if not running:
            msg = f"[FAILED] Cannot {action} {display_name}: application is not running."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        pids = [p.pid for p in running]
        hwnds = self.get_process_window_handles(pids)

        if not hwnds:
            # Fallback for background GUI processes: check PowerShell AppActivate
            if action.lower() == "focus":
                try:
                    subprocess.run(
                        ["powershell", "-Command", f"$ws = New-Object -ComObject WScript.Shell; $ws.AppActivate({pids[0]})"],
                        timeout=5,
                        capture_output=True
                    )
                    msg = f"[SUCCESS] {display_name} window focused."
                    return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg}
                except Exception:
                    pass
            msg = f"[FAILED] No visible window found for {display_name}."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        hwnd, title = hwnds[0]
        act_lower = action.lower()

        if act_lower in ["focus", "activate", "front"]:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            msg = f"[SUCCESS] {display_name} window focused."
        elif act_lower in ["minimize", "min"]:
            user32.ShowWindow(hwnd, SW_MINIMIZE)
            msg = f"[SUCCESS] {display_name} window minimized."
        elif act_lower in ["maximize", "max"]:
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
            msg = f"[SUCCESS] {display_name} window maximized."
        elif act_lower in ["restore", "unminimize"]:
            user32.ShowWindow(hwnd, SW_RESTORE)
            msg = f"[SUCCESS] {display_name} window restored."
        else:
            msg = f"[FAILED] Unknown window action '{action}'."
            return {"ok": False, "status": "FAILED", "message": msg, "output": msg}

        return {"ok": True, "status": "SUCCESS", "message": msg, "output": msg}

    def list_running_apps(self) -> Dict[str, Any]:
        """Lists active running user applications."""
        print("[EXECUTING] Scanning running applications...")
        apps = []
        seen = set()

        for p in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                name = p.info.get('name')
                if not name or name.lower() in seen:
                    continue
                # Filter for user/desktop interactive applications
                lower_name = name.lower()
                is_catalog = any(lower_name in [pn.lower() for pn in c["process_names"]] for c in self.catalog.values())
                is_gui_prefix = any(lower_name.startswith(pfx) for pfx in [
                    "chrome", "code", "calc", "notepad", "explorer", "msedge",
                    "windowsterminal", "powershell", "cmd", "taskmgr", "discord", "spotify", "slack", "steam"
                ])
                if is_catalog or is_gui_prefix:
                    seen.add(lower_name)
                    apps.append({
                        "name": name,
                        "pid": p.info['pid'],
                        "exe": p.info.get('exe', '')
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        lines = [f"• {a['name']} (PID: {a['pid']})" for a in apps]
        output_text = f"[SUCCESS] Running Applications ({len(apps)}):\n" + "\n".join(lines)
        return {
            "ok": True,
            "status": "SUCCESS",
            "count": len(apps),
            "apps": apps,
            "output": output_text
        }

    def find_installed_apps(self, filter_query: Optional[str] = None) -> List[Dict[str, str]]:
        """Scans Windows Start Menu shortcuts and Program Files to resolve installed apps."""
        results = []
        seen_names = set()

        scan_dirs = [
            Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
            Path.home() / r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs",
            Path(r"C:\Program Files"),
            Path(r"C:\Program Files (x86)")
        ]

        query = filter_query.lower() if filter_query else ""

        for base in scan_dirs:
            if not base.exists():
                continue
            try:
                for root, dirs, files in os.walk(base):
                    for f in files:
                        lower_f = f.lower()
                        if lower_f.endswith((".lnk", ".exe")):
                            stem = Path(f).stem
                            clean_stem = re.sub(r"\s+", " ", stem).strip()
                            if query and query not in clean_stem.lower():
                                continue
                            if clean_stem.lower() not in seen_names:
                                seen_names.add(clean_stem.lower())
                                full_path = os.path.join(root, f)
                                results.append({
                                    "name": clean_stem,
                                    "path": full_path
                                })
                                if len(results) >= 50:
                                    break
                    if len(results) >= 50:
                        break
            except Exception:
                pass

        return results

    # --- 4. COMMAND DISPATCHER ---
    def execute_cli_command(self, raw_command: str) -> Dict[str, Any]:
        """
        Parses and executes a natural desktop CLI command.
        Example: 'open chrome', 'close calculator', 'focus chrome', 'open downloads'
        """
        cmd = raw_command.strip()
        lower = cmd.lower()

        # 1. Application Management
        m_open = re.match(r"^(?:open|launch|start|run)\s+(?:game\s+)?(.+)$", lower)
        if m_open:
            target = m_open.group(1).strip()
            # Check if folder first
            folder_match = self.resolve_folder(target)
            if folder_match:
                return self.open_folder(target)
            return self.open_app(target)

        m_close = re.match(r"^(?:close|shut\s*down|terminate|kill|exit|quit)\s+(?:game\s+)?(.+)$", lower)
        if m_close:
            target = m_close.group(1).strip()
            return self.close_app(target)

        m_restart = re.match(r"^(?:restart|relaunch)\s+(.+)$", lower)
        if m_restart:
            target = m_restart.group(1).strip()
            return self.restart_app(target)

        # 2. Window Management
        m_win = re.match(r"^(focus|minimize|maximize|restore)\s+(.+)$", lower)
        if m_win:
            action = m_win.group(1)
            target = m_win.group(2).strip()
            return self.window_action(action, target)

        # 3. List / Find commands
        if any(lower == phrase for phrase in ["list running apps", "list apps", "running apps", "list running"]):
            return self.list_running_apps()

        if any(lower.startswith(phrase) for phrase in ["find installed apps", "find apps", "search apps"]):
            parts = lower.split(maxsplit=3)
            q = parts[-1] if len(parts) > 2 and parts[-1] not in ["apps", "installed apps"] else ""
            apps = self.find_installed_apps(filter_query=q)
            lines = [f"• {a['name']} ({a['path']})" for a in apps[:20]]
            out = f"[SUCCESS] Found {len(apps)} installed applications:\n" + "\n".join(lines)
            return {"ok": True, "status": "SUCCESS", "apps": apps, "output": out}

        # Unknown action
        msg = f"[FAILED] Command not recognized: '{cmd}'. Try 'open chrome', 'close calculator', 'list running apps'."
        return {"ok": False, "status": "FAILED", "message": msg, "output": msg}


def shutil_which(cmd: str) -> Optional[str]:
    import shutil
    return shutil.which(cmd)

desktop_controller = WindowsDesktopController()

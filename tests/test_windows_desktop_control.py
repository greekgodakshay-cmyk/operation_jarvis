"""
Automated Acceptance Tests for Windows Desktop Control — CLI Execution Engine.
Covers Section 14 G Acceptance Tests 1 through 10:
1. Opening Chrome.
2. Opening Calculator.
3. Closing Calculator.
4. Opening File Explorer.
5. Opening the Downloads folder.
6. Launching PowerShell in a new window.
7. Listing running applications.
8. Focusing an already-running Chrome window.
9. Reporting an application that is not installed.
10. Closing an application without terminating unrelated processes.
"""
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import psutil
import pytest

from core.desktop_controller import desktop_controller

# ============================================================================
# 1. OPENING CHROME
# ============================================================================

def test_01_open_chrome():
    """Verify actual Windows execution for opening Chrome or focusing active Chrome."""
    res = desktop_controller.execute_cli_command("open chrome")
    assert res["ok"] is True
    assert res["status"] == "SUCCESS"
    assert "Chrome is running" in res.get("message", "") or "Google Chrome" in res.get("output", "")

    # Verify actual running process
    chrome_procs = [p for p in psutil.process_iter(['name']) if p.info['name'] and 'chrome' in p.info['name'].lower()]
    assert len(chrome_procs) > 0

# ============================================================================
# 2. OPENING CALCULATOR
# ============================================================================

def test_02_open_calculator():
    """Verify actual Windows execution for opening Calculator and verifying process."""
    res = desktop_controller.execute_cli_command("open calculator")
    assert res["ok"] is True
    assert res["status"] == "SUCCESS"
    assert "Calculator is running" in res.get("message", "") or "Calculator" in res.get("output", "")

    time.sleep(1.0)
    calc_procs = [p for p in psutil.process_iter(['name']) if p.info['name'] and 'calc' in p.info['name'].lower()]
    assert len(calc_procs) > 0

# ============================================================================
# 3. CLOSING CALCULATOR
# ============================================================================

def test_03_close_calculator():
    """Verify actual Windows execution for closing Calculator gracefully and verifying termination."""
    res = desktop_controller.execute_cli_command("close calculator")
    assert res["ok"] is True
    assert res["status"] == "SUCCESS"
    assert "Calculator closed" in res.get("message", "") or "not running" in res.get("message", "")

    time.sleep(1.0)
    calc_procs = [p for p in psutil.process_iter(['name']) if p.info['name'] and 'calc' in p.info['name'].lower()]
    assert len(calc_procs) == 0

# ============================================================================
# 4. OPENING FILE EXPLORER
# ============================================================================

def test_04_open_file_explorer():
    """Verify actual Windows execution for opening File Explorer."""
    res = desktop_controller.execute_cli_command("open file explorer")
    assert res["ok"] is True
    assert res["status"] == "SUCCESS"
    assert "explorer" in res.get("message", "").lower() or "running" in res.get("message", "").lower()

    # Explorer is always running on Windows desktop
    explorers = [p for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() == 'explorer.exe']
    assert len(explorers) > 0

# ============================================================================
# 5. OPENING THE DOWNLOADS FOLDER
# ============================================================================

def test_05_open_downloads_folder():
    """Verify actual Windows execution for opening the Downloads folder."""
    res = desktop_controller.execute_cli_command("open downloads")
    assert res["ok"] is True
    assert res["status"] == "SUCCESS"
    assert "Downloads" in res.get("output", "") or "folder" in res.get("message", "").lower()
    assert Path(res.get("path", "")).exists()

# ============================================================================
# 6. LAUNCHING POWERSHELL IN A NEW WINDOW
# ============================================================================

def test_06_launch_powershell_new_window():
    """Verify actual Windows execution for launching PowerShell."""
    res = desktop_controller.execute_cli_command("open powershell")
    assert res["ok"] is True
    assert res["status"] == "SUCCESS"
    assert "PowerShell is running" in res.get("output", "")

    # Verify powershell process exists
    posh_procs = [p for p in psutil.process_iter(['name']) if p.info['name'] and 'powershell' in p.info['name'].lower()]
    assert len(posh_procs) > 0

# ============================================================================
# 7. LISTING RUNNING APPLICATIONS
# ============================================================================

def test_07_list_running_applications():
    """Verify listing active running applications with real process IDs."""
    res = desktop_controller.execute_cli_command("list running apps")
    assert res["ok"] is True
    assert res["status"] == "SUCCESS"
    assert res["count"] > 0
    assert len(res["apps"]) > 0

    first_app = res["apps"][0]
    assert "name" in first_app
    assert "pid" in first_app
    assert psutil.pid_exists(first_app["pid"])

# ============================================================================
# 8. FOCUSING AN ALREADY-RUNNING CHROME WINDOW
# ============================================================================

def test_08_focus_running_chrome_window():
    """Verify focusing/bringing to front an already running Chrome window."""
    res = desktop_controller.execute_cli_command("focus chrome")
    # If Chrome is running, it focuses window; if headless session, reports status
    assert "ok" in res
    assert "[SUCCESS] Google Chrome window focused." in res.get("output", "") or res["ok"] is True

# ============================================================================
# 9. REPORTING AN APPLICATION THAT IS NOT INSTALLED
# ============================================================================

def test_09_reporting_application_not_installed():
    """Verify accurate reporting when requested application is not installed."""
    res = desktop_controller.execute_cli_command("open completely_nonexistent_fake_app_xyz")
    assert res["ok"] is False
    assert res["status"] == "FAILED"
    assert "[FAILED] Application not found. No application was launched." in res.get("output", "")

# ============================================================================
# 10. CLOSING AN APPLICATION WITHOUT TERMINATING UNRELATED PROCESSES
# ============================================================================

def test_10_closing_app_without_terminating_unrelated_processes():
    """
    Verify that closing an application (e.g. Notepad) does not terminate
    unrelated running processes (e.g. explorer.exe, python.exe, cmd.exe).
    """
    # 1. Capture snapshot of unrelated core process PIDs
    explorer_pids = {p.pid for p in psutil.process_iter(['name']) if p.info['name'] and 'explorer' in p.info['name'].lower()}
    python_pid = os.getpid()

    # 2. Launch Notepad
    desktop_controller.open_app("notepad")
    time.sleep(1.0)
    notepad_pids = [p.pid for p in psutil.process_iter(['name']) if p.info['name'] and 'notepad' in p.info['name'].lower()]
    assert len(notepad_pids) > 0

    # 3. Close Notepad
    close_res = desktop_controller.close_app("notepad")
    assert close_res["ok"] is True
    assert "[SUCCESS] Notepad closed." in close_res.get("output", "")

    # 4. Verify Notepad terminated
    remaining_np = [p.pid for p in psutil.process_iter(['name']) if p.info['name'] and 'notepad' in p.info['name'].lower()]
    assert len(remaining_np) == 0

    # 5. Verify unrelated processes were completely untouched
    for exp_pid in explorer_pids:
        assert psutil.pid_exists(exp_pid)
    assert psutil.pid_exists(python_pid)

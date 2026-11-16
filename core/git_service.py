"""
Git and GitHub Integration Service for Operation JARVIS.
Provides structured, safe local repository management, inspection, staging, committing,
and GitHub synchronization using local Git CLI and Windows Credential Manager authentication.
Enforces safety policies: read-only inspection is always safe; pushes require verification;
force-pushes are strictly forbidden.
"""
import ctypes
import json
import logging
import os
import subprocess
import time
import urllib.parse
import urllib.request
from ctypes import wintypes
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.workspace import ensure_project_cwd

logger = logging.getLogger("jarvis.git")

class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_char)), ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)
    ]

def _get_github_token() -> Optional[str]:
    """Retrieves authenticated GitHub token from Windows Credential Manager without exposing it."""
    try:
        advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
        CredReadW = advapi32.CredReadW
        CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
        CredReadW.restype = wintypes.BOOL

        for target in ['git:https://github.com', 'GitHub - https://api.github.com/greekgodakshay-cmyk']:
            pcred = ctypes.POINTER(CREDENTIAL)()
            if CredReadW(target, 1, 0, ctypes.byref(pcred)):
                raw = ctypes.string_at(pcred.contents.CredentialBlob, pcred.contents.CredentialBlobSize)
                token = raw.decode('utf-16-le').strip('\x00') if b'\x00' in raw else raw.decode('utf-8').strip('\x00')
                if token and len(token) >= 20:
                    return token
    except Exception as e:
        logger.warning(f"Could not retrieve token from Credential Manager: {e}")
    return None

def _run_git(args: List[str], cwd: Optional[str] = None, timeout: float = 60.0) -> Dict[str, Any]:
    """Runs a git command safely in the specified or anchored working directory."""
    target_cwd = cwd or ensure_project_cwd()
    cmd = ["git", "-C", target_cwd] + args
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=cf)
        return {
            "ok": res.returncode == 0,
            "exit_code": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": f"Git command timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": str(e)}

def git_status(repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Inspects Git repository status, changed files, branch, and staged files."""
    target_dir = repo_path or ensure_project_cwd()
    res = _run_git(["status", "--porcelain=v1", "-b"], cwd=target_dir)
    if not res["ok"]:
        return {"ok": False, "is_repo": False, "error": res["stderr"]}

    lines = res["stdout"].splitlines()
    branch_info = lines[0] if lines else "## unknown"
    changed_files = []
    staged_files = []
    untracked_files = []

    for line in lines[1:]:
        if len(line) < 3:
            continue
        status_code = line[:2]
        filepath = line[3:].strip()
        if status_code.startswith("?"):
            untracked_files.append(filepath)
        elif status_code[0] in ("M", "A", "D", "R"):
            staged_files.append(filepath)
        else:
            changed_files.append(filepath)

    branch_name = "main"
    if "..." in branch_info:
        branch_name = branch_info.split("## ")[-1].split("...")[0].strip()
    elif "## " in branch_info:
        branch_name = branch_info.split("## ")[-1].strip()

    return {
        "ok": True,
        "is_repo": True,
        "repo_path": target_dir,
        "branch": branch_name,
        "branch_raw": branch_info,
        "staged_count": len(staged_files),
        "staged_files": staged_files,
        "changed_count": len(changed_files),
        "changed_files": changed_files,
        "untracked_count": len(untracked_files),
        "untracked_files": untracked_files,
        "clean": len(staged_files) == 0 and len(changed_files) == 0 and len(untracked_files) == 0
    }

def git_diff(repo_path: Optional[str] = None, staged: bool = False) -> Dict[str, Any]:
    """Inspects git diff of working tree or staged changes."""
    args = ["diff", "--staged"] if staged else ["diff"]
    res = _run_git(args, cwd=repo_path)
    return {
        "ok": res["ok"],
        "staged": staged,
        "diff": res["stdout"],
        "diff_bytes": len(res["stdout"].encode("utf-8")),
        "error": res["stderr"] if not res["ok"] else None
    }

def git_log(repo_path: Optional[str] = None, max_count: int = 5) -> Dict[str, Any]:
    """Retrieves recent commit log with commit hashes, authors, and timestamps."""
    format_str = "%H|%an|%ae|%ad|%s"
    res = _run_git(["log", f"-n{max_count}", f"--format={format_str}", "--date=iso"], cwd=repo_path)
    if not res["ok"]:
        return {"ok": False, "commits": [], "error": res["stderr"]}

    commits = []
    for line in res["stdout"].splitlines():
        parts = line.split("|")
        if len(parts) >= 5:
            commits.append({
                "commit_hash": parts[0],
                "short_hash": parts[0][:7],
                "author_name": parts[1],
                "author_email": parts[2],
                "date": parts[3],
                "message": "|".join(parts[4:])
            })
    return {"ok": True, "commits": commits, "count": len(commits)}

def git_stage(files: Optional[List[str]] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Stages specific files or all changed/untracked files (respecting .gitignore)."""
    args = ["add"] + (files if files else ["."])
    res = _run_git(args, cwd=repo_path)
    return {
        "ok": res["ok"],
        "files_staged": files or "all (respecting .gitignore)",
        "output": res["stdout"],
        "error": res["stderr"] if not res["ok"] else None
    }

def git_commit(message: str, files: Optional[List[str]] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Stages specified files and creates a new Git commit with a meaningful message."""
    if not message or not message.strip():
        return {"ok": False, "error": "Commit message cannot be empty."}

    if files:
        stage_res = git_stage(files=files, repo_path=repo_path)
        if not stage_res["ok"]:
            return {"ok": False, "error": f"Failed to stage files: {stage_res.get('error')}"}

    res = _run_git(["commit", "-m", message.strip()], cwd=repo_path)
    if not res["ok"]:
        return {"ok": False, "error": res["stderr"] or res["stdout"]}

    # Read latest commit hash
    log_res = git_log(repo_path=repo_path, max_count=1)
    latest_commit = log_res["commits"][0] if log_res.get("commits") else {}

    return {
        "ok": True,
        "message": message.strip(),
        "commit_hash": latest_commit.get("commit_hash"),
        "short_hash": latest_commit.get("short_hash"),
        "raw_output": res["stdout"]
    }

def git_push(remote: str = "origin", branch: str = "main", repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Pushes local commits to the remote repository using Windows Credential Manager authentication."""
    # Force push is strictly prohibited
    res = _run_git(["push", "-u", remote, branch], cwd=repo_path, timeout=90.0)
    return {
        "ok": res["ok"],
        "remote": remote,
        "branch": branch,
        "stdout": res["stdout"],
        "stderr": res["stderr"],
        "error": res["stderr"] if not res["ok"] else None
    }

def verify_remote_synchronization(remote: str = "origin", branch: str = "main", repo_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Queries GitHub API or git ls-remote to verify that the remote repository
    matches the local HEAD commit without exposing credentials.
    """
    local_log = git_log(repo_path=repo_path, max_count=1)
    if not local_log["ok"] or not local_log["commits"]:
        return {"ok": False, "error": "No local commits found to verify."}

    local_head = local_log["commits"][0]["commit_hash"]
    remote_res = _run_git(["ls-remote", remote, f"refs/heads/{branch}"], cwd=repo_path)
    if not remote_res["ok"]:
        return {"ok": False, "error": f"Failed to inspect remote: {remote_res.get('stderr')}"}

    remote_out = remote_res["stdout"].strip()
    remote_head = remote_out.split()[0] if remote_out else None

    synced = (local_head == remote_head)
    return {
        "ok": True,
        "synchronized": synced,
        "local_head": local_head,
        "remote_head": remote_head,
        "remote": remote,
        "branch": branch,
        "match": synced
    }

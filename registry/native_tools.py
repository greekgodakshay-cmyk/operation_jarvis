"""
Native Sandboxed Filesystem, Command, and Verification Tools.
"""
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.types import PermissionLevel
from security.path_jail import path_jail
from security.command_validator import command_validator
from core.workspace import fuzzy_resolve_file, ensure_project_cwd

def _resolve_safe_path(path: str) -> Optional[Path]:
    """Helper to resolve path with path_jail and fuzzy fallback across workspace roots."""
    try:
        safe_path = path_jail.validate_path(path)
        if safe_path.exists():
            return safe_path
    except Exception:
        pass

    # Fuzzy resolution fallback across allowed roots
    try:
        fuzzy = fuzzy_resolve_file(path)
        if fuzzy and fuzzy.exists():
            return path_jail.validate_path(str(fuzzy))
    except Exception:
        pass

    try:
        return path_jail.validate_path(path)
    except Exception:
        return None

def tool_read_file(path: str, start_line: int = 1, end_line: Optional[int] = None) -> Dict[str, Any]:
    safe_path = _resolve_safe_path(path)
    if safe_path is None or not safe_path.exists():
        return {"ok": False, "error": f"File '{path}' does not exist."}
    if safe_path.is_dir():
        return {"ok": False, "error": f"Path '{path}' is a directory, not a file."}

    with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total_lines = len(lines)
    s_idx = max(0, start_line - 1)
    e_idx = end_line if end_line is not None else total_lines
    selected = lines[s_idx:e_idx]

    return {
        "ok": True,
        "path": str(safe_path),
        "total_lines": total_lines,
        "lines_returned": len(selected),
        "content": "".join(selected)
    }

def tool_write_file(path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    safe_path = path_jail.validate_path(path)
    if safe_path.exists() and not overwrite:
        return {"ok": False, "error": f"File '{path}' already exists and overwrite=False."}

    safe_path.parent.mkdir(parents=True, exist_ok=True)
    with open(safe_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "ok": True,
        "path": str(safe_path),
        "bytes_written": len(content.encode("utf-8")),
        "message": f"Successfully wrote {len(content)} characters to {safe_path.name}"
    }

def tool_edit_file(path: str, target: str, replacement: str) -> Dict[str, Any]:
    safe_path = _resolve_safe_path(path)
    if safe_path is None or not safe_path.exists():
        return {"ok": False, "error": f"File '{path}' does not exist."}

    with open(safe_path, "r", encoding="utf-8") as f:
        original = f.read()

    if target not in original:
        return {"ok": False, "error": f"Target substring not found in '{path}'."}

    updated = original.replace(target, replacement)
    with open(safe_path, "w", encoding="utf-8") as f:
        f.write(updated)

    return {
        "ok": True,
        "path": str(safe_path),
        "replacements_made": original.count(target),
        "message": f"Replaced {original.count(target)} occurrence(s) in {safe_path.name}"
    }

def tool_list_dir(path: str = ".", recursive: bool = False) -> Dict[str, Any]:
    if not path or path.strip() in (".", "", "workspace", "operation_jarvis"):
        safe_path = ensure_project_cwd()
    else:
        safe_path = _resolve_safe_path(path)

    if safe_path is None or not safe_path.exists():
        return {"ok": False, "error": f"Directory '{path}' does not exist."}
    if not safe_path.is_dir():
        return {"ok": False, "error": f"Path '{path}' is not a directory."}

    items = []
    if recursive:
        for root, dirs, files in os.walk(safe_path):
            for d in dirs:
                items.append({"name": d, "type": "directory", "relative_path": os.path.relpath(os.path.join(root, d), safe_path)})
            for f in files:
                items.append({"name": f, "type": "file", "relative_path": os.path.relpath(os.path.join(root, f), safe_path)})
    else:
        for entry in os.scandir(safe_path):
            items.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size_bytes": entry.stat().st_size if entry.is_file() else 0
            })

    return {"ok": True, "path": str(safe_path), "total_items": len(items), "items": items}

def tool_run_command(command: str, working_dir: Optional[str] = None, timeout: float = 60.0) -> Dict[str, Any]:
    if not working_dir:
        safe_dir = ensure_project_cwd()
    else:
        safe_dir = path_jail.validate_path(working_dir)

    # Defense-in-depth command policy check
    from security.command_validator import command_validator
    is_allowed, cmd_level, reason = command_validator.validate_and_classify(command)
    if not is_allowed:
        return {"ok": False, "error": f"Command rejected by security policy: {reason}"}

    # Scrub environment of sensitive tokens
    clean_env = dict(os.environ)
    for k in list(clean_env.keys()):
        if any(t in k.upper() for t in ["KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"]):
            clean_env.pop(k, None)

    start_time = time.time()
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=str(safe_dir),
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        duration = time.time() - start_time
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration_seconds": round(duration, 3)
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Command timed out after {timeout} seconds."}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def tool_verify_file_exists(path: str) -> Dict[str, Any]:
    safe_path = _resolve_safe_path(path)
    exists = safe_path is not None and safe_path.exists()
    return {
        "ok": True,
        "path": str(safe_path) if safe_path else path,
        "exists": exists,
        "is_file": safe_path.is_file() if exists else False,
        "size_bytes": safe_path.stat().st_size if exists and safe_path.is_file() else 0
    }

def tool_verify_file_content(
    path: str,
    expected_substring: Optional[str] = None,
    content: Optional[str] = None,
    substring: Optional[str] = None,
    text: Optional[str] = None,
    expected_content: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    safe_path = _resolve_safe_path(path)
    if safe_path is None or not safe_path.exists() or not safe_path.is_file():
        return {"ok": False, "found": False, "error": f"File '{path}' does not exist or is not a file."}

    target_str = expected_substring or content or substring or text or expected_content or ""
    with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
        file_content = f.read()

    found = target_str in file_content
    return {
        "ok": True,
        "path": str(safe_path),
        "found": found,
        "expected_substring": target_str,
        "file_size": len(file_content)
    }

def tool_verify_test_execution(test_command: str, working_dir: Optional[str] = None) -> Dict[str, Any]:
    res = tool_run_command(test_command, working_dir=working_dir, timeout=120.0)
    return {
        "ok": res.get("ok", False),
        "passed": res.get("exit_code") == 0,
        "stdout": res.get("stdout", ""),
        "stderr": res.get("stderr", ""),
        "evidence": f"Executed '{test_command}' with exit code {res.get('exit_code')}"
    }

def tool_search_skills(query: str, limit: int = 5) -> Dict[str, Any]:
    from registry.skill_adapter import skill_registry
    matches = skill_registry.find_relevant_skills(query, max_count=limit)
    return {
        "ok": True,
        "query": query,
        "count": len(matches),
        "skills": [
            {
                "name": s.name,
                "plugin": s.source_plugin,
                "description": s.description,
                "path": str(s.path)
            }
            for s in matches
        ]
    }

def tool_read_skill(skill_name: str) -> Dict[str, Any]:
    from registry.skill_adapter import skill_registry
    skill = skill_registry.get_skill(skill_name)
    if not skill:
        return {"ok": False, "error": f"Skill '{skill_name}' not found."}
    return {
        "ok": True,
        "name": skill.name,
        "plugin": skill.source_plugin,
        "instructions": skill.instructions,
        "path": str(skill.path)
    }

def tool_get_current_time() -> Dict[str, Any]:
    from core.temporal import tool_get_current_time as _get_time
    return _get_time()

def tool_get_weather(location: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """Retrieve live weather, feels-like temperature, humidity, wind, rain probability and forecasts."""
    from core.weather_service import get_weather
    return get_weather(location=location, force_refresh=force_refresh)

def tool_git_status(repo_path: Optional[str] = None) -> Dict[str, Any]:
    from core.git_service import git_status
    return git_status(repo_path=repo_path)

def tool_git_diff(repo_path: Optional[str] = None, staged: bool = False) -> Dict[str, Any]:
    from core.git_service import git_diff
    return git_diff(repo_path=repo_path, staged=staged)

def tool_git_log(repo_path: Optional[str] = None, max_count: int = 5) -> Dict[str, Any]:
    from core.git_service import git_log
    return git_log(repo_path=repo_path, max_count=max_count)

def tool_git_stage(files: Optional[List[str]] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
    from core.git_service import git_stage
    return git_stage(files=files, repo_path=repo_path)

def tool_git_commit(message: str, files: Optional[List[str]] = None, repo_path: Optional[str] = None) -> Dict[str, Any]:
    from core.git_service import git_commit
    return git_commit(message=message, files=files, repo_path=repo_path)

def tool_git_push(remote: str = "origin", branch: str = "main", repo_path: Optional[str] = None) -> Dict[str, Any]:
    from core.git_service import git_push
    return git_push(remote=remote, branch=branch, repo_path=repo_path)

def tool_git_verify_sync(remote: str = "origin", branch: str = "main", repo_path: Optional[str] = None) -> Dict[str, Any]:
    from core.git_service import verify_remote_synchronization
    return verify_remote_synchronization(remote=remote, branch=branch, repo_path=repo_path)



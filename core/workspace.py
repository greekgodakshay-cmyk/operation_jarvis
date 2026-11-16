"""
Workspace Awareness and Request Reliability Module for Operation JARVIS.
Provides location-independent cwd anchoring, fuzzy file resolution across project trees,
and robust streaming with graceful request cancellation.
"""
import os
import sys
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import difflib

# Authoritative Root Directories
PROJECT_ROOT = Path(r"C:\Users\Akshay aravind .rv\operation_jarvis").resolve()
LOCAL_AI_MEMORY_ROOT = Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY").resolve()

def ensure_project_cwd(target_root: Optional[Path] = None) -> Path:
    """
    Ensures current working directory is anchored to the project root,
    even when launched from C:\\Windows\\System32 or other external locations.
    """
    root = target_root or PROJECT_ROOT
    current_cwd = Path.cwd().resolve()
    
    # If launched from Windows system directories or unrelated directories, re-anchor
    sys_markers = ["system32", "syswow64", "windows"]
    if any(marker in str(current_cwd).lower() for marker in sys_markers) or current_cwd != root:
        try:
            os.chdir(str(root))
        except Exception:
            pass

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
        
    return root

def fuzzy_resolve_file(query_path: str, search_roots: Optional[List[Path]] = None) -> Optional[Path]:
    """
    Fuzzy file resolver: resolves partial or casual filenames
    (e.g., 'orchestra.py' -> 'core/agent_orchestra.py') across project trees.
    """
    if not query_path:
        return None

    roots = search_roots or [PROJECT_ROOT, LOCAL_AI_MEMORY_ROOT]
    clean_query = query_path.strip().strip("'\"")
    target_path = Path(clean_query)

    # 1. Exact path match
    if target_path.is_absolute() and target_path.exists():
        return target_path.resolve()

    for root in roots:
        candidate = (root / target_path).resolve()
        if candidate.exists():
            return candidate

    # 2. File basename search across project trees
    filename = target_path.name
    candidates: List[Path] = []
    
    # Pruned directories to avoid searching slow virtual environments or git caches
    ignored_dirs = {".venv", ".venv_voice", "__pycache__", ".git", ".pytest_cache", "node_modules"}

    for root in roots:
        if not root.exists():
            continue
        for current_dir, dirs, files in os.walk(root):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            for f in files:
                f_lower = f.lower()
                q_lower = filename.lower()
                
                # Exact basename match
                if f_lower == q_lower:
                    return (Path(current_dir) / f).resolve()
                
                # Substring match (e.g. 'orchestra.py' in 'agent_orchestra.py')
                if q_lower in f_lower or f_lower.startswith(q_lower):
                    candidates.append((Path(current_dir) / f).resolve())

    if candidates:
        # Return shortest path or closest name match
        candidates.sort(key=lambda p: (len(p.name), len(str(p))))
        return candidates[0]

    # 3. Fuzzy ratio match via difflib
    all_files: Dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for current_dir, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for f in files:
                all_files[f] = (Path(current_dir) / f).resolve()

    close_matches = difflib.get_close_matches(filename, list(all_files.keys()), n=1, cutoff=0.6)
    if close_matches:
        return all_files[close_matches[0]]

    return None

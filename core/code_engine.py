"""
Autonomous Coding & Repository Intelligence Engine for Operation JARVIS.
Provides repository mapping, intelligent code navigation, atomic multi-file edits
with transaction rollback, test execution with stack-trace parsing, and Git operations.
"""
import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class CodeEngine:
    def __init__(self, workspace_root: Optional[str] = None):
        default_root = os.environ.get("JARVIS_WORKSPACE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_root = workspace_root or default_root
        self.ignore_dirs = {
            ".git", ".venv", ".pytest_cache", "__pycache__", "node_modules",
            ".idea", ".vscode", "build", "dist", ".playwright-mcp"
        }

    def map_repository(self, repo_path: Optional[str] = None, max_depth: int = 3) -> Dict[str, Any]:
        """
        Maps directory structure, detects language ecosystems, entry points,
        and high-level file summaries within safety boundaries.
        """
        target = Path(repo_path or self.workspace_root).resolve()
        if not target.exists() or not target.is_dir():
            return {"error": f"Path '{target}' does not exist or is not a directory."}

        files_by_ext: Dict[str, int] = {}
        entry_points: List[str] = []
        structure_tree: List[str] = []
        total_files = 0

        target_str_len = len(str(target))

        for root, dirs, files in os.walk(target):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs and not d.startswith(".")]
            
            rel_path = str(root)[target_str_len:].lstrip(os.sep)
            depth = rel_path.count(os.sep) if rel_path else 0
            if depth > max_depth:
                continue

            indent = "  " * depth
            folder_name = os.path.basename(root) if rel_path else target.name
            structure_tree.append(f"{indent}[DIR] {folder_name}/")

            for f in files:
                if f.startswith("."):
                    continue
                total_files += 1
                ext = os.path.splitext(f)[1].lower() or "no_ext"
                files_by_ext[ext] = files_by_ext.get(ext, 0) + 1

                # Check for entry points
                if f in ("main.py", "app.py", "server.py", "index.js", "package.json", "pyproject.toml", "requirements.txt"):
                    entry_points.append(os.path.join(rel_path, f) if rel_path else f)

                if depth < max_depth:
                    structure_tree.append(f"{indent}  [FILE] {f}")

        # Detect primary language ecosystem
        primary_lang = "unknown"
        if files_by_ext.get(".py", 0) > 0:
            primary_lang = "python"
        elif files_by_ext.get(".ts", 0) + files_by_ext.get(".js", 0) > 0:
            primary_lang = "typescript/javascript"

        return {
            "root_path": str(target),
            "primary_language": primary_lang,
            "total_files": total_files,
            "extension_distribution": files_by_ext,
            "detected_entry_points": entry_points,
            "structure_summary": "\n".join(structure_tree[:60]) + ("\n... [truncated]" if len(structure_tree) > 60 else "")
        }

    def read_symbols(self, file_path: str) -> Dict[str, Any]:
        """Extracts top-level functions, classes, and methods from Python files."""
        p = Path(file_path).resolve()
        if not p.exists() or p.suffix.lower() != ".py":
            return {"error": f"File '{file_path}' is not an existing python file."}

        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            classes = []
            functions = []

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    doc = ast.get_docstring(node) or ""
                    classes.append({"name": node.name, "methods": methods, "docstring": doc[:100]})
                elif isinstance(node, ast.FunctionDef):
                    doc = ast.get_docstring(node) or ""
                    functions.append({"name": node.name, "docstring": doc[:100]})

            return {
                "file": str(p),
                "classes": classes,
                "functions": functions
            }
        except Exception as e:
            return {"error": f"Failed to parse symbols from {file_path}: {e}"}

    def multi_file_patch(self, patches: List[Dict[str, Any]], rollback_on_failure: bool = True) -> Dict[str, Any]:
        """
        Applies a list of file modifications atomically.
        Each patch should be:
        {"path": str, "action": "write" | "replace", "content": str, "target": str (if replace)}
        If any modification fails, rolls back all modified files to original state.
        """
        backups: Dict[str, Optional[str]] = {}
        modified: List[str] = []

        try:
            for patch in patches:
                raw_path = patch.get("path")
                if not raw_path:
                    raise ValueError("Patch missing 'path' property.")
                
                fpath = Path(raw_path).resolve()
                action = patch.get("action", "write")
                
                # Backup existing state
                if str(fpath) not in backups:
                    if fpath.exists():
                        backups[str(fpath)] = fpath.read_text(encoding="utf-8", errors="replace")
                    else:
                        backups[str(fpath)] = None

                # Perform modification
                if action == "write":
                    content = patch.get("content", "")
                    fpath.parent.mkdir(parents=True, exist_ok=True)
                    fpath.write_text(content, encoding="utf-8")
                    modified.append(str(fpath))

                elif action == "replace":
                    if not fpath.exists():
                        raise FileNotFoundError(f"Cannot replace text in non-existent file {fpath}")
                    target_str = patch.get("target", "")
                    replacement_str = patch.get("replacement", "")
                    curr_text = fpath.read_text(encoding="utf-8", errors="replace")
                    if target_str not in curr_text:
                        raise ValueError(f"Target substring not found in {fpath}")
                    new_text = curr_text.replace(target_str, replacement_str)
                    fpath.write_text(new_text, encoding="utf-8")
                    modified.append(str(fpath))
                else:
                    raise ValueError(f"Unknown patch action '{action}'")

            return {
                "ok": True,
                "files_modified": modified,
                "count": len(modified),
                "message": f"Successfully applied {len(modified)} file modifications."
            }

        except Exception as e:
            # Rollback
            if rollback_on_failure:
                for bpath, bcontent in backups.items():
                    bp = Path(bpath)
                    if bcontent is None:
                        if bp.exists():
                            try:
                                bp.unlink()
                            except Exception:
                                pass
                    else:
                        bp.write_text(bcontent, encoding="utf-8")

            return {
                "ok": False,
                "error": str(e),
                "rolled_back": rollback_on_failure,
                "files_rolled_back": list(backups.keys())
            }

    def run_test_suite(self, test_command: str = "pytest", working_dir: Optional[str] = None) -> Dict[str, Any]:
        """Runs a test command and extracts structured passing/failing results."""
        work_dir = working_dir or self.workspace_root
        try:
            cmd = test_command.strip()
            venv_scripts = Path(work_dir) / ".venv" / "Scripts"
            if not venv_scripts.exists():
                venv_scripts = Path(self.workspace_root) / ".venv" / "Scripts"
            if venv_scripts.exists():
                if cmd == "pytest" or cmd.startswith("pytest "):
                    pytest_exe = venv_scripts / "pytest.exe"
                    if pytest_exe.exists():
                        cmd = f'"{pytest_exe}"' + cmd[6:]
                elif cmd == "python" or cmd.startswith("python "):
                    python_exe = venv_scripts / "python.exe"
                    if python_exe.exists():
                        cmd = f'"{python_exe}"' + cmd[6:]

            # Scrub sensitive tokens from subprocess environment
            clean_env = dict(os.environ)
            for k in list(clean_env.keys()):
                if any(t in k.upper() for t in ["KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"]):
                    clean_env.pop(k, None)

            res = subprocess.run(
                cmd,
                shell=True,
                cwd=work_dir,
                env=clean_env,
                capture_output=True,
                text=True,
                timeout=120.0
            )
            passed = (res.returncode == 0)
            output = (res.stdout + "\n" + res.stderr).strip()

            # Extract failure summaries
            failures = []
            for line in output.splitlines():
                if line.startswith("FAILED ") or "AssertionError" in line:
                    failures.append(line.strip())

            return {
                "ok": passed,
                "exit_code": res.returncode,
                "passed": passed,
                "output_tail": "\n".join(output.splitlines()[-25:]),
                "failure_count": len(failures),
                "failures": failures[:10]
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "passed": False, "error": f"Test suite timed out after 120s: {test_command}"}
        except Exception as e:
            return {"ok": False, "passed": False, "error": str(e)}

    def git_status(self, repo_path: Optional[str] = None) -> Dict[str, Any]:
        """Inspects Git status safely."""
        work_dir = repo_path or self.workspace_root
        try:
            branch_res = subprocess.run(["git", "branch", "--show-current"], cwd=work_dir, capture_output=True, text=True, check=False)
            status_res = subprocess.run(["git", "status", "--short"], cwd=work_dir, capture_output=True, text=True, check=False)
            if status_res.returncode != 0:
                return {"is_git_repo": False, "message": "Not a git repository."}

            changes = [line.strip() for line in status_res.stdout.splitlines() if line.strip()]
            return {
                "is_git_repo": True,
                "branch": branch_res.stdout.strip() or "HEAD",
                "clean": len(changes) == 0,
                "uncommitted_changes_count": len(changes),
                "changes": changes[:20]
            }
        except Exception as e:
            return {"is_git_repo": False, "error": str(e)}

    def diagnose_traceback(self, traceback_str: str) -> Dict[str, Any]:
        """Parses error tracebacks and extracts root-cause diagnostic information."""
        lines = traceback_str.strip().splitlines()
        root_cause = "Unknown error"
        failing_file = None
        failing_line = None

        for line in reversed(lines):
            line_str = line.strip()
            if any(err in line_str for err in ["Error:", "Exception:", "Fault:"]):
                root_cause = line_str
                break

        # Find last file/line
        for line in reversed(lines):
            m = re.search(r'File "([^"]+)", line (\d+)', line)
            if m:
                failing_file = m.group(1)
                failing_line = int(m.group(2))
                break

        return {
            "root_cause": root_cause,
            "failing_file": failing_file,
            "failing_line": failing_line,
            "diagnosis": f"Failure occurred at {failing_file}:{failing_line} due to {root_cause}"
        }

code_engine = CodeEngine()

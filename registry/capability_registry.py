"""
Central Capability Registry for Operation Jarvis.
Unifies Native Tools, Memory Adapters, Desktop Automation, and MCP Services.
"""
import re
import time
import uuid
from config.settings import settings
from typing import Any, Callable, Dict, List, Optional
from core.types import PermissionLevel, ToolCall, ToolResult
from security.policy_engine import policy_engine, ApprovalRequiredError
from security.injection_guard import injection_guard
from security.secret_redactor import redact_structure
from storage.audit_logger import audit_logger

from registry.native_tools import (
    tool_read_file, tool_write_file, tool_edit_file, tool_list_dir,
    tool_run_command, tool_verify_file_exists, tool_verify_file_content,
    tool_verify_test_execution, tool_search_skills, tool_read_skill,
    tool_get_current_time, tool_get_weather,
    tool_git_status, tool_git_diff, tool_git_log, tool_git_stage,
    tool_git_commit, tool_git_push, tool_git_verify_sync
)
from registry.memory_adapter import memory_adapter
from registry.desktop_adapter import desktop_adapter
from registry.browser_adapter import browser_adapter
from registry.security_tools import (
    tool_security_scan_secrets, tool_security_audit_code, tool_security_injection_scan
)
from registry.document_tools import tool_document_convert_markdown
from registry.system_diagnostics import tool_windows_diagnostics
from registry.data_tools import tool_data_profile_tabular
from registry.fact_tools import tool_verify_factual_claims
from registry.sequential_thinking import tool_sequential_thinking

class Capability:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        permission_level: PermissionLevel,
        handler: Callable[..., Any],
        timeout_seconds: float = 60.0
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.permission_level = permission_level
        self.handler = handler
        self.timeout_seconds = timeout_seconds

class CapabilityRegistry:
    def __init__(self):
        self._tools: Dict[str, Capability] = {}
        self._register_default_tools()

    def register(self, capability: Capability):
        self._tools[capability.name] = capability

    def get_tool(self, name: str) -> Optional[Capability]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": cap.name,
                "description": cap.description,
                "parameters": cap.parameters,
                "permission_level": cap.permission_level.value
            }
            for cap in self._tools.values()
        ]

    def list_tool_definitions_for_llm(self) -> List[Dict[str, Any]]:
        """Formats tool definitions for Ollama / Qwen function calling format."""
        defs = []
        for cap in self._tools.values():
            defs.append({
                "type": "function",
                "function": {
                    "name": cap.name,
                    "description": cap.description,
                    "parameters": cap.parameters
                }
            })
        return defs

    def find_relevant_tools(self, objective: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Progressive tool disclosure: Discovers and ranks the most relevant tools
        for the given objective to avoid overwhelming Qwen 3.5 9B with 30+ tools.
        """
        obj_lower = objective.lower()
        domain_keywords = {
            "code": ["code", "repo", "function", "class", "file", "test", "git", "bug", "patch", "edit", "write", "compile", "syntax", "directory", "dir", "folder", "list", "inspect"],
            "browser": ["browser", "web", "page", "chrome", "gmail", "email", "url", "scrape", "search", "html", "site", "online", "fetch", "news"],
            "system": ["command", "powershell", "process", "hardware", "cpu", "gpu", "vram", "ram", "desktop", "app", "disk", "terminal", "telemetry", "diagnostics", "eventlog", "event", "service", "socket", "port"],
            "desktop": ["desktop", "window", "windows", "snapshot", "click", "type", "press", "active", "apps", "application", "running", "accessibility"],
            "memory": ["remember", "memory", "recall", "store", "history", "knowledge", "note", "preference", "fact"],
            "assistant": ["calendar", "schedule", "reminder", "event", "meeting", "task", "deadline", "slot", "briefing", "brief", "research", "youtube", "video"],
            "security": ["cve", "vulnerability", "advisories", "advisory", "nvd", "exploit", "security", "patch", "secret", "secrets", "leak", "injection", "token", "audit", "bandit", "canary"],
            "documents": ["document", "documents", "pdf", "docx", "pptx", "xlsx", "upload", "ingest", "chunks", "citation", "manual", "textbook", "syllabus", "convert", "markdown", "markitdown"],
            "data": ["data", "csv", "json", "profile", "statistic", "statistics", "histogram", "dataset", "table", "tabular", "chart"],
            "reasoning": ["think", "sequential", "step", "reason", "hypothesis", "branch", "reflect", "complex", "plan"],
            "fact": ["fact", "claim", "verify", "corroborate", "truth", "true", "check", "evidence", "consensus"],
            "temporal": ["time", "date", "clock", "timestamp", "weekday", "timezone", "today"]
        }

        scored = []
        for cap in self._tools.values():
            score = 0
            desc = (cap.name + " " + cap.description).lower()
            
            # Direct word intersection
            words = [w for w in re.findall(r"\w+", obj_lower) if len(w) > 3]
            for w in words:
                if w in desc:
                    score += 2
                    
            # Domain relevance
            for domain, kws in domain_keywords.items():
                if any(k in obj_lower for k in kws) and any(k in desc for k in kws):
                    score += 3
                    
            # Core utility tools get small baseline score
            if cap.name in ("read_file", "run_command", "memory_search"):
                score += 1

            scored.append((score, cap))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_caps = [c for _, c in scored[:limit]]
        return [
            {
                "type": "function",
                "function": {
                    "name": cap.name,
                    "description": cap.description,
                    "parameters": cap.parameters
                }
            }
            for cap in top_caps
        ]

    def _validate_and_sanitize_arguments(self, cap: Capability, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validates arguments against schema with bounded type auto-casting and alias mapping."""
        sanitized = dict(arguments)
        props = cap.parameters.get("properties", {})

        # 1. Alias normalization for common LLM parameter name divergences
        alias_map = {
            "limit": "max_results",
            "max_results": "limit",
            "filepath": "path",
            "file": "path",
            "file_path": "path",
            "cmd": "command",
            "query_text": "query",
            "q": "query",
            "target_dir": "working_dir"
        }
        for alias, target in alias_map.items():
            if alias in sanitized and target in props and target not in sanitized:
                sanitized[target] = sanitized.pop(alias)

        # 2. Type validation and auto-casting
        for param, spec in props.items():
            expected_type = spec.get("type")
            if param in sanitized:
                val = sanitized[param]
                if expected_type == "integer" and isinstance(val, str) and val.isdigit():
                    sanitized[param] = int(val)
                elif expected_type == "number" and isinstance(val, str):
                    try:
                        sanitized[param] = float(val)
                    except ValueError:
                        pass
                elif expected_type == "boolean" and isinstance(val, str):
                    sanitized[param] = val.lower() in ("true", "1", "yes")
            elif "default" in spec:
                sanitized[param] = spec["default"]
        return sanitized

    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        task_id: str,
        step_number: int = 1,
        approval_token: Optional[str] = None
    ) -> ToolResult:
        call_id = f"call-{uuid.uuid4().hex[:8]}"
        if name not in self._tools:
            return ToolResult(
                call_id=call_id,
                tool_name=name,
                success=False,
                error=f"Tool '{name}' is not registered in capability registry."
            )

        cap = self._tools[name]
        sanitized_args = self._validate_and_sanitize_arguments(cap, arguments)
        tool_call = ToolCall(
            call_id=call_id,
            tool_name=name,
            arguments=sanitized_args,
            permission_level=cap.permission_level
        )

        # 1. Policy & Permission Enforcement
        can_exec, approval_req, reason = policy_engine.evaluate_tool_execution(
            task_id=task_id,
            step_number=step_number,
            tool_call=tool_call,
            approval_token=approval_token
        )

        if not can_exec:
            if approval_req:
                raise ApprovalRequiredError(approval_req)
            return ToolResult(
                call_id=call_id,
                tool_name=name,
                success=False,
                error=f"Permission Denied: {reason}"
            )

        # 2. Audit Trail Log: Tool Call Invocation
        audit_logger.log_event(
            task_id=task_id,
            event_type="tool_call",
            details={
                "call_id": call_id,
                "tool_name": name,
                "arguments": tool_call.arguments,
                "permission_level": cap.permission_level.value
            }
        )

        # 3. Execution with Timing and Error Handling
        start_time = time.time()
        try:
            try:
                output = cap.handler(**sanitized_args)
            except TypeError:
                output = cap.handler(**arguments)
            duration_ms = (time.time() - start_time) * 1000.0

            # Wrap string outputs in prompt-injection guard with source provenance
            sanitized_output = output
            if isinstance(output, str):
                sanitized_output = injection_guard.wrap_untrusted_content(output, source_identifier=name)
            elif isinstance(output, dict):
                sanitized_output = dict(output)
                for k in ("content", "text", "text_content", "body", "stdout", "extracted_text", "snippet", "raw_content"):
                    if k in sanitized_output and isinstance(sanitized_output[k], str):
                        sanitized_output[k] = injection_guard.wrap_untrusted_content(sanitized_output[k], source_identifier=f"{name}:{k}")

            # Redact secrets in result
            clean_output = redact_structure(sanitized_output)

            res = ToolResult(
                call_id=call_id,
                tool_name=name,
                success=output.get("ok", True) if isinstance(output, dict) else True,
                output=clean_output,
                error=output.get("error") if isinstance(output, dict) else None,
                duration_ms=round(duration_ms, 2)
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000.0
            res = ToolResult(
                call_id=call_id,
                tool_name=name,
                success=False,
                error=str(e),
                duration_ms=round(duration_ms, 2)
            )

        # 4. Audit Trail Log: Tool Result
        audit_logger.log_event(
            task_id=task_id,
            event_type="tool_result",
            details={
                "call_id": call_id,
                "tool_name": name,
                "success": res.success,
                "error": res.error,
                "duration_ms": res.duration_ms
            }
        )

        # 5. OpenTelemetry Live Ingestion to Tracelet
        try:
            from storage.tracelet_exporter import tracelet_exporter
            tracelet_exporter.export_tool_call_trace(
                task_id=task_id,
                tool_name=name,
                arguments=arguments,
                output=res.output,
                duration_ms=res.duration_ms,
                success=res.success,
                error_msg=res.error
            )
        except Exception:
            pass

        return res

    def _register_default_tools(self):
        # Native File Inspection & Writing
        self.register(Capability(
            name="read_file",
            description="Read lines from a file safely within workspace bounds.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                    "start_line": {"type": "integer", "default": 1},
                    "end_line": {"type": "integer"}
                },
                "required": ["path"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_read_file
        ))

        self.register(Capability(
            name="list_dir",
            description="List items inside a directory safely within workspace bounds.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                    "recursive": {"type": "boolean", "default": False}
                },
                "required": ["path"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_list_dir
        ))

        self.register(Capability(
            name="get_current_time",
            description="Retrieve authoritative host OS date, time, weekday, and timezone. Sub-millisecond deterministic reading from host clock.",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_get_current_time
        ))

        self.register(Capability(
            name="get_weather",
            description="Retrieve authoritative live weather conditions, feels-like temperature, humidity, wind speed, precipitation, and multi-day forecasts for any city or current workstation location using Open-Meteo.",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City or location name (e.g. 'Bengaluru', 'Tokyo', 'London'). Defaults to workstation location if omitted."},
                    "force_refresh": {"type": "boolean", "description": "Bypass in-memory cache to fetch live from provider", "default": False}
                },
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_get_weather
        ))

        # Git and Repository Management Capabilities
        self.register(Capability(
            name="git_status",
            description="Inspect git repository status, branch, staged files, and untracked changes.",
            parameters={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Repository path, defaults to workspace"}
                },
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_git_status
        ))

        self.register(Capability(
            name="git_diff",
            description="Inspect git diff of working tree or staged changes.",
            parameters={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Repository path"},
                    "staged": {"type": "boolean", "description": "Inspect staged diff", "default": False}
                },
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_git_diff
        ))

        self.register(Capability(
            name="git_log",
            description="Inspect recent commit history with hashes, authors, and timestamps.",
            parameters={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Repository path"},
                    "max_count": {"type": "integer", "description": "Number of commits to return", "default": 5}
                },
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_git_log
        ))

        self.register(Capability(
            name="git_stage",
            description="Stage files for commit in git repository.",
            parameters={
                "type": "object",
                "properties": {
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Files to stage"},
                    "repo_path": {"type": "string", "description": "Repository path"}
                },
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=tool_git_stage
        ))

        self.register(Capability(
            name="git_commit",
            description="Commit staged files with a clear, descriptive message.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Optional files to stage before committing"},
                    "repo_path": {"type": "string", "description": "Repository path"}
                },
                "required": ["message"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=tool_git_commit
        ))

        self.register(Capability(
            name="git_push",
            description="Push committed changes to remote repository on GitHub using authenticated credentials.",
            parameters={
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name", "default": "main"},
                    "repo_path": {"type": "string", "description": "Repository path"}
                },
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=tool_git_push
        ))

        self.register(Capability(
            name="git_verify_sync",
            description="Verify that remote repository on GitHub matches local HEAD commit hash.",
            parameters={
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name", "default": "origin"},
                    "branch": {"type": "string", "description": "Branch name", "default": "main"},
                    "repo_path": {"type": "string", "description": "Repository path"}
                },
                "required": []
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_git_verify_sync
        ))

        self.register(Capability(
            name="write_file",
            description="Write full contents to a file within workspace bounds.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target file path"},
                    "content": {"type": "string", "description": "File text content"},
                    "overwrite": {"type": "boolean", "default": False}
                },
                "required": ["path", "content"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=tool_write_file
        ))

        self.register(Capability(
            name="edit_file",
            description="Replace target substring with replacement in an existing file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target file path"},
                    "target": {"type": "string", "description": "Exact text to replace"},
                    "replacement": {"type": "string", "description": "New replacement text"}
                },
                "required": ["path", "target", "replacement"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=tool_edit_file
        ))

        self.register(Capability(
            name="run_command",
            description="Run a controlled shell command or test script with defense-in-depth inspection.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command line string"},
                    "working_dir": {"type": "string", "description": "Optional working directory"},
                    "timeout": {"type": "number", "default": 60.0}
                },
                "required": ["command"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=tool_run_command
        ))

        # Verification Tools
        self.register(Capability(
            name="verify_file_exists",
            description="Verify that a required file exists and check its size.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to verify"}},
                "required": ["path"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_verify_file_exists
        ))

        self.register(Capability(
            name="verify_file_content",
            description="Verify that a file contains an expected substring.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "expected_substring": {"type": "string", "description": "Expected content to assert"}
                },
                "required": ["path", "expected_substring"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_verify_file_content
        ))

        self.register(Capability(
            name="verify_test_suite",
            description="Run an automated test suite command (e.g. pytest) and verify passing exit code.",
            parameters={
                "type": "object",
                "properties": {
                    "test_command": {"type": "string", "description": "Test command (e.g. pytest tests/)"},
                    "working_dir": {"type": "string"}
                },
                "required": ["test_command"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=tool_verify_test_execution
        ))

        # Memory Integration Tools
        self.register(Capability(
            name="memory_search",
            description="Search persistent local memory and project knowledge using BM25 FTS5.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query keywords"},
                    "category": {"type": "string", "description": "Optional category filter"},
                    "project": {"type": "string", "description": "Optional project identifier"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=memory_adapter.search
        ))

        self.register(Capability(
            name="memory_store",
            description="Store a verified factual memory record in the persistent local memory ecosystem.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the memory"},
                    "content": {"type": "string", "description": "Markdown body"},
                    "category": {"type": "string", "description": "Optional category"},
                    "project": {"type": "string", "default": "global"},
                    "importance": {"type": "string", "enum": ["critical", "high", "normal", "low"], "default": "normal"},
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "content"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=memory_adapter.store
        ))

        self.register(Capability(
            name="memory_update",
            description="Update an existing memory record with version tracking and changelog.",
            parameters={
                "type": "object",
                "properties": {
                    "target_id_or_title": {"type": "string", "description": "Memory ID or title"},
                    "content": {"type": "string", "description": "New content"},
                    "changelog": {"type": "string", "description": "Reason for revision"}
                },
                "required": ["target_id_or_title", "content", "changelog"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=memory_adapter.update
        ))

        self.register(Capability(
            name="memory_status",
            description="Check storage health and utilization budgets of the persistent memory ecosystem.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=memory_adapter.get_status
        ))

        self.register(Capability(
            name="memory_project_overview",
            description="Get high-level summary of memory count and category distribution across projects.",
            parameters={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "default": "global"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=memory_adapter.get_project_overview
        ))

        # Desktop Automation Tool (matches Qwen /tools registry)
        self.register(Capability(
            name="desktop",
            description="Execute native desktop automation via Vercel Agent Desktop CLI (list-apps, list-windows, snapshot, get, click, set-value).",
            parameters={
                "type": "object",
                "properties": {
                    "subcommand": {
                        "type": "string",
                        "description": "CLI subcommand and arguments, e.g. 'list-apps', 'list-windows', 'snapshot', 'status'"
                    }
                },
                "required": ["subcommand"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=desktop_adapter.execute_subcommand
        ))

        # Skill Discovery & Progressive Disclosure Tools
        self.register(Capability(
            name="search_skills",
            description="Search available procedural skills across plugins (superpowers, ponytail, ui-ux, etc.).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords or task description to match skills"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_search_skills
        ))

        self.register(Capability(
            name="read_skill",
            description="Read the complete procedural instructions and workflow rules for a specific skill.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact or partial name of the skill"}
                },
                "required": ["name"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_read_skill
        ))

        # Browser & Web Automation Tools
        self.register(Capability(
            name="browser_status",
            description="Check status of Chrome process, Playwright MCP, and Chrome DevTools MCP.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=browser_adapter.get_status
        ))

        self.register(Capability(
            name="browser_list_pages",
            description="List all active browser pages and tabs in the Chrome session.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=browser_adapter.list_pages
        ))

        self.register(Capability(
            name="browser_navigate",
            description="Navigate browser to target URL with bounded timeout and load completion.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Destination URL"},
                    "timeout": {"type": "number", "default": 15.0}
                },
                "required": ["url"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=browser_adapter.navigate
        ))

        self.register(Capability(
            name="browser_snapshot",
            description="Capture text and accessibility tree snapshot of the current browser page.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=browser_adapter.snapshot
        ))

        self.register(Capability(
            name="browser_read_gmail",
            description="Inspect the user's Chrome Gmail session and read emails for a specified date or count (read-only; never sends or modifies).",
            parameters={
                "type": "object",
                "properties": {
                    "date_query": {"type": "string", "default": "5 November 2026", "description": "Date or search filter for emails"},
                    "date": {"type": "string", "description": "Date filter (e.g. 2026-11-05 or 5 November 2026)"},
                    "limit": {"type": "integer", "default": 5, "description": "Maximum number of recent emails to return"},
                    "mode": {"type": "string", "default": "read_only", "description": "Read-only access mode"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=browser_adapter.read_gmail
        ))

        self.register(Capability(
            name="browser_launch_persistent",
            description="Ensure the dedicated persistent JARVIS Google Chrome instance is running on port 9222.",
            parameters={
                "type": "object",
                "properties": {
                    "force_restart": {"type": "boolean", "default": False, "description": "Force restart existing instance"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=browser_adapter.ensure_jarvis_chrome
        ))

        # Skillet Skills Package Manager Tools
        def _exec_skillet_search(query: str = "") -> Dict[str, Any]:
            import subprocess, json
            cli_path = r"C:\Users\Akshay aravind .rv\operation_jarvis\data\repo_eval\final_toolkit\skillet\src\cli.js"
            cmd = ["node", cli_path, "search"]
            if query:
                cmd.append(query)
            cmd.append("--json")
            try:
                cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, creationflags=cf)
                return {"ok": res.returncode == 0, "results": json.loads(res.stdout.strip()) if res.stdout.strip() else []}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        def _exec_skillet_list() -> Dict[str, Any]:
            import subprocess, json
            cli_path = r"C:\Users\Akshay aravind .rv\operation_jarvis\data\repo_eval\final_toolkit\skillet\src\cli.js"
            target_dir = r"C:\Users\Akshay aravind .rv\.gemini\config\plugins\skillet_skills\skills"
            cmd = ["node", cli_path, "list", "--dir", target_dir, "--json"]
            try:
                cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15, creationflags=cf)
                return {"ok": res.returncode == 0, "installed": json.loads(res.stdout.strip()) if res.stdout.strip() else []}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        self.register(Capability(
            name="skillet_search",
            description="Search the Skillet agent skill registry for installable procedural skills.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword for skills (e.g. 'pdf', 'git', 'eval')"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=_exec_skillet_search
        ))

        self.register(Capability(
            name="skillet_list",
            description="List installed procedural skills in the workstation skillet repository.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=_exec_skillet_list
        ))

        # Live Read-Only Internet Intelligence Tools
        from registry.internet_gateway import internet_gateway

        self.register(Capability(
            name="web_search",
            description="Perform a multi-source live read-only internet search across Wikipedia, tech news, arXiv research papers, and CVE vulnerabilities with privacy redaction and freshness verification.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search topic or question (personal info is automatically sanitized)"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=internet_gateway.unified_search
        ))

        self.register(Capability(
            name="web_fetch",
            description="Safely fetch the text content of a public webpage via strict read-only HTTP GET with SSRF and DNS rebinding defense, content-size bounds, and prompt-injection neutralization.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Public HTTP/HTTPS URL (internal networks and localhost are strictly blocked)"}
                },
                "required": ["url"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=lambda url, **kwargs: internet_gateway.fetch_url(url=url, method="GET")
        ))

        self.register(Capability(
            name="wikipedia_search",
            description="Search official Wikipedia encyclopedia for clean, neutral, peer-reviewed educational articles and summaries.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or keyword"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=internet_gateway.search_wikipedia
        ))

        self.register(Capability(
            name="arxiv_search",
            description="Search arXiv repository for scientific research papers, preprints, abstracts, and publications (AI, machine learning, CS, math).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Research topic or paper title"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=internet_gateway.search_arxiv
        ))

        self.register(Capability(
            name="cve_search",
            description="Search public cybersecurity vulnerability databases (CVE/NVD) for CVE identifiers, vulnerability details, and CVSS scores.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "CVE ID or software keyword, e.g. 'CVE-2024' or 'openssh'"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=internet_gateway.search_cve
        ))

        self.register(Capability(
            name="tech_news_search",
            description="Search recent public tech news and developer release announcements.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic, product, or announcement"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=internet_gateway.search_tech_news
        ))

        self.register(Capability(
            name="search_news",
            description="Retrieve live real-time news headlines with source URLs and publication dates from Google News RSS feeds (supports optional query and region filter, e.g. 'IN', 'US').",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": "", "description": "Search keyword or topic (leave empty for top general headlines)"},
                    "region": {"type": "string", "default": "IN", "description": "Two-letter region code (e.g. 'IN', 'US', 'GB')"},
                    "max_results": {"type": "integer", "default": 5}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=internet_gateway.search_news
        ))

        # Antigravity Bidirectional Communication Bridge
        try:
            import sys
            local_mem_dir = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY"
            if local_mem_dir not in sys.path:
                sys.path.insert(0, local_mem_dir)
            from engine.antigravity_bridge import antigravity_bridge

            self.register(Capability(
                name="antigravity_bridge",
                description="Bidirectional communication bridge to Antigravity 2.0 Principal Orchestrator. Dispatches complex architecture, multi-turn implementation, deep code analysis, or cross-agent tasks to Antigravity and returns verified results.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task title or objective"},
                        "description": {"type": "string", "description": "Full specifications and context for Antigravity"},
                        "payload": {"type": "object", "description": "Optional structured parameters or context dictionary"}
                    },
                    "required": ["title", "description"]
                },
                permission_level=PermissionLevel.LEVEL_1_SAFE,
                handler=lambda title, description, payload=None, **kwargs: antigravity_bridge.execute_roundtrip(title=title, description=description, payload=payload)
            ))
        except Exception:
            pass

        # Scheduled Research Indexing Tools (Separate from LOCAL_AI_MEMORY)
        from core.research_indexer import research_indexer

        self.register(Capability(
            name="research_search",
            description="Search the isolated public research FTS5 database (papers, advisories, news) without touching personal memory or external internet.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword or topic"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=lambda query, limit=5: research_indexer.db.search_research(query=query, limit=limit)
        ))

        self.register(Capability(
            name="research_status",
            description="Inspect statistics and status of the background public research indexing subsystem.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=research_indexer.get_status
        ))

        self.register(Capability(
            name="research_trigger_cycle",
            description="Trigger a single indexing cycle across configured public research sources.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=research_indexer.run_indexing_cycle
        ))

        self.register(Capability(
            name="research_emergency_stop",
            description="Instantly halt background research indexing and release all network workers.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=research_indexer.emergency_stop
        ))

        # Agent Ecosystem Discovery (MultiAgentOrchestrator reconciliation)
        def _ensure_memory_path():
            import sys
            mem_root = str(settings.memory_root)
            if mem_root not in sys.path:
                sys.path.insert(0, mem_root)

        def _exec_agent_list(status: Optional[str] = None) -> Dict[str, Any]:
            try:
                _ensure_memory_path()
                from engine.orchestrator import MultiAgentOrchestrator
                orch = MultiAgentOrchestrator(str(settings.memory_db_path))
                agents = orch.get_agents(status=status)
                return {"ok": True, "count": len(agents), "agents": agents}
            except Exception as e:
                return {"ok": False, "error": str(e), "agents": []}

        def _exec_agent_status(agent_id: str) -> Dict[str, Any]:
            try:
                _ensure_memory_path()
                from engine.orchestrator import MultiAgentOrchestrator
                orch = MultiAgentOrchestrator(str(settings.memory_db_path))
                agents = orch.get_agents()
                for a in agents:
                    if a["agent_id"] == agent_id:
                        return {"ok": True, "agent": a}
                return {"ok": False, "error": f"Agent '{agent_id}' not found in registry."}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        self.register(Capability(
            name="agent_list",
            description="List all 6 registered agents in the workstation ecosystem with their tiers, statuses, and capabilities.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Optional filter: online, offline, busy"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=_exec_agent_list
        ))

        self.register(Capability(
            name="agent_status",
            description="Inspect detailed status, health, tier, and capabilities of a specific agent.",
            parameters={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "ID of agent (e.g. 'antigravity', 'qwen-batman', 'continue-ide', 'security-auditor', 'research', 'test-engineer')"}
                },
                "required": ["agent_id"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=_exec_agent_status
        ))

        # Persistent Scheduled Tasks Capabilities
        def _exec_schedule_create(name: str, schedule_type: str, schedule_expr: str, objective: str, start_delay_seconds: float = 0.0, max_runs: Optional[int] = None, requires_approval: bool = False) -> Dict[str, Any]:
            from core.scheduler import persistent_scheduler
            sched = persistent_scheduler.create_schedule(
                name=name,
                schedule_type=schedule_type,
                schedule_expr=schedule_expr,
                objective=objective,
                start_delay_seconds=start_delay_seconds,
                max_runs=max_runs,
                requires_approval=requires_approval
            )
            return {"ok": True, "schedule": sched}

        def _exec_schedule_list(status: Optional[str] = None) -> Dict[str, Any]:
            from core.scheduler import persistent_scheduler
            schedules = persistent_scheduler.list_schedules(status=status)
            return {"ok": True, "count": len(schedules), "schedules": schedules}

        def _exec_schedule_control(schedule_id: str, action: str) -> Dict[str, Any]:
            from core.scheduler import persistent_scheduler
            act = action.lower()
            if act == "pause":
                ok = persistent_scheduler.pause_schedule(schedule_id)
            elif act == "resume":
                ok = persistent_scheduler.resume_schedule(schedule_id)
            elif act == "cancel":
                ok = persistent_scheduler.cancel_schedule(schedule_id)
            elif act == "run_now":
                return persistent_scheduler.run_now(schedule_id)
            else:
                return {"ok": False, "error": f"Invalid schedule action '{action}'."}
            return {"ok": ok, "schedule_id": schedule_id, "action": action}

        self.register(Capability(
            name="schedule_create",
            description="Create a new one-time or recurring persistent scheduled agent task.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Descriptive title of schedule"},
                    "schedule_type": {"type": "string", "enum": ["interval", "one_time"], "description": "Type of schedule"},
                    "schedule_expr": {"type": "string", "description": "Interval in seconds or one-time delay/timestamp"},
                    "objective": {"type": "string", "description": "Agent goal to execute automatically"},
                    "max_runs": {"type": "integer", "description": "Optional maximum run count before completion"},
                    "requires_approval": {"type": "boolean", "default": False}
                },
                "required": ["name", "schedule_type", "schedule_expr", "objective"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=_exec_schedule_create
        ))

        self.register(Capability(
            name="schedule_list",
            description="List scheduled tasks with next-run times, status, and failure history.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["active", "paused", "cancelled", "completed"]}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=_exec_schedule_list
        ))

        self.register(Capability(
            name="schedule_control",
            description="Control a scheduled task (pause, resume, cancel, or run_now).",
            parameters={
                "type": "object",
                "properties": {
                    "schedule_id": {"type": "string", "description": "Target schedule ID"},
                    "action": {"type": "string", "enum": ["pause", "resume", "cancel", "run_now"]}
                },
                "required": ["schedule_id", "action"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=_exec_schedule_control
        ))

        # Email Integration Capabilities
        from registry.email_adapter import email_adapter

        self.register(Capability(
            name="email_search",
            description="Search local mailbox for emails matching query terms, category, or unread status.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword for subject, body, or sender"},
                    "category": {"type": "string", "description": "Optional category (work, personal, security, updates)"},
                    "unread_only": {"type": "boolean", "default": False},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=email_adapter.search_emails
        ))

        self.register(Capability(
            name="email_read",
            description="Read the complete text and metadata of a specific email message.",
            parameters={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "Email ID (e.g. 'msg-001')"}
                },
                "required": ["email_id"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=email_adapter.read_email
        ))

        self.register(Capability(
            name="email_classify",
            description="Classify an email's category and priority based on technical heuristics.",
            parameters={
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "Email ID to classify"}
                },
                "required": ["email_id"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=email_adapter.classify_email
        ))

        self.register(Capability(
            name="email_summarize",
            description="Summarize an entire email thread into key action points.",
            parameters={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Thread ID or Email ID to summarize"}
                },
                "required": ["thread_id"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=email_adapter.summarize_thread
        ))

        self.register(Capability(
            name="email_draft",
            description="Generate and save an email draft locally for review.",
            parameters={
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Subject line"},
                    "body": {"type": "string", "description": "Body content of the draft"},
                    "in_reply_to": {"type": "string", "description": "Optional message ID being replied to"}
                },
                "required": ["recipient", "subject", "body"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=email_adapter.create_draft
        ))

        self.register(Capability(
            name="email_send",
            description="Send an email message (Strictly gated behind Level 3 human approval).",
            parameters={
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Subject line"},
                    "body": {"type": "string", "description": "Email body content"},
                    "draft_id": {"type": "string", "description": "Optional draft ID to mark sent"}
                },
                "required": ["recipient", "subject", "body"]
            },
            permission_level=PermissionLevel.LEVEL_3_RESTRICTED,
            handler=lambda recipient, subject, body, draft_id=None, **kwargs: email_adapter.send_email(
                recipient=recipient, subject=subject, body=body, draft_id=draft_id,
                approval_token=kwargs.get("approval_token")
            )
        ))

        # Calendar Integration Capabilities
        from registry.calendar_adapter import calendar_adapter

        self.register(Capability(
            name="calendar_get_events",
            description="Retrieve calendar events within a specified date window.",
            parameters={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "Optional ISO start date/time"},
                    "end_date": {"type": "string", "description": "Optional ISO end date/time"},
                    "limit": {"type": "integer", "default": 20}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=calendar_adapter.get_events
        ))

        self.register(Capability(
            name="calendar_check_availability",
            description="Check for conflicting events in a requested time slot.",
            parameters={
                "type": "object",
                "properties": {
                    "start_time": {"type": "string", "description": "ISO start time"},
                    "end_time": {"type": "string", "description": "ISO end time"}
                },
                "required": ["start_time", "end_time"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=calendar_adapter.check_availability
        ))

        self.register(Capability(
            name="calendar_suggest_slots",
            description="Suggest available free daytime slots for a specified meeting duration.",
            parameters={
                "type": "object",
                "properties": {
                    "duration_minutes": {"type": "integer", "default": 60},
                    "day_date": {"type": "string", "description": "Target date (YYYY-MM-DD)"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=calendar_adapter.suggest_slots
        ))

        self.register(Capability(
            name="calendar_create_event",
            description="Schedule a new calendar event with duplicate event prevention.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title"},
                    "start_time": {"type": "string", "description": "ISO start time"},
                    "end_time": {"type": "string", "description": "ISO end time"},
                    "description": {"type": "string", "default": ""},
                    "location": {"type": "string", "default": ""},
                    "reminder_minutes": {"type": "integer", "default": 15}
                },
                "required": ["title", "start_time", "end_time"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=calendar_adapter.create_event
        ))

        self.register(Capability(
            name="calendar_cancel_event",
            description="Cancel a calendar event (Strictly gated behind Level 3 human approval).",
            parameters={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID (e.g. 'evt-001')"}
                },
                "required": ["event_id"]
            },
            permission_level=PermissionLevel.LEVEL_3_RESTRICTED,
            handler=lambda event_id, **kwargs: calendar_adapter.cancel_event(
                event_id=event_id, approval_token=kwargs.get("approval_token")
            )
        ))

        # Document Intelligence Capabilities
        from core.doc_intelligence import doc_intelligence
        from pathlib import Path

        self.register(Capability(
            name="document_ingest",
            description="Ingest and chunk a PDF, DOCX, TXT, or MD document into the FTS5 document index.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute or relative file path"},
                    "force_reindex": {"type": "boolean", "default": False}
                },
                "required": ["file_path"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=lambda file_path, force_reindex=False, **kwargs: doc_intelligence.ingest_document(
                file_path=Path(file_path), force_reindex=force_reindex
            )
        ))

        self.register(Capability(
            name="document_search",
            description="Search ingested documents using BM25 FTS5 ranking and return exact source citations.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords or search question"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=doc_intelligence.search_documents
        ))

        self.register(Capability(
            name="document_list",
            description="List all currently indexed documents with page counts and chunk statistics.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=doc_intelligence.list_documents
        ))

        # RAG and Memory Evaluation Capability
        from evaluation.rag_evaluator import rag_evaluator

        self.register(Capability(
            name="rag_evaluate",
            description="Run reproducible retrieval evaluation against the local memory database and compute IR metrics (Precision@K, Recall@K, MRR, Hit Rate) without modifying production memory.",
            parameters={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["json", "markdown"], "default": "json"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=lambda format="json", **kwargs: rag_evaluator.generate_markdown_report() if format == "markdown" else rag_evaluator.generate_full_evaluation_report()
        ))

        # Autonomous Coding & Engineering Capabilities
        from core.code_engine import code_engine
        from core.inference_queue import inference_queue
        import psutil

        self.register(Capability(
            name="repo_map",
            description="Map repository structure, language distributions, entry points, and directory layout.",
            parameters={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Optional repository path (defaults to workspace)"},
                    "max_depth": {"type": "integer", "default": 3}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=code_engine.map_repository
        ))

        self.register(Capability(
            name="code_symbols",
            description="Extract classes, functions, and docstrings from a Python source file using AST parsing.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to Python source file"}
                },
                "required": ["file_path"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=code_engine.read_symbols
        ))

        self.register(Capability(
            name="run_tests",
            description="Execute automated test suite command (e.g. pytest) and parse structured failures and stack traces.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "default": "pytest", "description": "Test command to execute"},
                    "working_dir": {"type": "string", "description": "Optional working directory"}
                }
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=lambda command="pytest", working_dir=None, **kwargs: code_engine.run_test_suite(command, working_dir)
        ))

        self.register(Capability(
            name="multi_file_patch",
            description="Apply atomic multi-file modifications with automatic rollback on failure.",
            parameters={
                "type": "object",
                "properties": {
                    "patches": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of patch dicts: [{'path': str, 'action': 'write'|'replace', 'content': str}]"
                    }
                },
                "required": ["patches"]
            },
            permission_level=PermissionLevel.LEVEL_2_CONTROLLED,
            handler=lambda patches=[], **kwargs: code_engine.multi_file_patch(patches)
        ))

        self.register(Capability(
            name="git_status",
            description="Inspect Git status, branch, uncommitted files, and changes safely.",
            parameters={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Optional repository path"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=code_engine.git_status
        ))

        def _get_system_telemetry(**kwargs) -> Dict[str, Any]:
            vram = inference_queue.get_vram_status()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            return {
                "ok": True,
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "ram_total_gb": round(mem.total / (1024**3), 2),
                "ram_used_gb": round(mem.used / (1024**3), 2),
                "ram_percent": mem.percent,
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "disk_percent": disk.percent,
                "gpu_vram": vram
            }

        self.register(Capability(
            name="system_telemetry",
            description="Inspect HP Victus hardware and resource utilization (CPU, RAM, GPU VRAM headroom, disk space).",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=_get_system_telemetry
        ))

        self.register(Capability(
            name="inference_health",
            description="Check GPU inference queue metrics, active requests, latency averages, and VRAM status.",
            parameters={"type": "object", "properties": {}},
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=lambda **kwargs: inference_queue.get_queue_health()
        ))

        from core.assistant import assistant

        self.register(Capability(
            name="daily_brief",
            description="Generate a daily operational briefing aggregating calendar events, pending tasks, academic milestones, and workout schedules.",
            parameters={
                "type": "object",
                "properties": {
                    "target_date": {"type": "string", "description": "Optional ISO date string (YYYY-MM-DD)"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=lambda **kwargs: assistant.generate_daily_brief(kwargs.get("target_date"))
        ))

        self.register(Capability(
            name="deep_research",
            description="Perform rigorous research decomposing queries into subqueries, gathering evidence, synthesizing facts vs inferences vs uncertainties, and indexing results.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Research objective or topic"},
                    "domain": {"type": "string", "description": "Domain context (technical, cybersecurity, systems)", "default": "technical"}
                },
                "required": ["query"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=lambda **kwargs: assistant.conduct_deep_research(kwargs.get("query", ""), kwargs.get("domain", "technical"))
        ))

        self.register(Capability(
            name="youtube_concept",
            description="Generate high-retention YouTube video concepts, hook options, beat outlines, and titles/descriptions for 'Mr Mysto'.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Video topic or theme"},
                    "niche": {"type": "string", "description": "Content niche", "default": "bodybuilding_motivation"}
                },
                "required": ["topic"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=lambda **kwargs: assistant.generate_youtube_concept(kwargs.get("topic", ""), kwargs.get("niche", "bodybuilding_motivation"))
        ))

        # External Integrated Skills & Security Capabilities
        self.register(Capability(
            name="security_scan_secrets",
            description="Scan files, directories, or code strings for leaked API keys, tokens, private keys, and high-entropy credentials (Yelp detect-secrets).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or directory path to scan within workspace bounds"},
                    "content": {"type": "string", "description": "Raw text or code snippet to scan in-memory"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_security_scan_secrets
        ))

        self.register(Capability(
            name="security_audit_code",
            description="Perform Static Application Security Testing (SAST) on Python code or files to detect SQL injection, shell execution, insecure deserialization, and crypto flaws (PyCQA Bandit).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target Python file path to audit"},
                    "code": {"type": "string", "description": "Raw Python code snippet to audit via AST"}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_security_audit_code
        ))

        self.register(Capability(
            name="security_injection_scan",
            description="Scan content for prompt injections, system override directives, zero-width obfuscation, base64 payloads, markdown image exfiltration, and canary leaks (Vigil/AgentDojo).",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Text content to inspect for prompt injections or data exfiltration"},
                    "canary_token": {"type": "string", "description": "Optional active canary token to check for leakage"}
                },
                "required": ["content"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_security_injection_scan
        ))

        self.register(Capability(
            name="document_convert_markdown",
            description="Convert complex documents (.docx, .pptx, .xlsx, .pdf, .html, .csv, .json, .xml) to clean structured Markdown for LLM analysis (Microsoft MarkItDown).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target document file path within workspace bounds"}
                },
                "required": ["path"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_document_convert_markdown
        ))

        self.register(Capability(
            name="windows_diagnostics",
            description="Inspect Windows 11 system health: retrieve recent Application/System event logs, active TCP network listening sockets, Windows service states, or hardware telemetry.",
            parameters={
                "type": "object",
                "properties": {
                    "diagnostic_type": {
                        "type": "string",
                        "description": "Diagnostic category ('system_info', 'event_logs', 'network_ports', 'services')",
                        "default": "system_info"
                    },
                    "filter_query": {"type": "string", "description": "Optional substring filter for service, log provider, or port"},
                    "limit": {"type": "integer", "description": "Max items to return (1-50)", "default": 10}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_windows_diagnostics
        ))

        self.register(Capability(
            name="data_profile_tabular",
            description="Perform automated profiling and summary statistics on CSV/JSON tabular datasets, calculating column types, null percentages, mean/std, and ASCII distribution charts.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to CSV or JSON tabular data file"},
                    "raw_data": {"type": "string", "description": "Raw CSV or JSON text string"},
                    "generate_chart": {"type": "boolean", "description": "Whether to render ASCII distribution histogram", "default": False}
                }
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_data_profile_tabular
        ))

        self.register(Capability(
            name="verify_factual_claims",
            description="Cross-reference a factual claim across independent search sources and local knowledge base to verify consensus, detect contradictions, and assign confidence scores.",
            parameters={
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "Factual claim or proposition to verify"},
                    "max_sources": {"type": "integer", "description": "Maximum independent sources to consult", "default": 3}
                },
                "required": ["claim"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_verify_factual_claims
        ))

        self.register(Capability(
            name="sequential_thinking",
            description="Execute dynamic reflective problem-solving: break complex problems into sequential thoughts, evaluate hypotheses, revise previous thoughts, and explore reasoning branches (Anthropic MCP).",
            parameters={
                "type": "object",
                "properties": {
                    "thought": {"type": "string", "description": "Current reasoning thought or step"},
                    "thought_number": {"type": "integer", "description": "Step index (1-based)"},
                    "total_thoughts": {"type": "integer", "description": "Estimated total steps"},
                    "next_thought_needed": {"type": "boolean", "description": "Whether more thinking steps are needed"},
                    "is_revision": {"type": "boolean", "description": "Whether revising a prior thought", "default": False},
                    "revises_thought": {"type": "integer", "description": "Which thought index is being revised"},
                    "branch_from_thought": {"type": "integer", "description": "Branching point if testing an alternative"},
                    "branch_id": {"type": "string", "description": "Identifier for reasoning branch"}
                },
                "required": ["thought", "thought_number", "total_thoughts", "next_thought_needed"]
            },
            permission_level=PermissionLevel.LEVEL_1_SAFE,
            handler=tool_sequential_thinking
        ))

capability_registry = CapabilityRegistry()

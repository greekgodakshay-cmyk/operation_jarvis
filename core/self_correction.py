"""
Self-Correction and Error Recovery Engine for Operation Jarvis.
Diagnoses tool failures, generates alternative parameters, and manages bounded retries.
"""
from typing import Any, Dict, Optional, Tuple
from core.types import ExecutionStep, ToolResult
from core.llm_client import llm_client

class SelfCorrectionEngine:
    def should_retry(self, step: ExecutionStep, result: ToolResult, max_retries: int = 3) -> bool:
        if result.success:
            return False
        if step.retry_count >= max_retries:
            return False
        # Do not retry if policy strictly denied the operation or authentication is required
        err_str = str(result.error)
        if any(k in err_str for k in ["Permission Denied", "Sandbox Boundary Violation", "AUTHENTICATION_REQUIRED", "Authentication required", "Google Account login is required"]):
            return False
        return True

    def formulate_recovery_step(self, step: ExecutionStep, result: ToolResult) -> ExecutionStep:
        """Constructs an adjusted execution step based on the observed error."""
        step.retry_count += 1
        err = str(result.error).lower()
        new_args = dict(step.tool_arguments)

        # Common deterministic self-corrections:
        if "already exists and overwrite=false" in err:
            new_args["overwrite"] = True
            step.description += " (retrying with overwrite=True)"
            step.tool_arguments = new_args
            return step

        if "does not exist" in err and step.tool_name == "read_file":
            # Attempt to list directory of target file to inspect available names
            path_val = step.tool_arguments.get("path", "")
            from pathlib import Path
            parent_dir = str(Path(path_val).parent)
            step.tool_name = "list_dir"
            step.tool_arguments = {"path": parent_dir}
            step.description = f"Self-correcting: Inspecting directory '{parent_dir}' to locate file."
            return step

        # LLM-assisted correction for complex failures
        try:
            recovery_prompt = f"""A tool execution failed during an agentic task.
TOOL: {step.tool_name}
ARGUMENTS: {step.tool_arguments}
ERROR: {result.error}

Provide corrected JSON arguments to fix this error and achieve: '{step.description}'.
Return only JSON:
{{"tool_name": "{step.tool_name}", "tool_arguments": {{...}}, "reasoning": "..."}}
"""
            res = llm_client.chat([
                {"role": "system", "content": "You are a senior debugging engine. Return only JSON."},
                {"role": "user", "content": recovery_prompt}
            ], format_json=True, temperature=0.1)
            parsed = llm_client.extract_json(res["content"])
            if "tool_arguments" in parsed:
                step.tool_arguments = parsed["tool_arguments"]
                step.description += f" (Auto-repaired: {parsed.get('reasoning', 'adjusted args')})"
                return step
        except Exception:
            pass

        step.description += f" (Retry attempt {step.retry_count})"
        return step

self_correction_engine = SelfCorrectionEngine()

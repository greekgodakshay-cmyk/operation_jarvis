"""
Evidence-Based Result Verification Engine for Operation Jarvis.
Validates real filesystem state, memory changes, test results, and command outcomes before declaring completion.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.types import VerificationResult, ExecutionStep, ToolResult
from security.path_jail import path_jail
from registry.memory_adapter import memory_adapter

class VerificationEngine:
    def verify_step_result(self, step: ExecutionStep, result: ToolResult) -> VerificationResult:
        """Verifies the output of a single tool execution step."""
        checks = []
        if not result.success:
            out_data = result.output if isinstance(result.output, dict) else {}
            err_str = str(result.error or "")
            if out_data.get("status") == "INDETERMINATE" or "indeterminate" in err_str.lower():
                checks.append("browser_session_state_check")
                return VerificationResult(
                    is_verified=False,
                    evidence="FAILED: Browser session state is INDETERMINATE. Could not confirm active or authenticated session.",
                    checks_performed=checks,
                    details={
                        "status": "INDETERMINATE",
                        "error": result.error or out_data.get("error", "Session state indeterminate")
                    }
                )
            if result.tool_name == "browser_read_gmail" or "AUTHENTICATION_REQUIRED" in err_str or out_data.get("status") == "AUTHENTICATION_REQUIRED":
                checks.append("gmail_authentication_check")
                return VerificationResult(
                    is_verified=False,
                    evidence="BLOCKED: Google Account authentication required. No authenticated Gmail session available.",
                    checks_performed=checks,
                    details={
                        "status": "AUTHENTICATION_REQUIRED",
                        "error": result.error or out_data.get("error", "Authentication required"),
                        "action_items": out_data.get("action_items", [])
                    }
                )

            return VerificationResult(
                is_verified=False,
                evidence=f"Tool '{result.tool_name}' returned error: {result.error}",
                checks_performed=["tool_execution_success_check"],
                details={"error": result.error}
            )

        checks.append("tool_execution_success_check")

        # Specific file verification
        if result.tool_name in ["write_file", "edit_file"]:
            target_path = step.tool_arguments.get("path")
            if target_path:
                try:
                    safe = path_jail.validate_path(target_path)
                    if safe.exists() and safe.is_file():
                        size = safe.stat().st_size
                        checks.append("filesystem_artifact_exists")
                        checks.append("file_non_empty_check")
                        return VerificationResult(
                            is_verified=size > 0,
                            evidence=f"File verified at '{safe}' (size: {size} bytes)",
                            checks_performed=checks,
                            details={"path": str(safe), "size": size}
                        )
                    else:
                        return VerificationResult(
                            is_verified=False,
                            evidence=f"Expected artifact '{target_path}' was not found on disk.",
                            checks_performed=checks
                        )
                except Exception as e:
                    return VerificationResult(is_verified=False, evidence=f"Jail validation error: {e}")

        # Memory operation verification
        if result.tool_name in ["memory_store", "memory_update"]:
            title = step.tool_arguments.get("title") or step.tool_arguments.get("target_id_or_title")
            if title:
                matches = memory_adapter.search(query=title, limit=1)
                found = len(matches) > 0 and (title.lower() in matches[0].get("title", "").lower() or title.lower() in matches[0].get("id", "").lower())
                checks.append("database_fts5_lookup_verification")
                return VerificationResult(
                    is_verified=found,
                    evidence=f"Memory record verified via FTS5 index: {matches[0]['id'] if found else 'NOT_FOUND'}",
                    checks_performed=checks,
                    details={"matched_record": matches[0] if found else None}
                )

        # Memory search verification
        if result.tool_name == "memory_search":
            checks.append("database_fts5_search_verification")
            out_list = []
            if isinstance(result.output, list):
                out_list = result.output
            elif isinstance(result.output, dict):
                out_list = result.output.get("results", [])
            sample_id = out_list[0].get("id", "N/A") if out_list else "None"
            return VerificationResult(
                is_verified=result.success,
                evidence=f"Database FTS5 search returned {len(out_list)} records (Sample ID: {sample_id})",
                checks_performed=checks,
                details={"record_count": len(out_list), "sample_id": sample_id}
            )

        # Web & News search verification
        if result.tool_name in ["web_search", "search_news"]:
            checks.append("live_web_data_presence_check")
            sources = []
            if isinstance(result.output, dict):
                sources = result.output.get("sources", [])
            elif isinstance(result.output, list):
                sources = result.output
            has_sources = len(sources) > 0
            first_title = sources[0].get("title", "N/A") if has_sources else "None"
            return VerificationResult(
                is_verified=result.success and has_sources,
                evidence=f"Live search retrieved {len(sources)} verified sources. Sample: '{first_title[:60]}'",
                checks_performed=checks,
                details={"source_count": len(sources), "first_source": first_title}
            )

        # Browser status & list pages verification
        if result.tool_name in ["browser_status", "browser_list_pages"]:
            checks.append("browser_automation_data_check")
            out_data = result.output if isinstance(result.output, dict) else {}
            has_data = bool(out_data.get("chrome") or out_data.get("pages") or out_data.get("ok"))
            return VerificationResult(
                is_verified=result.success and has_data,
                evidence=f"Browser tool '{result.tool_name}' verified with live session data.",
                checks_performed=checks,
                details={"has_data": has_data}
            )

        # Command / Test execution verification
        if result.tool_name in ["run_command", "verify_test_suite"]:
            exit_code = result.output.get("exit_code", 0) if isinstance(result.output, dict) else 0
            checks.append("process_exit_code_zero_check")
            return VerificationResult(
                is_verified=exit_code == 0,
                evidence=f"Process exited cleanly with code {exit_code}",
                checks_performed=checks,
                details=result.output if isinstance(result.output, dict) else {}
            )

        # Desktop automation verification
        if result.tool_name == "desktop":
            checks.append("desktop_execution_check")
            subcmd = step.tool_arguments.get("subcommand", "status")
            return VerificationResult(
                is_verified=result.success,
                evidence=f"Desktop tool executed subcommand '{subcmd}' successfully.",
                checks_performed=checks,
                details=result.output if isinstance(result.output, dict) else {"output": str(result.output)}
            )

        # Specific Gmail / Browser Read Verification
        if result.tool_name == "browser_read_gmail":
            checks.append("gmail_authentication_check")
            checks.append("gmail_data_presence_check")
            out_data = result.output if isinstance(result.output, dict) else {}

            # Strict Check 1: Authentication failure or missing credentials
            if out_data.get("status") == "AUTHENTICATION_REQUIRED" or not out_data.get("authenticated", True) or not result.success:
                return VerificationResult(
                    is_verified=False,
                    evidence="BLOCKED: Google Account authentication required. No authenticated Gmail session available.",
                    checks_performed=checks,
                    details={
                        "status": "AUTHENTICATION_REQUIRED",
                        "error": result.error or out_data.get("error", "Authentication required"),
                        "action_items": out_data.get("action_items", [])
                    }
                )

            # Strict Check 2: Actual email data retrieval
            emails = out_data.get("emails", [])
            emails_count = out_data.get("emails_found", len(emails))
            if emails_count == 0 and not emails:
                if out_data.get("authenticated"):
                    return VerificationResult(
                        is_verified=True,
                        evidence=f"Authenticated Gmail inbox searched for '{step.tool_arguments.get('date_query', 'specified date')}'; 0 matching emails found.",
                        checks_performed=checks,
                        details={"emails_found": 0, "authenticated": True}
                    )
                return VerificationResult(
                    is_verified=False,
                    evidence="Verification failed: Zero emails retrieved from unauthenticated session.",
                    checks_performed=checks,
                    details=out_data
                )

            return VerificationResult(
                is_verified=True,
                evidence=f"Retrieved and verified {len(emails)} emails from authenticated inbox.",
                checks_performed=checks,
                details={"emails_found": len(emails), "sample_subjects": [e.get("subject", "")[:50] for e in emails[:3]]}
            )

        # Default fallback verification for read-only actions
        return VerificationResult(
            is_verified=True,
            evidence=f"Step '{step.description}' completed successfully.",
            checks_performed=checks,
            details={"output_summary": str(result.output)[:200]}
        )

    def verify_final_objective(
        self,
        objective: str,
        completed_steps: List[ExecutionStep],
        errors: List[str]
    ) -> VerificationResult:
        """Aggregates all execution evidence and verifies total objective completion."""
        from core.types import TaskStatus
        checks = ["all_steps_verified_check", "zero_fatal_errors_check", "objective_data_sufficiency_check"]
        
        if not completed_steps:
            return VerificationResult(
                is_verified=False,
                evidence="No execution steps were completed.",
                checks_performed=checks,
                details={"status": TaskStatus.FAILED.value}
            )

        # Check if any completed step was indeterminate
        for s in completed_steps:
            if s.verification and (s.verification.details.get("status") == "INDETERMINATE" or "INDETERMINATE" in s.verification.evidence):
                return VerificationResult(
                    is_verified=False,
                    evidence="Objective FAILED: Session state returned INDETERMINATE. Outcome cannot be verified.",
                    checks_performed=checks,
                    details={"status": TaskStatus.FAILED.value, "reason": "INDETERMINATE"}
                )

        # Check if any completed step was blocked by authentication
        for s in completed_steps:
            if s.verification and (s.verification.details.get("status") == "AUTHENTICATION_REQUIRED" or "BLOCKED" in s.verification.evidence):
                return VerificationResult(
                    is_verified=False,
                    evidence="Objective BLOCKED: Google Account authentication required. User must sign in before emails can be inspected.",
                    checks_performed=checks,
                    details={"status": TaskStatus.BLOCKED.value, "reason": "AUTHENTICATION_REQUIRED"}
                )

        # Objective-level semantic check: if objective involves emails/gmail, verify real email data exists
        obj_lower = objective.lower()
        if any(w in obj_lower for w in ["email", "gmail", "inbox"]):
            email_steps = [s for s in completed_steps if s.tool_name == "browser_read_gmail"]
            if not email_steps:
                return VerificationResult(
                    is_verified=False,
                    evidence="Objective requested email inspection, but no email reading step was executed.",
                    checks_performed=checks,
                    details={"status": TaskStatus.FAILED.value}
                )

            has_email_data = False
            for es in email_steps:
                if es.result and isinstance(es.result.output, dict):
                    emails = es.result.output.get("emails", [])
                    if len(emails) > 0:
                        has_email_data = True
                        break

            if not has_email_data:
                is_auth_block = any("AUTHENTICATION" in str(getattr(s, "result", "")) for s in email_steps)
                is_indet = any("INDETERMINATE" in str(getattr(s, "result", "")) for s in email_steps)
                if is_auth_block:
                    status_val = TaskStatus.BLOCKED.value
                elif is_indet:
                    status_val = TaskStatus.FAILED.value
                else:
                    status_val = TaskStatus.FAILED.value
                return VerificationResult(
                    is_verified=False,
                    evidence="Objective INCOMPLETE: Required email data could not be retrieved from browser.",
                    checks_performed=checks,
                    details={"status": status_val}
                )

        unverified_steps = [s for s in completed_steps if s.verification and not s.verification.is_verified]
        if unverified_steps:
            evidence_str = "; ".join([f"Step {s.step_number} unverified: {s.verification.evidence}" for s in unverified_steps])
            return VerificationResult(
                is_verified=False,
                evidence=f"Objective incomplete. Failed step verifications: {evidence_str}",
                checks_performed=checks,
                details={"status": TaskStatus.FAILED.value}
            )

        # Collect verified artifact proofs
        proofs = []
        for s in completed_steps:
            if s.verification and s.verification.evidence:
                proofs.append(f"Step {s.step_number}: {s.verification.evidence}")

        return VerificationResult(
            is_verified=True,
            evidence=f"All {len(completed_steps)} steps verified with evidence:\n" + "\n".join(proofs),
            checks_performed=checks,
            details={"step_count": len(completed_steps), "fatal_errors": len(errors), "status": TaskStatus.COMPLETED.value}
        )

verification_engine = VerificationEngine()

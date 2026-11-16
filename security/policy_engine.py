"""
Central Policy and Permission Enforcement Engine.
Enforces Level 1 (Safe), Level 2 (Controlled), and Level 3 (Restricted with Approval).
"""
import uuid
from typing import Any, Dict, Optional, Tuple
from core.types import PermissionLevel, ToolCall, ApprovalRequest
from security.path_jail import path_jail, PathJailViolation
from security.command_validator import command_validator, CommandValidationError
from security.secret_redactor import redact_structure

class PolicyViolationError(Exception):
    pass

class ApprovalRequiredError(Exception):
    def __init__(self, approval_request: ApprovalRequest):
        super().__init__(f"Action requires explicit user approval: {approval_request.reason}")
        self.approval_request = approval_request

class PolicyEngine:
    def __init__(self):
        # In-memory store for approved request IDs
        self._approved_tokens: set = set()
        self._emergency_stopped: bool = False

    def trigger_emergency_stop(self) -> Dict[str, Any]:
        """Instantly revokes all approvals and halts all execution gates."""
        self._emergency_stopped = True
        self._approved_tokens.clear()
        return {
            "ok": True,
            "status": "EMERGENCY_STOP_ACTIVATED",
            "message": "All execution channels locked. Approvals revoked."
        }

    def reset_emergency_stop(self) -> Dict[str, Any]:
        """Clears emergency stop and returns policy engine to standard operation."""
        self._emergency_stopped = False
        return {
            "ok": True,
            "status": "OPERATIONAL",
            "message": "Emergency stop cleared. Policy engine operational."
        }

    def is_emergency_stopped(self) -> bool:
        return self._emergency_stopped

    def grant_approval(self, request_id: str) -> bool:
        if self._emergency_stopped:
            return False
        self._approved_tokens.add(request_id)
        return True

    def revoke_approval(self, request_id: str):
        self._approved_tokens.discard(request_id)

    def is_approved(self, request_id: str) -> bool:
        if self._emergency_stopped:
            return False
        return request_id in self._approved_tokens

    def check_permission(
        self,
        tool_name: str,
        permission_level: PermissionLevel,
        arguments: Dict[str, Any],
        approval_token: Optional[str] = None,
        task_id: str = "check",
        step_number: int = 1
    ) -> Tuple[bool, str]:
        tool_call = ToolCall(
            call_id="check",
            tool_name=tool_name,
            arguments=arguments,
            permission_level=permission_level
        )
        can_exec, req, reason = self.evaluate_tool_execution(task_id, step_number, tool_call, approval_token)
        return can_exec, reason

    def evaluate_tool_execution(
        self,
        task_id: str,
        step_number: int,
        tool_call: ToolCall,
        approval_token: Optional[str] = None
    ) -> Tuple[bool, Optional[ApprovalRequest], str]:
        """
        Evaluates whether a tool call may proceed.
        Returns: (can_execute, optional_approval_request, reason)
        """
        # 0. Emergency Stop Interception
        if self._emergency_stopped:
            return False, None, "EMERGENCY STOP ACTIVE: All operations are strictly halted."

        # Redact secrets in arguments for security review
        clean_args = redact_structure(tool_call.arguments)
        level = tool_call.permission_level

        # Level 1 Safe: Always permitted after basic path bounds checking if path is present
        if level == PermissionLevel.LEVEL_1_SAFE:
            if "path" in tool_call.arguments:
                try:
                    path_jail.validate_path(tool_call.arguments["path"])
                except PathJailViolation as e:
                    return False, None, f"Level 1 Path Jail Violation: {e}"
            return True, None, "Level 1 Safe inspection action permitted."

        # Level 2 Controlled: Permitted if paths and commands pass validation
        if level == PermissionLevel.LEVEL_2_CONTROLLED:
            if "path" in tool_call.arguments:
                try:
                    path_jail.validate_path(tool_call.arguments["path"])
                except PathJailViolation as e:
                    return False, None, f"Level 2 Path Jail Violation: {e}"

            if tool_call.tool_name in ["run_command", "shell_execute"]:
                cmd = tool_call.arguments.get("command", "")
                is_allowed, cmd_level, reason = command_validator.validate_and_classify(cmd)
                if not is_allowed:
                    return False, None, f"Command Rejected: {reason}"
                if cmd_level == PermissionLevel.LEVEL_3_RESTRICTED:
                    # Elevate to Level 3 approval
                    req = self._create_approval_request(task_id, step_number, tool_call, reason)
                    if approval_token and self.is_approved(approval_token):
                        return True, None, f"Level 3 Approved by user token '{approval_token}'."
                    return False, req, f"Escalated to Level 3 Restricted: {reason}"

            return True, None, "Level 2 Controlled operation validated and permitted."

        # Level 3 Restricted: Requires explicit human approval gate
        if level == PermissionLevel.LEVEL_3_RESTRICTED:
            # Check if this exact action was already approved via token
            if approval_token and self.is_approved(approval_token):
                return True, None, f"Level 3 Restricted operation approved with token '{approval_token}'."

            # Construct ApprovalRequest
            reason = f"Restricted operation '{tool_call.tool_name}' requires human confirmation."
            req = self._create_approval_request(task_id, step_number, tool_call, reason)
            return False, req, reason

        return False, None, "Unknown permission level."

    def _create_approval_request(
        self,
        task_id: str,
        step_number: int,
        tool_call: ToolCall,
        reason: str
    ) -> ApprovalRequest:
        from datetime import datetime
        req_id = f"appr-{uuid.uuid4().hex[:10]}"
        return ApprovalRequest(
            request_id=req_id,
            task_id=task_id,
            step_number=step_number,
            tool_name=tool_call.tool_name,
            arguments=redact_structure(tool_call.arguments),
            reason=reason,
            permission_level=PermissionLevel.LEVEL_3_RESTRICTED,
            created_at=datetime.now().isoformat(),
            is_granted=None
        )

policy_engine = PolicyEngine()

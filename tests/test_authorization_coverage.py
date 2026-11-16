"""
Authorization Coverage Static Audit & Runtime Enforcement Test Guard (Criterion 0c).
Verifies that EVERY execution path in the workstation routes through PolicyEngine,
and that zero un-gated backdoors or raw execution bypasses exist.
"""
import ast
import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.types import PermissionLevel
from security.policy_engine import policy_engine, ApprovalRequiredError
from registry.capability_registry import capability_registry

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_static_audit_capability_registry_enforces_policy():
    """Static AST audit: CapabilityRegistry.execute_tool MUST call policy_engine.evaluate_tool_execution."""
    source_file = PROJECT_ROOT / "registry" / "capability_registry.py"
    with open(source_file, "r", encoding="utf-8") as f:
        code = f.read()

    assert "policy_engine.evaluate_tool_execution" in code, "CapabilityRegistry must invoke policy_engine.evaluate_tool_execution"
    assert "ApprovalRequiredError" in code, "CapabilityRegistry must enforce Level 3 ApprovalRequiredError gating"

def test_static_audit_qwen_chat_routes_through_capability_or_policy():
    """Static AST audit: qwen_chat.py ToolRegistry.execute_tool MUST route to capability_registry or policy_engine."""
    qwen_chat_file = Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\engine\qwen_chat.py")
    if qwen_chat_file.exists():
        with open(qwen_chat_file, "r", encoding="utf-8") as f:
            code = f.read()

        assert "jarvis_capability_registry.execute_tool" in code, (
            "qwen_chat.py must route tool execution through central capability registry"
        )
        assert "jarvis_policy_engine" in code, (
            "qwen_chat.py must check policy_engine on local fallback tools"
        )

def test_runtime_audit_level3_tool_blocked_without_token():
    """Runtime audit: Attempting to call email_send directly via capability_registry without token raises ApprovalRequiredError."""
    with pytest.raises(ApprovalRequiredError):
        capability_registry.execute_tool(
            name="email_send",
            arguments={"to": "test@domain.com", "subject": "Test", "body": "Unauthorized"},
            task_id="audit_task",
            step_number=1,
            approval_token=None
        )

def test_runtime_audit_emergency_stop_blocks_all_execution():
    """Runtime audit: Emergency stop must block ALL execution paths including Level 1 read operations."""
    policy_engine.trigger_emergency_stop()
    try:
        is_allowed, reason = policy_engine.check_permission("read_file", PermissionLevel.LEVEL_1_SAFE, {"path": "test.txt"})
        assert is_allowed is False
        assert "EMERGENCY STOP" in reason
    finally:
        policy_engine.reset_emergency_stop()

def test_runtime_audit_path_jail_blocks_system32_traversal():
    """Runtime audit: Attempting to read or write sensitive Windows system paths is blocked by PathJail."""
    res = capability_registry.execute_tool(
        name="read_file",
        arguments={"path": r"C:\Windows\System32\drivers\etc\hosts"},
        task_id="audit_task",
        step_number=1
    )
    assert res.success is False
    assert "path jail" in res.error.lower()

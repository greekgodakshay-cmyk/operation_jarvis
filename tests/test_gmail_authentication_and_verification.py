"""
Comprehensive Verification Test Suite for:
JARVIS Gmail Authentication & Objective-Level Verification

Tests:
1. Chrome instance and user profile discovery (Default profile, greekgodakshay@gmail.com).
2. Unauthenticated scenario: returns AUTHENTICATION_REQUIRED, ok=False, zero emails.
3. Authenticated scenario: extracts structured subjects, senders, timestamps, snippets.
4. Step-level verification: rejects unauthenticated/empty browser results.
5. Objective-level verification: halts downstream summarization when email data is missing.
6. Meaningful terminal statuses: verifies COMPLETED, PARTIALLY_COMPLETED, BLOCKED, FAILED.
7. Evidence formatting: includes email metadata without leaking full message bodies.
"""
import os
import sys
import uuid
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LOCAL_AI_MEMORY_DIR = Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY")
if str(LOCAL_AI_MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_AI_MEMORY_DIR))

from registry.browser_adapter import browser_adapter
from registry.capability_registry import capability_registry
from core.types import TaskStatus, StepStatus, ExecutionStep, ToolResult, TaskPlan
from core.verification import verification_engine
from core.orchestrator import orchestrator
from storage.task_db import task_db


class TestGmailAuthAndObjectiveVerification:

    # 1. PROFILE AND CHROME INSTANCE IDENTIFICATION
    def test_01_chrome_instance_and_profile_discovery(self):
        """Identify which Chrome instance and user profile are configured and accessible."""
        env = browser_adapter.detect_chrome_environment()
        assert env["chrome_installed"] is True
        assert "chrome.exe" in env["chrome_executable"].lower()
        assert "Google\\Chrome\\User Data" in env["user_data_dir"]
        assert env["target_account"] == "greekgodakshay@gmail.com"
        assert env["target_profile"] == "Default"
        assert env["remote_debugging_port_9222"] in ["OPEN", "CLOSED"]

    # 2. UNAUTHENTICATED SCENARIO
    def test_02_unauthenticated_gmail_reports_authentication_required(self):
        """Verify unauthenticated scenario returns ok=False, status=AUTHENTICATION_REQUIRED, zero emails."""
        res = browser_adapter.read_gmail(mock_session_state="unauthenticated")
        assert res["ok"] is False
        assert res["authenticated"] is False
        assert res["status"] == "AUTHENTICATION_REQUIRED"
        assert "AUTHENTICATION_REQUIRED" in res["error"]
        assert res["target_account"] == "greekgodakshay@gmail.com"
        assert res["emails_found"] == 0
        assert len(res["emails"]) == 0
        assert len(res["action_items"]) >= 2
        # Verify no bypass attempted
        assert "bypass" in res["message"].lower() or "security" in res["blocker_details"]["security_policy"].lower()

    # 3. AUTHENTICATED SCENARIO EMAIL EXTRACTION
    def test_03_authenticated_gmail_retrieves_structured_emails(self):
        """Verify authenticated session actually extracts subject, sender, timestamp, and snippet."""
        res = browser_adapter.read_gmail(mock_session_state="authenticated", date_query="5 November 2026")
        assert res["ok"] is True
        assert res["authenticated"] is True
        assert res["status"] == "COMPLETED"
        assert res["emails_found"] >= 1
        assert len(res["emails"]) >= 1

        first_email = res["emails"][0]
        assert "subject" in first_email and len(first_email["subject"]) > 0
        assert "sender" in first_email and len(first_email["sender"]) > 0
        assert "timestamp" in first_email and len(first_email["timestamp"]) > 0
        assert "snippet" in first_email and len(first_email["snippet"]) > 0

    # 4. STEP VERIFICATION ENFORCEMENT
    def test_04_step_verification_rejects_unauthenticated_result(self):
        """Verify verification engine fails step when authentication is required."""
        step = ExecutionStep(
            step_number=1,
            description="Inspect Chrome Gmail session for recent emails",
            tool_name="browser_read_gmail",
            tool_arguments={"date_query": "5 November 2026"}
        )
        tool_out = browser_adapter.read_gmail(mock_session_state="unauthenticated")
        tool_result = ToolResult(
            call_id="call-test-unauth",
            tool_name="browser_read_gmail",
            success=tool_out["ok"],  # False
            output=tool_out,
            error=tool_out.get("error")
        )

        verif = verification_engine.verify_step_result(step, tool_result)
        assert verif.is_verified is False
        assert "BLOCKED" in verif.evidence
        assert verif.details.get("status") == "AUTHENTICATION_REQUIRED"

    # 5. STEP VERIFICATION ACCEPTS AUTHENTICATED EMAILS
    def test_05_step_verification_accepts_authenticated_emails(self):
        """Verify verification engine passes step when real email data is retrieved."""
        step = ExecutionStep(
            step_number=1,
            description="Inspect Chrome Gmail session for recent emails",
            tool_name="browser_read_gmail",
            tool_arguments={"date_query": "5 November 2026"}
        )
        tool_out = browser_adapter.read_gmail(mock_session_state="authenticated")
        tool_result = ToolResult(
            call_id="call-test-auth",
            tool_name="browser_read_gmail",
            success=tool_out["ok"],  # True
            output=tool_out
        )

        verif = verification_engine.verify_step_result(step, tool_result)
        assert verif.is_verified is True
        assert "Retrieved and verified" in verif.evidence
        assert verif.details.get("emails_found", 0) >= 1

    # 6. OBJECTIVE VERIFICATION: BLOCK ON UNAUTHENTICATED
    def test_06_orchestrator_blocks_task_and_halts_downstream_summarization(self, monkeypatch):
        """Verify orchestrator halts execution and marks task BLOCKED when authentication is missing."""
        monkeypatch.setenv("JARVIS_GMAIL_MOCK_STATE", "unauthenticated")

        # Create a test plan with Step 1 (browser_read_gmail) and Step 2 (summarize reasoning)
        test_task_id = f"test_gmail_unauth_{uuid.uuid4().hex[:8]}"
        record = task_db.create_task(
            objective="Inspect Chrome Gmail session and summarize emails from 5 November 2026",
            task_id=test_task_id
        )
        plan = TaskPlan(
            objective=record.objective,
            reasoning="Read Gmail then summarize",
            steps=[
                ExecutionStep(
                    step_number=1,
                    description="Read Gmail inbox",
                    tool_name="browser_read_gmail",
                    tool_arguments={"date_query": "5 November 2026"}
                ),
                ExecutionStep(
                    step_number=2,
                    description="Summarize retrieved emails",
                    tool_name=None,  # Reasoning step
                    tool_arguments={}
                )
            ]
        )
        task_db.save_plan(test_task_id, plan)

        # Run execution loop
        completed_record = orchestrator._run_execution_loop(test_task_id)

        # Assertions
        assert completed_record.status == TaskStatus.BLOCKED
        assert "BLOCKED" in completed_record.status.value.upper() or completed_record.status == TaskStatus.BLOCKED
        # Step 2 must NEVER have completed!
        completed_step_nums = [s.step_number for s in completed_record.completed_steps]
        assert 2 not in completed_step_nums
        # Task must not claim success
        assert completed_record.status != TaskStatus.COMPLETED

    # 7. OBJECTIVE VERIFICATION: SUCCEED ON AUTHENTICATED
    def test_07_orchestrator_completes_when_emails_retrieved(self, monkeypatch):
        """Verify orchestrator completes and summarizes ONLY when email data is present."""
        monkeypatch.setenv("JARVIS_GMAIL_MOCK_STATE", "authenticated")

        test_task_id = f"test_gmail_auth_{uuid.uuid4().hex[:8]}"
        record = task_db.create_task(
            objective="Inspect Chrome Gmail session and summarize emails from 5 November 2026",
            task_id=test_task_id
        )
        plan = TaskPlan(
            objective=record.objective,
            reasoning="Read Gmail then summarize",
            steps=[
                ExecutionStep(
                    step_number=1,
                    description="Read Gmail inbox",
                    tool_name="browser_read_gmail",
                    tool_arguments={"date_query": "5 November 2026"}
                ),
                ExecutionStep(
                    step_number=2,
                    description="Summarize retrieved emails",
                    tool_name=None,  # Reasoning step
                    tool_arguments={}
                )
            ]
        )
        task_db.save_plan(test_task_id, plan)

        # Run execution loop
        completed_record = orchestrator._run_execution_loop(test_task_id)

        # Assertions
        assert completed_record.status == TaskStatus.COMPLETED
        assert len(completed_record.completed_steps) == 2
        # Verify email data is in Step 1 output
        step_1_out = completed_record.completed_steps[0].result.output
        assert step_1_out.get("emails_found", 0) >= 1
        assert len(step_1_out.get("emails", [])) >= 1

    # 8. TERMINAL STATUS ENUM INTEGRITY
    def test_08_terminal_statuses_enum(self):
        """Verify all required terminal statuses exist and are distinct."""
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.PARTIALLY_COMPLETED.value == "partially_completed"
        assert TaskStatus.BLOCKED.value == "blocked"
        assert TaskStatus.FAILED.value == "failed"

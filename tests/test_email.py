import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from registry.email_adapter import email_adapter
from security.policy_engine import policy_engine, ApprovalRequiredError
from registry.capability_registry import capability_registry

def test_email_search_and_read():
    results = email_adapter.search_emails("internship")
    assert len(results) >= 1
    assert "internship" in results[0]["subject"].lower()

    # Read email
    msg = email_adapter.read_email(results[0]["id"])
    assert msg is not None
    assert msg["is_read"] == 1
    assert "advising@university.edu" in msg["sender"]

def test_email_classify():
    res = email_adapter.classify_email("msg-002")
    assert res["ok"] is True
    assert res["category"] == "security"
    assert res["urgency"] == "high"

def test_email_summarize():
    res = email_adapter.summarize_thread("thread-001")
    assert res["ok"] is True
    assert "Fall Internship Documentation Review" in res["subject"]
    assert "Internship Advisory Board" in res["summary"]

def test_email_draft_creation():
    draft = email_adapter.create_draft(
        recipient="mentor@university.edu",
        subject="Internship Tracker Submission Update",
        body="Attached is my completed progress report and tracker update."
    )
    assert draft["ok"] is True
    assert draft["status"] == "draft"
    assert "approval" in draft["message"].lower()

def test_email_send_requires_approval_gate():
    # Attempting to send without approval token MUST raise ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError) as exc_info:
        email_adapter.send_email(
            recipient="test@example.com",
            subject="Test Restricted Action",
            body="Should fail without token"
        )
    appr_req = exc_info.value.approval_request
    assert appr_req.tool_name == "email_send"
    assert appr_req.permission_level.value == 3

    # Now grant approval for this token
    token = appr_req.request_id
    policy_engine.grant_approval(token)

    # Sending with approved token must succeed
    send_res = email_adapter.send_email(
        recipient="test@example.com",
        subject="Test Restricted Action",
        body="Should succeed now",
        approval_token=token
    )
    assert send_res["ok"] is True
    assert send_res["status"] == "SENT"
    assert send_res["approval_token"] == token

def test_capability_registry_email_tools():
    tool_names = {t["name"] for t in capability_registry.list_tools()}
    assert "email_search" in tool_names
    assert "email_read" in tool_names
    assert "email_classify" in tool_names
    assert "email_summarize" in tool_names
    assert "email_draft" in tool_names
    assert "email_send" in tool_names

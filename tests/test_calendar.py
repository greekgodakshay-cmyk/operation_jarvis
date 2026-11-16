import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from registry.calendar_adapter import calendar_adapter
from security.policy_engine import policy_engine, ApprovalRequiredError
from registry.capability_registry import capability_registry

def test_calendar_get_events():
    events = calendar_adapter.get_events()
    assert len(events) >= 2
    titles = [e["title"] for e in events]
    assert "Operation Jarvis Architecture Review" in titles

def test_calendar_availability():
    # Slot during evt-001 (2026-11-07 10:00 to 11:00)
    busy = calendar_adapter.check_availability("2026-11-07T10:15:00", "2026-11-07T10:45:00")
    assert busy["available"] is False
    assert busy["conflict_count"] >= 1

    # Empty slot
    free = calendar_adapter.check_availability("2026-11-07T12:00:00", "2026-11-07T13:00:00")
    assert free["available"] is True
    assert free["conflict_count"] == 0

def test_calendar_create_and_duplicate_prevention():
    import uuid
    uid = uuid.uuid4().hex[:6]
    start = "2026-11-09T11:00:00"
    end = "2026-11-09T12:00:00"
    title = f"Workstation Security Hardening Session {uid}"

    # First creation must succeed
    res1 = calendar_adapter.create_event(
        title=title,
        start_time=start,
        end_time=end,
        description="Review Tailscale Serve and token revocation."
    )
    assert res1["ok"] is True
    assert res1["title"] == title

    # Second creation with identical title and start time MUST be rejected as duplicate
    res2 = calendar_adapter.create_event(
        title=title,
        start_time=start,
        end_time=end,
        description="Duplicate attempt"
    )
    assert res2["ok"] is False
    assert "duplicate" in res2["error"].lower()

def test_calendar_slot_suggestions():
    slots = calendar_adapter.suggest_slots(duration_minutes=30, day_date="2026-11-10")
    assert len(slots) > 0
    assert "start_time" in slots[0]
    assert slots[0]["duration_minutes"] == 30

def test_calendar_cancel_requires_approval():
    # Attempting to cancel without approval token MUST raise ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError) as exc_info:
        calendar_adapter.cancel_event("evt-002")
    
    appr_req = exc_info.value.approval_request
    assert appr_req.tool_name == "calendar_cancel_event"
    assert appr_req.permission_level.value == 3

    # Grant approval
    token = appr_req.request_id
    policy_engine.grant_approval(token)

    # Cancel with token must succeed
    res = calendar_adapter.cancel_event("evt-002", approval_token=token)
    assert res["ok"] is True
    assert res["status"] == "cancelled"

def test_capability_registry_calendar_tools():
    tool_names = {t["name"] for t in capability_registry.list_tools()}
    assert "calendar_get_events" in tool_names
    assert "calendar_check_availability" in tool_names
    assert "calendar_suggest_slots" in tool_names
    assert "calendar_create_event" in tool_names
    assert "calendar_cancel_event" in tool_names

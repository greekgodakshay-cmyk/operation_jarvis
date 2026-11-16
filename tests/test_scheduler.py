import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.scheduler import persistent_scheduler
from storage.scheduler_db import SchedulerDB

def test_schedule_lifecycle_and_persistence():
    # 1. Create an interval schedule
    sched = persistent_scheduler.create_schedule(
        name="Test Memory Health Check",
        schedule_type="interval",
        schedule_expr="3600",
        objective="Verify local memory integrity",
        start_delay_seconds=3600,
        max_runs=5,
        requires_approval=False
    )
    assert sched is not None
    sid = sched["id"]
    assert sched["status"] == "active"
    assert sched["name"] == "Test Memory Health Check"

    # 2. Pause
    ok_pause = persistent_scheduler.pause_schedule(sid)
    assert ok_pause is True
    s_paused = persistent_scheduler.get_schedule(sid)
    assert s_paused["status"] == "paused"

    # 3. Resume
    ok_resume = persistent_scheduler.resume_schedule(sid)
    assert ok_resume is True
    s_resumed = persistent_scheduler.get_schedule(sid)
    assert s_resumed["status"] == "active"

    # 4. Duplicate execution / Lock Acquisition Test
    locked_first = persistent_scheduler.db.acquire_schedule_lock(sid)
    assert locked_first is True
    # Second acquisition must fail (duplicate run protection)
    locked_second = persistent_scheduler.db.acquire_schedule_lock(sid)
    assert locked_second is False

    # Release lock
    persistent_scheduler.db.release_schedule_lock(sid, next_run_at=None, success=True)
    s_unlocked = persistent_scheduler.get_schedule(sid)
    assert s_unlocked["is_running"] == 0
    assert s_unlocked["run_count"] == 1

    # 5. Verify persistence across restarts: instantiate a new SchedulerDB instance
    new_db = SchedulerDB(persistent_scheduler.db.db_path)
    persisted = new_db.get_schedule(sid)
    assert persisted is not None
    assert persisted["id"] == sid
    assert persisted["name"] == "Test Memory Health Check"
    assert persisted["run_count"] == 1

    # 6. Cancel
    ok_cancel = persistent_scheduler.cancel_schedule(sid)
    assert ok_cancel is True
    s_cancelled = persistent_scheduler.get_schedule(sid)
    assert s_cancelled["status"] == "cancelled"

def test_capability_registry_schedule_tools():
    from registry.capability_registry import capability_registry
    tool_names = {t["name"] for t in capability_registry.list_tools()}
    assert "schedule_create" in tool_names
    assert "schedule_list" in tool_names
    assert "schedule_control" in tool_names

    # Test listing via tool
    res = capability_registry.get_tool("schedule_list").handler()
    assert res["ok"] is True
    assert "schedules" in res

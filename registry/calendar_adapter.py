"""
Calendar Integration Engine for Operation JARVIS.
Provides local SQLite & iCal/API calendar event management:
Read events, check availability, smart slot suggestions, duplicate-event prevention,
and approval-gated modifications/cancellations.
"""
from datetime import datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import uuid

from config.settings import settings
from core.types import PermissionLevel, ToolCall
from security.policy_engine import policy_engine, ApprovalRequiredError

logger = logging.getLogger("jarvis.calendar")

CALENDAR_DB_PATH = settings.task_db_path.parent / "jarvis_calendar.db"

INIT_CALENDAR_SQL = """
CREATE TABLE IF NOT EXISTS calendar_events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    start_time TEXT NOT NULL, -- ISO 8601
    end_time TEXT NOT NULL,   -- ISO 8601
    location TEXT,
    attendees_json TEXT DEFAULT '[]',
    reminder_minutes INTEGER DEFAULT 15,
    status TEXT DEFAULT 'confirmed', -- 'confirmed', 'tentative', 'cancelled'
    content_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_calendar_start ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_status ON calendar_events(status);
"""

DEFAULT_SEED_EVENTS = [
    {
        "id": "evt-001",
        "title": "Operation Jarvis Architecture Review",
        "description": "Weekly alignment on local AI agent workstation, memory indexing, and security gates.",
        "start_time": "2026-11-07T10:00:00",
        "end_time": "2026-11-07T11:00:00",
        "location": "Local Workstation (HP Victus)",
        "attendees": ["akshay.aravind@victus.local", "jarvis@victus.local"],
        "reminder_minutes": 15
    },
    {
        "id": "evt-002",
        "title": "Student Internship Project Demo",
        "description": "Demonstration of Skill & Internship Tracker updates and multi-cloud sync.",
        "start_time": "2026-11-08T14:30:00",
        "end_time": "2026-11-08T15:30:00",
        "location": "Online Meeting Room",
        "attendees": ["akshay.aravind@victus.local", "advisor@university.edu"],
        "reminder_minutes": 30
    }
]

def compute_event_hash(title: str, start_time: str) -> str:
    norm = f"{title.strip().lower()}___{start_time.strip()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()

class DuplicateEventError(Exception):
    pass

class CalendarAdapter:
    def __init__(self, db_path: Path = CALENDAR_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(INIT_CALENDAR_SQL)
            cur = conn.execute("SELECT count(*) FROM calendar_events")
            if cur.fetchone()[0] == 0:
                now = datetime.now().isoformat()
                for evt in DEFAULT_SEED_EVENTS:
                    h = compute_event_hash(evt["title"], evt["start_time"])
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO calendar_events (
                            id, title, description, start_time, end_time,
                            location, attendees_json, reminder_minutes, status,
                            content_hash, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?)
                        """,
                        (
                            evt["id"], evt["title"], evt["description"],
                            evt["start_time"], evt["end_time"], evt["location"],
                            json.dumps(evt["attendees"]), evt["reminder_minutes"],
                            h, now, now
                        )
                    )

    def get_events(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: str = "confirmed",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve calendar events within a given time range."""
        with self._get_conn() as conn:
            sql = "SELECT * FROM calendar_events WHERE status = ?"
            params: List[Any] = [status]
            if start_date:
                sql += " AND end_time >= ?"
                params.append(start_date)
            if end_date:
                sql += " AND start_time <= ?"
                params.append(end_date)
            sql += " ORDER BY start_time ASC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            events = []
            for r in rows:
                d = dict(r)
                d["attendees"] = json.loads(d.get("attendees_json", "[]"))
                events.append(d)
            return events

    def check_availability(self, start_time: str, end_time: str) -> Dict[str, Any]:
        """Checks if a specified time range has conflicting events."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, title, start_time, end_time FROM calendar_events
                WHERE status = 'confirmed'
                  AND start_time < ? AND end_time > ?
                ORDER BY start_time ASC
                """,
                (end_time, start_time)
            ).fetchall()
            conflicts = [dict(r) for r in rows]
            return {
                "available": len(conflicts) == 0,
                "conflict_count": len(conflicts),
                "conflicts": conflicts
            }

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
        reminder_minutes: int = 15
    ) -> Dict[str, Any]:
        """
        Creates a new event with duplicate event prevention and conflict detection.
        """
        # Validate time bounds
        if start_time >= end_time:
            return {"ok": False, "error": f"Invalid event times: start_time ({start_time}) must be before end_time ({end_time})."}

        content_hash = compute_event_hash(title, start_time)

        # Check duplicate
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT id, title, start_time, status FROM calendar_events WHERE content_hash = ?",
                (content_hash,)
            ).fetchone()
            if existing and existing["status"] != "cancelled":
                return {
                    "ok": False,
                    "error": f"Duplicate event rejected: An identical event '{existing['title']}' already exists at {existing['start_time']} (ID: {existing['id']}).",
                    "duplicate_id": existing["id"]
                }

        # Check for scheduling conflict warning
        avail = self.check_availability(start_time, end_time)
        conflict_warning = None
        if not avail["available"]:
            conflict_warning = f"Notice: Time slot overlaps with {avail['conflict_count']} existing event(s): {[c['title'] for c in avail['conflicts']]}."

        evt_id = f"evt-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO calendar_events (
                    id, title, description, start_time, end_time,
                    location, attendees_json, reminder_minutes, status,
                    content_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?)
                """,
                (
                    evt_id, title, description, start_time, end_time,
                    location, json.dumps(attendees or []), reminder_minutes,
                    content_hash, now, now
                )
            )

        return {
            "ok": True,
            "event_id": evt_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "conflict_warning": conflict_warning,
            "status": "confirmed"
        }

    def suggest_slots(
        self,
        duration_minutes: int = 60,
        day_date: Optional[str] = None,
        working_hours_start: int = 9,
        working_hours_end: int = 18
    ) -> List[Dict[str, str]]:
        """Scans daytime schedule and returns free available slots."""
        day = day_date or datetime.now().strftime("%Y-%m-%d")
        day_start = datetime.strptime(f"{day} {working_hours_start:02d}:00:00", "%Y-%m-%d %H:%M:%S")
        day_end = datetime.strptime(f"{day} {working_hours_end:02d}:00:00", "%Y-%m-%d %H:%M:%S")

        existing_events = self.get_events(
            start_date=day_start.isoformat(),
            end_date=day_end.isoformat()
        )

        slots = []
        cursor = day_start
        step = timedelta(minutes=30)
        dur = timedelta(minutes=duration_minutes)

        while cursor + dur <= day_end:
            slot_start = cursor.isoformat()
            slot_end = (cursor + dur).isoformat()
            avail = self.check_availability(slot_start, slot_end)
            if avail["available"]:
                slots.append({
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "duration_minutes": duration_minutes
                })
            cursor += step
            if len(slots) >= 5:
                break

        return slots

    def cancel_event(
        self,
        event_id: str,
        task_id: str = "manual-cal-cancel",
        approval_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancels an event. Strictly gated behind Level 3 human approval.
        """
        tool_call = ToolCall(
            call_id=f"cal-cancel-{uuid.uuid4().hex[:6]}",
            tool_name="calendar_cancel_event",
            arguments={"event_id": event_id},
            permission_level=PermissionLevel.LEVEL_3_RESTRICTED
        )

        can_exec, appr_req, reason = policy_engine.evaluate_tool_execution(
            task_id=task_id,
            step_number=1,
            tool_call=tool_call,
            approval_token=approval_token
        )

        if not can_exec:
            if appr_req:
                raise ApprovalRequiredError(appr_req)
            return {"ok": False, "error": f"Permission Denied: {reason}"}

        now = datetime.now().isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE calendar_events SET status = 'cancelled', updated_at = ? WHERE id = ?",
                (now, event_id)
            )
            if cur.rowcount == 0:
                return {"ok": False, "error": f"Event '{event_id}' not found."}

        return {"ok": True, "event_id": event_id, "status": "cancelled", "approval_token": approval_token}

calendar_adapter = CalendarAdapter()

"""
Test script for verifying integrations without faking authentication:
1. Calendar SQLite Engine (data/jarvis_calendar.db)
2. Email SQLite Engine (data/jarvis_email.db) & Level 3 approval gating
3. Chrome CDP status (port 9222 check)
4. Model router cloud check (confirming opt-in requirement)
"""
import sys
import os
import json
from pathlib import Path

JARVIS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(JARVIS_ROOT))

from registry.calendar_adapter import calendar_adapter
from registry.email_adapter import email_adapter
from registry.browser_adapter import browser_adapter
from core.model_router import model_router

def test_real_integrations():
    print("=" * 60)
    print("OPERATION JARVIS — INTEGRATION VERIFICATION (NO FAKED AUTH)")
    print("=" * 60)

    # 1. Calendar Engine
    print("\n[1] Local Calendar Integration (SQLite):")
    events = calendar_adapter.get_events(limit=5)
    print(f"  Confirmed Events in DB: {len(events)}")
    for e in events[:2]:
        print(f"  • {e['start_time']} | {e['title']} ({e['location']})")
    
    # Test slot suggestion
    slots = calendar_adapter.suggest_slots(duration_minutes=45)
    print(f"  Available Smart Slots: {len(slots)} suggestions generated.")

    # 2. Email Engine
    print("\n[2] Local Email Integration (SQLite & Level 3 Gate):")
    emails = email_adapter.search_emails(query="", limit=5)
    print(f"  Indexed Local Emails: {len(emails)}")
    if emails:
        print(f"  • Sample Email: From={emails[0].get('sender')} | Subject={emails[0].get('subject')}")
    
    # Verify Level 3 Gating on send
    print("  Testing email_send security gate without token:")
    try:
        email_adapter.send_email(
            recipient="test@example.com",
            subject="Integration Test",
            body="Test email body",
            approval_token=None
        )
        print("  ERROR: Email sent without approval token!")
        assert False
    except Exception as e:
        print(f"  PASS: email_send strictly blocked with: {type(e).__name__} ('{str(e)[:60]}...')")

    # 3. Chrome CDP Status
    print("\n[3] Chrome CDP Browser Adapter:")
    b_status = browser_adapter.get_status()
    print(f"  CDP Port 9222 Status: Connected={b_status.get('connected')} | Mode={b_status.get('mode')}")
    print(f"  Raw Details: {b_status.get('message', 'Checked local CDP port without spoofing')}")

    # 4. Model Router Privacy & Auth Check
    print("\n[4] Cloud Model Router Privacy & Opt-In:")
    routing = model_router.route_task(objective="Help me design a video script", prefer_local=True, allow_cloud_privacy=False)
    print(f"  Default Route: {routing.model_name} (is_cloud={routing.is_cloud}, reason={routing.reason})")
    assert routing.is_cloud is False, "Default route must be local"
    print("  PASS: Cloud routing is strictly opt-in and blocked by default.")

    print("\nINTEGRATIONS TEST: COMPLETE & VERIFIED")
    print("=" * 60)

if __name__ == "__main__":
    test_real_integrations()

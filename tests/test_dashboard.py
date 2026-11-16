import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from fastapi.testclient import TestClient
from api.app import app
from security.policy_engine import policy_engine

@pytest.fixture
def client():
    return TestClient(app)

def test_dashboard_root_redirect(client):
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (301, 302, 307)
    assert res.headers["location"] == "/dashboard/"

def test_dashboard_static_page(client):
    res = client.get("/dashboard/")
    assert res.status_code == 200
    assert "JARVIS" in res.text
    assert "WORKSTATION CORE" in res.text
    assert "stats-grid" in res.text

def test_dashboard_summary_api(client):
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "system" in data
    assert "HP Victus" in data["system"]["workstation"]
    assert "capabilities" in data
    assert data["capabilities"]["total_tools"] >= 50
    assert "agents" in data
    assert len(data["agents"]) == 6
    assert "schedules" in data
    assert "knowledge" in data
    assert data["knowledge"]["memory_nodes"] >= 1000
    assert "communications" in data
    assert "security" in data

def test_dashboard_emergency_stop_toggle(client):
    # Ensure initially online
    policy_engine.reset_emergency_stop()

    # Trigger emergency stop
    res_trigger = client.post(
        "/api/v1/security/emergency_stop",
        json={"action": "trigger", "reason": "Automated regression test"}
    )
    assert res_trigger.status_code == 200
    assert res_trigger.json()["emergency_stopped"] is True
    assert policy_engine.is_emergency_stopped() is True

    # Check summary reflects emergency stop
    res_sum = client.get("/api/v1/dashboard/summary")
    assert res_sum.json()["status"] == "emergency_stopped"

    # Reset emergency stop
    res_reset = client.post(
        "/api/v1/security/emergency_stop",
        json={"action": "reset"}
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["emergency_stopped"] is False
    assert policy_engine.is_emergency_stopped() is False

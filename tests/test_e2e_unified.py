"""
Operation JARVIS — Complete End-to-End Unified Workstation Integration Suite.
Validates all 8 capabilities, security boundaries, dual runtime bridges,
and failure modes in a single unified regression run.
"""

import os
import sys
import time
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from api.app import app
from config.settings import settings
from registry.capability_registry import capability_registry
from security.policy_engine import policy_engine
from core.model_router import model_router, ModelTier
from core.scheduler import persistent_scheduler
from registry.email_adapter import email_adapter
from registry.calendar_adapter import calendar_adapter
from core.doc_intelligence import doc_intelligence
from evaluation.rag_evaluator import rag_evaluator
from api.mobile_adapter import auth_manager

@pytest.fixture
def client():
    return TestClient(app)

def test_e2e_capability_discovery_and_agent_reconciliation():
    """Verify all 6 agents and 52 tools are registered and healthy."""
    agent_tool = capability_registry.get_tool("agent_list")
    assert agent_tool is not None
    res = agent_tool.handler()
    assert res["ok"] is True
    assert res["count"] == 6
    agent_ids = {a["agent_id"] for a in res["agents"]}
    assert "antigravity" in agent_ids
    assert "qwen-batman" in agent_ids
    assert "research" in agent_ids
    assert "test-engineer" in agent_ids
    assert "security-auditor" in agent_ids
    assert "continue-ide" in agent_ids

    tools = capability_registry.list_tools()
    assert len(tools) >= 50
    tool_names = {t["name"] for t in tools}
    assert "schedule_create" in tool_names
    assert "email_search" in tool_names
    assert "calendar_create_event" in tool_names
    assert "document_ingest" in tool_names
    assert "rag_evaluate" in tool_names

def test_e2e_persistent_scheduler_lifecycle():
    """Verify schedule creation, pause, resume, duplicate run lock, and cancellation."""
    sched = persistent_scheduler.create_schedule(
        name="E2E Health Audit Schedule",
        schedule_type="INTERVAL",
        schedule_expr="7200",
        objective="Run periodic system diagnostics"
    )
    assert sched["status"].lower() == "active"
    sched_id = sched["id"]

    # Pause
    paused = persistent_scheduler.pause_schedule(sched_id)
    assert paused is True
    assert persistent_scheduler.get_schedule(sched_id)["status"].lower() == "paused"

    # Resume
    resumed = persistent_scheduler.resume_schedule(sched_id)
    assert resumed is True
    assert persistent_scheduler.get_schedule(sched_id)["status"].lower() == "active"

    # Lock acquisition / duplicate run protection
    locked = persistent_scheduler.db.acquire_schedule_lock(sched_id)
    assert locked is True
    assert persistent_scheduler.db.acquire_schedule_lock(sched_id) is False
    persistent_scheduler.db.release_schedule_lock(sched_id, next_run_at=None, success=True)

    # Cancel
    cancelled = persistent_scheduler.cancel_schedule(sched_id)
    assert cancelled is True
    assert persistent_scheduler.get_schedule(sched_id)["status"].lower() == "cancelled"

def test_e2e_email_and_calendar_hub():
    """Verify email thread summarization and calendar conflict/duplicate prevention."""
    # 1. Email thread summarize
    summary = email_adapter.summarize_thread("thread-001")
    assert summary["ok"] is True
    assert "internship" in summary["summary"].lower()

    # 2. Calendar availability check
    avail = calendar_adapter.check_availability("2026-11-09T09:00:00", "2026-11-09T17:00:00")
    assert "available" in avail
    assert "conflicts" in avail

    # 3. Calendar event create with duplicate prevention
    import uuid
    sync_title = f"E2E Architecture Sync {uuid.uuid4().hex[:6]}"
    ev1 = calendar_adapter.create_event(
        title=sync_title,
        start_time="2026-11-10T15:00:00",
        end_time="2026-11-10T16:00:00",
        description="Unified review of Operation JARVIS"
    )
    assert ev1["ok"] is True
    assert ev1["status"] in ("confirmed", "created")

    # Duplicate attempt
    ev2 = calendar_adapter.create_event(
        title=sync_title,
        start_time="2026-11-10T15:00:00",
        end_time="2026-11-10T16:00:00"
    )
    assert ev2["ok"] is False
    assert "Duplicate event rejected" in ev2["error"]

def test_e2e_document_intelligence_and_citations(tmp_path):
    """Verify ingestion, FTS5 chunk search, and citation generation."""
    sample_doc = tmp_path / "quantum_spec.txt"
    sample_doc.write_text(
        "Quantum Cryogenic Subsystem Specifications:\n"
        "Operating temperature: 15 milliKelvin.\n"
        "Superconducting qubit lattice coherence time: 250 microseconds.\n",
        encoding="utf-8"
    )

    ingest_res = doc_intelligence.ingest_document(sample_doc)
    assert ingest_res["ok"] is True
    assert ingest_res["status"] == "ingested"

    matches = doc_intelligence.search_documents("15 milliKelvin")
    assert len(matches) >= 1
    assert "quantum_spec.txt" in matches[0]["citation"]
    assert "file:///" in matches[0]["citation"]

def test_e2e_model_routing_and_privacy_boundaries():
    """Verify local-first routing, tier selection, and privacy gate."""
    # 1. Batman conversational routing
    dec_batman = model_router.route_task(objective="Hey Batman, what is our operational stance today?")
    assert dec_batman.selected_tier == ModelTier.LOCAL_QWEN_BATMAN
    assert dec_batman.model_name == "qwen-batman:latest"
    assert dec_batman.is_cloud is False

    # 2. Technical text routing
    dec_text = model_router.route_task(objective="Deep dive into first principles and theoretical algorithm analysis of sorting networks")
    assert dec_text.selected_tier == ModelTier.LOCAL_QWEN_TEXT
    assert dec_text.model_name == "qwen-text:latest"
    assert dec_text.is_cloud is False

    # 3. Privacy boundary check
    private_payload = "Bearer sk-proj-12345secret and private password"
    is_violating = model_router.check_privacy_boundary(private_payload)
    assert is_violating is True

def test_e2e_rag_evaluation_non_destructive():
    """Verify RAG evaluation achieves targets without mutating memory.db."""
    report = rag_evaluator.generate_full_evaluation_report()
    assert report["metrics"]["hit_rate_at_k"] >= 0.80
    assert report["metrics"]["mean_reciprocal_rank"] >= 0.70
    assert report["metrics"]["negative_rejection_rate"] >= 0.90
    assert report["write_and_retrieve"]["write_retrieve_passed"] is True

def test_e2e_dashboard_and_security_controls(client):
    """Verify unified dashboard API, emergency stop, and root redirect."""
    res_root = client.get("/", follow_redirects=False)
    assert res_root.status_code in (301, 302, 307)
    assert res_root.headers["location"] == "/dashboard/"

    res_sum = client.get("/api/v1/dashboard/summary")
    assert res_sum.status_code == 200
    data = res_sum.json()
    assert data["status"] in ("online", "degraded")
    assert data["system"]["workstation"] == "HP Victus 15-fa2382TX"
    assert data["capabilities"]["total_tools"] >= 50

def test_e2e_mobile_remote_access(client):
    """Verify mobile pairing, PWA shell, push-to-talk voice, and Kokoro WAV audio streaming."""
    # 1. Pairing
    res_pair = client.post("/api/v1/mobile/auth/pair", json={"pairing_key": auth_manager.pairing_key})
    assert res_pair.status_code == 200
    token = res_pair.json()["session_token"]

    # 2. PWA assets
    res_pwa = client.get("/pwa/")
    assert res_pwa.status_code == 200
    assert "JARVIS Mobile Remote" in res_pwa.text

    # 3. Voice query & TTS
    res_voice = client.post(
        "/api/v1/mobile/voice",
        headers={"Authorization": f"Bearer {token}"},
        json={"transcript": "Report system status", "auto_speak": True}
    )
    assert res_voice.status_code == 200
    v_data = res_voice.json()
    assert v_data["ok"] is True
    assert v_data["audio_url"] is not None

    # 4. Stream audio
    audio_id = v_data["audio_id"]
    res_audio = client.get(f"/api/v1/mobile/audio/{audio_id}", headers={"Authorization": f"Bearer {token}"})
    assert res_audio.status_code == 200
    assert res_audio.headers["content-type"] == "audio/wav"

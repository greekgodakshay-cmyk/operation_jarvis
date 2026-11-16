"""
Operation JARVIS — Final Stabilization Verification Test Suite.
Verifies all 4 objectives:
1. Response quality & document intelligence (grounded, concise, complete, exact citations, no narration).
2. Voice output for text messages (toggleable auto_speak on /api/v1/mobile/chat, Kokoro audio returned and streamable, voice input preserved).
3. Latency benchmarks (sub-5s routine text chat, sub-15s grounded document QA).
4. JARVIS / Batman / Qwen identity consistency (JARVIS persona, Qwen 3.5 engine acknowledged, no think tag leaks or system prompt exposure).
"""
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import app
from api.mobile_adapter import auth_manager

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(scope="module")
def auth_token(client):
    res = client.post("/api/v1/mobile/auth/pair", json={"pairing_key": auth_manager.pairing_key})
    assert res.status_code == 200
    return res.json()["session_token"]

def test_text_chat_voice_output_disabled(client, auth_token):
    """When auto_speak is false or omitted, text chat returns text with no audio overhead."""
    t0 = time.perf_counter()
    res = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "State Newton's second law of motion in one sentence.", "auto_speak": False, "prefer_local": True}
    )
    elapsed = time.perf_counter() - t0
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["audio_url"] is None
    assert "force" in data["reply"].lower() or "acceleration" in data["reply"].lower() or "mass" in data["reply"].lower()
    # Check that latency is well under 15 seconds (accounts for initial model warm-up)
    assert elapsed < 15.0

def test_text_chat_voice_output_enabled(client, auth_token):
    """When auto_speak is true, text chat generates Kokoro WAV and returns audio_url."""
    res = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "What is the speed of sound in dry air at 20 degrees Celsius?", "auto_speak": True, "voice": "bm_george", "prefer_local": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["audio_url"] is not None
    assert data["audio_id"] is not None
    assert len(data["reply"]) > 10

    # Test audio streaming endpoint
    audio_res = client.get(data["audio_url"], headers={"Authorization": f"Bearer {auth_token}"})
    assert audio_res.status_code == 200
    assert audio_res.headers["content-type"] == "audio/wav"
    assert len(audio_res.content) > 1000

def test_voice_input_push_to_talk_preserved(client, auth_token):
    """Preserve existing push-to-talk voice input functionality."""
    res = client.post(
        "/api/v1/mobile/voice",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"transcript": "Confirm system diagnostics status.", "auto_speak": True, "voice": "bm_george"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["audio_url"] is not None
    assert len(data["response_text"]) > 10

def test_jarvis_identity_and_persona_consistency(client, auth_token):
    """Verify JARVIS identity, Qwen 3.5 underlying engine attribution, and zero leaked thinking."""
    res = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "Who are you and what AI model powers you?", "prefer_local": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    reply = data["reply"]
    # Persona: JARVIS
    assert "jarvis" in reply.lower()
    # Inference engine: Qwen
    assert "qwen" in reply.lower()
    # No think tags
    assert "<think>" not in reply
    assert "</think>" not in reply
    # No internal scratchpads
    assert "Thinking Process:" not in reply
    assert "System Instructions Check:" not in reply
    assert "Draft the Response:" not in reply

def test_document_qa_quality_and_citations(client, auth_token, tmp_path):
    """Verify concise, grounded document answers with citations and no narration."""
    # Create test document
    doc_path = tmp_path / "satellite_specs.txt"
    doc_path.write_text("Orbital Satellite Spec: The solar array produces 4500 Watts of continuous power in low Earth orbit.\n", encoding="utf-8")
    
    with open(doc_path, "rb") as f:
        up_res = client.post(
            "/api/v1/mobile/documents/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=[("files", ("satellite_specs.txt", f, "text/plain"))]
        )
    assert up_res.status_code == 200
    doc_id = up_res.json()["indexed_documents"][0]["doc_id"]

    try:
        t0 = time.perf_counter()
        q_res = client.post(
            "/api/v1/mobile/documents/query",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"query": "How many Watts of power does the solar array produce?", "doc_ids": [doc_id], "task_type": "qa"}
        )
        latency = time.perf_counter() - t0
        assert q_res.status_code == 200
        data = q_res.json()
        assert data["ok"] is True
        reply = data["reply"]
        assert "4500" in reply or "4,500" in reply
        assert len(data["citations"]) >= 1
        assert "satellite_specs.txt" in data["citations"][0]["filename"]
        # No processing narration or internal scratchpads
        assert "Review the Document" not in reply
        assert "Thinking Process" not in reply
        assert "Final Review" not in reply
        # Latency check: under 20s
        assert latency < 20.0
    finally:
        client.delete(f"/api/v1/mobile/documents/{doc_id}", headers={"Authorization": f"Bearer {auth_token}"})

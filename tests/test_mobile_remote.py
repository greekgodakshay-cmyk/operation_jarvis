import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from fastapi.testclient import TestClient
from api.app import app
from api.mobile_adapter import auth_manager, rate_limiter

@pytest.fixture
def client():
    return TestClient(app)

def test_mobile_pwa_static_assets(client):
    """Verify Android PWA manifests and app shell are served properly."""
    res_index = client.get("/pwa/")
    assert res_index.status_code == 200
    assert "JARVIS Mobile Remote" in res_index.text
    assert "btnPtt" in res_index.text

    res_manifest = client.get("/pwa/manifest.json")
    assert res_manifest.status_code == 200
    assert res_manifest.json()["short_name"] == "JARVIS"
    assert res_manifest.json()["display"] == "standalone"

    res_sw = client.get("/pwa/service-worker.js")
    assert res_sw.status_code == 200
    assert "jarvis-pwa" in res_sw.text

def test_mobile_auth_pairing_flow(client):
    """Verify secure pairing handshake and token validation."""
    # 1. Invalid key returns 403
    res_bad = client.post("/api/v1/mobile/auth/pair", json={"pairing_key": "wrong_key_123"})
    assert res_bad.status_code == 403

    # 2. Valid pairing key returns session token
    res_good = client.post(
        "/api/v1/mobile/auth/pair",
        json={"pairing_key": auth_manager.pairing_key}
    )
    assert res_good.status_code == 200
    data = res_good.json()
    assert data["ok"] is True
    assert data["session_token"].startswith("mobsess_")
    token = data["session_token"]

    # 3. Unauthenticated request to status returns 401
    res_unauth = client.get("/api/v1/mobile/status")
    assert res_unauth.status_code == 401

    # 4. Authenticated request to status returns 200
    res_auth = client.get(
        "/api/v1/mobile/status",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_auth.status_code == 200
    st = res_auth.json()
    assert st["ok"] is True
    assert st["primary_model"] == "qwen-batman:latest"
    assert st["memory_nodes"] >= 1000

def test_mobile_voice_query_and_tts(client):
    """Verify push-to-talk voice dispatch and Kokoro TTS audio generation."""
    token = auth_manager.pairing_key  # bootstrap token

    res = client.post(
        "/api/v1/mobile/voice",
        headers={"X-Jarvis-Mobile-Token": token},
        json={
            "transcript": "Status report on workstation resources, JARVIS.",
            "auto_speak": True,
            "voice": "bm_george"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert len(data["response_text"]) > 0
    assert data["model_used"] == "qwen-batman:latest"
    assert data["audio_url"] is not None

    # Fetch the generated audio file
    audio_id = data["audio_id"]
    res_audio = client.get(
        f"/api/v1/mobile/audio/{audio_id}",
        headers={"X-Jarvis-Mobile-Token": token}
    )
    assert res_audio.status_code == 200
    assert res_audio.headers["content-type"] == "audio/wav"
    assert len(res_audio.content) > 1000  # valid wav header and PCM audio samples

def test_mobile_surface_isolation(client):
    """Verify mobile API has NO direct shell, filesystem traversal or raw SQL endpoints."""
    token = auth_manager.pairing_key
    # Try accessing hypothetical shell or db under mobile
    res1 = client.get("/api/v1/mobile/shell", headers={"X-Jarvis-Mobile-Token": token})
    assert res1.status_code == 404

    res2 = client.get("/api/v1/mobile/raw_sql", headers={"X-Jarvis-Mobile-Token": token})
    assert res2.status_code == 404

    res3 = client.get("/api/v1/mobile/filesystem", headers={"X-Jarvis-Mobile-Token": token})
    assert res3.status_code == 404

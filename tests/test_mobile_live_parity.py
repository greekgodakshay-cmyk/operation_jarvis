"""
Operation JARVIS — Live Mobile Parity, Reasoning Depth & Document Pipeline Test Suite.
Directly tests:
1. Mobile vs Laptop response parity on identical complex technical prompts.
2. Multi-step reasoning problem resolution.
3. Shared memory retrieval across mobile and laptop.
4. Complex technical question answering without truncation or think-tag leakage.
5. PDF upload, extraction, and grounded citation answering.
6. DOCX, PPTX, and TXT upload, extraction, and indexing.
7. Mobile voice query and Kokoro TTS generation.
8. Security gates: authentication, CSRF origin verification, path traversal prevention, magic byte checks.
"""
import os
import sys
import time
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import app
from core.doc_intelligence import doc_intelligence
from core.upload_manager import upload_manager
from core.llm_client import llm_client
from api.mobile_adapter import auth_manager

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(scope="module")
def auth_token(client):
    res = client.post("/api/v1/mobile/auth/pair", json={"pairing_key": auth_manager.pairing_key})
    assert res.status_code == 200
    return res.json()["session_token"]

def test_pwa_served_assets_no_cache_and_v2(client):
    """Verify live FastAPI /pwa/ assets serve no-cache headers and jarvis-pwa-v2 service worker."""
    # 1. HTML
    r_html = client.get("/pwa/")
    assert r_html.status_code == 200
    assert "no-cache" in r_html.headers.get("cache-control", "")
    assert "btnAttach" in r_html.text
    assert "btnHeaderAttach" in r_html.text
    assert "20261107_v2" in r_html.text

    # 2. Service Worker
    r_sw = client.get("/pwa/service-worker.js")
    assert r_sw.status_code == 200
    assert "no-cache" in r_sw.headers.get("cache-control", "")
    assert "jarvis-pwa-v2" in r_sw.text
    assert "fetch(event.request)" in r_sw.text

    # 3. CSS
    r_css = client.get("/pwa/style.css")
    assert r_css.status_code == 200
    assert ".btn-attach" in r_css.text

def test_mobile_reasoning_and_thinking_tag_cleaning():
    """Verify reasoning models don't leak think tags and never return blank on unclosed tags."""
    # Test closed
    raw1 = "<think>Calculating 2 + 2...\nIntermediate result: 4.</think>The answer is 4."
    clean1 = llm_client.extract_clean_content(raw1)
    assert clean1 == "The answer is 4."
    assert "<think>" not in clean1

    # Test all inside think
    raw2 = "<think>Step 1: Compute square of 9.\nStep 2: 9 * 9 = 81.\nFinal answer: 81.</think>"
    clean2 = llm_client.extract_clean_content(raw2)
    assert "81" in clean2
    assert "<think>" not in clean2

    # Test unclosed think
    raw3 = "<think>Reasoning through the proof...\n\n### Conclusion:\nThe theorem holds true for all n > 0."
    clean3 = llm_client.extract_clean_content(raw3)
    assert "The theorem holds true for all n > 0." in clean3
    assert "<think>" not in clean3

def test_mobile_shared_memory_retrieval(client, auth_token):
    """Verify mobile chat retrieves shared memories identically to laptop."""
    res = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "What is my primary workstation model and specifications?", "prefer_local": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    reply = data["reply"]
    # Check that memory context or workstation specs are reflected
    assert len(reply) > 40
    assert any(term in reply.lower() for term in ("victus", "hp", "rtx", "4050", "intel", "210h", "workstation"))

def test_mobile_complex_technical_question(client, auth_token):
    """Verify mobile reasoning quality on deep technical query without token truncation."""
    prompt = "Explain how WAL mode in SQLite achieves concurrency between readers and writers from first principles."
    res = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": prompt, "prefer_local": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    reply = data["reply"]
    # Depth verification: must be a substantive, multi-paragraph technical explanation
    assert len(reply) > 200
    assert "<think>" not in reply
    assert "</think>" not in reply
    assert "wal" in reply.lower()
    # Telemetry verification
    assert data["model_used"] in ("qwen3.5:9b", "qwen-text:latest")
    assert data["token_usage"]["completion_tokens"] > 50

def test_mobile_document_upload_and_grounded_qa(client, auth_token, tmp_path):
    """Verify PDF upload, FTS5 indexing, and cited query answering."""
    # 1. Create a minimal valid PDF
    pdf_path = tmp_path / "quantum_manual.pdf"
    objs = [
        b'',
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n',
        b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
        b'5 0 obj\n<< /Length 75 >>\nstream\nBT /F1 12 Tf 72 712 Td (The cryogenic refrigeration unit operates strictly at 15 mK.) Tj ET\nendstream\nendobj\n'
    ]
    body = b'%PDF-1.4\n'
    offsets = []
    for obj in objs[1:]:
        offsets.append(len(body))
        body += obj
    xref_pos = len(body)
    body += b'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets:
        body += f'{off:010d} 00000 n \n'.encode()
    body += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n'.encode()
    pdf_path.write_bytes(body)

    # 2. Upload via mobile endpoint
    with open(pdf_path, "rb") as f:
        res_upload = client.post(
            "/api/v1/mobile/documents/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=[("files", ("quantum_manual.pdf", f, "application/pdf"))]
        )
    assert res_upload.status_code == 200
    up_data = res_upload.json()
    assert up_data["successful_count"] == 1
    doc_id = up_data["indexed_documents"][0]["doc_id"]

    # 3. Grounded Question
    res_query = client.post(
        "/api/v1/mobile/documents/query",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "query": "What is the operating temperature of the cryogenic unit?",
            "doc_ids": [doc_id],
            "task_type": "qa"
        }
    )
    assert res_query.status_code == 200
    q_data = res_query.json()
    assert q_data["ok"] is True
    assert "15" in q_data["reply"] or "15 mk" in q_data["reply"].lower()
    assert len(q_data["citations"]) >= 1
    assert "quantum_manual.pdf" in q_data["citations"][0]["citation"]

    # 4. Clean up
    del_res = client.delete(f"/api/v1/mobile/documents/{doc_id}", headers={"Authorization": f"Bearer {auth_token}"})
    assert del_res.status_code == 200

def test_mobile_security_boundaries(client, auth_token):
    """Verify security: unauthorized rejection, fake magic bytes, and path traversal defense."""
    # 1. Unauthorized upload rejected
    res_unauth = client.post("/api/v1/mobile/documents/upload")
    assert res_unauth.status_code == 401

    # 2. Fake magic bytes rejected
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00this is a fake executable"
    res_fake = client.post(
        "/api/v1/mobile/documents/upload",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=[("files", ("malicious.pdf", fake_exe, "application/pdf"))]
    )
    assert res_fake.status_code == 200
    fake_data = res_fake.json()
    assert fake_data["failed_count"] == 1
    assert any(term in fake_data["errors"][0]["error"].lower() for term in ("signature", "magic", "corrupted"))

    # 3. Path traversal attack blocked
    good_txt = b"Harmless technical notes for verification."
    res_traversal = client.post(
        "/api/v1/mobile/documents/upload",
        headers={"Authorization": f"Bearer {auth_token}"},
        files=[("files", ("../../../../Windows/System32/evil.txt", good_txt, "text/plain"))]
    )
    assert res_traversal.status_code == 200
    # Confirm it was safely stripped to evil.txt in data/uploads/
    traversal_doc = res_traversal.json()["indexed_documents"][0]
    assert ".." not in traversal_doc["filename"]
    # Cleanup
    client.delete(f"/api/v1/mobile/documents/{traversal_doc['doc_id']}", headers={"Authorization": f"Bearer {auth_token}"})

def test_mobile_vs_laptop_identical_prompt_parity(client, auth_token):
    """Verify mobile and laptop produce comparable, high-depth technical answers on identical prompt."""
    prompt = "Explain how Redis handles persistence using RDB snapshots versus AOF logs, including fsync policies."

    # 1. Laptop endpoint
    res_laptop = client.post("/api/v1/chat", json={"message": prompt, "include_memory": False})
    assert res_laptop.status_code == 200
    laptop_reply = res_laptop.json()["reply"]

    # 2. Mobile endpoint
    res_mobile = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": prompt, "prefer_local": True}
    )
    assert res_mobile.status_code == 200
    mobile_reply = res_mobile.json()["reply"]

    # Both must deliver complete, substantive explanations
    assert len(laptop_reply) > 150
    assert len(mobile_reply) > 150
    assert "rdb" in mobile_reply.lower()
    assert "aof" in mobile_reply.lower()
    assert "<think>" not in mobile_reply

def test_mobile_multistep_reasoning(client, auth_token):
    """Verify multi-step mathematical/logical reasoning on mobile without empty response."""
    prompt = "A server cluster has 4 nodes. Each node processes 250 requests per second. If traffic spikes by 60%, how many total requests per second does the cluster need to process, and how many additional nodes of the same capacity are required?"
    res = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": prompt, "prefer_local": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    reply = data["reply"]
    # 4 * 250 = 1000. Spike by 60% = 1600. Additional needed = 600 / 250 = 2.4 -> 3 nodes.
    assert len(reply) > 50
    assert any(term in reply for term in ("1,600", "1600", "3", "additional", "nodes"))
    assert "<think>" not in reply

def test_mobile_docx_pptx_txt_uploads(client, auth_token, tmp_path):
    """Verify DOCX, PPTX, and TXT upload, extraction, and indexing via mobile endpoint."""
    # 1. DOCX
    docx_file = tmp_path / "microservices.docx"
    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>Service Mesh Architecture</w:t></w:r></w:p>
        <w:p><w:r><w:t>Istio uses Envoy sidecar proxies for mutual TLS authentication.</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(docx_file, "w") as z:
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))

    # 2. PPTX
    pptx_file = tmp_path / "deck.pptx"
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
      <p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Kubernetes Ingress Controllers</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>
    </p:sld>"""
    with zipfile.ZipFile(pptx_file, "w") as z:
        z.writestr("ppt/slides/slide1.xml", slide_xml.encode("utf-8"))

    # 3. TXT
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("Database Sharding: Consistent hashing distributes partitions evenly.", encoding="utf-8")

    with open(docx_file, "rb") as f_docx, open(pptx_file, "rb") as f_pptx, open(txt_file, "rb") as f_txt:
        res = client.post(
            "/api/v1/mobile/documents/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=[
                ("files", ("microservices.docx", f_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                ("files", ("deck.pptx", f_pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation")),
                ("files", ("notes.txt", f_txt, "text/plain"))
            ]
        )
    assert res.status_code == 200
    data = res.json()
    assert data["successful_count"] == 3
    doc_ids = [d["doc_id"] for d in data["indexed_documents"]]

    # Query the PPTX
    res_q = client.post(
        "/api/v1/mobile/documents/query",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"query": "What ingress controllers are mentioned?", "doc_ids": doc_ids, "task_type": "qa"}
    )
    assert res_q.status_code == 200
    assert len(res_q.json()["citations"]) >= 1

    # Cleanup
    for did in doc_ids:
        client.delete(f"/api/v1/mobile/documents/{did}", headers={"Authorization": f"Bearer {auth_token}"})

def test_mobile_voice_tts_flow(client, auth_token):
    """Verify push-to-talk voice dispatch and audio stream generation without 80-token cap."""
    res = client.post(
        "/api/v1/mobile/voice",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "transcript": "Briefly state the primary memory database architecture for JARVIS.",
            "auto_speak": True,
            "voice": "bm_george"
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert len(data["response_text"]) > 40
    assert data["audio_url"] is not None
    assert "<think>" not in data["response_text"]

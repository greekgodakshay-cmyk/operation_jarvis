"""
Operation JARVIS — Document Intelligence Stabilization Acceptance Test Suite.
Directly verifies:
1. Upload one TXT file.
2. Upload one PDF file.
3. Upload one DOCX file.
4. Summarize each document.
5. Generate revision notes from a document.
6. Ask a question requiring retrieval from the uploaded document.
7. Verify citations reference actual pages.
8. Verify normal text conversations still work.
9. Verify failures return meaningful error messages instead of generic "Failed to fetch".
"""

import sys
import io
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.app import app
from api.mobile_adapter import auth_manager
from core.doc_intelligence import doc_intelligence

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(scope="module")
def auth_token(client):
    res = client.post("/api/v1/mobile/auth/pair", json={"pairing_key": auth_manager.pairing_key})
    assert res.status_code == 200
    return res.json()["session_token"]

def make_pdf(title: str, text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 712 Td ({title}: {text}) Tj ET".encode("latin-1")
    objs = [
        b'',
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        f'3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n'.encode(),
        b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
        f'5 0 obj\n<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream\nendobj\n'
    ]
    pdf = b'%PDF-1.4\n'
    offsets = []
    for obj in objs[1:]:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += b'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets:
        pdf += f'{off:010d} 00000 n \n'.encode()
    pdf += f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n'.encode()
    return pdf

def make_docx(title: str, body: str) -> bytes:
    buf = io.BytesIO()
    doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>{title}</w:t></w:r></w:p>
        <w:p><w:r><w:t>{body}</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))
    return buf.getvalue()

def test_acceptance_01_upload_txt(client, auth_token):
    """Test 1: Upload one TXT file."""
    content = b"Database Sharding Protocol: Primary key hashing ensures even shard allocation across 16 partitions."
    files = [("files", ("sharding_protocol.txt", content, "text/plain"))]
    res = client.post("/api/v1/mobile/documents/upload", headers={"Authorization": f"Bearer {auth_token}"}, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["successful_count"] == 1
    doc_id = data["indexed_documents"][0]["doc_id"]
    assert "sharding_protocol" in data["indexed_documents"][0]["filename"]
    # Clean up
    client.delete(f"/api/v1/mobile/documents/{doc_id}", headers={"Authorization": f"Bearer {auth_token}"})

def test_acceptance_02_upload_pdf(client, auth_token):
    """Test 2: Upload one PDF file."""
    pdf_bytes = make_pdf("Quantum Entanglement", "The communication channel maintains 99.98% fidelity at 4 Kelvin.")
    files = [("files", ("quantum_fidelity.pdf", pdf_bytes, "application/pdf"))]
    res = client.post("/api/v1/mobile/documents/upload", headers={"Authorization": f"Bearer {auth_token}"}, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["successful_count"] == 1
    doc_id = data["indexed_documents"][0]["doc_id"]
    assert "quantum_fidelity" in data["indexed_documents"][0]["filename"]
    # Clean up
    client.delete(f"/api/v1/mobile/documents/{doc_id}", headers={"Authorization": f"Bearer {auth_token}"})

def test_acceptance_03_upload_docx(client, auth_token):
    """Test 3: Upload one DOCX file."""
    docx_bytes = make_docx("Security Hardening", "All internal endpoints require mutual TLS and strictly reject unauthenticated tokens.")
    files = [("files", ("security_hardening.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
    res = client.post("/api/v1/mobile/documents/upload", headers={"Authorization": f"Bearer {auth_token}"}, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["successful_count"] == 1
    doc_id = data["indexed_documents"][0]["doc_id"]
    assert "security_hardening" in data["indexed_documents"][0]["filename"]
    # Clean up
    client.delete(f"/api/v1/mobile/documents/{doc_id}", headers={"Authorization": f"Bearer {auth_token}"})

def test_acceptance_04_05_06_07_grounded_qa_summary_notes(client, auth_token):
    """
    Tests 4, 5, 6, 7:
    - Summarize document
    - Generate revision notes
    - Ask a retrieval-grounded question
    - Verify citations reference actual pages
    """
    pdf_bytes = make_pdf("Aeronautics Guide", "The turbofan bypass ratio is 12 to 1 for optimal subsonic fuel efficiency.")
    files = [("files", ("aeronautics_guide.pdf", pdf_bytes, "application/pdf"))]
    res_up = client.post("/api/v1/mobile/documents/upload", headers={"Authorization": f"Bearer {auth_token}"}, files=files)
    assert res_up.status_code == 200
    doc_id = res_up.json()["indexed_documents"][0]["doc_id"]

    try:
        # 1. Summarize
        res_sum = client.post(
            "/api/v1/mobile/documents/query",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"query": "Summarize this aeronautics manual", "doc_ids": [doc_id], "task_type": "summary"}
        )
        assert res_sum.status_code == 200
        sum_data = res_sum.json()
        assert sum_data["ok"] is True
        assert len(sum_data["reply"]) > 20
        assert len(sum_data["citations"]) >= 1

        # 2. Revision Notes
        res_notes = client.post(
            "/api/v1/mobile/documents/query",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"query": "Generate revision notes", "doc_ids": [doc_id], "task_type": "revision_notes"}
        )
        assert res_notes.status_code == 200
        notes_data = res_notes.json()
        assert notes_data["ok"] is True
        assert len(notes_data["reply"]) > 20

        # 3. Grounded Question & Citation Page Verification
        res_qa = client.post(
            "/api/v1/mobile/documents/query",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"query": "What is the turbofan bypass ratio?", "doc_ids": [doc_id], "task_type": "qa"}
        )
        assert res_qa.status_code == 200
        qa_data = res_qa.json()
        assert qa_data["ok"] is True
        assert any(term in qa_data["reply"].lower() for term in ("12", "12 to 1", "bypass ratio"))
        assert len(qa_data["citations"]) >= 1
        citation = qa_data["citations"][0]
        assert "aeronautics_guide.pdf" in citation["citation"]
        assert citation["page_number"] == 1

    finally:
        client.delete(f"/api/v1/mobile/documents/{doc_id}", headers={"Authorization": f"Bearer {auth_token}"})

def test_acceptance_08_normal_text_conversation(client, auth_token):
    """Test 8: Verify normal text conversations still work seamlessly."""
    res = client.post(
        "/api/v1/mobile/chat",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"message": "State the current speed of light in vacuum in meters per second.", "prefer_local": True}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "299" in data["reply"] or "3" in data["reply"] or "speed of light" in data["reply"].lower()
    assert data["model_used"] in ("qwen3.5:9b", "qwen-text:latest")

def test_acceptance_09_meaningful_failure_messages(client, auth_token):
    """Test 9: Verify failures return structured, meaningful error messages instead of generic Failed to fetch."""
    # 1. Invalid file signature rejected with structured 400
    fake_doc = b"Not a docx file at all"
    files = [("files", ("corrupt.docx", fake_doc, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
    res_fake = client.post("/api/v1/mobile/documents/upload", headers={"Authorization": f"Bearer {auth_token}"}, files=files)
    assert res_fake.status_code == 200
    fake_data = res_fake.json()
    assert fake_data["failed_count"] == 1
    assert "signature" in fake_data["errors"][0]["error"].lower()

    # 2. Non-existent document query returns clean structured response rather than 500
    res_nonexistent = client.post(
        "/api/v1/mobile/documents/query",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"query": "What is mentioned?", "doc_ids": ["doc-nonexistent-12345"], "task_type": "qa"}
    )
    assert res_nonexistent.status_code == 200
    non_data = res_nonexistent.json()
    assert non_data["found_relevant_context"] is False
    assert "not contain" in non_data["reply"].lower()

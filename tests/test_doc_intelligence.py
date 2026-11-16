import sys
import os
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.doc_intelligence import doc_intelligence
from registry.capability_registry import capability_registry
from pypdf import PdfWriter

@pytest.fixture
def sample_files(tmp_path):
    # 1. Create a sample TXT
    txt_path = tmp_path / "workstation_specs.txt"
    txt_path.write_text(
        "HP Victus 15-fa2382TX Technical Specifications:\n"
        "Processor: Intel Core 5 210H with 12 logical cores.\n"
        "Memory: 24 GB DDR5 high-speed RAM.\n"
        "Graphics: NVIDIA GeForce RTX 4050 6GB Laptop GPU.\n"
        "Operating System: Windows 11 Home 64-bit edition.\n",
        encoding="utf-8"
    )

    # 2. Create a valid sample DOCX
    docx_path = tmp_path / "architecture_plan.docx"
    doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>Operation Jarvis Architecture Document</w:t></w:r></w:p>
        <w:p><w:r><w:t>The system unifies local-first agent reasoning with strict policy boundaries and persistent SQLite memory.</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    with zipfile.ZipFile(docx_path, "w") as z:
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))

    # 3. Create a valid text PDF
    pdf_path = tmp_path / "security_policy.pdf"
    objs = [
        b'',
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n',
        b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
        b'5 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 72 712 Td (Quantum Cryptography Security Protocol) Tj ET\nendstream\nendobj\n'
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

    return {"txt": txt_path, "docx": docx_path, "pdf": pdf_path}

def test_document_ingest_txt(sample_files):
    res = doc_intelligence.ingest_document(sample_files["txt"])
    assert res["ok"] is True
    assert res["status"] == "ingested"
    assert res["total_chunks"] >= 1
    doc_id = res["doc_id"]

    # Search for processor spec
    matches = doc_intelligence.search_documents("Intel Core 5 210H")
    assert len(matches) >= 1
    assert "210H" in matches[0]["text_content"]
    assert "workstation_specs.txt" in matches[0]["citation"]
    assert "file:///" in matches[0]["citation"]

    # Test Deduplication: Ingesting again without force_reindex must return 'already_indexed'
    res_dup = doc_intelligence.ingest_document(sample_files["txt"])
    assert res_dup["ok"] is True
    assert res_dup["status"] == "already_indexed"

def test_document_ingest_docx(sample_files):
    res = doc_intelligence.ingest_document(sample_files["docx"])
    assert res["ok"] is True
    assert res["status"] in ("ingested", "already_indexed")

    matches = doc_intelligence.search_documents("Operation Jarvis Architecture", doc_id=res["doc_id"])
    assert len(matches) >= 1
    assert "strict policy boundaries" in matches[0]["text_content"]
    assert "architecture_plan.docx" in matches[0]["citation"]

def test_document_ingest_pdf(sample_files):
    res = doc_intelligence.ingest_document(sample_files["pdf"])
    assert res["ok"] is True
    assert res["status"] == "ingested"

    matches = doc_intelligence.search_documents("Quantum Cryptography")
    assert len(matches) >= 1
    assert "Security Protocol" in matches[0]["text_content"]
    assert "security_policy.pdf" in matches[0]["citation"]
    assert matches[0]["page_number"] == 1

def test_capability_registry_document_tools(sample_files):
    tool_names = {t["name"] for t in capability_registry.list_tools()}
    assert "document_ingest" in tool_names
    assert "document_search" in tool_names
    assert "document_list" in tool_names

    # Test list via tool
    res_list = capability_registry.get_tool("document_list").handler()
    assert len(res_list) >= 2

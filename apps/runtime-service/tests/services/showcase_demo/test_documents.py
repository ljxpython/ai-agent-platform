from pathlib import Path
import hashlib

import fitz
import pytest

from runtime_service.tools.documents import build_document_tools


def _tool(root: Path):
    return build_document_tools(root)[0]


def test_parse_pdf_returns_page_metadata(tmp_path: Path):
    (tmp_path / "uploads").mkdir()
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Payment is due on page one.")
    raw = pdf.tobytes()
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / "uploads" / f"{digest}.pdf").write_bytes(raw)
    result = _tool(tmp_path).invoke(
        {"file_path": f"/workspace/uploads/{digest}.pdf", "query": "payment"}
    )
    assert result["format"] == "pdf"
    assert result["matched_pages"] == [1]
    assert "Payment" in result["text"]


def test_parse_text_and_rejects_escape(tmp_path: Path):
    (tmp_path / "uploads").mkdir()
    raw = b"hello"
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / "uploads" / f"{digest}.md").write_bytes(raw)
    result = _tool(tmp_path).invoke({"file_path": f"/workspace/uploads/{digest}.md"})
    assert result["text"] == "hello"
    escaped = _tool(tmp_path).invoke({"file_path": "/workspace/uploads/../secret.txt"})
    assert "workspace" in str(escaped).lower() or "invalid" in str(escaped).lower()

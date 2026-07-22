from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient

os.environ["IKIP_ENV"] = "development"
os.environ["IKIP_DEV_AUTH"] = "1"
os.environ["IKIP_STORAGE_PROFILE"] = "memory"
from ikip_api.app import create_app  # noqa: E402
from ikip_api.services import build_services  # noqa: E402

A = {"X-Dev-Subject": "eng-a", "X-Dev-Roles": "engineer", "X-Dev-Sites": "site-a"}
B = {"X-Dev-Subject": "eng-b", "X-Dev-Roles": "engineer", "X-Dev-Sites": "site-b"}
STL = b"""solid demo\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid demo\n"""  # noqa: E501


def test_stl_upload_is_processed_previewable_and_searchable_with_acl() -> None:
    c = TestClient(create_app(build_services()))
    r = c.post("/documents", headers=A, files={"file": ("demo.stl", STL, "model/stl")})
    assert r.status_code == 202
    document_id = r.json()["document_id"]
    status = c.get(f"/documents/{document_id}", headers=A)
    assert status.json()["state"] == "completed"
    assert status.json()["metadata"]["geometry_available"] is True
    assert c.get(f"/documents/{document_id}/content", headers=A).content == STL
    evidence = c.post(
        "/search", headers=A, json={"question": "CAD model properties metrics"}
    ).json()["evidence"]
    assert any(e["document_id"] == document_id for e in evidence)
    assert c.get(f"/documents/{document_id}", headers=B).status_code == 404
    assert all(
        d["document_id"] != document_id for d in c.get("/documents", headers=B).json()["documents"]
    )


def test_upload_rejects_extension_content_mismatch_and_unsafe_name() -> None:
    c = TestClient(create_app(build_services()))
    assert (
        c.post(
            "/documents", headers=A, files={"file": ("fake.pdf", STL, "application/pdf")}
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/documents", headers=A, files={"file": ("../demo.stl", STL, "model/stl")}
        ).status_code
        == 422
    )


def test_uploader_cannot_expand_acl() -> None:
    c = TestClient(create_app(build_services()))
    r = c.post(
        "/documents",
        headers=A,
        files={"file": ("demo.stl", STL, "model/stl")},
        data={"sites": "site-b"},
    )
    assert r.status_code == 403


def _pdf_with_text(text: str) -> bytes:
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",  # noqa: E501
    ]
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs += [
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def test_pdf_text_is_extracted_and_answers_can_use_it() -> None:
    c = TestClient(create_app(build_services()))
    pdf = _pdf_with_text("ZEPHYR inspection interval is 42 hours")
    r = c.post("/documents", headers=A, files={"file": ("manual.pdf", pdf, "application/pdf")})
    assert r.status_code == 202
    document_id = r.json()["document_id"]
    assert c.get(f"/documents/{document_id}", headers=A).json()["state"] == "completed"
    result = c.post(
        "/answer", headers=A, json={"question": "What is the ZEPHYR inspection interval?"}
    ).json()
    cited = {eid for claim in result["claims"] for eid in claim["citation"]["evidence_ids"]}
    assert any(eid.startswith(document_id) for eid in cited)


def test_pdf_extraction_limit_marks_document_failed_without_indexing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IKIP_PDF_MAX_EXTRACTED_TEXT_CHARS", "10")
    c = TestClient(create_app(build_services()))
    pdf = _pdf_with_text("this text deliberately exceeds ten characters")
    r = c.post("/documents", headers=A, files={"file": ("manual.pdf", pdf, "application/pdf")})
    assert r.status_code == 202
    document_id = r.json()["document_id"]
    status = c.get(f"/documents/{document_id}", headers=A).json()
    assert status["state"] == "failed"
    assert "extracted text exceeds" in status["message"]
    assert all(chunk[0] != document_id for chunk in c.app.state.services.upload_repository.chunks)


def test_pdf_page_limit_marks_document_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    from pypdf import PdfWriter

    monkeypatch.setenv("IKIP_PDF_MAX_PAGES", "1")
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    c = TestClient(create_app(build_services()))
    r = c.post(
        "/documents",
        headers=A,
        files={"file": ("two-pages.pdf", output.getvalue(), "application/pdf")},
    )
    assert r.status_code == 202
    status = c.get(f"/documents/{r.json()['document_id']}", headers=A).json()
    assert status["state"] == "failed"
    assert "pages; limit is 1" in status["message"]


def test_postgres_repository_get_reads_persisted_updated_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ikip_api.uploads import PostgresRepository

    row = (
        "doc-1",
        "manual.pdf",
        "application/pdf",
        "PDF",
        42,
        "checksum",
        "key",
        "owner",
        ["site-a"],
        ["engineer"],
        "completed",
        None,
        "created",
        "updated",
        {"pages": 1},
    )

    class Cursor:
        def execute(self, query: str, parameters: tuple[str]) -> Cursor:
            assert "updated_at::text" in query
            assert parameters == ("doc-1",)
            return self

        def fetchone(self) -> tuple[object, ...]:
            return row

    class Connection:
        def __enter__(self) -> Connection:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, query: str, parameters: tuple[str]) -> Cursor:
            return Cursor().execute(query, parameters)

    repository = PostgresRepository("unused")
    monkeypatch.setattr(repository, "_connect", Connection)
    document = repository.get("doc-1")
    assert document is not None
    assert document.created_at == "created"
    assert document.updated_at == "updated"

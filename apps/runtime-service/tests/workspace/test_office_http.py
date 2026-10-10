import asyncio
import hashlib

import httpx
import pytest
from test_image_http import SECRET, _make_token
from workspace.test_office_documents import docx_bytes, pptx_bytes, replace_member

from runtime_service.webapp import app
from runtime_service.workspace.document_reader import DOCX_MIME, PPTX_MIME
from runtime_service.workspace.documents import DocumentError, DocumentWorkspace
from runtime_service.workspace.scoped import resolve_thread_workspace


@pytest.mark.parametrize(
    "mime,builder",
    [(DOCX_MIME, docx_bytes), (PPTX_MIME, pptx_bytes)],
    ids=["docx", "pptx"],
)
def test_signed_office_upload_download_hash_and_scope(
    monkeypatch, tmp_path, mime, builder
):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    raw = builder("private document text 125")
    digest = hashlib.sha256(raw).hexdigest()

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            upload = await client.put(
                f"/internal/threads/thread-1/files/uploads/{digest}",
                content=raw,
                headers={
                    "Authorization": "Bearer "
                    + _make_token(operation="workspace-file-upload"),
                    "Content-Type": mime,
                },
            )
            assert upload.status_code == 200, upload.text
            ref = upload.json()
            assert set(ref) == {
                "version",
                "path",
                "file_name",
                "mime_type",
                "size_bytes",
                "sha256",
            }
            for scope, status in [
                ({}, 200),
                ({"tenant_id": "other"}, 404),
                ({"project_id": "other"}, 404),
                ({"assistant_id": "dearflow_agent"}, 404),
                ({"thread_id": "other"}, 404),
                ({"operation": "workspace-file-upload"}, 403),
            ]:
                thread = scope.get("thread_id", "thread-1")
                response = await client.get(
                    f"/internal/threads/{thread}/files/content",
                    params={"path": ref["path"]},
                    headers={
                        "Authorization": "Bearer "
                        + _make_token(**{"operation": "workspace-file-read", **scope})
                    },
                )
                assert response.status_code == status, (
                    response.text if status != 200 else status
                )
                if status == 200:
                    assert (
                        response.content == raw
                        and response.headers["content-type"] == mime
                    )
                    assert response.headers["cache-control"] == "private, no-store"
            root = resolve_thread_workspace(
                "tenant-a", "project-a", "thread-1", "showcase_demo"
            )
            assert len(list((root / "uploads").iterdir())) == 1
            # Rehearse removing Office writes while preserving authorized existing downloads.
            with monkeypatch.context() as rollback:

                def unsupported(*args, **kwargs):
                    raise DocumentError("unsupported_file_type", 415)

                rollback.setattr(DocumentWorkspace, "put", unsupported)
                refused = await client.put(
                    f"/internal/threads/thread-1/files/uploads/{digest}",
                    content=raw,
                    headers={
                        "Authorization": "Bearer "
                        + _make_token(operation="workspace-file-upload"),
                        "Content-Type": mime,
                    },
                )
                assert refused.status_code == 415
                kept = await client.get(
                    "/internal/threads/thread-1/files/content",
                    params={"path": ref["path"]},
                    headers={
                        "Authorization": "Bearer "
                        + _make_token(operation="workspace-file-read")
                    },
                )
                assert kept.status_code == 200 and kept.content == raw
            (root / "uploads" / ref["path"].rsplit("/", 1)[-1]).write_bytes(b"changed")
            response = await client.get(
                "/internal/threads/thread-1/files/content",
                params={"path": ref["path"]},
                headers={
                    "Authorization": "Bearer "
                    + _make_token(operation="workspace-file-read")
                },
            )
            assert response.status_code == 409 and "file_hash_mismatch" in response.text

    asyncio.run(run())


def test_office_http_rejects_malformed_and_hash_without_storing(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    valid = docx_bytes("valid")
    invalid = replace_member(valid, "word/document.xml", b"broken")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for raw, digest, status in [
                (invalid, hashlib.sha256(invalid).hexdigest(), 422),
                (valid, "a" * 64, 400),
            ]:
                response = await client.put(
                    f"/internal/threads/thread-1/files/uploads/{digest}",
                    content=raw,
                    headers={
                        "Authorization": "Bearer "
                        + _make_token(operation="workspace-file-upload"),
                        "Content-Type": DOCX_MIME,
                    },
                )
                assert response.status_code == status, response.text
            assert not list(tmp_path.rglob("*.docx"))

    asyncio.run(run())

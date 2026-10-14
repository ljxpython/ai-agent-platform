import hashlib

from runtime_service.workspace.attachment_receipts import AttachmentReceipts
from runtime_service.workspace.file_refs import FileRef
from runtime_service.workspace.target import RemoteWorkspace


def test_attachment_receipts_remote_workspace_record_and_require(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "workspaces"))

    remote_ws = RemoteWorkspace(
        scope=("tenant-test", "proj-test", "thread-1"),
        graph="showcase_demo",
        execution_host="host-1",
        node_id="node-1",
        workspace_id="test_ws_id",
    )

    content = b"docx content for testing"
    digest = hashlib.sha256(content).hexdigest()
    ref: FileRef = {
        "version": 1,
        "path": f"/workspace/uploads/{digest}.docx",
        "file_name": "10.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": len(content),
        "sha256": digest,
    }

    receipts = AttachmentReceipts(remote_ws)
    receipts.record(ref)
    assert receipts.require(ref) is True

    # Check non-showcase graph as well
    dear_ws = RemoteWorkspace(
        scope=("tenant-test", "proj-test", "thread-2"),
        graph="dearflow_agent",
        execution_host="host-1",
        node_id="node-1",
        workspace_id="test_dear_id",
    )
    dear_receipts = AttachmentReceipts(dear_ws)
    dear_receipts.record(ref)
    assert dear_receipts.require(ref) is True


def test_attachment_receipts_remote_workspace_image_and_copy(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))

    ws1 = RemoteWorkspace(
        scope=("tenant-test", "proj-test", "thread-src"),
        graph="showcase_demo",
        execution_host="host-1",
        node_id="node-1",
        workspace_id="ws_src",
    )
    ws2 = RemoteWorkspace(
        scope=("tenant-test", "proj-test", "thread-dst"),
        graph="showcase_demo",
        execution_host="host-1",
        node_id="node-1",
        workspace_id="ws_dst",
    )

    image_bytes = b"fake-png-bytes"
    img_hash = hashlib.sha256(image_bytes).hexdigest()
    img_ref = {
        "version": 1,
        "path": f"/workspace/uploads/{img_hash}.png",
        "mime_type": "image/png",
        "size_bytes": len(image_bytes),
        "sha256": img_hash,
    }

    receipts_src = AttachmentReceipts(ws1)
    saved = receipts_src.record_image(img_ref, "test_pic.png")
    assert saved["file_name"] == "test_pic.png"
    assert receipts_src.require_image(img_ref)["file_name"] == "test_pic.png"

    # Copy to ws2
    receipts_src.copy_to(ws2)
    receipts_dst = AttachmentReceipts(ws2)
    assert receipts_dst.require_image(img_ref)["file_name"] == "test_pic.png"


def test_http_upload_with_remote_workspace(monkeypatch, tmp_path):
    import asyncio
    from unittest.mock import MagicMock

    import httpx
    from test_image_http import SECRET, _make_token

    from runtime_service.webapp import app

    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))

    remote_ws = RemoteWorkspace(
        scope=("tenant-a", "project-a", "thread-1"),
        graph="showcase_demo",
        execution_host="host-1",
        node_id="node-1",
        workspace_id="test_ws_id",
    )
    monkeypatch.setattr(
        "runtime_service.http.documents.resolve_thread_workspace",
        lambda *args: remote_ws,
    )

    content = b"fake-docx-data"
    digest = hashlib.sha256(content).hexdigest()
    expected_ref = {
        "version": 1,
        "path": f"/workspace/uploads/{digest}.docx",
        "file_name": "10.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": len(content),
        "sha256": digest,
    }
    monkeypatch.setattr(
        "runtime_service.workspace.documents.DocumentWorkspace.put",
        MagicMock(return_value=expected_ref),
    )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            upload = await client.put(
                f"/internal/threads/thread-1/files/uploads/{digest}?file_name=10.docx",
                content=content,
                headers={
                    "Authorization": "Bearer "
                    + _make_token(operation="workspace-file-upload"),
                    "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                },
            )
            assert upload.status_code == 200, upload.text
            assert upload.json() == expected_ref
            assert AttachmentReceipts(remote_ws).require(expected_ref) is True

    asyncio.run(run())

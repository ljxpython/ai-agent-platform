import asyncio
import hashlib

import httpx
import pytest

from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.scoped import resolve_thread_workspace
from runtime_service.webapp import app
from test_image_http import _make_token, SECRET


def test_signed_upload_artifact_download_and_scope_isolation(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))

    async def run():
        raw = b"input text"
        digest = hashlib.sha256(raw).hexdigest()
        token = _make_token(assistant_id="dearflow_agent", operation="workspace-file-upload")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(
                f"/internal/threads/thread-1/files/uploads/{digest}", content=raw,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
            )
            assert response.status_code == 200, response.text
            root = resolve_thread_workspace("tenant-a", "project-a", "thread-1", "dearflow_agent")
            (root / "work").mkdir()
            (root / "work/result.txt").write_bytes(raw.upper())
            ref = ArtifactWorkspace(root).publish("/workspace/work/result.txt")
            for graph, tenant, expected in [
                ("dearflow_agent", "tenant-a", 200),
                ("showcase_demo", "tenant-a", 404),
                ("dearflow_agent", "tenant-b", 404),
            ]:
                token = _make_token(assistant_id=graph, tenant_id=tenant, operation="workspace-file-read")
                response = await client.get("/internal/threads/thread-1/files/content",
                    params={"path": ref["path"]}, headers={"Authorization": f"Bearer {token}"})
                assert response.status_code == expected, response.text
                if expected == 200:
                    assert response.content == raw.upper()
                    assert hashlib.sha256(response.content).hexdigest() == ref["sha256"]
            response = await client.get("/internal/threads/other/files/content",
                params={"path": ref["path"]}, headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 403
    asyncio.run(run())


def test_artifact_symlink_and_corruption_rejected(tmp_path):
    from langchain_core.tools import ToolException
    from runtime_service.workspace.documents import DocumentError
    (tmp_path / "work").mkdir()
    (tmp_path / "work/secret.txt").symlink_to("/etc/passwd")
    store = ArtifactWorkspace(tmp_path)
    with pytest.raises(ToolException):
        store.publish("/workspace/work/secret.txt")
    (tmp_path / "work/result.txt").write_text("valid")
    ref = store.publish("/workspace/work/result.txt")
    (tmp_path / "outputs" / ref["file_name"]).write_text("corrupted")
    with pytest.raises(DocumentError, match="artifact_hash_mismatch"):
        store.read(ref["path"])

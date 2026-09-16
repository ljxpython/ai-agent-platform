from __future__ import annotations

import hashlib
import io
import time
from pathlib import Path
from PIL import Image
import jwt
import httpx
import pytest

from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.webapp import app

SECRET = "r1-test-secret-with-at-least-32-bytes"


def make_test_png(color="blue", size=(10, 10)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_token(
    *,
    tenant_id: str = "tenant-a",
    project_id: str = "project-a",
    thread_id: str = "thread-1",
    assistant_id: str = "showcase_demo",
    operation: str = "image-upload",
) -> str:
    now = int(time.time())
    claims = {
        "type": "runtime_delegation",
        "sub": "user-a",
        "tenant_id": tenant_id,
        "project_id": project_id,
        "role": "developer",
        "permissions": ["runtime.tool.read"],
        "policy_version": "policy-1",
        "allowed_model_ids": ["deepseek:deepseek-chat"],
        "allowed_tool_names": ["read_reference"],
        "iat": now,
        "exp": now + 60,
        "iss": "runtime-test",
        "aud": "runtime-service",
        "scope": {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "thread_id": thread_id,
            "assistant_id": assistant_id,
            "operation": operation,
        },
        "context_hash": runtime_context_hash(None),
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def setup_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "shared"))


@pytest.mark.anyio
@pytest.mark.parametrize("graph_id", ["showcase_demo", "dearflow_agent"])
async def test_upload_and_read_image_flow(graph_id):
    png_bytes = make_test_png()
    sha256 = hashlib.sha256(png_bytes).hexdigest()
    thread_id = "thread-1"

    upload_token = _make_token(thread_id=thread_id, operation="image-upload", assistant_id=graph_id)
    read_token = _make_token(thread_id=thread_id, operation="image-read", assistant_id=graph_id)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Successful upload
        resp = await client.put(
            f"/internal/threads/{thread_id}/images/uploads/{sha256}",
            content=png_bytes,
            headers={
                "Authorization": f"Bearer {upload_token}",
                "Content-Type": "image/png",
            },
        )
        assert resp.status_code == 200, resp.text
        ref = resp.json()
        assert ref["version"] == 1
        assert ref["sha256"] == sha256
        assert ref["path"] == f"/workspace/uploads/{sha256}.png"

        # 2. Idempotent upload
        resp_idemp = await client.put(
            f"/internal/threads/{thread_id}/images/uploads/{sha256}",
            content=png_bytes,
            headers={"Authorization": f"Bearer {upload_token}"},
        )
        assert resp_idemp.status_code == 200
        assert resp_idemp.json() == ref

        # 3. Read image
        resp_read = await client.get(
            f"/internal/threads/{thread_id}/images/content",
            params={"path": ref["path"]},
            headers={"Authorization": f"Bearer {read_token}"},
        )
        assert resp_read.status_code == 200
        assert resp_read.content == png_bytes
        assert resp_read.headers["Content-Type"] == "image/png"
        assert resp_read.headers["Content-Length"] == str(len(png_bytes))
        assert resp_read.headers["Cache-Control"] == "private, no-store"
        other = "dearflow_agent" if graph_id == "showcase_demo" else "showcase_demo"
        isolated = await client.get(
            f"/internal/threads/{thread_id}/images/content", params={"path": ref["path"]},
            headers={"Authorization": "Bearer " + _make_token(thread_id=thread_id, operation="image-read", assistant_id=other)},
        )
        assert isolated.status_code == 404



@pytest.mark.anyio
async def test_upload_and_read_security_checks():
    png_bytes = make_test_png()
    sha256 = hashlib.sha256(png_bytes).hexdigest()
    thread_id = "thread-1"

    upload_token = _make_token(thread_id=thread_id, operation="image-upload")
    read_token = _make_token(thread_id=thread_id, operation="image-read")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. 401 Unauthorized (missing header)
        resp = await client.put(
            f"/internal/threads/{thread_id}/images/uploads/{sha256}",
            content=png_bytes,
        )
        assert resp.status_code == 401

        # 2. 403 Operation mismatch (use read token to upload)
        resp = await client.put(
            f"/internal/threads/{thread_id}/images/uploads/{sha256}",
            content=png_bytes,
            headers={"Authorization": f"Bearer {read_token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "image_scope_denied"

        # 3. 403 Thread mismatch
        wrong_thread_token = _make_token(thread_id="thread-other", operation="image-upload")
        resp = await client.put(
            f"/internal/threads/{thread_id}/images/uploads/{sha256}",
            content=png_bytes,
            headers={"Authorization": f"Bearer {wrong_thread_token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "runtime_target_denied"

        # 4. 409 Graph not supporting image workspace
        wrong_graph_token = _make_token(
            thread_id=thread_id, assistant_id="other_agent", operation="image-upload"
        )
        resp = await client.put(
            f"/internal/threads/{thread_id}/images/uploads/{sha256}",
            content=png_bytes,
            headers={"Authorization": f"Bearer {wrong_graph_token}"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "image_capability_unavailable"

        # 5. 400 Hash mismatch
        resp = await client.put(
            f"/internal/threads/{thread_id}/images/uploads/{'0'*64}",
            content=png_bytes,
            headers={"Authorization": f"Bearer {upload_token}"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "image_digest_mismatch"

        # 6. 404 Not Found on read
        resp = await client.get(
            f"/internal/threads/{thread_id}/images/content",
            params={"path": f"/workspace/uploads/{'f'*64}.png"},
            headers={"Authorization": f"Bearer {read_token}"},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "image_not_found"

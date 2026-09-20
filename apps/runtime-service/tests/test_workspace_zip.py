import io
import time
import zipfile
import jwt
import httpx
import pytest

from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.workspace.browser import WorkspaceBrowser
from runtime_service.webapp import app

SECRET = "r1-test-secret-with-at-least-32-bytes"


def _read_token(thread_id: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "type": "runtime_delegation", "delegation_version": 2,
            "sub": "user-a",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "role": "developer",
            "permissions": ["runtime.tool.read"],
            "policy_version": "policy-1",
            "allowed_model_ids": ["deepseek:deepseek-chat"],
            "tool_overrides": {}, "tool_policy_version": "test-tools-v2",
            "iat": now,
            "exp": now + 60,
            "iss": "runtime-test",
            "aud": "runtime-service",
            "scope": {
                "tenant_id": "tenant-a",
                "project_id": "project-a",
                "thread_id": thread_id,
                "assistant_id": "showcase_demo",
                "operation": "workspace-file-read",
            },
            "context_hash": runtime_context_hash(None),
        },
        SECRET,
        algorithm="HS256",
    )


def test_workspace_browser_create_archive_empty(tmp_path):
    browser = WorkspaceBrowser(tmp_path)
    data, filename = browser.create_archive()
    assert filename.endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.namelist() == []


def test_workspace_browser_create_archive_with_files(tmp_path):
    (tmp_path / "hello.txt").write_text("world", encoding="utf-8")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "测试.md").write_text("# 标题", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("hidden", encoding="utf-8")
    (tmp_path / ".DS_Store").write_text("system", encoding="utf-8")

    browser = WorkspaceBrowser(tmp_path)
    data, filename = browser.create_archive()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert "hello.txt" in names
        assert "subdir/测试.md" in names
        # 排除系统隐藏文件和 .git
        assert ".DS_Store" not in names
        assert ".git/config" not in names

        # 检查内容无损
        assert zf.read("hello.txt").decode("utf-8") == "world"
        assert zf.read("subdir/测试.md").decode("utf-8") == "# 标题"


@pytest.mark.anyio
async def test_workspace_zip_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))

    thread_id = "test-thread-zip"
    # 创建对应工作区物理目录
    from runtime_service.workspace.scoped import resolve_thread_workspace
    root = resolve_thread_workspace("tenant-a", "project-a", thread_id, "showcase_demo")
    root.mkdir(parents=True, exist_ok=True)
    (root / "doc.txt").write_text("archive test", encoding="utf-8")

    token = _read_token(thread_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/internal/threads/{thread_id}/workspace/zip",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert "attachment; filename*=UTF-8''workspace-" in resp.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            assert "doc.txt" in zf.namelist()
            assert zf.read("doc.txt").decode("utf-8") == "archive test"

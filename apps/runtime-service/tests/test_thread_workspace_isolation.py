import asyncio
import httpx
import jwt
import time

from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.webapp import app
from runtime_service.workspace.scoped import resolve_thread_workspace

SECRET = "r1-test-secret-with-at-least-32-bytes"


def _source_workspace_token(thread_id: str) -> str:
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


def test_thread_workspaces_are_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))

    source = resolve_thread_workspace("tenant", "project", "source", "showcase_demo")
    target = resolve_thread_workspace("tenant", "project", "target", "showcase_demo")

    assert source != target


def test_source_thread_token_cannot_read_fork_target_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    source_thread_id = "source-thread"
    target_thread_id = "fork-target-thread"
    source_token = _source_workspace_token(source_thread_id)

    async def request_target_workspace():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(
                f"/internal/threads/{target_thread_id}/workspace/tree",
                headers={"Authorization": f"Bearer {source_token}"},
            )

    response = asyncio.run(request_target_workspace())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "file_scope_denied"


def _fork_workspace_token(thread_id: str) -> str:
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
                "operation": "workspace-fork",
            },
            "context_hash": runtime_context_hash(None),
        },
        SECRET,
        algorithm="HS256",
    )


def test_fork_workspace_copies_files_and_remains_isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))

    source_thread_id = "source-thread-123"
    target_thread_id = "target-thread-456"

    source_root = resolve_thread_workspace("tenant-a", "project-a", source_thread_id, "showcase_demo")
    target_root = resolve_thread_workspace("tenant-a", "project-a", target_thread_id, "showcase_demo")

    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "hello.txt").write_text("Hello from source!", encoding="utf-8")
    (source_root / "docs").mkdir(parents=True, exist_ok=True)
    (source_root / "docs" / "design.md").write_text("# Design doc", encoding="utf-8")

    fork_token = _fork_workspace_token(target_thread_id)

    async def do_fork():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                f"/internal/threads/{target_thread_id}/workspace/fork",
                json={"source_thread_id": source_thread_id},
                headers={"Authorization": f"Bearer {fork_token}"},
            )

    response = asyncio.run(do_fork())
    assert response.status_code == 200
    data = response.json()
    assert data["forked"] is True
    assert data["files_copied"] == 2

    # 验证复制成功
    assert (target_root / "hello.txt").exists()
    assert (target_root / "hello.txt").read_text(encoding="utf-8") == "Hello from source!"
    assert (target_root / "docs" / "design.md").exists()
    assert (target_root / "docs" / "design.md").read_text(encoding="utf-8") == "# Design doc"

    # 验证独立物理隔离：修改 target 不影响 source
    (target_root / "hello.txt").write_text("Mutated in target!", encoding="utf-8")
    assert (source_root / "hello.txt").read_text(encoding="utf-8") == "Hello from source!"

    (target_root / "target_only.txt").write_text("target only", encoding="utf-8")
    assert not (source_root / "target_only.txt").exists()

    (source_root / "source_only.txt").write_text("source only", encoding="utf-8")
    assert not (target_root / "source_only.txt").exists()


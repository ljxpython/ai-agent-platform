import asyncio

import httpx
import pytest
from runtime_service.webapp import app
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.scoped import resolve_thread_workspace
from test_image_http import SECRET, _make_token


@pytest.mark.parametrize("graph", ["showcase_demo", "dearflow_agent"])
def test_signed_workspace_http(monkeypatch, tmp_path, graph):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    root = resolve_thread_workspace("tenant-a", "project-a", "thread-1", graph)
    (root / "work").mkdir(parents=True)
    (root / "work/payment.yaml").write_text("openapi: 3.1.0")
    (root / "work/view.html").write_text("<h1>Diagram</h1><script>alert(1)</script>")
    ref = ArtifactWorkspace(root).publish("/workspace/work/payment.yaml")

    async def run():
        headers = {
            "Authorization": "Bearer "
            + _make_token(assistant_id=graph, operation="workspace-file-read")
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            prefix = "/internal/threads/thread-1"
            tree = await client.get(prefix + "/workspace/tree", headers=headers)
            assert tree.status_code == 200, tree.text
            assert {x["name"] for x in tree.json()["items"]} == {"work", "outputs"}
            listed = await client.get(prefix + "/artifacts", headers=headers)
            assert listed.json()["items"] == [ref]
            for route in ("/workspace/content", "/files/content"):
                response = await client.get(
                    prefix + route, params={"path": ref["path"]}, headers=headers
                )
                assert (
                    response.status_code == 200
                    and response.content == b"openapi: 3.1.0"
                )
            preview = await client.get(
                prefix + "/workspace/preview",
                params={"path": "/workspace/work/view.html"},
                headers=headers,
            )
            assert preview.status_code == 200 and "<script" not in preview.text
            assert "sandbox" in preview.headers["content-security-policy"]
            for token, url, status in [
                (_make_token(operation="read"), prefix + "/workspace/tree", 403),
                (
                    _make_token(operation="workspace-file-read"),
                    "/internal/threads/other/artifacts",
                    403,
                ),
            ]:
                response = await client.get(
                    url, headers={"Authorization": "Bearer " + token}
                )
                assert response.status_code == status
            response = await client.get(prefix + "/workspace/tree")
            assert response.status_code == 401

    asyncio.run(run())

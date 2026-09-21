import asyncio
import io
import zipfile

import httpx
import pytest
from runtime_service.webapp import app
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.scoped import resolve_thread_workspace
from test_image_http import SECRET, _make_token
from test_image_http import make_test_png


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


def test_dear_artifact_types_errors_and_scope(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    root = resolve_thread_workspace("tenant-a", "project-a", "thread-1", "dearflow_agent")
    (root / "work").mkdir(parents=True)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("report.txt", "report")
    sources = {
        "report.md": b"# report\n", "pixel.png": make_test_png(),
        "page.html": b'<h1>Report</h1><script>alert(1)</script>',
        "data.zip": archive.getvalue(),
    }
    refs = {}
    for name, data in sources.items():
        (root / "work" / name).write_bytes(data)
        refs[name] = ArtifactWorkspace(root).publish("/workspace/work/" + name)

    async def run():
        headers = {"Authorization": "Bearer " + _make_token(
            assistant_id="dearflow_agent", operation="workspace-file-read")}
        prefix = "/internal/threads/thread-1"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers) as client:
            listed = await client.get(prefix + "/artifacts")
            assert {row["path"] for row in listed.json()["items"]} == {row["path"] for row in refs.values()}
            assert listed.json()["next_cursor"] is None
            for name, ref in refs.items():
                downloaded = await client.get(prefix + "/workspace/content", params={"path": ref["path"]})
                assert downloaded.content == sources[name]
                assert downloaded.headers["etag"] == '"' + ref["sha256"] + '"'
                preview = await client.get(prefix + "/workspace/preview", params={"path": ref["path"]})
                if name.endswith(".zip"):
                    assert preview.status_code == 415
                    assert preview.json()["detail"]["code"] == "workspace_preview_unsupported"
                elif name.endswith(".png"):
                    assert preview.status_code == 200 and preview.content == sources[name]
                    assert preview.headers["content-type"] == "image/png"
                elif name.endswith(".html"):
                    assert preview.status_code == 200 and "<script" not in preview.text
                    assert "Content-Security-Policy" in preview.text
                else:
                    assert preview.json()["text"] == sources[name].decode()
                    assert preview.json()["truncated"] is False
            for query in ({"limit": 0}, {"limit": 201}):
                assert (await client.get(prefix + "/artifacts", params=query)).status_code == 422
            assert (await client.get(prefix + "/workspace/preview")).status_code == 422
            bad_cursor = await client.get(prefix + "/artifacts", params={"cursor": "!"})
            assert bad_cursor.status_code == 400
            assert bad_cursor.json()["detail"]["code"] == "invalid_workspace_cursor"
            for change in ({"tenant_id": "other"}, {"project_id": "other"}, {"assistant_id": "showcase_demo"}):
                scope = {"assistant_id": "dearflow_agent", "operation": "workspace-file-read", **change}
                isolated = await client.get(prefix + "/artifacts", headers={"Authorization": "Bearer " + _make_token(**scope)})
                assert isolated.status_code == 200 and isolated.json()["items"] == []
            for path, status, code in (
                ("/workspace/outputs/" + "0" * 64 + ".md", 404, "artifact_not_found"),
                ("/workspace/../secret", 400, "invalid_workspace_path"),
            ):
                response = await client.get(prefix + "/workspace/content", params={"path": path})
                assert (response.status_code, response.json()["detail"]["code"]) == (status, code)
            (root / "work/large.html").write_bytes(b"x" * (256 * 1024 + 1))
            response = await client.get(prefix + "/workspace/preview", params={"path": "/workspace/work/large.html"})
            assert response.status_code == 413 and response.json()["detail"]["code"] == "html_preview_too_large"
            ref = refs["report.md"]
            (root / ref["path"].removeprefix("/workspace/")).write_bytes(b"changed")
            response = await client.get(prefix + "/workspace/content", params={"path": ref["path"]})
            assert response.status_code == 409 and response.json()["detail"]["code"] == "artifact_hash_mismatch"

    asyncio.run(run())

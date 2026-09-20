import asyncio
import base64
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
from langgraph_sdk import Auth
from runtime_service.auth.platform import deny_image_scope_on_server_resources
from runtime_service.webapp import app
from runtime_service.workspace.terminal import terminals
from test_image_http import SECRET, _make_token


def token(operation="terminal-write", **changes):
    claims = jwt.decode(
        _make_token(operation=operation),
        SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    claims.update(permissions=["runtime.tool.execute"], tool_overrides={}, tool_policy_version="test-tools-v2")
    claims.update(changes)
    return "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")


def test_signed_terminal_routes(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_TERMINAL_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_SHOWCASE_BACKEND", "local")

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            prefix = "/internal/threads/thread-1/terminals"
            write = {"authorization": token()}
            read = {"authorization": token("terminal-read")}
            body = {"request_id": str(uuid4()), "acknowledge_execution": True}
            assert (await client.post(prefix, json=body)).status_code == 401
            assert (
                await client.post(prefix, json=body, headers=read)
            ).status_code == 403
            for changes in ({"tool_overrides": {"execute": False}}, {"tool_overrides": {"unknown": False}}):
                assert (
                    await client.post(
                        prefix, json=body, headers={"authorization": token(**changes)}
                    )
                ).status_code == 403
            for changes in (
                {"acknowledge_execution": False},
                {"rows": 201},
                {"command": "sh"},
            ):
                assert (
                    await client.post(prefix, json={**body, **changes}, headers=write)
                ).status_code == 422
            created = await client.post(prefix, json=body, headers=write)
            assert created.status_code == 200, created.text
            identifier = created.json()["terminal_id"]
            assert (await client.post(prefix, json=body, headers=write)).json()[
                "terminal_id"
            ] == identifier
            assert len((await client.get(prefix, headers=read)).json()["items"]) == 1
            url = prefix + "/" + identifier
            for encoded, expected in (
                ("?", 400),
                (base64.b64encode(b"x" * 4097).decode(), 413),
            ):
                assert (
                    await client.post(
                        url + "/input",
                        json={"sequence": 0, "data_base64": encoded},
                        headers=write,
                    )
                ).status_code == expected
            assert (
                await client.get(url + "/output?offset=-1", headers=read)
            ).status_code == 422
            payload = {
                "sequence": 0,
                "data_base64": base64.b64encode(b"echo signed-terminal\n").decode(),
            }
            assert (
                await client.post(url + "/input", json=payload, headers=write)
            ).status_code == 200
            assert (
                await client.post(
                    url + "/resize", json={"rows": 35, "cols": 100}, headers=write
                )
            ).status_code == 200
            assert (await client.get(url + "/output", headers=write)).status_code == 403
            other = {"authorization": token("terminal-read", sub="other-user")}
            assert (await client.get(url + "/output", headers=other)).status_code == 404
            assert (
                await client.get(
                    url.replace("thread-1", "other") + "/output", headers=read
                )
            ).status_code == 403
            assert (await client.get(url + "/output", headers=read)).status_code == 200
            revoked = {"authorization": token("terminal-write", tool_overrides={"execute": False})}
            assert (await client.post(url + "/input", json=payload, headers=revoked)).status_code == 403
            assert (await client.delete(url, headers=revoked)).json()[
                "status"
            ] == "exited"
            monkeypatch.setenv("RUNTIME_TERMINAL_ENABLED", "0")
            assert (await client.get(prefix, headers=read)).status_code == 409

    try:
        asyncio.run(run())
    finally:
        terminals.shutdown()


def test_terminal_tokens_cannot_use_native_graph_routes():
    for operation in ("terminal-read", "terminal-write"):
        context = SimpleNamespace(user={"runtime_scope": {"operation": operation}})
        with pytest.raises(Auth.exceptions.HTTPException) as error:
            asyncio.run(deny_image_scope_on_server_resources(context, {}))
        assert error.value.status_code == 403

"""Runtime rechecks Platform's signed ACL decision before memory use."""
import asyncio
from types import SimpleNamespace

import httpx

from runtime_service.services.dearflow_agent import memory_access


def test_acl_callback_fails_closed_and_uses_current_decision(monkeypatch):
    facts = SimpleNamespace(scope=SimpleNamespace(operation="run-create"),
        principal=SimpleNamespace(project_id="project", user_id="owner"))
    monkeypatch.setattr(memory_access, "verified_delegation_from_user", lambda user: facts)
    monkeypatch.setenv("PLATFORM_RUNTIME_MEMORY_AUTH_URL", "http://platform/check")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "test-secret")
    responses = [True, False]

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, *, params, headers):
            assert url == "http://platform/check"
            assert params == {"project_id": "project", "thread_id": "thread", "user_id": "owner"}
            assert len(headers["x-runtime-memory-signature"]) == 64
            return httpx.Response(200, json={"allowed": responses.pop(0)},
                                  request=httpx.Request("GET", url))

    monkeypatch.setattr(memory_access.httpx, "AsyncClient", Client)
    assert asyncio.run(memory_access.memory_allowed({}, "thread"))
    assert not asyncio.run(memory_access.memory_allowed({}, "thread"))
    monkeypatch.delenv("PLATFORM_RUNTIME_MEMORY_AUTH_URL")
    assert not asyncio.run(memory_access.memory_allowed({}, "thread"))

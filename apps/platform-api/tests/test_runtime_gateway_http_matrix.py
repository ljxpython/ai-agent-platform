"""Every public gateway route must preserve scope and fail before SSE starts."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
from fastapi import FastAPI

from platform_api.core.errors import ForbiddenError, register_exception_handlers
from platform_api.core.context.models import ActorContext
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_actor_context,
    get_runtime_gateway_service,
    router,
)

# Explicit inventory: a newly exposed route must receive a matrix case.
CASES = [
    ("GET", "/info", "get_info"),
    ("POST", "/graphs/search", "search_graphs"),
    ("POST", "/graphs/count", "count_graphs"),
    ("POST", "/threads", "create_thread"),
    ("POST", "/threads/search", "search_threads"),
    ("POST", "/threads/count", "count_threads"),
    ("GET", "/threads/{thread_id}", "get_thread"),
    ("DELETE", "/threads/{thread_id}", "delete_thread"),
    ("GET", "/threads/{thread_id}/state", "get_thread_state"),
    ("POST", "/threads/{thread_id}/state", "update_thread_state"),
    ("POST", "/threads/{thread_id}/history", "get_thread_history"),
    ("POST", "/threads/{thread_id}/runs", "create_thread_run"),
    ("POST", "/threads/{thread_id}/runs/stream", "stream_thread_run"),
    ("POST", "/threads/{thread_id}/commands", "send_thread_command"),
    ("POST", "/threads/{thread_id}/stream/events", "stream_thread_events"),
    ("GET", "/threads/{thread_id}/runs/{run_id}", "get_thread_run"),
    ("GET", "/threads/{thread_id}/runs", "list_thread_runs"),
    ("GET", "/threads/{thread_id}/runs/{run_id}/join", "join_thread_run"),
    ("GET", "/threads/{thread_id}/runs/{run_id}/stream", "join_thread_run_stream"),
    ("POST", "/threads/{thread_id}/runs/{run_id}/cancel", "cancel_thread_run"),
]


class GatewayHttpMatrixTest(unittest.IsolatedAsyncioTestCase):
    async def test_public_route_inventory_and_boundaries(self):
        self.assertEqual(
            {
                (method, route.path.removeprefix("/api/langgraph"))
                for route in router.routes
                for method in route.methods
            },
            {(method, path) for method, path, _ in CASES},
        )
        app = FastAPI()
        app.include_router(router)
        register_exception_handlers(app)
        actor = SimpleNamespace(user_id="user-1")
        service = SimpleNamespace()
        app.dependency_overrides[get_actor_context] = lambda: actor
        app.dependency_overrides[get_runtime_gateway_service] = lambda: service

        @app.middleware("http")
        async def scope(request, call_next):
            request.state.platform_context = SimpleNamespace(
                project=SimpleNamespace(project_id=request.headers.get("x-project-id"))
            )
            return await call_next(request)

        async def events():
            yield b'data: {"visible":"yes","runtime_model_ref":"opaque"}\n\n'

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for method, path, name in CASES:
                for outcome in ("success", "forbidden", "missing_scope"):
                    with self.subTest(route=path, method=method, outcome=outcome):
                        streaming = name in {
                            "stream_thread_run",
                            "stream_thread_events",
                            "join_thread_run_stream",
                        }
                        callback = AsyncMock(
                            return_value=(
                                events()
                                if streaming
                                else {
                                    "visible": "yes",
                                    "nested": {"runtime_model_ref": "opaque"},
                                }
                            )
                        )
                        if outcome == "forbidden":
                            callback.side_effect = ForbiddenError(
                                code="scope_denied", message="Denied"
                            )
                        setattr(service, name, callback)
                        headers = {"Idempotency-Key": "request-1"}
                        if outcome != "missing_scope":
                            headers["x-project-id"] = "project-1"
                        response = await client.request(
                            method,
                            "/api/langgraph"
                            + path.format(thread_id="thread-1", run_id="run-1"),
                            json={"probe": "body"} if method == "POST" else None,
                            headers=headers,
                        )
                        expected = {
                            "success": 200,
                            "forbidden": 403,
                            "missing_scope": 400,
                        }[outcome]
                        self.assertEqual(response.status_code, expected, response.text)
                        if outcome == "missing_scope":
                            callback.assert_not_awaited()
                            continue
                        callback.assert_awaited_once()
                        kwargs = callback.call_args.kwargs
                        self.assertIs(kwargs["actor"], actor)
                        self.assertEqual(kwargs["project_id"], "project-1")
                        for key in ("thread_id", "run_id"):
                            if "{" + key + "}" in path:
                                self.assertEqual(kwargs[key], key.replace("_id", "-1"))
                        if method == "POST":
                            self.assertEqual(kwargs["payload"], {"probe": "body"})
                        if name in {
                            "create_thread_run",
                            "stream_thread_run",
                            "send_thread_command",
                        }:
                            self.assertEqual(kwargs["idempotency_key"], "request-1")
                        if outcome == "success":
                            self.assertIn("yes", response.text)
                            self.assertNotIn("opaque", response.text)
                            self.assertNotIn("runtime_model_ref", response.text)
                        else:
                            self.assertEqual(
                                response.json()["error"]["code"], "scope_denied"
                            )
                            self.assertNotIn(
                                "text/event-stream", response.headers["content-type"]
                            )

            # Exercise real authorization for every route, not a mocked rejection.
            upstream = Mock()
            session_factory = Mock()
            service = RuntimeGatewayService(
                session_factory=session_factory, upstream=upstream
            )
            for principal, expected in (
                (ActorContext(), 401),
                (ActorContext(user_id="outsider"), 403),
            ):
                actor = principal
                for method, path, _ in CASES:
                    with self.subTest(route=path, principal=principal.user_id):
                        response = await client.request(
                            method,
                            "/api/langgraph"
                            + path.format(thread_id="thread-1", run_id="run-1"),
                            json={} if method == "POST" else None,
                            headers={"x-project-id": "project-1"},
                        )
                        self.assertEqual(response.status_code, expected, response.text)
            self.assertEqual(upstream.mock_calls, [])
            session_factory.assert_not_called()

            # A caller authorized for project-1 still cannot touch another project's thread.
            service._prepare_project_scope = Mock()
            upstream.get_thread = AsyncMock(
                return_value={"metadata": {"project_id": "other-project"}}
            )
            actor = ActorContext(user_id="member")
            for method, path, _ in CASES:
                if "{thread_id}" not in path:
                    continue
                with self.subTest(cross_project=path, method=method):
                    response = await client.request(
                        method,
                        "/api/langgraph"
                        + path.format(thread_id="thread-1", run_id="run-1"),
                        json={} if method == "POST" else None,
                        headers={"x-project-id": "project-1"},
                    )
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertEqual(
                        response.json()["error"]["code"], "thread_project_denied"
                    )
            self.assertTrue(
                all(call[0] == "get_thread" for call in upstream.mock_calls)
            )

            service = SimpleNamespace()
            queries = [
                (
                    "/state?subgraphs=true&checkpoint_id=checkpoint-1",
                    "get_thread_state",
                    {"subgraphs": True, "checkpoint_id": "checkpoint-1"},
                ),
                (
                    "/runs?limit=7&offset=2&status=success&select=run_id&select=status",
                    "list_thread_runs",
                    {
                        "limit": 7,
                        "offset": 2,
                        "status": "success",
                        "select": ["run_id", "status"],
                    },
                ),
                (
                    "/runs/run-1/stream?cancel_on_disconnect=false&stream_mode=values&last_event_id=12",
                    "join_thread_run_stream",
                    {
                        "cancel_on_disconnect": False,
                        "stream_mode": "values",
                        "last_event_id": "12",
                    },
                ),
            ]
            for suffix, name, params in queries:
                with self.subTest(query=suffix):
                    callback = AsyncMock(
                        return_value=events() if name.endswith("stream") else {}
                    )
                    setattr(service, name, callback)
                    response = await client.get(
                        "/api/langgraph/threads/thread-1" + suffix,
                        headers={"x-project-id": "project-1"},
                    )
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(callback.call_args.kwargs["params"], params)


if __name__ == "__main__":
    unittest.main()

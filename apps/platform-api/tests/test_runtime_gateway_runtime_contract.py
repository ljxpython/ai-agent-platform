from __future__ import annotations

from contextlib import nullcontext

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch

from platform_api.core.errors import BadRequestError, ForbiddenError
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
    _merge_runtime_context,
    _normalize_protocol_lifecycle_frame,
    _runtime_context_snapshot,
)


class RuntimeGatewayRuntimeContractTest(unittest.IsolatedAsyncioTestCase):
    def test_protocol_lifecycle_is_normalized_for_frontend_sdk(self) -> None:
        frame, terminal = _normalize_protocol_lifecycle_frame(
            b'data: {"seq":4,"method":"lifecycle","params":{"namespace":[],"data":{"event":"success","status":"success"},"run_id":"run-1"}}'
        )

        self.assertEqual(
            frame,
            b'data: {"seq":4,"method":"lifecycle","params":{"namespace":[],"data":{"event":"completed","status":"success"},"run_id":"run-1"}}',
        )
        self.assertEqual(terminal, {"run_id": "run-1", "status": "success"})

    def test_protocol_lifecycle_keeps_interrupt_active(self) -> None:
        _, terminal = _normalize_protocol_lifecycle_frame(
            b'data: {"method":"lifecycle","params":{"data":{"event":"interrupted","status":"interrupted"},"run_id":"run-1"}}'
        )

        self.assertIsNone(terminal)

    def test_context_hash_matches_runtime_context_v1_canonicalization(self) -> None:
        context_hash, snapshot = _runtime_context_snapshot(
            {
                "params": {
                    "context": {
                        "model_id": "model-1",
                        "temperature": 0.2,
                        "top_p": 1,
                        "max_tokens": 128,
                        "tools": ["search"],
                    },
                    "config": {
                        "configurable": {
                            "platform_runtime": {
                                "temperature": 0,
                                "tools": ["utc_now", "search"],
                            }
                        }
                    },
                }
            }
        )

        self.assertEqual(
            context_hash,
            "sha256:67b573b27851ae07ed231facfcccf00fe7450a6aab56541e4a9cc790da0c8864",
        )
        self.assertEqual(
            snapshot,
            {
                "model_id": "model-1",
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 128,
                "tools": ["search", "utc_now"],
            },
        )

    def test_runtime_context_precedence_is_explicit_then_agent_then_project(self) -> None:
        self.assertEqual(
            _merge_runtime_context(
                project_default_model="project:model",
                agent_defaults={"model_id": "agent:model", "temperature": 0.4},
                requested={"temperature": 0.8},
            ),
            {"model_id": "agent:model", "temperature": 0.8},
        )
        self.assertEqual(
            _merge_runtime_context(
                project_default_model="project:model",
                agent_defaults={},
                requested={},
            ),
            {"model_id": "project:model"},
        )

    async def test_thread_graph_target_does_not_allow_a_different_target(self) -> None:
        service = RuntimeGatewayService(session_factory=None, upstream=SimpleNamespace())
        service._assistant_belongs_project = Mock(return_value=False)  # type: ignore[method-assign]
        thread = {"metadata": {"project_id": "project-1", "graph_id": "test_case_agent"}}

        with self.assertRaises(ForbiddenError):
            service._assert_runtime_target_allowed(
                project_id="project-1",
                assistant_id="test_case_agent",
                thread=thread,
            )
        with self.assertRaises(ForbiddenError) as denied:
            service._assert_runtime_target_allowed(
                project_id="project-1",
                assistant_id="sql_agent",
                thread=thread,
            )

        self.assertEqual(denied.exception.code, "runtime_target_denied")

    async def test_agent_profile_defaults_are_filtered_before_runtime_context(self) -> None:
        service = RuntimeGatewayService(session_factory=object(), upstream=SimpleNamespace())
        service._project_default_model_id = Mock(return_value="project:model")  # type: ignore[method-assign]
        agent = SimpleNamespace(
            context={
                "model_id": "agent:model",
                "temperature": 0.4,
                "system_prompt": "must not cross the boundary",
                "project_id": "must not cross the boundary",
                "unknown": "must not cross the boundary",
            }
        )
        with (
            patch("platform_api.modules.runtime_gateway.application.service.session_scope", return_value=nullcontext(object())),
            patch("platform_api.modules.runtime_gateway.application.service.SqlAlchemyAssistantsRepository") as repository,
        ):
            repository.return_value.get_by_project_and_graph_id.return_value = agent
            result = service._inject_project_default_model(
                project_id="00000000-0000-0000-0000-000000000001",
                payload={"assistant_id": "agent", "context": {"temperature": 0.8}},
            )

        self.assertEqual(
            result["context"],
            {"model_id": "agent:model", "temperature": 0.8},
        )

    def test_inject_project_scope_moves_runtime_fields_into_context(self) -> None:
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=SimpleNamespace(),
        )

        payload = service._inject_project_scope(
            project_id="project-1",
            payload={
                "project_id": "legacy-project",
                "context": {
                    "system_prompt": "context prompt",
                    "project_id": "legacy-project",
                    "user_id": "user-1",
                },
                "config": {
                    "recursion_limit": 12,
                    "model_id": "config-model",
                    "metadata": {
                        "request_origin": "workspace-ui",
                        "project_id": "legacy-project",
                    },
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_id": "checkpoint-1",
                        "enable_tools": True,
                        "tools": ["utc_now"],
                        "project_id": "legacy-project",
                        "tenant_id": "tenant-1",
                    },
                },
                "metadata": {
                    "source": "chat",
                    "project_id": "legacy-project",
                },
            },
        )

        self.assertEqual(
            payload,
            {
                "context": {
                    "system_prompt": "context prompt",
                    "model_id": "config-model",
                    "enable_tools": True,
                    "tools": ["utc_now"],
                },
                "config": {
                    "recursion_limit": 12,
                    "metadata": {
                        "request_origin": "workspace-ui",
                    },
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_id": "checkpoint-1",
                    },
                },
                "metadata": {
                    "source": "chat",
                },
            },
        )



    async def test_v2_event_subscription_preserves_upstream_before_http_filter(self) -> None:
        async def stream():
            yield b'data: {"method":"lifecycle","params":{"namespace":[],"data":{"event":"success","status":"success"},"run_id":"run-1"}}\n\n'

        upstream = SimpleNamespace(stream_thread_events=AsyncMock(return_value=stream()))
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]
        payload = {"channels": ["messages", "values"], "since": 12}

        result = await service.stream_thread_events(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            payload=payload,
        )

        self.assertEqual(
            [chunk async for chunk in result],
            [
                b'data: {"method":"lifecycle","params":{"namespace":[],"data":{"event":"success","status":"success"},"run_id":"run-1"}}\n\n'
            ],
        )
        service._load_thread.assert_awaited_once_with(
            actor=unittest.mock.ANY,
            project_id="project-1",
            thread_id="thread-1",
            write=False,
        )
        upstream.stream_thread_events.assert_awaited_once_with("thread-1", payload)

    async def test_v2_event_subscription_rejects_unknown_channels_before_upstream(self) -> None:
        upstream = SimpleNamespace(stream_thread_events=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        with self.assertRaises(BadRequestError) as ctx:
            await service.stream_thread_events(
                actor=SimpleNamespace(),
                project_id="project-1",
                thread_id="thread-1",
                payload={"channels": ["debug", "custom:progress"]},
            )

        self.assertEqual(ctx.exception.code, "invalid_protocol_event_subscription")
        upstream.stream_thread_events.assert_not_awaited()

    async def test_join_stream_disconnect_never_cancels_run(self) -> None:
        upstream = SimpleNamespace(join_thread_run_stream=AsyncMock(return_value=object()))
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        await service.join_thread_run_stream(
            actor=SimpleNamespace(),
            project_id="project-1",
            thread_id="thread-1",
            run_id="run-1",
            params={"stream_mode": "values"},
        )
        upstream.join_thread_run_stream.assert_awaited_once_with(
            "thread-1",
            "run-1",
            {"stream_mode": "values", "cancel_on_disconnect": False},
        )

    async def test_join_stream_rejects_disconnect_cancellation_before_upstream(self) -> None:
        upstream = SimpleNamespace(join_thread_run_stream=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        with self.assertRaises(BadRequestError) as ctx:
            await service.join_thread_run_stream(
                actor=SimpleNamespace(),
                project_id="project-1",
                thread_id="thread-1",
                run_id="run-1",
                params={"cancel_on_disconnect": True},
            )

        self.assertEqual(ctx.exception.code, "cancel_on_disconnect_not_supported")
        upstream.join_thread_run_stream.assert_not_awaited()

    async def test_invalid_v2_command_does_not_reach_upstream(self) -> None:
        upstream = SimpleNamespace(send_thread_command=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]
        service._project_default_model_id = Mock(return_value=None)  # type: ignore[method-assign]

        with self.assertRaises(BadRequestError) as ctx:
            await service.send_thread_command(
                actor=SimpleNamespace(),
                project_id="project-1",
                thread_id="thread-1",
                payload={"id": "invalid", "method": "run.start", "params": {}},
            )

        self.assertEqual(ctx.exception.code, "invalid_protocol_command")
        upstream.send_thread_command.assert_not_awaited()


    async def test_run_launch_attaches_opaque_model_reference_from_platform_runtime_context(self) -> None:
        service = RuntimeGatewayService(session_factory=object(), upstream=SimpleNamespace())
        service._runtime_model_config_secret = "test-secret"  # type: ignore[attr-defined]
        service._runtime_model_config_ttl_seconds = 60  # type: ignore[attr-defined]
        service._runtime_id = "runtime-1"  # type: ignore[attr-defined]
        item = SimpleNamespace(enabled=True)
        with (
            patch("platform_api.modules.runtime_gateway.application.service.session_scope", return_value=nullcontext(object())),
            patch("platform_api.modules.runtime_gateway.application.service.SqlAlchemyRuntimeCatalogRepository") as repository,
            patch("platform_api.modules.runtime_gateway.application.service.create_model_reference", return_value="v1.opaque.sig"),
        ):
            repository.return_value.get_model_by_id.return_value = item
            result = service._attach_runtime_model_reference(
                project_id="project-1",
                payload={
                    "config": {
                        "configurable": {
                            "platform_runtime": {"model_id": "11111111-1111-1111-1111-111111111111"},
                        },
                    },
                },
            )

        configurable = result["config"]["configurable"]
        self.assertEqual(configurable["runtime_model_ref"], "v1.opaque.sig")
        self.assertNotIn("api_key", str(result))



    async def test_thread_state_redacts_runtime_private_fields(self) -> None:
        upstream = SimpleNamespace(
            get_thread_state=AsyncMock(return_value={"values": {"_runtime_model_ref": "opaque", "runtime_model_ref": "opaque", "message": "hello"}})
        )
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {}})  # type: ignore[method-assign]

        result = await service.get_thread_state(
            actor=SimpleNamespace(), project_id="project-1", thread_id="thread-1", params=None
        )

        self.assertEqual(result, {"values": {"message": "hello"}})





if __name__ == "__main__":
    unittest.main()

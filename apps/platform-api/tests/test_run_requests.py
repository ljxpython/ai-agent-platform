from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch

from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    UpstreamServiceError,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunRequestRecord,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import (
    RunRequestsRepository,
)
from sqlalchemy import select


class RunRequestsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "durable-runs.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)
        self.actor = ActorContext(user_id="user-1", subject="user-1")
        run_start = AsyncMock(return_value={"run_id": "run-1"})
        self.upstream = SimpleNamespace(
            create_thread_run=run_start,
            send_thread_command=run_start,
            get_thread_run=AsyncMock(
                return_value={"run_id": "run-1", "status": "success"}
            ),
            get_thread_state=AsyncMock(
                return_value={"metadata": {"run_id": "run-1"}, "tasks": [{"interrupts": [{"id": "interrupt-1"}]}]}
            ),
            list_thread_runs=AsyncMock(return_value={"runs": []}),
            cancel_thread_run=AsyncMock(return_value={"status": "accepted"}),
        )
        self.service = RuntimeGatewayService(
            session_factory=self._session_factory,
            upstream=self.upstream,
        )
        self.service._load_thread = AsyncMock(
            return_value={"metadata": {"graph_id": "agent-1"}}
        )  # type: ignore[method-assign]
        self.service._project_default_model_id = Mock(return_value=None)  # type: ignore[method-assign]
        self.service._assert_runtime_options_allowed = Mock()  # type: ignore[method-assign]
        self.service._assert_runtime_target_allowed = Mock()  # type: ignore[method-assign]

    def tearDown(self) -> None:
        self._engine.dispose()
        self._tmpdir.cleanup()

    @staticmethod
    def _command(*, content: str = "hello") -> dict:
        return {
            "id": 1,
            "method": "run.start",
            "params": {
                "assistant_id": "agent-1",
                "input": {"messages": [{"type": "human", "content": content}]},
            },
        }

    async def start(self, key="request-1", content="hello", **kwargs):
        return await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=self._command(content=content),
            idempotency_key=key,
            **kwargs,
        )

    def records(self):
        with self._session_factory() as session:
            return session.scalars(select(RunRequestRecord)).all()

    async def test_retry_conflict_and_independent_actions(self):
        await self.start()
        await self.start()
        self.assertEqual(self.upstream.create_thread_run.await_count, 1)
        with self.assertRaises(ConflictError):
            await self.start(content="different")
        await self.start(key="request-2")
        self.assertEqual(self.upstream.create_thread_run.await_count, 2)
        self.assertEqual(len(self.records()), 2)
        self.assertFalse(hasattr(self.records()[0], "active"))

    async def test_changed_protocol_id_is_not_a_new_action(self):
        await self.start()
        await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload={**self._command(), "id": 99},
            idempotency_key="request-1",
        )
        self.assertEqual(self.upstream.create_thread_run.await_count, 1)

    async def test_unknown_submission_retries_same_upstream_key_after_restart(self):
        self.upstream.create_thread_run.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            await self.start()
        self.assertEqual(self.records()[0].submission_status, "unknown")
        first = self.upstream.create_thread_run.call_args.args[1]
        self.service = RuntimeGatewayService(
            session_factory=self._session_factory, upstream=self.upstream
        )
        self.service._load_thread = AsyncMock(return_value={})
        self.service._project_default_model_id = Mock(return_value=None)
        self.service._assert_runtime_options_allowed = Mock()
        self.service._assert_runtime_target_allowed = Mock()
        self.upstream.create_thread_run.side_effect = None
        await self.start()
        second = self.upstream.create_thread_run.call_args.args[1]
        self.assertEqual(first["idempotency_key"], second["idempotency_key"])
        self.assertEqual(self.records()[0].submission_status, "accepted")

    async def test_rejection_has_no_local_active_lock(self):
        self.upstream.create_thread_run.side_effect = UpstreamServiceError(
            code="busy", message="busy", upstream="langgraph", status_code=409
        )
        with self.assertRaises(UpstreamServiceError):
            await self.start()
        self.assertEqual(self.records()[0].submission_status, "rejected")
        self.upstream.create_thread_run.side_effect = None
        await self.start()
        self.assertEqual(self.records()[0].run_id, "run-1")

    async def test_missing_run_id_is_recoverable(self):
        self.upstream.create_thread_run.return_value = {}
        with self.assertRaises(UpstreamServiceError):
            await self.start()
        self.assertEqual(self.records()[0].submission_status, "unknown")
        self.upstream.create_thread_run.return_value = {"run_id": "run-1"}
        await self.start()
        self.assertEqual(self.records()[0].run_id, "run-1")

    async def test_identical_standard_requests_without_key_are_independent(self):
        for _ in range(2):
            await self.service.create_thread_run(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload={"assistant_id": "agent-1", "input": {"x": 1}},
            )
        self.assertEqual(len(self.records()), 2)
        calls = self.upstream.create_thread_run.call_args_list
        self.assertNotEqual(
            calls[0].args[1]["idempotency_key"], calls[1].args[1]["idempotency_key"]
        )

    async def test_resume_maps_interrupt_and_preserves_both_run_ids(self):
        await self.start()
        self.upstream.create_thread_run.return_value = {"run_id": "run-2"}
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "interrupted"}
        response = {
            "id": 2,
            "method": "input.respond",
            "params": {
                "interrupt_id": "interrupt-1",
                "response": {"decision": "approve"},
            },
        }

        async def resume(payload):
            return await self.service.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=payload,
            )

        await resume(response)
        sent = self.upstream.create_thread_run.call_args.args[1]
        self.assertEqual(
            sent["command"], {"resume": {"interrupt-1": {"decision": "approve"}}}
        )
        rows = self.records()
        self.assertEqual({r.run_id for r in rows}, {"run-1", "run-2"})
        self.assertEqual(next(r for r in rows if r.interrupt_id).parent_run_id, "run-1")
        self.upstream.get_thread_state.return_value = {"tasks": []}
        self.upstream.get_thread_run.return_value = {"run_id": "run-2"}
        await resume(response)
        self.assertEqual(self.upstream.create_thread_run.await_count, 2)
        with self.assertRaises(ConflictError):
            await resume(
                {**response, "params": {**response["params"], "response": "reject"}}
            )
        with self.assertRaises(BadRequestError):
            await resume(
                {
                    **response,
                    "params": {**response["params"], "context": {"model_id": "other"}},
                }
            )
        self.service._assert_runtime_target_allowed.side_effect = ForbiddenError(
            code="disabled", message="disabled"
        )
        with self.assertRaises(ForbiddenError):
            await resume(response)

    async def test_model_revocation_rechecks_saved_context(self):
        self.service._project_default_model_id.return_value = "model-old"
        await self.start()
        self.service._project_default_model_id.return_value = "model-new"
        self.upstream.get_thread_run.return_value = {"run_id": "run-1"}
        await self.start()
        self.assertEqual(self.upstream.create_thread_run.await_count, 1)
        self.assertEqual(self.records()[0].context_snapshot["model_id"], "model-old")
        self.service._assert_runtime_options_allowed.side_effect = ForbiddenError(
            code="disabled", message="disabled"
        )
        with self.assertRaises(ForbiddenError):
            await self.start()

    async def test_other_identity_and_missing_membership_are_denied(self):
        await self.start()
        self.actor = ActorContext(user_id="other", subject="other")
        with self.assertRaises(ConflictError):
            await self.start()
        denied = RuntimeGatewayService(
            session_factory=self._session_factory, upstream=self.upstream
        )
        with self.assertRaises(ForbiddenError):
            await denied.send_thread_command(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
                payload=self._command(),
                idempotency_key="x",
            )

    async def test_request_record_does_not_store_message_or_replace_run(self):
        await self.start(content="private-message")
        row = self.records()[0]
        self.assertNotIn("private-message", str(row.__dict__))
        with self.assertRaises(ConflictError):
            with self._session_factory.begin() as session:
                RunRequestsRepository(session).mark(
                    str(row.id), "accepted", "different-run"
                )

    async def test_delegation_is_bound_to_frozen_context_and_upstream_key(self):
        captured = []
        self.service._delegation_headers_factory = lambda **values: captured.append(values) or {"authorization": "scoped"}
        self.upstream.with_forwarded_headers = lambda headers: self.upstream
        await self.start()
        self.assertEqual(captured[0]["context_hash"], self.records()[0].context_hash)
        self.assertEqual(captured[0]["agent_key"], "agent-1")
        self.assertEqual(captured[0]["thread_id"], "thread-1")
        sent = self.upstream.create_thread_run.call_args.args[1]
        self.assertEqual(sent["multitask_strategy"], "reject")
        self.assertTrue(sent["idempotency_key"].startswith("platform:"))

    async def test_commit_response_loss_and_cancelled_submission_reuse_key(self):
        for failure in (RuntimeError("db association lost"), asyncio.CancelledError()):
            with self.subTest(failure=type(failure).__name__):
                key = type(failure).__name__
                if isinstance(failure, asyncio.CancelledError):
                    self.upstream.create_thread_run.side_effect = failure
                    with self.assertRaises(asyncio.CancelledError):
                        await self.start(key=key)
                    self.upstream.create_thread_run.side_effect = None
                else:
                    with patch.object(RunRequestsRepository, "mark", side_effect=failure):
                        with self.assertRaises(RuntimeError):
                            await self.start(key=key)
                first = self.upstream.create_thread_run.call_args.args[1]
                await self.start(key=key)
                second = self.upstream.create_thread_run.call_args.args[1]
                self.assertEqual(first["idempotency_key"], second["idempotency_key"])
                self.assertEqual(next(r for r in self.records() if r.idempotency_key == key).run_id, "run-1")

    async def test_standard_multi_resume_uses_parent_config_and_current_authorization(self):
        await self.service.create_thread_run(
            actor=self.actor, project_id="project-1", thread_id="thread-1",
            payload={"assistant_id": "agent-1", "config": {"recursion_limit": 100}, "input": {}},
            idempotency_key="initial")
        self.upstream.get_thread_state.return_value = {"metadata": {"run_id": "run-1"}, "interrupts": [{"id": "a"}, {"id": "b"}]}
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "interrupted"}
        self.upstream.create_thread_run.return_value = {"run_id": "run-2"}
        resume = {"command": {"resume": {"b": {"decisions": [{"type": "reject", "message": "no"}]},
                                         "a": {"decisions": [{"type": "approve"}]}}}}
        await self.service.create_thread_run(actor=self.actor, project_id="project-1",
            thread_id="thread-1", payload=resume)
        sent = self.upstream.create_thread_run.call_args.args[1]
        self.assertEqual(sent["config"], {"recursion_limit": 100})
        self.assertEqual(sent["command"], resume["command"])
        self.assertEqual(next(r for r in self.records() if r.run_id == "run-2").parent_run_id, "run-1")
        count = self.upstream.create_thread_run.await_count
        await self.service.create_thread_run(actor=self.actor, project_id="project-1",
            thread_id="thread-1", payload=resume)
        self.assertEqual(self.upstream.create_thread_run.await_count, count)
        for extra in ({"context": {"model_id": "other"}}, {"input": {}}, {"config": {"recursion_limit": 1}}):
            with self.assertRaises(BadRequestError):
                await self.service.create_thread_run(actor=self.actor, project_id="project-1",
                    thread_id="thread-1", payload={**resume, **extra})
        self.service._assert_runtime_options_allowed.side_effect = ForbiddenError(code="revoked", message="revoked")
        with self.assertRaises(ForbiddenError):
            await self.service.create_thread_run(actor=self.actor, project_id="project-1",
                thread_id="thread-1", payload=resume)

    async def test_stale_interrupt_and_configurable_secrets_are_rejected(self):
        await self.start()
        with self.assertRaises(ConflictError):
            await self.service.create_thread_run(actor=self.actor, project_id="project-1",
                thread_id="thread-1", payload={"command": {"resume": {"stale": "approve"}}})
        with self.assertRaises(BadRequestError):
            await self.service.create_thread_run(actor=self.actor, project_id="project-1",
                thread_id="thread-1", payload={"assistant_id": "agent-1",
                    "config": {"configurable": {"api_key": "secret"}}})

    async def test_cancel_then_new_action_gets_new_submission(self):
        await self.start()
        await self.service.cancel_thread_run(actor=self.actor, project_id="project-1",
            thread_id="thread-1", run_id="run-1", payload={"action": "interrupt"})
        self.upstream.create_thread_run.return_value = {"run_id": "run-2"}
        await self.start(key="after-cancel")
        self.assertEqual({r.run_id for r in self.records()}, {"run-1", "run-2"})

    async def test_resume_uses_checkpoint_origin_not_latest_cancelled_request(self):
        await self.start()
        self.upstream.create_thread_run.return_value = {"run_id": "cancelled-run"}
        await self.start(key="cancelled-later")
        self.upstream.create_thread_run.return_value = {"run_id": "resumed-run"}
        self.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "interrupted"}
        await self.service.create_thread_run(actor=self.actor, project_id="project-1",
            thread_id="thread-1", payload={"command": {"resume": {"interrupt-1": "approve"}}})
        parent = next(r for r in self.records() if r.run_id == "resumed-run").parent_run_id
        self.assertEqual(parent, "run-1")

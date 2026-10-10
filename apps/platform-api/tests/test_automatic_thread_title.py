"""Automatic-title boundaries, using real ACL decisions and scoped transports."""

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from platform_api.adapters.langgraph.runtime_gateway_upstream import (
    LangGraphRuntimeGatewayUpstream,
)
from platform_api.adapters.langgraph.sdk_client import redact_runtime_private_fields
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import BadRequestError, ForbiddenError, PlatformApiError
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.application.thread_titles import (
    TITLE_SEED_KEY,
    conversation_materials,
)
from tests.thread_acl_fixture import thread_acl_factory

THREAD = str(uuid4())
RUN = str(uuid4())


class AutomaticThreadTitleTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.actor = ActorContext(
            user_id="owner", project_roles={"p": ("project_executor",)}
        )
        self.thread = {
            "thread_id": THREAD,
            "status": "idle",
            "metadata": {
                "project_id": "p",
                "graph_id": "reference_agent",
                "title": "规则标题",
                TITLE_SEED_KEY: "规则标题",
                "owner_user_id": "owner",
                "visibility": "private",
                "access_version": 1,
            },
        }
        self.state = {
            "checkpoint": {"checkpoint_id": "first"},
            "values": {
                "messages": [
                    {"type": "human", "content": "规划权限设计"},
                    {"type": "ai", "content": "使用精确授权"},
                ]
            },
            "next": [],
        }
        self.upstream = SimpleNamespace(
            get_thread=AsyncMock(side_effect=lambda *_: copy.deepcopy(self.thread)),
            get_thread_state=AsyncMock(
                side_effect=lambda *_: copy.deepcopy(self.state)
            ),
            get_thread_run=AsyncMock(
                return_value={
                    "thread_id": THREAD,
                    "run_id": RUN,
                    "assistant_id": "reference_agent",
                    "status": "success",
                    "kwargs": {},
                }
            ),
            list_thread_runs=AsyncMock(return_value=[]),
            summarize_thread_title=AsyncMock(
                return_value={
                    "thread_id": THREAD,
                    "title": "权限设计",
                    "outcome": "applied",
                    "reason": None,
                }
            ),
            update_thread=AsyncMock(),
            compare_thread_metadata=AsyncMock(side_effect=self.save),
        )
        self.operations = []

        def delegation(**kwargs):
            self.operations.append(kwargs["operation"])
            return {"Authorization": kwargs["operation"]}

        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service = RuntimeGatewayService(
            session_factory=None,
            upstream=self.upstream,
            title_auto_enabled=True,
            delegation_headers_factory=delegation,
        )
        self.service._load_thread = AsyncMock(
            side_effect=lambda **_: copy.deepcopy(self.thread)
        )
        self.service._inject_project_default_model = Mock(
            side_effect=lambda **kwargs: kwargs["payload"]
        )
        self.service._validate_run_options = Mock()
        self.service._attach_runtime_model_reference = Mock(
            side_effect=lambda **kwargs: kwargs["payload"]
        )

    async def save(self, thread_id, *, metadata, expected):
        self.assertEqual(thread_id, THREAD)
        if any(
            self.thread["metadata"].get(key) != value for key, value in expected.items()
        ):
            raise PlatformApiError(code="conflict", status_code=409, message="conflict")
        self.thread["metadata"].update(metadata)
        return copy.deepcopy(self.thread)

    async def generate(self, **payload):
        return await self.service.summarize_thread_title(
            actor=self.actor,
            project_id="p",
            thread_id=THREAD,
            payload={"mode": "auto", "run_id": RUN, **payload},
        )

    async def test_auto_reads_committed_materials_and_separates_operations(self):
        result = await self.generate()
        self.assertEqual(result["outcome"], "applied")
        self.assertEqual(result["title"], "权限设计")
        self.assertFalse(result["metadata"]["auto_title_pending"])
        self.assertNotIn(TITLE_SEED_KEY, result["metadata"])
        self.assertEqual(
            self.operations, ["read", "title-generate", "read", "thread-edit"]
        )
        self.assertEqual(self.upstream.get_thread_state.await_count, 2)
        self.assertEqual(self.upstream.summarize_thread_title.await_count, 1)
        self.assertEqual((await self.generate())["reason"], "not_pending")

    async def test_failed_and_maintenance_runs_do_not_generate(self):
        for mutation in (
            {"status": "pending"},
            {"status": "running"},
            {"status": "interrupted"},
            {"status": "error"},
            {"status": "timeout"},
            {"status": "cancelled"},
            {"kwargs": {"command": {"resume": "yes"}}},
            {"kwargs": {"checkpoint_id": "old"}},
            {"kwargs": {"context": {"offload_conversation": True}}},
            {"assistant_id": "other"},
            {"thread_id": "other"},
        ):
            with self.subTest(mutation=mutation):
                run = {
                    "thread_id": THREAD,
                    "run_id": RUN,
                    "assistant_id": "reference_agent",
                    "status": "success",
                    "kwargs": {},
                    **mutation,
                }
                self.upstream.get_thread_run.return_value = run
                self.assertEqual((await self.generate())["reason"], "run_not_ready")
        self.upstream.summarize_thread_title.assert_not_awaited()

    async def test_thread_active_interrupt_or_next_node_skips(self):
        for status in ("busy", "interrupted", "error"):
            self.thread["status"] = status
            self.assertEqual((await self.generate())["reason"], "run_not_ready")
        self.thread["status"] = "idle"
        self.state["next"] = ["tools"]
        self.assertEqual((await self.generate())["reason"], "run_not_ready")
        self.state["next"] = []
        self.upstream.list_thread_runs.return_value = [{"status": "pending"}]
        self.assertEqual((await self.generate())["reason"], "run_not_ready")
        self.upstream.summarize_thread_title.assert_not_awaited()

    async def test_first_round_requires_final_body_and_excludes_reminders(self):
        original = copy.deepcopy(self.state)
        for extra in (
            {"type": "human", "content": "第二轮"},
            {"type": "ai", "content": "", "tool_calls": [{"name": "read"}]},
            {"type": "ai", "content": "<think>private</think>"},
        ):
            self.state = copy.deepcopy(original)
            self.state["values"]["messages"].append(extra)
            self.assertIn(
                (await self.generate())["reason"],
                {"not_first_round", "materials_missing"},
            )
        self.state = original
        self.state["values"]["messages"].insert(
            1,
            {"type": "human", "content": "<system_reminder>internal</system_reminder>"},
        )
        self.assertEqual((await self.generate())["outcome"], "applied")

    async def test_generation_rechecks_gate_access_model_and_materials(self):
        async def mutate(*_):
            self.service._title_auto_enabled = False
            return {
                "thread_id": THREAD,
                "title": "候选",
                "outcome": "applied",
                "reason": None,
            }

        self.upstream.summarize_thread_title.side_effect = mutate
        self.assertEqual((await self.generate())["reason"], "disabled")
        self.upstream.compare_thread_metadata.assert_not_awaited()
        self.service._title_auto_enabled = True

        async def continuation(*_):
            self.state["values"]["messages"].append(
                {"type": "human", "content": "第二轮"}
            )
            return {
                "thread_id": THREAD,
                "title": "候选",
                "outcome": "applied",
                "reason": None,
            }

        self.upstream.summarize_thread_title.side_effect = continuation
        self.assertEqual((await self.generate())["reason"], "not_first_round")
        self.upstream.compare_thread_metadata.assert_not_awaited()

    async def test_access_and_model_revoked_after_generation_fail_closed(self):
        self.service._load_thread.side_effect = [
            copy.deepcopy(self.thread),
            ForbiddenError(code="thread_access_denied", message="denied"),
        ]
        with self.assertRaises(ForbiddenError):
            await self.generate()
        self.service._load_thread.side_effect = lambda **_: copy.deepcopy(self.thread)
        self.service._validate_run_options.side_effect = [
            None,
            ForbiddenError(code="runtime_model_denied", message="denied"),
        ]
        with self.assertRaises(ForbiddenError):
            await self.generate()
        self.upstream.compare_thread_metadata.assert_not_awaited()

    async def test_comment_only_cannot_generate(self):
        self.actor = ActorContext(
            user_id="collaborator", project_roles={"p": ("project_executor",)}
        )
        with self.assertRaises(ForbiddenError):
            await self.generate()
        self.upstream.summarize_thread_title.assert_not_awaited()

    async def test_rename_wins_in_both_orders_including_same_title(self):
        async def rename(*_):
            await self.service.update_thread(
                actor=self.actor,
                project_id="p",
                thread_id=THREAD,
                metadata_updates={"title": "规则标题"},
            )
            self.thread["metadata"][TITLE_SEED_KEY] = None
            return {
                "thread_id": THREAD,
                "title": "候选",
                "outcome": "applied",
                "reason": None,
            }

        self.upstream.summarize_thread_title.side_effect = rename
        self.assertEqual((await self.generate())["reason"], "not_pending")
        self.upstream.compare_thread_metadata.assert_not_awaited()
        self.thread["metadata"][TITLE_SEED_KEY] = "规则标题"
        self.upstream.summarize_thread_title.side_effect = None
        self.assertEqual((await self.generate())["outcome"], "applied")
        await self.service.update_thread(
            actor=self.actor,
            project_id="p",
            thread_id=THREAD,
            metadata_updates={"title": "人工标题"},
        )
        self.assertEqual(
            self.upstream.update_thread.await_args.args[1]["metadata"],
            {"title": "人工标题", TITLE_SEED_KEY: None},
        )

    async def test_conflict_returns_persisted_title_and_unknown_write_never_applies(
        self,
    ):
        async def competing(*args, **kwargs):
            self.thread["metadata"].update(title="人工标题", **{TITLE_SEED_KEY: None})
            raise PlatformApiError(code="conflict", status_code=409, message="conflict")

        self.upstream.compare_thread_metadata.side_effect = competing
        result = await self.generate()
        self.assertEqual((result["reason"], result["title"]), ("conflict", "人工标题"))
        self.thread["metadata"].update(title="规则标题", **{TITLE_SEED_KEY: "规则标题"})
        for status, code in (
            (404, "title_cas_unavailable"),
            (405, "title_cas_unavailable"),
            (503, "title_write_unconfirmed"),
            (504, "title_write_unconfirmed"),
        ):
            self.upstream.compare_thread_metadata.side_effect = PlatformApiError(
                code="upstream", status_code=status, message="private"
            )
            with self.assertRaises(PlatformApiError) as ctx:
                await self.generate()
            self.assertEqual(ctx.exception.code, code)

    async def test_model_failure_consumes_auto_seed_without_replacing_rule_title(self):
        self.upstream.summarize_thread_title.return_value = {
            "thread_id": THREAD,
            "title": None,
            "outcome": "degraded",
            "reason": "timeout",
        }
        result = await self.generate()
        self.assertEqual((result["outcome"], result["title"]), ("degraded", "规则标题"))
        self.assertFalse(result["metadata"]["auto_title_pending"])
        self.assertEqual(
            self.upstream.compare_thread_metadata.await_args.kwargs["metadata"],
            {TITLE_SEED_KEY: None},
        )

    async def test_invalid_public_payloads_never_read_or_generate(self):
        for updates in (
            {"messages": None},
            {"messages": []},
            {"files": []},
            {"context": {}},
            {"run_id": "invalid"},
            {"mode": "manual", "run_id": None},
            {"mode": "manual", "messages": [{"role": "tool", "content": "private"}]},
            {"mode": "manual", "messages": [{"role": "user", "content": "x" * 4001}]},
        ):
            with self.subTest(updates=updates), self.assertRaises(PlatformApiError):
                await self.generate(**updates)
        self.service._load_thread.assert_not_awaited()

    async def test_invalid_runtime_result_is_rejected(self):
        for result in (
            {
                "thread_id": THREAD,
                "title": "candidate",
                "outcome": "applied",
                "reason": "provider-secret",
            },
            {
                "thread_id": "other",
                "title": "candidate",
                "outcome": "applied",
                "reason": None,
            },
            {"title": "candidate"},
        ):
            self.upstream.summarize_thread_title.return_value = result
            with self.assertRaises(PlatformApiError) as ctx:
                await self.generate()
            self.assertEqual(ctx.exception.code, "invalid_title_response")
        self.upstream.compare_thread_metadata.assert_not_awaited()

    async def test_preview_keeps_pending_and_public_seed_is_hidden(self):
        result = await self.service.update_thread(
            actor=self.actor,
            project_id="p",
            thread_id=THREAD,
            metadata_updates={"preview": "摘要"},
        )
        self.assertEqual(
            self.upstream.update_thread.await_args.args[1],
            {"metadata": {"preview": "摘要"}},
        )
        self.assertTrue(result["metadata"]["auto_title_pending"])
        projected = redact_runtime_private_fields(
            self.service._thread_with_access(
                self.actor, "p", self.thread, self.thread["metadata"]
            )
        )
        self.assertNotIn(TITLE_SEED_KEY, projected["metadata"])
        self.assertTrue(projected["metadata"]["auto_title_pending"])

    async def test_preview_response_uses_current_stored_title_after_concurrent_cas(
        self,
    ):
        self.upstream.update_thread.return_value = {
            "thread_id": THREAD,
            "metadata": {
                "title": "已升级标题",
                TITLE_SEED_KEY: None,
                "preview": "摘要",
            },
        }
        result = await self.service.update_thread(
            actor=self.actor,
            project_id="p",
            thread_id=THREAD,
            metadata_updates={"preview": "摘要"},
        )
        self.assertEqual(result["metadata"]["title"], "已升级标题")
        self.assertFalse(result["metadata"]["auto_title_pending"])

    async def test_old_forked_and_disabled_threads_are_not_backfilled(self):
        for metadata in (
            {TITLE_SEED_KEY: None},
            {"forked_from": {"thread_id": "source"}},
            {"title": "人工标题"},
        ):
            original = copy.deepcopy(self.thread)
            self.thread["metadata"].update(metadata)
            self.assertEqual((await self.generate())["reason"], "not_pending")
            self.thread = original
        self.service._title_auto_enabled = False
        self.assertEqual((await self.generate())["reason"], "disabled")
        self.upstream.summarize_thread_title.assert_not_awaited()

    async def test_create_opt_in_and_reject_client_owned_markers(self):
        factory = thread_acl_factory(self, actor=self.actor, project_id="p")
        upstream = SimpleNamespace(
            create_thread=AsyncMock(side_effect=lambda payload: copy.deepcopy(payload))
        )
        service = RuntimeGatewayService(
            session_factory=factory, upstream=upstream, title_auto_enabled=True
        )
        service._prepare_project_scope = Mock()
        for payload in (
            {"auto_title": True},
            {"auto_title": False},
            {"auto_title": True, "supersteps": [{}]},
            {"auto_title": True, "metadata": {"forked_from": {"thread_id": "source"}}},
        ):
            await service.create_thread(
                actor=self.actor, project_id="p", payload=payload
            )
            sent = upstream.create_thread.await_args.args[0]
            self.assertNotIn("auto_title", sent)
            self.assertEqual(
                TITLE_SEED_KEY in sent["metadata"], payload == {"auto_title": True}
            )
        for payload in (
            {"metadata": {TITLE_SEED_KEY: "forged"}},
            {"metadata": {"auto_title_pending": True}},
            {"supersteps": [{"values": {TITLE_SEED_KEY: "forged"}}]},
            {"auto_title": "true"},
        ):
            with self.assertRaises(BadRequestError):
                await service.create_thread(
                    actor=self.actor, project_id="p", payload=payload
                )

    async def test_transport_uses_separate_cas_uri(self):
        upstream = LangGraphRuntimeGatewayUpstream(
            base_url="http://runtime.invalid", timeout_seconds=8
        )
        upstream._http = SimpleNamespace(require_json=AsyncMock(return_value={}))
        await upstream.compare_thread_metadata(
            THREAD, metadata={"title": "new"}, expected={"title": "old"}
        )
        self.assertEqual(
            upstream._http.require_json.await_args.args,
            ("PATCH", f"/threads/{THREAD}/metadata/cas"),
        )

    def test_materials_strip_internal_blocks_and_do_not_use_reasoning(self):
        messages, _, reason = conversation_materials(
            [
                {
                    "type": "human",
                    "content": "设计 https://private.invalid/key /workspace/secret.txt 权限",
                },
                {
                    "type": "ai",
                    "content": [
                        {"type": "reasoning", "text": "private"},
                        {"type": "text", "text": "精确授权"},
                    ],
                },
            ],
            first_round=True,
        )
        self.assertIsNone(reason)
        self.assertEqual(
            messages,
            [
                {"role": "user", "content": "设计 权限"},
                {"role": "assistant", "content": "精确授权"},
            ],
        )

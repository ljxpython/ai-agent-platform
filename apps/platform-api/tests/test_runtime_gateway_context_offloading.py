import unittest
from unittest.mock import AsyncMock

import test_run_requests as fixtures

from platform_api.core.errors import BadRequestError, ConflictError


class ContextOffloadingTest(unittest.IsolatedAsyncioTestCase):
    tearDown = fixtures.RunRequestsTest.tearDown

    def setUp(self):
        fixtures.RunRequestsTest.setUp(self)
        self.service._load_thread.return_value["metadata"].update(
            visibility="private",
            owner_user_id="user-1",
            owner_type="user",
            project_id="project-1",
            access_version=1,
        )
        self.upstream.get_graph_capabilities = AsyncMock(
            return_value={"conversation_offloading": True}
        )
        self.upstream.list_thread_messages = AsyncMock(
            return_value={"has_pending_input": False}
        )
        self.upstream.get_thread_state.return_value = {
            "values": {"messages": [{"type": "human", "content": "earlier"}]},
            "tasks": [],
            "next": [],
        }

    def command(self, *, input=None, context=None, configurable=None):
        return {
            "id": 1,
            "method": "run.start",
            "params": {
                "assistant_id": "agent-1",
                "input": input,
                "context": context or {},
                "config": {
                    "configurable": {
                        "platform_runtime": {"offload_conversation": True},
                        **(configurable or {}),
                    }
                },
            },
        }

    async def maintain(self, command=None, key="maintain"):
        return await self.service.send_thread_command(
            actor=self.actor,
            project_id="project-1",
            thread_id="thread-1",
            payload=command or self.command(),
            idempotency_key=key,
        )

    async def test_maintenance_accepts_empty_input_and_retry_reuses_active_run(self):
        audit = []
        self.service._on_correlation = lambda event, fields: audit.append(fields)
        first = await self.maintain()
        sent = self.upstream.create_thread_run.call_args.args[1]
        self.assertTrue(sent["context"]["offload_conversation"])
        self.assertEqual(sent["multitask_strategy"], "reject")
        self.upstream.list_thread_runs.return_value = [
            {"run_id": "run-1", "status": "running"}
        ]
        self.assertEqual(
            (await self.maintain())["result"]["run_id"], first["result"]["run_id"]
        )
        self.assertEqual(self.upstream.create_thread_run.await_count, 1)
        self.assertTrue(
            any(
                fields.get("maintenance_type") == "conversation_offloading"
                for fields in audit
            )
        )

    async def test_capability_false_and_read_only_acl_do_not_enable_maintenance(self):
        self.service._load_thread.return_value["metadata"].update(
            owner_user_id="other",
            shared_actions={"user-1": ["read"]},
        )
        capability = await self.service.get_thread_capabilities(
            actor=self.actor, project_id="project-1", thread_id="thread-1"
        )
        self.assertFalse(capability["conversation_offloading"])
        self.service._load_thread.return_value["metadata"]["owner_user_id"] = "user-1"
        self.upstream.get_graph_capabilities.return_value = {
            "conversation_offloading": False
        }
        with self.assertRaises(ConflictError):
            await self.maintain()
        self.upstream.create_thread_run.assert_not_awaited()

    async def test_unknown_retries_forward_original_key_without_rechecking_busy_state(
        self,
    ):
        self.upstream.create_thread_run.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            await self.maintain()
        first_key = self.upstream.create_thread_run.call_args.args[1]["idempotency_key"]
        self.upstream.list_thread_runs.return_value = [{"status": "running"}]
        self.upstream.create_thread_run.side_effect = None
        await self.maintain()
        self.assertEqual(
            self.upstream.create_thread_run.call_args.args[1]["idempotency_key"],
            first_key,
        )

    async def test_all_start_entries_use_same_preflight(self):
        for index, entry in enumerate(
            (self.service.create_thread_run, self.service.stream_thread_run)
        ):
            self.upstream.get_graph_capabilities.return_value = {}
            with self.assertRaises(ConflictError) as error:
                await entry(
                    actor=self.actor,
                    project_id="project-1",
                    thread_id="thread-1",
                    payload=self.command()["params"],
                    idempotency_key=f"entry-{index}",
                )
            self.assertEqual(error.exception.code, "context_offload_not_supported")
        self.upstream.create_thread_run.assert_not_awaited()

    async def test_preflight_rejects_busy_interrupt_empty_pending_and_input(self):
        cases = (
            ("busy", "thread_active_run_conflict"),
            ("interrupt", "context_offload_interrupt_pending"),
            ("empty", "context_offload_empty_thread"),
            ("queue", "context_offload_pending_input"),
            ("input", "context_offload_input_invalid"),
            ("checkpoint", "context_offload_input_invalid"),
        )
        for name, code in cases:
            self.upstream.list_thread_runs.return_value = []
            self.upstream.get_thread_state.return_value = {
                "values": {"messages": ["old"]}
            }
            self.upstream.list_thread_messages.return_value = {
                "has_pending_input": False
            }
            command = self.command()
            if name == "busy":
                self.upstream.list_thread_runs.return_value = [{"status": "running"}]
            if name == "interrupt":
                self.upstream.get_thread_state.return_value["tasks"] = [
                    {"interrupts": [{"id": "approval"}]}
                ]
            if name == "empty":
                self.upstream.get_thread_state.return_value = {}
            if name == "queue":
                self.upstream.list_thread_messages.return_value = {
                    "has_pending_input": True
                }
            if name == "input":
                command["params"]["input"] = {"messages": []}
            if name == "checkpoint":
                command["params"]["checkpoint_id"] = "older"
            with self.assertRaises((ConflictError, BadRequestError)) as error:
                await self.maintain(command, key=name)
            self.assertEqual(error.exception.code, code)
        self.upstream.create_thread_run.assert_not_awaited()

    async def test_conflicting_and_null_flags_rejected_before_defaults(self):
        for value in (False, None, "true", 1):
            command = self.command()
            command["params"]["context"] = {"offload_conversation": value}
            with self.assertRaises(BadRequestError):
                await self.maintain(command, key=str(value))
        self.upstream.create_thread_run.assert_not_awaited()

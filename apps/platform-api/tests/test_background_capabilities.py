"""Starting can be disabled without revoking existing task reads."""

import unittest
from unittest.mock import AsyncMock, patch

import test_run_requests as fixtures


class BackgroundCapabilitiesTest(unittest.IsolatedAsyncioTestCase):
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
        self.upstream.get_graph_capabilities = AsyncMock()

    async def capabilities(self, runtime, restrictions=None):
        self.upstream.get_graph_capabilities.return_value = runtime
        with patch(
            "platform_api.modules.runtime_policies.application.RuntimePolicyOverlayService.resolve_tool_overrides",
            return_value={"tool_overrides": restrictions or {}},
        ):
            return await self.service.get_thread_capabilities(
                actor=self.actor,
                project_id="project-1",
                thread_id="thread-1",
            )

    async def test_runtime_disabled_start_keeps_queries(self):
        for query, start in ((True, False), (True, True), (False, False)):
            result = await self.capabilities(
                {
                    "background_tasks": query,
                    "background_tasks_start_enabled": start,
                }
            )
            self.assertIs(result["background_tasks"], query)
            self.assertIs(result["background_tasks_start_enabled"], start)

    async def test_execute_deny_and_read_only_acl_disable_only_start(self):
        runtime = {"background_tasks": True, "background_tasks_start_enabled": True}
        for denied in ("execute", "background_execute"):
            result = await self.capabilities(runtime, {denied: False})
            self.assertTrue(result["background_tasks"])
            self.assertFalse(result["background_tasks_start_enabled"])
        self.service._load_thread.return_value["metadata"].update(
            owner_user_id="other",
            shared_actions={"user-1": ["read"]},
        )
        result = await self.capabilities(runtime)
        self.assertTrue(result["background_tasks"])
        self.assertFalse(result["background_tasks_start_enabled"])

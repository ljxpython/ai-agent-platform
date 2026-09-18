import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from platform_api.core.errors import BadRequestError
from platform_api.modules.runtime_gateway.application.service import RuntimeGatewayService


class ThreadMetadataUpdateTest(unittest.IsolatedAsyncioTestCase):
    async def test_update_thread_title_and_preview_success(self) -> None:
        upstream = SimpleNamespace(update_thread=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "graph_id": "reference_agent", "title": "旧标题"}}
        )
        result = await service.update_thread(
            actor=SimpleNamespace(),
            project_id="proj-1",
            thread_id="th-1",
            metadata_updates={"title": "新标题", "preview": "最新消息摘要"},
        )
        self.assertEqual(result["thread_id"], "th-1")
        self.assertEqual(result["metadata"]["title"], "新标题")
        self.assertEqual(result["metadata"]["preview"], "最新消息摘要")
        self.assertEqual(result["metadata"]["project_id"], "proj-1")
        upstream.update_thread.assert_awaited_once_with(
            "th-1",
            {
                "metadata": {
                    "project_id": "proj-1",
                    "graph_id": "reference_agent",
                    "title": "新标题",
                    "preview": "最新消息摘要",
                }
            },
        )

    async def test_update_thread_rejects_empty_updates(self) -> None:
        upstream = SimpleNamespace(update_thread=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1"}}
        )
        with self.assertRaises(BadRequestError) as ctx:
            await service.update_thread(
                actor=SimpleNamespace(),
                project_id="proj-1",
                thread_id="th-1",
                metadata_updates={"unsupported_key": 123},
            )
        self.assertEqual(ctx.exception.code, "invalid_metadata")

    async def test_update_thread_rejects_non_string_title(self) -> None:
        upstream = SimpleNamespace(update_thread=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1"}}
        )
        with self.assertRaises(BadRequestError) as ctx:
            await service.update_thread(
                actor=SimpleNamespace(),
                project_id="proj-1",
                thread_id="th-1",
                metadata_updates={"title": 12345},  # type: ignore[dict-item]
            )
        self.assertEqual(ctx.exception.code, "invalid_metadata")

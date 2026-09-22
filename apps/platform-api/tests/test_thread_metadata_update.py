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

    async def test_summarize_thread_title_success_and_persists_metadata(self) -> None:
        upstream = SimpleNamespace(
            summarize_thread_title=AsyncMock(return_value={"title": "用户注册架构"}),
            update_thread=AsyncMock(),
        )
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "title": "旧标题"}}
        )
        result = await service.summarize_thread_title(
            actor=SimpleNamespace(),
            project_id="proj-1",
            thread_id="th-1",
            payload={"messages": [{"role": "user", "content": "帮我设计注册系统"}]},
        )
        self.assertEqual(result["thread_id"], "th-1")
        self.assertEqual(result["title"], "用户注册架构")
        self.assertEqual(result["metadata"]["title"], "用户注册架构")
        upstream.summarize_thread_title.assert_awaited_once_with(
            "th-1", {"messages": [{"role": "user", "content": "帮我设计注册系统"}]}
        )
        upstream.update_thread.assert_awaited_once_with(
            "th-1", {"metadata": {"title": "用户注册架构"}}
        )

    async def test_summarize_thread_title_handles_empty_title_fallback(self) -> None:
        upstream = SimpleNamespace(
            summarize_thread_title=AsyncMock(return_value={"title": ""}),
            update_thread=AsyncMock(),
        )
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "title": "旧标题"}}
        )
        result = await service.summarize_thread_title(
            actor=SimpleNamespace(),
            project_id="proj-1",
            thread_id="th-1",
        )
        self.assertEqual(result["thread_id"], "th-1")
        self.assertEqual(result["title"], "新对话")
        upstream.update_thread.assert_not_called()

    async def test_summarize_thread_title_auto_extracts_messages_from_thread_state(self) -> None:
        upstream = SimpleNamespace(
            get_thread_state=AsyncMock(return_value={
                "values": {
                    "messages": [
                        {"type": "human", "content": "你来给我画一只鹈鹕"},
                        {"type": "ai", "content": "好的，我来帮你画"},
                    ]
                }
            }),
            summarize_thread_title=AsyncMock(return_value={"title": "画鹈鹕"}),
            update_thread=AsyncMock(),
        )
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(
            return_value={"metadata": {"project_id": "proj-1", "title": "旧标题"}}
        )
        result = await service.summarize_thread_title(
            actor=SimpleNamespace(),
            project_id="proj-1",
            thread_id="th-1",
            payload={},  # 没有传入 messages
        )
        self.assertEqual(result["thread_id"], "th-1")
        self.assertEqual(result["title"], "画鹈鹕")
        upstream.summarize_thread_title.assert_awaited_once_with(
            "th-1",
            {
                "messages": [
                    {"role": "human", "content": "你来给我画一只鹈鹕"},
                    {"role": "ai", "content": "好的，我来帮你画"},
                ]
            }
        )
        upstream.update_thread.assert_awaited_once_with(
            "th-1", {"metadata": {"title": "画鹈鹕"}}
        )

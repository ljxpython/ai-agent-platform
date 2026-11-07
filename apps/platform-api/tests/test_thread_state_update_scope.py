import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)


def test_state_edit_uses_read_delegation_for_plan_precondition():
    reader = SimpleNamespace(get_thread_state=AsyncMock(return_value={"values": {}}))
    writer = SimpleNamespace(
        update_thread_state=AsyncMock(return_value={"checkpoint_id": "new"})
    )
    service = SimpleNamespace(
        _load_thread=AsyncMock(return_value={"thread_id": "thread", "metadata": {}}),
        _thread_upstream=AsyncMock(side_effect=[reader, writer]),
    )
    result = asyncio.run(
        RuntimeGatewayService.update_thread_state(
            service,
            actor=None,
            project_id="project",
            thread_id="thread",
            payload={"values": {"messages": []}},
        )
    )
    assert result == {"checkpoint_id": "new"}
    assert [
        call.kwargs["operation"] for call in service._thread_upstream.call_args_list
    ] == ["read", "thread-edit"]
    reader.get_thread_state.assert_awaited_once_with("thread", {})
    writer.update_thread_state.assert_awaited_once()

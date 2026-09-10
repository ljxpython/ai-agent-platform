from __future__ import annotations

from typing import Any

from platform_api.core.context.models import ActorContext
from platform_api.modules.agents.application import AssistantsService
from platform_api.modules.operations.application.ports import (
    OperationExecutionResult,
    OperationExecutorProtocol,
    StoredOperation,
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


class AssistantResyncExecutor(OperationExecutorProtocol):
    kind = "assistant.resync"

    def __init__(self, *, service: AssistantsService) -> None:
        self._service = service

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        assistant_id = _clean(operation.input_payload.get("assistant_id"))
        if not assistant_id:
            raise ValueError("assistant_id is required for assistant resync operation")

        item = await self._service.resync_assistant(actor=actor, assistant_id=assistant_id)
        return OperationExecutionResult(
            result_payload=item.model_dump(mode="json"),
            metadata={
                "assistant_id": item.id,
                "project_id": item.project_id,
            },
        )

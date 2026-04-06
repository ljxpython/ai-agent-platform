from __future__ import annotations

from app.core.context.models import ActorContext
from app.modules.operations.application.ports import (
    OperationExecutionResult,
    OperationExecutorProtocol,
    StoredOperation,
)
from app.modules.runtime_catalog.application import RuntimeCatalogService


class RuntimeCatalogRefreshExecutor(OperationExecutorProtocol):
    def __init__(
        self,
        *,
        kind: str,
        resource: str,
        service: RuntimeCatalogService,
    ) -> None:
        self.kind = kind
        self._resource = resource
        self._service = service

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        if not operation.project_id:
            raise ValueError("project_id is required for runtime refresh operation")

        if self._resource == "models":
            result = await self._service.refresh_models(actor=actor, project_id=operation.project_id)
        elif self._resource == "tools":
            result = await self._service.refresh_tools(actor=actor, project_id=operation.project_id)
        elif self._resource == "graphs":
            result = await self._service.refresh_graphs(actor=actor, project_id=operation.project_id)
        else:
            raise ValueError(f"unsupported_runtime_resource:{self._resource}")

        return OperationExecutionResult(
            result_payload=result.model_dump(mode="json"),
            metadata={"resource": self._resource},
        )

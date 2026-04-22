from __future__ import annotations

from app.core.context.models import ActorContext
from app.modules.operations.application.ports import (
    OperationExecutionResult,
    OperationExecutorProtocol,
    StoredOperation,
)
from app.modules.project_knowledge.application.service import ProjectKnowledgeService


class ProjectKnowledgeDocumentsExecutor(OperationExecutorProtocol):
    def __init__(self, *, kind: str, action: str, service: ProjectKnowledgeService) -> None:
        self.kind = kind
        self._action = action
        self._service = service

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        if not operation.project_id:
            raise ValueError('project_id is required for knowledge operation')
        if self._action == 'scan':
            result = await self._service.trigger_scan(actor=actor, project_id=operation.project_id)
        elif self._action == 'clear':
            result = await self._service.clear_documents(actor=actor, project_id=operation.project_id)
        else:
            raise ValueError(f'unsupported_project_knowledge_action:{self._action}')
        return OperationExecutionResult(result_payload=dict(result))

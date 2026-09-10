from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from platform_api.adapters.langgraph import GraphParameterSchemaProvider
from platform_api.config import Settings
from platform_api.modules.agents.application import AssistantsService
from platform_api.modules.operations.application.artifacts import LocalOperationArtifactStore
from platform_api.modules.operations.application.executors import AssistantResyncExecutor
from platform_api.modules.operations.application.execution import (
    DatabasePollingOperationDispatcher,
    OperationExecutorRegistry,
)
from platform_api.modules.operations.application.heartbeat import OperationWorkerHeartbeatReporter
from platform_api.modules.operations.application.ports import (
    OperationDispatcherProtocol,
    OperationQueueConsumerProtocol,
)
from platform_api.modules.operations.application.service import OperationsService
from platform_api.modules.operations.application.worker import OperationWorker
from platform_api.modules.runtime_gateway.application.executor import RuntimeDurableRunReconciliationExecutor
from platform_api.modules.runtime_gateway.application.service import RuntimeGatewayService
from platform_api.adapters.langgraph.runtime_gateway_upstream import LangGraphRuntimeGatewayUpstream
from platform_api.modules.operations.infra import RedisListOperationQueue
from platform_api.modules.runtime_catalog.application.operations import RuntimeCatalogRefreshExecutor
from platform_api.modules.runtime_catalog.bootstrap import build_runtime_catalog_service


def _build_operation_artifact_store(settings: Settings) -> LocalOperationArtifactStore:
    return LocalOperationArtifactStore(
        settings.operations_artifacts_dir,
        storage_backend=settings.operations_artifact_storage_backend,
        retention_hours=settings.operations_artifact_retention_hours,
    )


def _build_operation_dispatcher(settings: Settings) -> OperationDispatcherProtocol:
    if settings.operations_queue_backend == "redis_list":
        return RedisListOperationQueue(
            redis_url=settings.operations_redis_url or "",
            queue_name=settings.operations_redis_queue_name,
        )
    return DatabasePollingOperationDispatcher()


def _resolve_queue_consumer(
    *,
    settings: Settings,
    dispatcher: OperationDispatcherProtocol,
) -> OperationQueueConsumerProtocol | None:
    if settings.operations_queue_backend == "redis_list" and isinstance(dispatcher, RedisListOperationQueue):
        return dispatcher
    return None


def _build_assistants_service(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session] | None,
) -> AssistantsService:
    schema_provider = GraphParameterSchemaProvider(build_runtime_catalog_service(
        settings=settings, session_factory=session_factory,
    ))
    return AssistantsService(
        session_factory=session_factory,
        runtime_base_url=settings.langgraph_upstream_url,
        schema_provider=schema_provider,
    )


def build_operations_service(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session] | None,
) -> OperationsService:
    dispatcher = _build_operation_dispatcher(settings)
    return OperationsService(
        session_factory=session_factory,
        dispatcher=dispatcher,
        artifact_store=_build_operation_artifact_store(settings),
    )


def build_operation_worker(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> OperationWorker:
    dispatcher = _build_operation_dispatcher(settings)
    runtime_catalog_service = build_runtime_catalog_service(
        settings=settings,
        session_factory=session_factory,
    )
    assistants_service = _build_assistants_service(
        settings=settings,
        session_factory=session_factory,
    )
    runtime_gateway = RuntimeGatewayService(
        session_factory=session_factory,
        upstream=LangGraphRuntimeGatewayUpstream(
            base_url=settings.langgraph_upstream_url,
            api_key=settings.langgraph_upstream_api_key,
            timeout_seconds=settings.langgraph_upstream_timeout_seconds,
            forwarded_headers={},
        ),
        runtime_base_url=settings.langgraph_upstream_url,
    )
    registry = OperationExecutorRegistry(
        (
            RuntimeDurableRunReconciliationExecutor(service=runtime_gateway),
            RuntimeCatalogRefreshExecutor(
                kind="runtime.models.refresh",
                resource="models",
                service=runtime_catalog_service,
            ),
            RuntimeCatalogRefreshExecutor(
                kind="runtime.tools.refresh",
                resource="tools",
                service=runtime_catalog_service,
            ),
            RuntimeCatalogRefreshExecutor(
                kind="runtime.graphs.refresh",
                resource="graphs",
                service=runtime_catalog_service,
            ),
            AssistantResyncExecutor(service=assistants_service),
        )
    )
    return OperationWorker(
        session_factory=session_factory,
        executor_registry=registry,
        dispatcher=dispatcher,
        queue_consumer=_resolve_queue_consumer(settings=settings, dispatcher=dispatcher),
        poll_interval_seconds=settings.operations_worker_poll_interval_seconds,
        idle_sleep_seconds=settings.operations_worker_idle_sleep_seconds,
        heartbeat_reporter=OperationWorkerHeartbeatReporter(
            session_factory=session_factory,
            queue_backend=settings.operations_queue_backend,
            heartbeat_interval_seconds=settings.operations_worker_heartbeat_interval_seconds,
        ),
    )

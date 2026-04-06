from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.interaction_data import InteractionDataClient
from app.adapters.langgraph import GraphParameterSchemaProvider, LangGraphAssistantsClient
from app.core.config import Settings
from app.modules.assistants.application import AssistantsService
from app.modules.operations.application.artifacts import LocalOperationArtifactStore
from app.modules.operations.application.executors import (
    AssistantResyncExecutor,
    TestcaseCasesExportExecutor,
    TestcaseDocumentsExportExecutor,
)
from app.modules.operations.application.execution import (
    DatabasePollingOperationDispatcher,
    OperationExecutorRegistry,
)
from app.modules.operations.application.service import OperationsService
from app.modules.operations.application.worker import OperationWorker
from app.modules.runtime_catalog.application.operations import RuntimeCatalogRefreshExecutor
from app.modules.runtime_catalog.bootstrap import build_runtime_catalog_service
from app.modules.testcase.application import TestcaseService


def _build_operation_artifact_store(settings: Settings) -> LocalOperationArtifactStore:
    return LocalOperationArtifactStore(settings.operations_artifacts_dir)


def _build_assistants_service(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session] | None,
) -> AssistantsService:
    upstream = LangGraphAssistantsClient(
        base_url=settings.langgraph_upstream_url,
        api_key=settings.langgraph_upstream_api_key,
        timeout_seconds=settings.langgraph_upstream_timeout_seconds,
        forwarded_headers={},
    )
    schema_provider = GraphParameterSchemaProvider(settings)
    return AssistantsService(
        session_factory=session_factory,
        runtime_base_url=settings.langgraph_upstream_url,
        upstream=upstream,
        schema_provider=schema_provider,
    )


def _build_testcase_service(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session] | None,
) -> TestcaseService:
    upstream = InteractionDataClient(
        base_url=settings.interaction_data_service_url,
        token=settings.interaction_data_service_token,
        timeout_seconds=settings.interaction_data_service_timeout_seconds,
        forwarded_headers={},
    )
    return TestcaseService(
        session_factory=session_factory,
        upstream=upstream,
    )


def build_operations_service(
    *,
    settings: Settings,
    session_factory: sessionmaker[Session] | None,
) -> OperationsService:
    dispatcher = DatabasePollingOperationDispatcher()
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
    runtime_catalog_service = build_runtime_catalog_service(
        settings=settings,
        session_factory=session_factory,
    )
    assistants_service = _build_assistants_service(
        settings=settings,
        session_factory=session_factory,
    )
    testcase_service = _build_testcase_service(
        settings=settings,
        session_factory=session_factory,
    )
    artifact_store = _build_operation_artifact_store(settings)
    registry = OperationExecutorRegistry(
        (
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
            TestcaseDocumentsExportExecutor(
                service=testcase_service,
                artifact_store=artifact_store,
            ),
            TestcaseCasesExportExecutor(
                service=testcase_service,
                artifact_store=artifact_store,
            ),
        )
    )
    return OperationWorker(
        session_factory=session_factory,
        executor_registry=registry,
        poll_interval_seconds=settings.operations_worker_poll_interval_seconds,
        idle_sleep_seconds=settings.operations_worker_idle_sleep_seconds,
    )

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import ForbiddenError, NotFoundError, PlatformApiError, ServiceUnavailableError
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository
from app.modules.runtime_catalog.domain import (
    RuntimeCatalogRefreshResult,
    RuntimeGraphCatalogItem,
    RuntimeGraphCatalogList,
    RuntimeModelCatalogItem,
    RuntimeModelCatalogList,
    RuntimeToolCatalogItem,
    RuntimeToolCatalogList,
)
from app.modules.runtime_catalog.infra import SqlAlchemyRuntimeCatalogRepository


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_uuid(value: str, *, code: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise PlatformApiError(
            code=code,
            status_code=400,
            message=code.replace("_", " "),
        ) from exc


def _runtime_id(value: str) -> str:
    return value.rstrip("/")


class RuntimeCatalogService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: Any,
        runtime_base_url: str,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._runtime_id = _runtime_id(runtime_base_url)
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _require_project_exists(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        project_id: str,
    ) -> UUID:
        project_uuid = _parse_uuid(project_id, code="invalid_project_id")
        repository = SqlAlchemyProjectsRepository(uow.session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")
        return project_uuid

    async def _prepare_project_scope(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        permission: PermissionCode,
    ) -> UUID:
        session_factory = self._require_session_factory()
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=permission,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            return self._require_project_exists(uow=uow, project_id=project_id)

    def _require_refresh_access(self, *, actor: ActorContext, project_id: str) -> None:
        try:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PLATFORM_CATALOG_REFRESH,
                ),
            )
            return
        except ForbiddenError:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_RUNTIME_WRITE,
                    project_id=project_id,
                ),
            )

    def _model_item(self, item: Any) -> RuntimeModelCatalogItem:
        return RuntimeModelCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            model_id=item.model_key,
            display_name=item.display_name or item.model_key,
            is_default=item.is_default_runtime,
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
        )

    def _tool_item(self, item: Any) -> RuntimeToolCatalogItem:
        return RuntimeToolCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            tool_key=item.tool_key,
            name=item.name,
            source=item.source or "",
            description=item.description or "",
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
        )

    def _graph_item(self, item: Any) -> RuntimeGraphCatalogItem:
        return RuntimeGraphCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            graph_id=item.graph_key,
            display_name=item.display_name or item.graph_key,
            description=item.description or "",
            source_type=item.source_type,
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
        )

    @staticmethod
    def _normalize_model_items(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            return []
        return [item for item in payload["models"] if isinstance(item, dict)]

    @staticmethod
    def _normalize_tool_items(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("tools"), list):
            return []
        return [item for item in payload["tools"] if isinstance(item, dict)]

    @staticmethod
    def _normalize_graph_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        return []

    @staticmethod
    def _latest_synced_at(items: list[Any]) -> datetime | None:
        return max(
            (item.last_synced_at for item in items if item.last_synced_at is not None),
            default=None,
        )

    async def list_models(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeModelCatalogList:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            rows = repository.list_models(runtime_id=self._runtime_id)
            items = [self._model_item(item) for item in rows]
            return RuntimeModelCatalogList(
                count=len(items),
                models=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_models(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        payload = await self._upstream.require_json("GET", "/internal/capabilities/models")
        items = self._normalize_model_items(payload)
        synced_at = datetime.now(timezone.utc)
        active_keys = {
            model_key
            for model_key in (_clean(item.get("model_id")) for item in items)
            if model_key
        }

        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            repository.upsert_model_items(
                runtime_id=self._runtime_id,
                items=items,
                synced_at=synced_at,
            )
            repository.mark_missing_models_deleted(
                runtime_id=self._runtime_id,
                active_keys=active_keys,
                synced_at=synced_at,
            )

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )

    async def list_tools(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeToolCatalogList:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            rows = repository.list_tools(runtime_id=self._runtime_id)
            items = [self._tool_item(item) for item in rows]
            return RuntimeToolCatalogList(
                count=len(items),
                tools=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_tools(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        payload = await self._upstream.require_json("GET", "/internal/capabilities/tools")
        items = self._normalize_tool_items(payload)
        synced_at = datetime.now(timezone.utc)
        active_keys = {
            tool_key
            for tool_key in (
                _clean(item.get("tool_key"))
                or (
                    f"{_clean(item.get('source'))}:{_clean(item.get('name'))}"
                    if _clean(item.get("source")) and _clean(item.get("name"))
                    else _clean(item.get("name"))
                )
                for item in items
            )
            if tool_key
        }

        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            repository.upsert_tool_items(
                runtime_id=self._runtime_id,
                items=items,
                synced_at=synced_at,
            )
            repository.mark_missing_tools_deleted(
                runtime_id=self._runtime_id,
                active_keys=active_keys,
                synced_at=synced_at,
            )

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )

    async def list_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeGraphCatalogList:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            rows = repository.list_graphs(runtime_id=self._runtime_id)
            items = [self._graph_item(item) for item in rows]
            return RuntimeGraphCatalogList(
                count=len(items),
                graphs=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        graph_map: dict[str, dict[str, Any]] = {}
        offset = 0
        limit = 200

        while True:
            payload = await self._upstream.request_json(
                "POST",
                "/assistants/search",
                payload={
                    "limit": limit,
                    "offset": offset,
                    "select": ["graph_id", "description"],
                },
            )
            rows = self._normalize_graph_items(payload)
            if not rows:
                break

            for item in rows:
                graph_id = _clean(item.get("graph_id"))
                if not graph_id:
                    continue

                description = _clean(item.get("description")) or ""
                existing = graph_map.get(graph_id)
                if existing is None:
                    graph_map[graph_id] = {
                        "graph_id": graph_id,
                        "display_name": graph_id,
                        "description": description,
                    }
                    continue
                if not existing.get("description") and description:
                    existing["description"] = description

            if len(rows) < limit:
                break
            offset += len(rows)

        items = list(graph_map.values())
        synced_at = datetime.now(timezone.utc)
        active_keys = {graph_id for graph_id in (_clean(item.get("graph_id")) for item in items) if graph_id}

        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyRuntimeCatalogRepository(uow.session)
            repository.upsert_graph_items(
                runtime_id=self._runtime_id,
                items=items,
                synced_at=synced_at,
                source_type="assistant_search",
            )
            repository.mark_missing_graphs_deleted(
                runtime_id=self._runtime_id,
                active_keys=active_keys,
                synced_at=synced_at,
            )

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.langgraph import LangGraphRuntimeClient
from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from app.modules.assistants.infra.sqlalchemy.repository import SqlAlchemyAssistantsRepository
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository

_THREAD_PROJECT_ID_KEYS = ("project_id", "x-project-id", "projectId")
_THREAD_GRAPH_ID_KEYS = ("graph_id", "graphId")


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


def _normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _thread_metadata(thread: dict[str, Any]) -> dict[str, Any]:
    metadata = thread.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _thread_project_id(thread: dict[str, Any]) -> str | None:
    metadata = _thread_metadata(thread)
    for key in _THREAD_PROJECT_ID_KEYS:
        value = _clean(metadata.get(key))
        if value:
            return value
    return None


def _thread_graph_id(thread: dict[str, Any]) -> str | None:
    metadata = _thread_metadata(thread)
    for key in _THREAD_GRAPH_ID_KEYS:
        value = _clean(metadata.get(key))
        if value:
            return value
    return None


class RuntimeGatewayService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: LangGraphRuntimeClient,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _authorize(self, *, actor: ActorContext, project_id: str, write: bool) -> None:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=(
                    PermissionCode.PROJECT_RUNTIME_WRITE
                    if write
                    else PermissionCode.PROJECT_RUNTIME_READ
                ),
                project_id=project_id,
            ),
        )

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
        write: bool,
    ) -> UUID:
        session_factory = self._require_session_factory()
        self._authorize(actor=actor, project_id=project_id, write=write)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            return self._require_project_exists(uow=uow, project_id=project_id)

    def _inject_project_metadata(
        self,
        *,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        next_payload = _normalize_payload(payload)
        metadata = next_payload.get("metadata")
        metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}
        metadata_dict["project_id"] = project_id
        next_payload["metadata"] = metadata_dict
        return next_payload

    def _inject_project_scope(
        self,
        *,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        config = next_payload.get("config")
        config_dict = dict(config) if isinstance(config, dict) else {}
        configurable = config_dict.get("configurable")
        if isinstance(configurable, dict) and not configurable:
            config_dict.pop("configurable", None)
            configurable = None

        if not isinstance(configurable, dict):
            context = next_payload.get("context")
            context_dict = dict(context) if isinstance(context, dict) else {}
            context_dict["project_id"] = project_id
            next_payload["context"] = context_dict

        config_metadata = config_dict.get("metadata")
        config_metadata_dict = (
            dict(config_metadata) if isinstance(config_metadata, dict) else {}
        )
        config_metadata_dict["project_id"] = project_id
        config_dict["metadata"] = config_metadata_dict
        next_payload["config"] = config_dict
        return next_payload

    def _assert_thread_project_scope(
        self,
        *,
        project_id: str,
        thread: dict[str, Any],
    ) -> None:
        thread_project_id = _thread_project_id(thread)
        if thread_project_id != project_id:
            raise ForbiddenError(
                code="thread_project_denied",
                message="thread_project_denied",
            )

    async def _load_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        write: bool,
    ) -> dict[str, Any]:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=write)
        thread = await self._upstream.require_json("GET", f"/threads/{thread_id}")
        self._assert_thread_project_scope(project_id=project_id, thread=thread)
        return thread

    async def _assistant_belongs_project(
        self,
        *,
        project_id: str,
        assistant_id: str,
    ) -> bool:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            project_uuid = self._require_project_exists(uow=uow, project_id=project_id)
            repository = SqlAlchemyAssistantsRepository(uow.session)
            item = repository.get_by_project_and_langgraph_assistant_id(
                project_id=project_uuid,
                langgraph_assistant_id=assistant_id,
            )
            return item is not None

    async def _assert_runtime_target_allowed(
        self,
        *,
        project_id: str,
        assistant_id: str,
        thread: dict[str, Any] | None = None,
    ) -> None:
        normalized_assistant_id = _clean(assistant_id)
        if not normalized_assistant_id:
            raise BadRequestError(
                message="assistant_id is required",
                code="assistant_id_required",
            )

        if await self._assistant_belongs_project(
            project_id=project_id,
            assistant_id=normalized_assistant_id,
        ):
            return

        if thread is not None and _thread_graph_id(thread) == normalized_assistant_id:
            return

        raise ForbiddenError(
            code="runtime_target_denied",
            message="runtime_target_denied",
        )

    async def get_info(self, *, actor: ActorContext, project_id: str) -> dict[str, Any]:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.require_json("GET", "/info")

    async def search_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.request_json("POST", "/graphs/search", payload=_normalize_payload(payload))

    async def count_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.request_json("POST", "/graphs/count", payload=_normalize_payload(payload))

    async def create_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        return await self._upstream.request_json("POST", "/threads", payload=next_payload)

    async def search_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        return await self._upstream.request_json("POST", "/threads/search", payload=next_payload)

    async def count_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        return await self._upstream.request_json("POST", "/threads/count", payload=next_payload)

    async def prune_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = _normalize_payload(payload)
        thread_ids = next_payload.get("thread_ids")
        if isinstance(thread_ids, list):
            for thread_id in thread_ids:
                normalized_thread_id = _clean(thread_id)
                if normalized_thread_id:
                    await self._load_thread(
                        actor=actor,
                        project_id=project_id,
                        thread_id=normalized_thread_id,
                        write=True,
                    )
        return await self._upstream.request_json("POST", "/threads/prune", payload=next_payload)

    async def get_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
    ) -> dict[str, Any]:
        return await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )

    async def update_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_metadata(project_id=project_id, payload=payload)
        return await self._upstream.request_json(
            "PATCH",
            f"/threads/{thread_id}",
            payload=next_payload,
        )

    async def delete_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        return await self._upstream.request_json("DELETE", f"/threads/{thread_id}")

    async def copy_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        copied = await self._upstream.require_json("POST", f"/threads/{thread_id}/copy")
        self._assert_thread_project_scope(project_id=project_id, thread=copied)
        return copied

    async def get_thread_state(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        params: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.request_json(
            "GET",
            f"/threads/{thread_id}/state",
            params=_normalize_payload(params),
        )

    async def update_thread_state(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        return await self._upstream.request_json(
            "POST",
            f"/threads/{thread_id}/state",
            payload=_normalize_payload(payload),
        )

    async def get_thread_state_at_checkpoint(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        checkpoint_id: str,
    ) -> Any:
        return await self.get_thread_state(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            params={"checkpoint_id": checkpoint_id},
        )

    async def get_thread_history(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.request_json(
            "POST",
            f"/threads/{thread_id}/history",
            payload=_normalize_payload(payload),
        )

    async def create_global_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.request_json("POST", "/runs", payload=next_payload)

    async def stream_global_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.stream("POST", "/runs/stream", payload=next_payload)

    async def wait_global_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.request_json("POST", "/runs/wait", payload=next_payload)

    async def create_batch_runs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payloads: list[dict[str, Any]],
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payloads: list[dict[str, Any]] = []
        for item in payloads:
            next_item = self._inject_project_scope(project_id=project_id, payload=item)
            assistant_id = _clean(next_item.get("assistant_id"))
            await self._assert_runtime_target_allowed(
                project_id=project_id,
                assistant_id=assistant_id or "",
            )
            next_payloads.append(next_item)
        return await self._upstream.request_json("POST", "/runs/batch", payload=next_payloads)

    async def cancel_runs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = _normalize_payload(payload)
        thread_id = _clean(next_payload.get("thread_id"))
        if thread_id:
            await self._load_thread(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                write=True,
            )
        return await self._upstream.request_json("POST", "/runs/cancel", payload=next_payload)

    async def create_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
        )
        return await self._upstream.request_json("POST", "/runs/crons", payload=next_payload)

    async def search_crons(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.request_json("POST", "/runs/crons/search", payload=_normalize_payload(payload))

    async def count_crons(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._upstream.request_json("POST", "/runs/crons/count", payload=_normalize_payload(payload))

    async def update_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        cron_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        return await self._upstream.request_json(
            "PATCH",
            f"/runs/crons/{cron_id}",
            payload=next_payload,
        )

    async def delete_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        cron_id: str,
    ) -> Any:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        return await self._upstream.request_json("DELETE", f"/runs/crons/{cron_id}")

    async def create_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.request_json(
            "POST",
            f"/threads/{thread_id}/runs",
            payload=next_payload,
        )

    async def stream_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.stream(
            "POST",
            f"/threads/{thread_id}/runs/stream",
            payload=next_payload,
        )

    async def wait_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.request_json(
            "POST",
            f"/threads/{thread_id}/runs/wait",
            payload=next_payload,
        )

    async def get_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.request_json(
            "GET",
            f"/threads/{thread_id}/runs/{run_id}",
        )

    async def list_thread_runs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        params: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.request_json(
            "GET",
            f"/threads/{thread_id}/runs",
            params=_normalize_payload(params),
        )

    async def delete_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        return await self._upstream.request_json(
            "DELETE",
            f"/threads/{thread_id}/runs/{run_id}",
        )

    async def join_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.request_json(
            "GET",
            f"/threads/{thread_id}/runs/{run_id}/join",
        )

    async def join_thread_run_stream(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
        params: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        return await self._upstream.stream(
            "GET",
            f"/threads/{thread_id}/runs/{run_id}/stream",
            params=_normalize_payload(params),
        )

    async def create_thread_run_cron(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(project_id=project_id, payload=payload)
        assistant_id = _clean(next_payload.get("assistant_id"))
        await self._assert_runtime_target_allowed(
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        return await self._upstream.request_json(
            "POST",
            f"/threads/{thread_id}/runs/crons",
            payload=next_payload,
        )

    async def cancel_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        return await self._upstream.request_json(
            "POST",
            f"/threads/{thread_id}/runs/{run_id}/cancel",
            payload=_normalize_payload(payload),
        )

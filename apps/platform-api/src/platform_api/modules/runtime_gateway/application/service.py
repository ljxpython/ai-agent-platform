from __future__ import annotations

from platform_api.core.security import empty_runtime_context_hash

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from platform_api.adapters.langgraph.sdk_client import (
    redact_runtime_private_fields as _redact_runtime_private_fields,
)
from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
    UpstreamServiceError,
)
from platform_api.core.identifiers import parse_uuid
from platform_api.core.normalization import clean_str, ensure_dict
from platform_api.core.runtime_contract import (
    PROJECT_SCOPE_ALIAS_KEYS,
    normalize_protocol_v2_command,
    normalize_protocol_v2_event_request,
    normalize_runtime_payload,
    strip_keys,
    validate_runtime_option_values,
)
from platform_api.modules.agents.infra.sqlalchemy.repository import (
    SqlAlchemyAssistantsRepository,
)
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.application.model_connection import (
    create_model_reference,
)
from platform_api.modules.runtime_catalog.infra.sqlalchemy.repository import (
    SqlAlchemyRuntimeCatalogRepository,
)
from platform_api.modules.runtime_gateway.application.ports import (
    RuntimeGatewayUpstreamProtocol,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import (
    RunRequestsRepository,
    StoredRunRequest,
)
from platform_api.modules.runtime_policies.infra import (
    SqlAlchemyRuntimePolicyRepository,
)

_THREAD_PROJECT_ID_KEYS = PROJECT_SCOPE_ALIAS_KEYS
_THREAD_GRAPH_ID_KEYS = ("graph_id", "graphId")
_SDK_LIFECYCLE_EVENTS = {
    "started": "running",
    "success": "completed",
    "error": "failed",
}
# Default stream modes for LangGraph Protocol v2 SSE events
# Required for frontend to receive streaming messages, tools, and lifecycle events
_DEFAULT_STREAM_MODES: tuple[str, ...] = (
    "values",
    "updates",
    "messages",
    "checkpoints",
)


def _request_digest(command: dict[str, Any]) -> str:
    encoded = json.dumps(
        {"method": command.get("method"), "params": command.get("params")},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _execution_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = ensure_dict(payload.get("config"))
    # Only recursion_limit is a supported non-Context execution override.
    # Identity and credentials are created by the server, never persisted here.
    unknown = set(config) - {"recursion_limit", "configurable"}
    configurable = ensure_dict(config.get("configurable"))
    if unknown or set(configurable) - {"platform_runtime", "project_id"}:
        raise BadRequestError(
            code="unsupported_run_config", message="Unsupported execution config"
        )
    limit = config.get("recursion_limit", 25)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise BadRequestError(
            code="invalid_recursion_limit", message="recursion_limit must be 1..1000"
        )
    return {"recursion_limit": limit}


def _runtime_context_snapshot(command: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    params = ensure_dict(command.get("params"))
    config = ensure_dict(params.get("config"))
    configurable = ensure_dict(config.get("configurable"))
    runtime_options = ensure_dict(configurable.get("platform_runtime"))
    context = ensure_dict(params.get("context"))
    # Protocol promotion applies platform_runtime over the submitted context.
    merged = {**context, **runtime_options}
    tools = merged.get("tools")
    if tools is not None:
        tools = sorted(tools)
    snapshot = {
        "model_id": merged.get("model_id"),
        "temperature": (
            float(merged["temperature"])
            if isinstance(merged.get("temperature"), (int, float))
            and not isinstance(merged.get("temperature"), bool)
            else merged.get("temperature")
        ),
        "max_tokens": merged.get("max_tokens"),
        "top_p": (
            float(merged["top_p"])
            if isinstance(merged.get("top_p"), (int, float))
            and not isinstance(merged.get("top_p"), bool)
            else merged.get("top_p")
        ),
        "tools": tools,
    }
    encoded = json.dumps(
        {"schema": "runtime-context/v1", **snapshot},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    persisted_snapshot = {
        key: value for key, value in snapshot.items() if value is not None
    }
    return "sha256:" + hashlib.sha256(
        encoded.encode("utf-8")
    ).hexdigest(), persisted_snapshot


def _normalize_idempotency_key(value: str | None) -> str:
    normalized = clean_str(value)
    if not normalized:
        raise BadRequestError(
            code="idempotency_key_required",
            message="Idempotency-Key header is required for run.start",
        )
    if len(normalized) > 128:
        raise BadRequestError(
            code="invalid_idempotency_key",
            message="Idempotency-Key header must not exceed 128 characters",
        )
    return normalized


def _run_id_from_command_result(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    candidate = result.get("run_id")
    if not candidate and isinstance(result.get("result"), dict):
        candidate = result["result"].get("run_id")
    return clean_str(candidate)


def _protocol_command_response(command: Mapping[str, Any], result: Any) -> Any:
    """Normalize GraphHarbor's legacy command result to Protocol v2."""
    if isinstance(result, dict) and result.get("type") in {"success", "error"}:
        return result
    response: dict[str, Any] = {
        "type": "success",
        "id": command.get("id"),
        "result": (
            result["result"]
            if isinstance(result, dict) and "result" in result
            else result
            if isinstance(result, dict)
            else {}
        ),
    }
    if isinstance(result, dict) and isinstance(result.get("meta"), dict):
        response["meta"] = result["meta"]
    return response


def _run_items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if not isinstance(result, dict):
        return []
    for key in ("runs", "data", "items"):
        value = result.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _promote_protocol_run_start(params: dict[str, Any]) -> dict[str, Any]:
    """Convert Platform's v2 candidate envelope into a standard Runs payload."""
    config = ensure_dict(params.get("config"))
    configurable = ensure_dict(config.get("configurable"))
    runtime_options = ensure_dict(configurable.get("platform_runtime"))
    next_configurable = dict(configurable)
    next_configurable.pop("platform_runtime", None)
    next_config = dict(config)
    if next_configurable:
        next_config["configurable"] = next_configurable
    else:
        next_config.pop("configurable", None)

    context = ensure_dict(params.get("context"))
    context.update(runtime_options)
    promoted = {
        key: params[key]
        for key in (
            "assistant_id",
            "input",
            "command",
            "stream_mode",
            "stream_subgraphs",
            "stream_resumable",
            "metadata",
            "context",
            "checkpoint",
            "checkpoint_id",
            "checkpoint_during",
            "interrupt_before",
            "interrupt_after",
            "webhook",
            "multitask_strategy",
            "if_not_exists",
            "on_completion",
            "after_seconds",
            "durability",
        )
        if key in params
    }
    promoted["context"] = context
    if next_config:
        promoted["config"] = next_config
    return promoted


def _normalize_protocol_lifecycle_frame(
    frame: bytes,
) -> tuple[bytes, dict[str, str] | None]:
    """Bridge GraphHarbor lifecycle labels to the locked frontend SDK contract."""
    try:
        lines = frame.decode("utf-8").split("\n")
    except UnicodeDecodeError:
        return frame, None
    data_positions = [
        index for index, line in enumerate(lines) if line.startswith("data:")
    ]
    if not data_positions:
        return frame, None
    try:
        payload = json.loads(
            "\n".join(lines[index][5:].lstrip() for index in data_positions)
        )
    except ValueError:
        return frame, None
    if not isinstance(payload, dict) or payload.get("method") != "lifecycle":
        return frame, None
    params = ensure_dict(payload.get("params"))
    data = ensure_dict(params.get("data"))
    event = clean_str(data.get("event"))
    normalized_event = _SDK_LIFECYCLE_EVENTS.get(event, event)
    if normalized_event != event:
        payload["params"] = {**params, "data": {**data, "event": normalized_event}}
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        first_data_position = data_positions[0]
        lines = [
            f"data: {encoded}" if index == first_data_position else line
            for index, line in enumerate(lines)
            if index not in data_positions[1:]
        ]
        frame = "\n".join(lines).encode("utf-8")
    run_id = clean_str(params.get("run_id"))
    status = clean_str(data.get("status"))
    if not run_id or status not in {
        "success",
        "succeeded",
        "completed",
        "error",
        "failed",
        "timeout",
        "cancelled",
        "canceled",
    }:
        return frame, None
    return frame, {"run_id": run_id, "status": status}


def _interrupt_ids(state: Any) -> set[str]:
    if not isinstance(state, dict):
        return set()
    interrupts = state.get("interrupts")
    if isinstance(interrupts, dict):
        return {
            interrupt_id
            for interrupt_id in (clean_str(key) for key in interrupts)
            if interrupt_id
        }
    if isinstance(interrupts, list):
        return {
            interrupt_id
            for interrupt in interrupts
            if isinstance(interrupt, dict)
            for interrupt_id in [
                clean_str(interrupt.get("id") or interrupt.get("interrupt_id"))
            ]
            if interrupt_id
        }
    tasks = state.get("tasks")
    if not isinstance(tasks, list):
        return set()
    return {
        interrupt_id
        for task in tasks
        if isinstance(task, dict)
        for interrupt in (task.get("interrupts") or [])
        if isinstance(interrupt, dict)
        for interrupt_id in [clean_str(interrupt.get("id"))]
        if interrupt_id
    }


def _normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    return ensure_dict(payload)


def _thread_metadata(thread: dict[str, Any]) -> dict[str, Any]:
    metadata = thread.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _thread_project_id(thread: dict[str, Any]) -> str | None:
    metadata = _thread_metadata(thread)
    for key in _THREAD_PROJECT_ID_KEYS:
        value = clean_str(metadata.get(key))
        if value:
            return value
    return None


def _without_project_scope_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    return strip_keys(payload, _THREAD_PROJECT_ID_KEYS)


def _thread_graph_id(thread: dict[str, Any]) -> str | None:
    metadata = _thread_metadata(thread)
    for key in _THREAD_GRAPH_ID_KEYS:
        value = clean_str(metadata.get(key))
        if value:
            return value
    if clean_str(metadata.get("target_type")) == "graph":
        legacy_graph_id = clean_str(metadata.get("assistant_id"))
        if legacy_graph_id:
            return legacy_graph_id
    return None


def _promote_thread_graph_id(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    if clean_str(next_payload.get("graph_id")):
        return next_payload

    metadata = ensure_dict(next_payload.get("metadata"))
    graph_id = clean_str(metadata.get("graph_id"))
    if not graph_id and clean_str(metadata.get("target_type")) == "graph":
        graph_id = clean_str(metadata.get("assistant_id"))

    if graph_id:
        next_payload["graph_id"] = graph_id

    return next_payload


def _merge_runtime_context(
    *,
    project_default_model: str | None,
    agent_defaults: dict[str, Any],
    requested: dict[str, Any],
) -> dict[str, Any]:
    defaults = dict(agent_defaults)
    if project_default_model and "model_id" not in defaults:
        defaults["model_id"] = project_default_model
    return {**defaults, **requested}


class RuntimeGatewayService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: RuntimeGatewayUpstreamProtocol,
        runtime_base_url: str = "",
        policy_engine: IamPolicyEngine | None = None,
        delegation_headers_factory: Callable[..., Mapping[str, str]] | None = None,
        runtime_model_config_secret: str | None = None,
        runtime_model_config_ttl_seconds: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._runtime_id = "default" if runtime_base_url else ""
        self._policy_engine = policy_engine or IamPolicyEngine()
        self._delegation_headers_factory = delegation_headers_factory
        self._runtime_model_config_secret = runtime_model_config_secret
        self._runtime_model_config_ttl_seconds = runtime_model_config_ttl_seconds

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
        session: Session,
        project_id: str,
    ) -> UUID:
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        repository = SqlAlchemyProjectsRepository(session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")
        return project_uuid

    def _prepare_project_scope(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        write: bool,
    ) -> UUID:
        self._authorize(actor=actor, project_id=project_id, write=write)
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            return self._require_project_exists(session=session, project_id=project_id)

    def _inject_project_metadata(
        self,
        *,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        next_payload = _normalize_payload(payload)
        metadata = next_payload.get("metadata")
        metadata_dict = (
            _without_project_scope_aliases(dict(metadata))
            if isinstance(metadata, dict)
            else {}
        )
        metadata_dict["project_id"] = project_id
        next_payload["metadata"] = metadata_dict
        return next_payload

    def _inject_project_scope(
        self,
        *,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return normalize_runtime_payload(payload=payload, project_id=project_id)

    def _inject_project_default_model(
        self,
        *,
        project_id: str,
        payload: dict[str, Any],
        default_model_id: str | None = None,
    ) -> dict[str, Any]:
        context = ensure_dict(payload.get("context"))
        assistant_id = clean_str(payload.get("assistant_id"))
        profile_defaults: dict[str, Any] = {}
        if assistant_id and self._session_factory is not None:
            try:
                project_uuid = parse_uuid(project_id, code="invalid_project_id")
            except PlatformApiError:
                project_uuid = None
            if project_uuid is not None:
                with session_scope(self._session_factory) as session:
                    agent = SqlAlchemyAssistantsRepository(
                        session
                    ).get_by_project_and_graph_id(
                        project_id=project_uuid,
                        graph_id=assistant_id,
                    )
                    if agent is not None:
                        profile_defaults = {
                            key: agent.context[key]
                            for key in (
                                "model_id",
                                "temperature",
                                "max_tokens",
                                "top_p",
                                "tools",
                            )
                            if key in agent.context
                        }

        if default_model_id is None and not clean_str(context.get("model_id")):
            default_model_id = self._project_default_model_id(project_id=project_id)
        merged = _merge_runtime_context(
            project_default_model=default_model_id,
            agent_defaults=profile_defaults,
            requested=context,
        )
        if merged == context:
            next_payload = payload
        else:
            next_payload = dict(payload)
            next_payload["context"] = merged
        return next_payload

    def _project_default_model_id(self, *, project_id: str) -> str | None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimePolicyRepository(session)
            return repository.get_default_model_id(
                project_id=project_uuid,
            )

    def _assert_runtime_options_allowed(
        self,
        *,
        project_id: str,
        options: dict[str, Any],
    ) -> None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        with session_scope(session_factory) as session:
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(session)

            model_policies = {
                str(item.model_catalog_id): item
                for item in policy_repository.list_model_policies(
                    project_id=project_uuid
                )
            }
            allowed_models = {
                str(item.id)
                for item in catalog_repository.list_models()
                if item.enabled
                and (
                    str(item.id) not in model_policies
                    or model_policies[str(item.id)].is_enabled
                )
            }
            requested_model = clean_str(options.get("model_id"))
            if requested_model and requested_model not in allowed_models:
                raise ForbiddenError(
                    code="runtime_model_denied",
                    message="Requested runtime model is not enabled for this project",
                )

            tool_policies = {
                str(item.tool_catalog_id): item
                for item in policy_repository.list_tool_policies(
                    project_id=project_uuid
                )
            }
            allowed_tools = {
                item.tool_key
                for item in catalog_repository.list_tools(runtime_id=self._runtime_id)
                if str(item.id) not in tool_policies
                or tool_policies[str(item.id)].is_enabled
            }
            requested_tools = {
                name
                for name in (
                    clean_str(item)
                    for item in options.get("tools", [])
                    if isinstance(item, str)
                )
                if name
            }
            denied_tools = sorted(requested_tools - allowed_tools)
            if denied_tools:
                raise ForbiddenError(
                    code="runtime_tools_denied",
                    message="Requested runtime tools are not enabled for this project",
                )

    def _validate_run_options(
        self, *, project_id: str, payload: dict[str, Any]
    ) -> None:
        context = ensure_dict(payload.get("context"))
        config = ensure_dict(payload.get("config"))
        configurable = ensure_dict(config.get("configurable"))
        options = {**ensure_dict(configurable.get("platform_runtime")), **context}
        try:
            validate_runtime_option_values(options)
        except ValueError as exc:
            raise BadRequestError(
                code="invalid_runtime_options",
                message=str(exc),
            ) from exc
        self._assert_runtime_options_allowed(project_id=project_id, options=options)

    def _attach_runtime_model_reference(
        self,
        *,
        project_id: str,
        actor: ActorContext | None = None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass only a short-lived model capability through the generic Agent Server."""
        if not self._runtime_model_config_secret:
            return payload
        context = ensure_dict(payload.get("context"))
        config = ensure_dict(payload.get("config"))
        configurable = ensure_dict(config.get("configurable"))
        runtime_options = ensure_dict(configurable.get("platform_runtime"))
        model_id = clean_str(context.get("model_id") or runtime_options.get("model_id"))
        if not model_id:
            return payload
        if "model_id" not in context:
            context = {**runtime_options, **context}
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            item = SqlAlchemyRuntimeCatalogRepository(session).get_model_by_id(
                parse_uuid(model_id, code="invalid_model_id")
            )
            if item is None or not item.enabled:
                raise ForbiddenError(
                    code="runtime_model_denied",
                    message="Requested runtime model is not enabled",
                )
        reference = create_model_reference(
            project_id=project_id,
            model_id=model_id,
            secret=self._runtime_model_config_secret,
            ttl_seconds=self._runtime_model_config_ttl_seconds,
            actor={
                "user_id": actor.user_id,
                "principal_type": actor.principal_type,
                "credential_id": actor.credential_id,
            }
            if actor
            else None,
            agent_key=clean_str(payload.get("assistant_id")),
        )
        config = ensure_dict(payload.get("config"))
        configurable = dict(ensure_dict(config.get("configurable")))
        # GraphHarbor drops configurable fields prefixed with `_` when a Run
        # resumes. This opaque capability must survive that generic transport.
        configurable["runtime_model_ref"] = reference
        next_config = dict(config)
        next_config["configurable"] = configurable
        next_payload = dict(payload)
        next_payload["config"] = next_config
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
        await run_in_threadpool(
            self._prepare_project_scope, actor=actor, project_id=project_id, write=write
        )
        thread = await self._upstream.get_thread(thread_id)
        self._assert_thread_project_scope(project_id=project_id, thread=thread)
        return thread

    async def enqueue_thread_message(self, *, actor: ActorContext, project_id: str,
                                     thread_id: str, payload: dict[str, Any],
                                     idempotency_key: str | None) -> Any:
        if not idempotency_key or len(idempotency_key) > 128:
            raise BadRequestError(code="idempotency_key_required", message="Idempotency-Key header is required")
        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=True)
        metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
        agent_key = clean_str(metadata.get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")
        if agent_key not in {"reference_agent", "showcase_demo"}:
            raise ConflictError(code="queue_not_supported", message="Graph does not support queued messages")
        target_run_id = clean_str(payload.get("target_run_id"))
        if not target_run_id:
            raise BadRequestError(code="target_run_required", message="Target Run is required")
        await self._upstream.get_thread_run(thread_id, target_run_id)
        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(self._delegation_headers_factory(
                project_id=project_id, agent_key=agent_key, thread_id=thread_id,
                context_hash=empty_runtime_context_hash(), operation="message-enqueue"))
        import jwt
        import time
        if not self._runtime_model_config_secret:
            raise ServiceUnavailableError(code="message_auth_unavailable", message="Message authorization is not configured")
        reference = jwt.encode({
            "aud": "runtime-message", "exp": int(time.time()) + 86400,
            "project_id": project_id, "thread_id": thread_id, "run_id": target_run_id,
            "agent_key": agent_key, "actor": {"user_id": actor.user_id,
                "principal_type": actor.principal_type, "credential_id": actor.credential_id},
        }, self._runtime_model_config_secret, algorithm="HS256")
        return await upstream.enqueue_thread_message(thread_id, {
            **payload, "idempotency_key": idempotency_key, "authorization_ref": reference,
        })

    async def list_thread_messages(self, *, actor: ActorContext, project_id: str, thread_id: str) -> Any:
        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=False)
        metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
        agent_key = clean_str(metadata.get("graph_id"))
        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(self._delegation_headers_factory(project_id=project_id, agent_key=agent_key, thread_id=thread_id, context_hash=empty_runtime_context_hash(), operation="message-read"))
        return await upstream.list_thread_messages(thread_id)

    def _assistant_belongs_project(
        self,
        *,
        project_id: str,
        assistant_id: str,
    ) -> bool:
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            project_uuid = self._require_project_exists(
                session=session, project_id=project_id
            )
            repository = SqlAlchemyAssistantsRepository(session)
            item = repository.get_by_project_and_graph_id(
                project_id=project_uuid,
                graph_id=assistant_id,
            )
            if item is None or item.status != "active":
                return False
            catalog = SqlAlchemyRuntimeCatalogRepository(session)
            graph_ids = {
                str(graph.id)
                for graph in catalog.list_graphs(runtime_id=self._runtime_id)
                if graph.graph_key == assistant_id
            }
            return not any(
                str(policy.graph_catalog_id) in graph_ids and not policy.is_enabled
                for policy in SqlAlchemyRuntimePolicyRepository(
                    session
                ).list_graph_policies(project_id=project_uuid)
            )

    def _assert_runtime_target_allowed(
        self,
        *,
        project_id: str,
        assistant_id: str,
        thread: dict[str, Any] | None = None,
    ) -> None:
        normalized_assistant_id = clean_str(assistant_id)
        if not normalized_assistant_id:
            raise BadRequestError(
                message="assistant_id is required",
                code="assistant_id_required",
            )

        if self._assistant_belongs_project(
            project_id=project_id,
            assistant_id=normalized_assistant_id,
        ):
            return

        raise ForbiddenError(
            code="runtime_target_denied",
            message="runtime_target_denied",
        )

    async def launch_runtime_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        command: dict[str, Any],
        upstream_payload: dict[str, Any],
        idempotency_key: str,
        parent_run_id: str | None = None,
        interrupt_id: str | None = None,
    ) -> tuple[StoredRunRequest, Any]:
        """Persist submission identity; Agent Server owns execution and concurrency."""
        if upstream_payload.get("assistant_id") in {"reference_agent", "showcase_demo"}:
            upstream_payload = {**upstream_payload, "durability": "sync"}
        key = _normalize_idempotency_key(idempotency_key)
        actor_id = (
            clean_str(actor.user_id)
            or clean_str(actor.credential_id)
            or clean_str(actor.subject)
        )
        if not actor_id:
            raise ForbiddenError(
                code="actor_required", message="Authenticated identity required"
            )
        agent_key = clean_str(upstream_payload.get("assistant_id"))
        if not agent_key:
            raise BadRequestError(
                code="assistant_id_required", message="assistant_id is required"
            )
        _execution_config(upstream_payload)
        digest = _request_digest(command)
        context_hash, snapshot = _runtime_context_snapshot({"params": upstream_payload})
        factory = self._require_session_factory()

        def reserve():
            with factory.begin() as session:
                repo = RunRequestsRepository(session)
                existing = repo.get(
                    project_id=project_id, thread_id=thread_id, idempotency_key=key
                )
                if existing:
                    if (
                        existing.requested_by != actor_id
                        or existing.request_digest != digest
                    ):
                        raise ConflictError(
                            code="idempotency_key_conflict",
                            message="Key already used for a different request",
                        )
                    return existing
                return repo.create(
                    project_id=project_id,
                    thread_id=thread_id,
                    agent_key=agent_key,
                    requested_by=actor_id,
                    idempotency_key=key,
                    request_digest=digest,
                    context_hash=context_hash,
                    context_snapshot=snapshot,
                    config_snapshot=_execution_config(upstream_payload),
                    parent_run_id=parent_run_id,
                    interrupt_id=interrupt_id,
                    submission_status="submitted",
                )

        try:
            record = await run_in_threadpool(reserve)
        except IntegrityError:
            record = await run_in_threadpool(reserve)
        await run_in_threadpool(
            self._validate_run_options,
            project_id=project_id,
            payload={"context": record.context_snapshot},
        )
        if record.run_id:
            return record, await self._upstream.get_thread_run(thread_id, record.run_id)

        payload = dict(upstream_payload)
        payload["multitask_strategy"] = "reject"
        payload["context"] = dict(record.context_snapshot)
        payload["config"] = dict(record.config_snapshot)
        payload = await run_in_threadpool(
            self._attach_runtime_model_reference,
            project_id=project_id,
            payload=payload,
            actor=actor,
        )
        # A stable key covers timeout, response loss and API death after server commit.
        payload["idempotency_key"] = (
            "platform:"
            + hashlib.sha256(
                json.dumps([project_id, thread_id, key], separators=(",", ":")).encode()
            ).hexdigest()
        )
        upstream = self._upstream
        if self._delegation_headers_factory is not None and hasattr(
            upstream, "with_forwarded_headers"
        ):
            upstream = upstream.with_forwarded_headers(
                self._delegation_headers_factory(
                    project_id=project_id,
                    agent_key=agent_key,
                    thread_id=thread_id,
                    context_hash=record.context_hash,
                )
            )

        def mark(status, run_id=None):
            with factory.begin() as session:
                RunRequestsRepository(session).mark(record.id, status, run_id)

        try:
            result = await upstream.create_thread_run(thread_id, payload)
            run_id = _run_id_from_command_result(result)
            if not run_id:
                raise UpstreamServiceError(
                    code="protocol_run_id_missing",
                    message="Run creation response did not include run_id",
                    upstream="langgraph",
                )
        except PlatformApiError as exc:
            await run_in_threadpool(
                mark, "rejected" if 400 <= exc.status_code < 500 else "unknown"
            )
            raise
        except Exception:
            await run_in_threadpool(mark, "unknown")
            raise
        await run_in_threadpool(mark, "accepted", run_id)
        return record, result

    async def get_info(self, *, actor: ActorContext, project_id: str) -> dict[str, Any]:
        await run_in_threadpool(
            self._prepare_project_scope, actor=actor, project_id=project_id, write=False
        )
        return await self._upstream.get_info()

    async def search_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await run_in_threadpool(
            self._prepare_project_scope, actor=actor, project_id=project_id, write=False
        )
        return await self._upstream.search_graphs(_normalize_payload(payload))

    async def count_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await run_in_threadpool(
            self._prepare_project_scope, actor=actor, project_id=project_id, write=False
        )
        return await self._upstream.count_graphs(_normalize_payload(payload))

    async def create_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await run_in_threadpool(
            self._prepare_project_scope, actor=actor, project_id=project_id, write=True
        )
        next_payload = self._inject_project_metadata(
            project_id=project_id, payload=payload
        )
        next_payload = _promote_thread_graph_id(next_payload)
        return await self._upstream.create_thread(next_payload)

    async def search_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await run_in_threadpool(
            self._prepare_project_scope, actor=actor, project_id=project_id, write=False
        )
        next_payload = self._inject_project_metadata(
            project_id=project_id, payload=payload
        )
        return await self._upstream.search_threads(next_payload)

    async def count_threads(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: dict[str, Any] | None,
    ) -> Any:
        await run_in_threadpool(
            self._prepare_project_scope, actor=actor, project_id=project_id, write=False
        )
        next_payload = self._inject_project_metadata(
            project_id=project_id, payload=payload
        )
        return await self._upstream.count_threads(next_payload)

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
        return await self._upstream.delete_thread(thread_id)

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
        state = await self._upstream.get_thread_state(
            thread_id, _normalize_payload(params)
        )
        return _redact_runtime_private_fields(state)

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
        return await self._upstream.update_thread_state(
            thread_id, _normalize_payload(payload)
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
        history = await self._upstream.get_thread_history(
            thread_id, _normalize_payload(payload)
        )
        return _redact_runtime_private_fields(history)

    async def create_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
        idempotency_key: str | None = None,
    ) -> Any:
        raw = ensure_dict(payload)
        if "command" in raw:
            command = raw["command"]
            if not isinstance(command, dict) or set(command) != {"resume"}:
                raise BadRequestError(
                    code="invalid_resume", message="Only command.resume is supported"
                )
            if set(raw) - {"assistant_id", "command"}:
                raise BadRequestError(
                    code="resume_configuration_override",
                    message="Resume cannot override input or configuration",
                )
            result = await self.send_thread_command(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                payload={
                    "id": 0,
                    "method": "input.respond",
                    "params": {
                        "resume": command["resume"],
                        "assistant_id": raw.get("assistant_id"),
                    },
                },
            )
            return await self._upstream.get_thread_run(
                thread_id, result["result"]["run_id"]
            )
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        next_payload = self._inject_project_scope(
            project_id=project_id, payload=payload
        )
        next_payload = await run_in_threadpool(
            self._inject_project_default_model,
            project_id=project_id,
            payload=next_payload,
        )
        assistant_id = clean_str(next_payload.get("assistant_id"))
        await run_in_threadpool(
            self._assert_runtime_target_allowed,
            project_id=project_id,
            assistant_id=assistant_id or "",
            thread=thread,
        )
        # Set default stream_mode for Protocol v2 SSE events if not specified
        next_payload.setdefault("stream_mode", list(_DEFAULT_STREAM_MODES))
        next_payload.setdefault("stream_resumable", True)
        command = {"method": "run.start", "params": payload}
        _, result = await self.launch_runtime_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            command=command,
            upstream_payload=next_payload,
            idempotency_key=idempotency_key or str(uuid4()),
        )
        return result

    async def stream_thread_run(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None,
        idempotency_key: str | None = None,
    ) -> Any:
        next_payload = _normalize_payload(payload)
        result = await self.create_thread_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=next_payload,
            idempotency_key=idempotency_key,
        )
        run_id = _run_id_from_command_result(result)
        if not run_id:
            raise UpstreamServiceError(
                code="protocol_run_id_missing",
                message="Run creation response did not include run_id",
                upstream="langgraph",
            )
        stream_params = {
            key: next_payload[key]
            for key in (
                "stream_mode",
                "stream_subgraphs",
                "stream_resumable",
                "on_disconnect",
            )
            if key in next_payload
        }
        return await self._upstream.join_thread_run_stream(
            thread_id, run_id, stream_params
        )

    async def send_thread_command(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
        )
        raw_payload = dict(payload)
        raw_params = ensure_dict(raw_payload.get("params"))
        if raw_payload.get("method") == "run.start":
            raw_params = await run_in_threadpool(
                self._inject_project_default_model,
                project_id=project_id,
                payload=raw_params,
            )
        raw_payload["params"] = raw_params
        default_model_id = clean_str(
            ensure_dict(raw_params.get("context")).get("model_id")
        )
        try:
            command = normalize_protocol_v2_command(
                payload=raw_payload,
                default_model_id=default_model_id,
            )
        except ValueError as exc:
            raise BadRequestError(
                code="invalid_protocol_command",
                message=str(exc),
            ) from exc

        if command["method"] == "run.start":
            assistant_id = clean_str(command["params"].get("assistant_id"))
            await run_in_threadpool(
                self._assert_runtime_target_allowed,
                project_id=project_id,
                assistant_id=assistant_id or "",
                thread=thread,
            )
            promoted_payload = _promote_protocol_run_start(command["params"])
            _, result = await self.launch_runtime_run(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                command=payload,
                upstream_payload=promoted_payload,
                idempotency_key=_normalize_idempotency_key(idempotency_key),
            )
            run_id = _run_id_from_command_result(result)
            return {
                "type": "success",
                "id": command["id"],
                "result": {"run_id": run_id, "thread_id": thread_id},
            }
        if command["method"] == "input.respond":
            params = ensure_dict(command["params"])
            if set(params) - {"interrupt_id", "response", "resume", "assistant_id"}:
                raise BadRequestError(
                    code="resume_configuration_override",
                    message="Resume cannot change execution configuration",
                )
            resumes = params.get("resume")
            if resumes is None:
                interrupt_id = clean_str(params.get("interrupt_id"))
                resumes = {interrupt_id: params.get("response")} if interrupt_id else {}
            if (
                not isinstance(resumes, dict)
                or not resumes
                or any(not isinstance(key, str) or not key.strip() for key in resumes)
            ):
                raise BadRequestError(
                    code="interrupt_id_required",
                    message="Resume requires interrupt IDs",
                )
            interrupt_ids = sorted(resumes)
            interrupt_id = (
                interrupt_ids[0]
                if len(interrupt_ids) == 1
                else hashlib.sha256(json.dumps(interrupt_ids).encode()).hexdigest()
            )
            resume_key = "resume:" + interrupt_id

            def load_request(run_id=None):
                with self._require_session_factory()() as session:
                    repo = RunRequestsRepository(session)
                    if run_id:
                        return repo.for_run(
                            project_id=project_id, thread_id=thread_id, run_id=run_id
                        )
                    return repo.get(
                        project_id=project_id,
                        thread_id=thread_id,
                        idempotency_key=resume_key,
                    )

            previous = await run_in_threadpool(load_request)
            parent = previous
            if previous is None:
                state = await self._upstream.get_thread_state(thread_id, {})
                if not set(interrupt_ids) <= _interrupt_ids(state):
                    raise ConflictError(
                        code="interrupt_not_active",
                        message="Interrupt is no longer active",
                    )
                checkpoint_run_id = clean_str(
                    ensure_dict(state.get("metadata")).get("run_id")
                )
                if not checkpoint_run_id:
                    raise ConflictError(
                        code="interrupt_run_missing",
                        message="Checkpoint has no originating Run",
                    )
                parent = await run_in_threadpool(load_request, checkpoint_run_id)
            if parent is None:
                raise ConflictError(
                    code="run_request_missing",
                    message="Original authorized request is required",
                )
            if previous is None:
                parent_run = await self._upstream.get_thread_run(
                    thread_id, parent.run_id
                )
                if (
                    not isinstance(parent_run, dict)
                    or parent_run.get("status") != "interrupted"
                ):
                    raise ConflictError(
                        code="interrupt_run_mismatch",
                        message="Original run is not interrupted",
                    )
            await run_in_threadpool(
                self._assert_runtime_target_allowed,
                project_id=project_id,
                assistant_id=parent.agent_key,
                thread=thread,
            )
            if (
                params.get("assistant_id")
                and params["assistant_id"] != parent.agent_key
            ):
                raise ForbiddenError(
                    code="runtime_target_denied",
                    message="Resume Agent does not match original Run",
                )
            resume_payload = {
                "assistant_id": parent.agent_key,
                "command": {"resume": resumes},
                "context": dict(parent.context_snapshot),
                "config": dict(parent.config_snapshot),
                "multitask_strategy": "reject",
            }
            await run_in_threadpool(
                self._validate_run_options,
                project_id=project_id,
                payload=resume_payload,
            )
            _, result = await self.launch_runtime_run(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                command={"method": "input.respond", "params": {"resume": resumes}},
                upstream_payload=resume_payload,
                idempotency_key=resume_key,
                parent_run_id=previous.parent_run_id if previous else parent.run_id,
                interrupt_id=interrupt_id,
            )
            return _protocol_command_response(
                command,
                {"run_id": _run_id_from_command_result(result), "thread_id": thread_id},
            )
        return _protocol_command_response(
            command,
            await self._upstream.send_thread_command(thread_id, command),
        )

    async def stream_thread_events(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any],
    ) -> Any:
        await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=False,
        )
        try:
            subscription = normalize_protocol_v2_event_request(payload)
        except ValueError as exc:
            raise BadRequestError(
                code="invalid_protocol_event_subscription",
                message=str(exc),
            ) from exc
        stream = await self._upstream.stream_thread_events(thread_id, subscription)

        return stream

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
        snapshot = await self._upstream.get_thread_run(thread_id, run_id)
        return snapshot

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
        return await self._upstream.list_thread_runs(
            thread_id, _normalize_payload(params)
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
        return await self._upstream.delete_thread_run(thread_id, run_id)

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
        return await self._upstream.join_thread_run(thread_id, run_id)

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
        stream_params = _normalize_payload(params)
        if stream_params.get("cancel_on_disconnect") is True:
            raise BadRequestError(
                code="cancel_on_disconnect_not_supported",
                message="SSE disconnect must not cancel a run; use the explicit cancel endpoint",
            )
        stream_params["cancel_on_disconnect"] = False
        return await self._upstream.join_thread_run_stream(
            thread_id,
            run_id,
            stream_params,
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
        result = await self._upstream.cancel_thread_run(
            thread_id,
            run_id,
            _normalize_payload(payload),
        )
        return result

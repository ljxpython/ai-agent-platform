from __future__ import annotations

from platform_api.core.security import empty_runtime_context_hash

import hashlib
import json
import logging
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

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
    BinaryPayload,
    RuntimeGatewayUpstreamProtocol,
)
from platform_api.modules.runtime_gateway.application.clarification import validate_clarification_resumes
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import (
    RunRequestsRepository,
    StoredRunRequest,
)
from platform_api.modules.runtime_policies.infra import (
    SqlAlchemyRuntimePolicyRepository,
)

_THREAD_PROJECT_ID_KEYS = PROJECT_SCOPE_ALIAS_KEYS
_THREAD_GRAPH_ID_KEYS = ("graph_id", "graphId")
_ACCESS_POLICY_KEY = "access_policy"
_ACCESS_POLICIES = frozenset(("review", "workspace_write", "full_access"))
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


_ALLOWED_CONFIGURABLE_KEYS = {
    "platform_runtime",
    "project_id",
    "checkpoint_id",
    "checkpoint_ns",
    "thread_id",
}


def _execution_config(payload: dict[str, Any]) -> dict[str, Any]:
    config = ensure_dict(payload.get("config"))
    # Only recursion_limit is a supported non-Context execution override.
    # Identity and credentials are created by the server, never persisted here.
    unknown = set(config) - {"recursion_limit", "configurable"}
    configurable = ensure_dict(config.get("configurable"))
    if unknown or set(configurable) - _ALLOWED_CONFIGURABLE_KEYS:
        raise BadRequestError(
            code="unsupported_run_config", message="Unsupported execution config"
        )
    checkpoint_id = configurable.get("checkpoint_id")
    if checkpoint_id is not None and (
        not isinstance(checkpoint_id, str) or not clean_str(checkpoint_id)
    ):
        raise BadRequestError(
            code="invalid_checkpoint_id",
            message="checkpoint_id must be a non-empty string",
        )
    checkpoint_ns = configurable.get("checkpoint_ns")
    if checkpoint_ns is not None and not isinstance(checkpoint_ns, str):
        raise BadRequestError(
            code="invalid_checkpoint_ns",
            message="checkpoint_ns must be a string",
        )
    thread_id = configurable.get("thread_id")
    if thread_id is not None and (
        not isinstance(thread_id, str) or not clean_str(thread_id)
    ):
        raise BadRequestError(
            code="invalid_thread_id",
            message="thread_id must be a non-empty string",
        )
    limit = config.get("recursion_limit", 1000)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise BadRequestError(
            code="invalid_recursion_limit", message="recursion_limit must be 1..1000"
        )
    result: dict[str, Any] = {"recursion_limit": limit}
    config_configurable: dict[str, Any] = {}
    if checkpoint_id is not None:
        config_configurable["checkpoint_id"] = clean_str(checkpoint_id)
    if checkpoint_ns is not None:
        config_configurable["checkpoint_ns"] = checkpoint_ns
    if thread_id is not None:
        config_configurable["thread_id"] = clean_str(thread_id)
    if config_configurable:
        result["configurable"] = config_configurable
    return result


def _runtime_context_snapshot(command: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    params = ensure_dict(command.get("params"))
    config = ensure_dict(params.get("config"))
    configurable = ensure_dict(config.get("configurable"))
    runtime_options = ensure_dict(configurable.get("platform_runtime"))
    context = ensure_dict(params.get("context"))
    # Protocol promotion applies platform_runtime over the submitted context.
    merged = {**context, **runtime_options}
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
    }
    mode = merged.get("execution_mode")
    if mode is not None:
        snapshot["execution_mode"] = mode
    if merged.get("access_policy") is not None:
        snapshot["access_policy"] = merged["access_policy"]
    schema = "runtime-context/v4"
    encoded = json.dumps(
        {"schema": schema, **snapshot},
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
            "version",
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
    if "checkpoint_id" not in promoted and "checkpoint_id" in configurable:
        cid = clean_str(configurable["checkpoint_id"])
        if cid:
            promoted["checkpoint_id"] = cid
    if "checkpoint_ns" not in promoted and "checkpoint_ns" in configurable:
        cns = configurable["checkpoint_ns"]
        if isinstance(cns, str):
            promoted["checkpoint_ns"] = cns
    promoted.setdefault("stream_mode", list(_DEFAULT_STREAM_MODES))
    promoted.setdefault("stream_resumable", True)
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
    def check(value):
        if isinstance(value, dict):
            if "dear_skill_snapshot" in value:
                raise BadRequestError(code="runtime_private_state", message="Skill execution state is server-owned")
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    check(payload)
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


def _thread_access_policy(thread: dict[str, Any]) -> str:
    value = _thread_metadata(thread).get(_ACCESS_POLICY_KEY)
    return value if value in _ACCESS_POLICIES else "review"


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
    if project_default_model and not clean_str(defaults.get("model_id")):
        defaults["model_id"] = project_default_model
    merged = dict(defaults)
    for key, value in requested.items():
        if key == "model_id":
            cleaned = clean_str(value)
            if cleaned:
                merged[key] = cleaned
            elif "model_id" not in merged and project_default_model:
                merged[key] = project_default_model
        elif value is not None:
            merged[key] = value
    if project_default_model and not clean_str(merged.get("model_id")):
        merged["model_id"] = project_default_model
    return merged


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
                    PermissionCode.PROJECT_RUNTIME_EXECUTE
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
        try:
            return normalize_runtime_payload(payload=payload, project_id=project_id)
        except ValueError as exc:
            raise BadRequestError(code="invalid_runtime_payload", message=str(exc)) from exc

    def _inject_project_default_model(
        self,
        *,
        project_id: str,
        payload: dict[str, Any],
        default_model_id: str | None = None,
    ) -> dict[str, Any]:
        context = ensure_dict(payload.get("context"))
        config = ensure_dict(payload.get("config"))
        configurable = ensure_dict(config.get("configurable"))
        runtime_options = ensure_dict(configurable.get("platform_runtime"))
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
                                "execution_mode",
                            )
                            if key in agent.context
                        }

        requested_model = clean_str(context.get("model_id") or runtime_options.get("model_id"))
        if default_model_id is None and not requested_model:
            default_model_id = self._project_default_model_id(project_id=project_id)

        combined_requested = {**context, **{k: v for k, v in runtime_options.items() if v is not None}}
        merged = _merge_runtime_context(
            project_default_model=default_model_id,
            agent_defaults=profile_defaults,
            requested=combined_requested,
        )
        if assistant_id == "dearflow_agent" and merged.get("execution_mode") is None:
            merged["execution_mode"] = "standard"

        next_payload = dict(payload)
        next_payload["context"] = merged

        if merged.get("model_id"):
            next_config = dict(config)
            next_configurable = dict(configurable)
            next_runtime_options = dict(runtime_options)
            next_runtime_options["model_id"] = merged["model_id"]
            if merged.get("execution_mode") and "execution_mode" not in next_runtime_options:
                next_runtime_options["execution_mode"] = merged["execution_mode"]
            next_configurable["platform_runtime"] = next_runtime_options
            next_config["configurable"] = next_configurable
            next_payload["config"] = next_config

        return next_payload

    @staticmethod
    def _inject_thread_access_policy(*, thread: dict[str, Any], payload: dict[str, Any], actor: ActorContext | None = None) -> dict[str, Any]:
        policy = _thread_access_policy(thread)
        if actor is not None and not thread_access.private_owner(actor, _thread_metadata(thread)):
            policy = "review"
        next_payload = dict(payload)
        context = dict(ensure_dict(next_payload.get("context")))
        context[_ACCESS_POLICY_KEY] = policy
        next_payload["context"] = context
        config = dict(ensure_dict(next_payload.get("config")))
        configurable = dict(ensure_dict(config.get("configurable")))
        runtime_options = dict(ensure_dict(configurable.get("platform_runtime")))
        runtime_options[_ACCESS_POLICY_KEY] = policy
        configurable["platform_runtime"] = runtime_options
        config["configurable"] = configurable
        next_payload["config"] = config
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
                for item in catalog_repository.list_models(project_id=project_uuid)
                if item.enabled
                and (
                    item.scope_type == "project"
                    or (
                        str(item.id) not in model_policies
                        or model_policies[str(item.id)].is_enabled
                    )
                )
            }
            requested_model = clean_str(options.get("model_id"))
            if requested_model and requested_model not in allowed_models:
                raise ForbiddenError(
                    code="runtime_model_denied",
                    message="Requested runtime model is not enabled for this project",
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
        thread_id: str | None = None,
        thread_action: str = "comment",
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
            if getattr(item, "scope_type", "platform") == "project" and str(getattr(item, "project_id", None)) != project_id:
                raise ForbiddenError(
                    code="runtime_model_denied",
                    message="Requested project runtime model belongs to another project",
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
            thread_id=thread_id,
            thread_action=thread_action,
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
        action: str | None = None,
    ) -> dict[str, Any]:
        action = action or ("edit" if write else "read")
        if thread_access.is_manager(actor, project_id) and not actor.project_role_set(project_id) and action in {"read", "approve", "delete"}:
            def validate_project():
                with session_scope(self._require_session_factory()) as session:
                    self._require_project_exists(session=session, project_id=project_id)
            await run_in_threadpool(validate_project)
        else:
            await run_in_threadpool(
                self._prepare_project_scope, actor=actor, project_id=project_id,
                write=write and action not in {"delete", "approve", "share"},
            )
        access = await run_in_threadpool(thread_access.get, self._require_session_factory(), thread_id)
        if not access and action == "delete" and thread_access.is_manager(actor, project_id):
            access = {"project_id": project_id}
        thread_access.require_action(actor, project_id, access, action)
        if action == "read" and not thread_access.is_owner(actor, access) and thread_access.is_manager(actor, project_id) and (access.get("visibility") == "private" or not actor.project_role_set(project_id)):
            await run_in_threadpool(thread_access.audit_takeover_access, self._require_session_factory(),
                                   actor=actor, project_id=project_id, thread_id=thread_id)
        thread = await self._upstream.get_thread(thread_id)
        self._assert_thread_project_scope(project_id=project_id, thread=thread)
        return self._thread_with_access(actor, project_id, thread, access)

    @staticmethod
    def _thread_with_access(actor: ActorContext, project_id: str, thread: dict, access: dict) -> dict:
        metadata = {key: value for key, value in _thread_metadata(thread).items() if key not in thread_access.ACL_KEYS}
        metadata.update(access)
        metadata["allowed_actions"] = [action for action in (*sorted(thread_access.SHARE_ACTIONS), "approve", "terminal", "full_access")
                                       if thread_access.allowed(actor, project_id, access, action)]
        metadata.pop("takeovers", None)
        if "share" not in metadata["allowed_actions"]:
            metadata.pop("shared_actions", None)
        return {**thread, "metadata": metadata}

    async def enqueue_thread_message(self, *, actor: ActorContext, project_id: str,
                                     thread_id: str, payload: dict[str, Any],
                                     idempotency_key: str | None) -> Any:
        if not idempotency_key or len(idempotency_key) > 128:
            raise BadRequestError(code="idempotency_key_required", message="Idempotency-Key header is required")
        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=True, action="comment")
        metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
        agent_key = clean_str(metadata.get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")
        if agent_key not in {"reference_agent", "showcase_demo", "dearflow_agent"}:
            raise ConflictError(code="queue_not_supported", message="Graph does not support queued messages")
        target_run_id = clean_str(payload.get("target_run_id"))
        if not target_run_id:
            raise BadRequestError(code="target_run_required", message="Target Run is required")
        await self._upstream.get_thread_run(thread_id, target_run_id)
        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(await run_in_threadpool(self._delegation_headers_factory,
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
            upstream = upstream.with_forwarded_headers(await run_in_threadpool(self._delegation_headers_factory,project_id=project_id, agent_key=agent_key, thread_id=thread_id, context_hash=empty_runtime_context_hash(), operation="message-read"))
        return await upstream.list_thread_messages(thread_id)

    async def upload_thread_image(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        sha256: str,
        content_type: str,
        content_length: int,
        body: AsyncIterator[bytes],
    ) -> dict[str, Any]:
        sha256 = clean_str(sha256).lower()
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise BadRequestError(code="image_hash_invalid", message="Invalid image sha256")

        media_type = content_type.split(";")[0].strip().lower()
        if media_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise PlatformApiError(
                code="image_mime_unsupported",
                status_code=415,
                message=f"Unsupported image content type: {content_type}",
            )

        if content_length <= 0:
            raise BadRequestError(code="image_length_required", message="Content-Length must be a positive integer")
        if content_length > 5 * 1024 * 1024:
            raise PlatformApiError(
                code="image_too_large",
                status_code=413,
                message="Image upload exceeds 5 MiB limit",
            )

        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=True)
        metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
        agent_key = clean_str(metadata.get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")

        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(
                await run_in_threadpool(self._delegation_headers_factory,
                    project_id=project_id,
                    agent_key=agent_key,
                    thread_id=thread_id,
                    context_hash=empty_runtime_context_hash(),
                    operation="image-upload",
                )
            )

        ref = await upstream.upload_thread_image(
            graph_id=agent_key,
            thread_id=thread_id,
            sha256=sha256,
            content_type=media_type,
            content_length=content_length,
            body=body,
        )

        version = ref.get("version") if isinstance(ref, dict) else None
        mime_type = (ref.get("mime_type") or ref.get("mime")) if isinstance(ref, dict) else None
        path = ref.get("path") if isinstance(ref, dict) else None
        ref_sha256 = ref.get("sha256") if isinstance(ref, dict) else None
        size_bytes = ref.get("size_bytes") if isinstance(ref, dict) else None

        if (
            not isinstance(ref, dict)
            or version not in (1, "v1")
            or not isinstance(path, str)
            or not isinstance(ref_sha256, str)
            or not isinstance(mime_type, str)
            or not isinstance(size_bytes, int)
            or size_bytes <= 0
        ):
            raise PlatformApiError(
                code="runtime_invalid_image_response",
                status_code=502,
                message="Invalid ImageRef from runtime",
            )

        return {
            "version": 1,
            "path": path,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "sha256": ref_sha256,
        }

    async def read_thread_image(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        path: str,
    ) -> BinaryPayload:
        path = clean_str(path)
        if not path or ".." in path or "\\" in path:
            raise BadRequestError(code="image_path_invalid", message="Invalid image path")

        allowed_prefixes = (
            "/workspace/uploads/",
            "/workspace/generated/",
            "/workspace/charts/",
            "/workspace/outputs/",
        )
        if not any(path.startswith(prefix) for prefix in allowed_prefixes):
            raise BadRequestError(code="image_path_invalid", message="Path must be in allowed workspace image directories")

        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=False)
        metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
        agent_key = clean_str(metadata.get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")

        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(
                await run_in_threadpool(self._delegation_headers_factory,
                    project_id=project_id,
                    agent_key=agent_key,
                    thread_id=thread_id,
                    context_hash=empty_runtime_context_hash(),
                    operation="image-read",
                )
            )

        return await upstream.read_thread_image(
            graph_id=agent_key,
            thread_id=thread_id,
            path=path,
        )

    async def upload_thread_file(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        sha256: str,
        content_type: str,
        content_length: int,
        body: AsyncIterator[bytes],
        file_name: str | None = None,
    ) -> dict[str, Any]:
        sha256 = clean_str(sha256).lower()
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise BadRequestError(code="invalid_file_ref", message="Invalid file sha256")

        media_type = content_type.split(";")[0].strip().lower()
        allowed_mimes = {
            "application/zip",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/html", "text/css", "text/javascript",
            "application/pdf",
            "text/plain",
            "text/markdown",
            "application/json",
            "text/csv",
        }
        if media_type not in allowed_mimes:
            raise PlatformApiError(
                code="unsupported_file_type",
                status_code=415,
                message=f"Unsupported document type: {content_type}",
            )

        if content_length <= 0:
            raise BadRequestError(code="file_length_required", message="Content-Length must be a positive integer")
        if content_length > 20 * 1024 * 1024:
            raise PlatformApiError(
                code="file_too_large",
                status_code=413,
                message="File upload exceeds 20 MiB limit",
            )

        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=True)
        metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
        agent_key = clean_str(metadata.get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")

        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(
                await run_in_threadpool(self._delegation_headers_factory,
                    project_id=project_id,
                    agent_key=agent_key,
                    thread_id=thread_id,
                    context_hash=empty_runtime_context_hash(),
                    operation="workspace-file-upload",
                )
            )

        ref = await upstream.upload_thread_file(
            graph_id=agent_key,
            thread_id=thread_id,
            sha256=sha256,
            content_type=media_type,
            content_length=content_length,
            body=body,
            file_name=file_name,
        )

        version = ref.get("version") if isinstance(ref, dict) else None
        mime_type = (ref.get("mime_type") or ref.get("mime")) if isinstance(ref, dict) else None
        path = ref.get("path") if isinstance(ref, dict) else None
        ref_sha256 = ref.get("sha256") if isinstance(ref, dict) else None
        size_bytes = ref.get("size_bytes") if isinstance(ref, dict) else None
        stored_file_name = ref.get("file_name") if isinstance(ref, dict) else None

        if (
            not isinstance(ref, dict)
            or version not in (1, "v1")
            or not isinstance(path, str)
            or not isinstance(ref_sha256, str)
            or not isinstance(mime_type, str)
            or not isinstance(size_bytes, int)
            or size_bytes <= 0
        ):
            raise PlatformApiError(
                code="runtime_invalid_file_response",
                status_code=502,
                message="Invalid FileRef from runtime",
            )

        return {
            "version": 1,
            "path": path,
            "file_name": stored_file_name or (file_name or path.rsplit("/", 1)[-1]),
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "sha256": ref_sha256,
        }

    async def dear_skills(self, *, actor: ActorContext, project_id: str, method: str,
                          suffix: str = "", payload: dict | None = None, params: dict | None = None):
        write = method != "GET"
        await run_in_threadpool(self._prepare_project_scope, actor=actor, project_id=project_id, write=write)
        await run_in_threadpool(self._assert_runtime_target_allowed, project_id=project_id, assistant_id="dearflow_agent")
        if not self._delegation_headers_factory:
            raise ServiceUnavailableError(code="runtime_delegation_not_configured", message="Runtime delegation required")
        upstream = self._upstream.with_forwarded_headers(await run_in_threadpool(self._delegation_headers_factory,
            project_id=project_id, agent_key="dearflow_agent", thread_id=None,
            context_hash=empty_runtime_context_hash(),
            operation="dear-skills-write" if write else "dear-skills-read"))
        result = await upstream.dear_skills(method, suffix, payload=payload, params=params)
        if method == "GET" and not suffix:
            can_write = True
            try:
                self._authorize(actor=actor, project_id=project_id, write=True)
            except ForbiddenError:
                can_write = False
            result["capabilities"]["can_write"] = can_write and result["capabilities"]["custom_management_enabled"]
        return result

    async def dear_governance(self, *, actor: ActorContext, project_id: str, thread_id: str,
                              resource: str, payload: dict | None = None, query: str = "") -> dict:
        if resource != "memory":
            raise BadRequestError(code="invalid_dear_resource", message="Unknown Dear resource")
        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=payload is not None)
        agent_key = clean_str(ensure_dict(thread.get("metadata")).get("graph_id"))
        if agent_key != "dearflow_agent":
            raise BadRequestError(code="dear_agent_required", message="Dear Agent thread required")
        await run_in_threadpool(self._assert_runtime_target_allowed, project_id=project_id,
                                assistant_id=agent_key, thread=thread)
        if not self._delegation_headers_factory:
            raise ServiceUnavailableError(code="runtime_delegation_not_configured", message="Runtime delegation required")
        upstream = self._upstream.with_forwarded_headers(await run_in_threadpool(self._delegation_headers_factory,
            project_id=project_id, agent_key=agent_key, thread_id=thread_id,
            context_hash=empty_runtime_context_hash(),
            operation="dear-governance-write" if payload is not None else "dear-governance-read"))
        return await upstream.dear_governance(thread_id, resource, payload=payload, query=query)

    async def get_thread_capabilities(
        self, *, actor: ActorContext, project_id: str, thread_id: str,
    ) -> dict[str, Any]:
        thread = await self._load_thread(
            actor=actor, project_id=project_id, thread_id=thread_id, write=False
        )
        agent_key = clean_str(ensure_dict(thread.get("metadata")).get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")
        await run_in_threadpool(
            self._assert_runtime_target_allowed, project_id=project_id,
            assistant_id=agent_key, thread=thread,
        )
        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(await run_in_threadpool(self._delegation_headers_factory,
                project_id=project_id, agent_key=agent_key, thread_id=thread_id,
                context_hash=empty_runtime_context_hash(), operation="read",
            ))
        capabilities = await upstream.get_graph_capabilities(agent_key)
        return {**capabilities, "terminal": bool(capabilities.get("terminal")) and
                thread_access.allowed(actor, project_id, _thread_metadata(thread), "terminal")}

    async def thread_terminal(self, *, actor: ActorContext, project_id: str, thread_id: str,
                              action: str, terminal_id: str | None = None, payload: dict | None = None,
                              offset: int = 0) -> dict:
        if action not in {"create", "list", "output", "input", "resize", "close"}:
            raise BadRequestError(code="invalid_terminal_action", message="Unknown terminal action")
        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=True)
        thread_access.require_action(actor, project_id, _thread_metadata(thread), "terminal")
        agent_key = clean_str(ensure_dict(thread.get("metadata")).get("graph_id"))
        await run_in_threadpool(self._assert_runtime_target_allowed, project_id=project_id,
                                assistant_id=agent_key, thread=thread)
        if not self._delegation_headers_factory:
            raise ServiceUnavailableError(code="runtime_delegation_not_configured", message="Runtime delegation required")
        upstream = self._upstream.with_forwarded_headers(await run_in_threadpool(self._delegation_headers_factory,
            project_id=project_id, agent_key=agent_key, thread_id=thread_id,
            context_hash=empty_runtime_context_hash(),
            operation="terminal-read" if action in {"list", "output"} else "terminal-write"))
        return await upstream.terminal_request(thread_id, action, terminal_id=terminal_id, payload=payload, offset=offset)

    async def thread_workspace(self, *, actor: ActorContext, project_id: str, thread_id: str,
                               resource: str, path: str = "/workspace", cursor: str | None = None,
                               limit: int = 100) -> Any:
        if resource not in {"workspace/tree", "workspace/content", "workspace/preview", "artifacts", "workspace/zip"}:
            raise BadRequestError(code="invalid_workspace_resource", message="Unknown workspace resource")
        if resource != "workspace/zip":
            if (len(path) > 4096 or "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or path != "/workspace" and (not path.startswith("/workspace/") or any(p in {"", ".", ".."} for p in path[11:].split("/")))):
                raise BadRequestError(code="invalid_workspace_path", message="Invalid workspace path")
        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=False)
        agent_key = clean_str(ensure_dict(thread.get("metadata")).get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")
        await run_in_threadpool(self._assert_runtime_target_allowed, project_id=project_id,
                                assistant_id=agent_key, thread=thread)
        if not self._delegation_headers_factory:
            raise ServiceUnavailableError(code="runtime_delegation_not_configured", message="Runtime delegation required")
        upstream = self._upstream.with_forwarded_headers(await run_in_threadpool(self._delegation_headers_factory,
            project_id=project_id, agent_key=agent_key, thread_id=thread_id,
            context_hash=empty_runtime_context_hash(), operation="workspace-file-read"))
        if resource in {"workspace/content", "workspace/preview"}:
            return await upstream.workspace_file(thread_id, resource, path)
        if resource == "workspace/zip":
            return await upstream.workspace_zip(thread_id)
        params = {"limit": limit}
        if resource == "workspace/tree":
            params["path"] = path
        if cursor:
            params["cursor"] = cursor
        return await upstream.workspace_json(thread_id, resource, params)

    async def read_thread_file(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        path: str,
    ) -> BinaryPayload:
        path = clean_str(path)
        if not path or ".." in path or "\\" in path:
            raise BadRequestError(code="invalid_file_ref", message="Invalid file path")

        if not path.startswith(("/workspace/uploads/", "/workspace/outputs/")):
            raise BadRequestError(code="invalid_file_ref", message="Path must be in uploads or published outputs")

        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=False)
        metadata = thread.get("metadata") if isinstance(thread.get("metadata"), dict) else {}
        agent_key = clean_str(metadata.get("graph_id"))
        if not agent_key:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")

        upstream = self._upstream
        if self._delegation_headers_factory:
            upstream = upstream.with_forwarded_headers(
                await run_in_threadpool(self._delegation_headers_factory,
                    project_id=project_id,
                    agent_key=agent_key,
                    thread_id=thread_id,
                    context_hash=empty_runtime_context_hash(),
                    operation="workspace-file-read",
                )
            )

        return await upstream.read_thread_file(
            graph_id=agent_key,
            thread_id=thread_id,
            path=path,
        )

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
        thread_action = "approve" if interrupt_id or parent_run_id or "resume" in ensure_dict(upstream_payload.get("command")) else "comment"
        await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=True, action=thread_action)
        _normalize_payload(upstream_payload)
        if "version" in upstream_payload and upstream_payload["version"] not in ("v2", "v3"):
            raise BadRequestError(code="invalid_stream_version", message="version must be v2 or v3")
        if upstream_payload.get("assistant_id") in {"reference_agent", "showcase_demo", "dearflow_agent"}:
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
        payload.setdefault("stream_mode", list(_DEFAULT_STREAM_MODES))
        payload.setdefault("stream_resumable", True)
        payload["multitask_strategy"] = str(upstream_payload.get("multitask_strategy") or "reject")
        payload["context"] = dict(record.context_snapshot)
        payload["config"] = dict(record.config_snapshot)
        config_configurable = ensure_dict(payload["config"].get("configurable"))
        if "checkpoint_id" not in payload and "checkpoint_id" in config_configurable:
            payload["checkpoint_id"] = config_configurable["checkpoint_id"]
        if "checkpoint_ns" not in payload and "checkpoint_ns" in config_configurable:
            payload["checkpoint_ns"] = config_configurable["checkpoint_ns"]
        payload = await run_in_threadpool(
            self._attach_runtime_model_reference,
            project_id=project_id,
            payload=payload,
            actor=actor,
            thread_id=thread_id,
            thread_action=thread_action,
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
                await run_in_threadpool(self._delegation_headers_factory,
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
        metadata = thread_access.initial_metadata(actor, dict(ensure_dict(next_payload.get("metadata"))))
        policy = metadata.get(_ACCESS_POLICY_KEY)
        if policy == "full_access":
            thread_access.require_action(actor, project_id, metadata, "full_access")
        if policy in _ACCESS_POLICIES:
            metadata[_ACCESS_POLICY_KEY] = policy
        next_payload["metadata"] = {key: value for key, value in metadata.items() if key not in thread_access.ACL_KEYS}
        next_payload["thread_id"] = str(uuid4())
        next_payload["if_exists"] = "raise"
        next_payload = _promote_thread_graph_id(next_payload)
        thread = await self._upstream.create_thread(next_payload)
        if thread.get("thread_id") != next_payload["thread_id"]:
            raise PlatformApiError(code="invalid_created_thread_id", status_code=502, message="Runtime did not preserve the requested Thread identity")
        try:
            access = await run_in_threadpool(thread_access.register, self._require_session_factory(),
                                            thread_id=thread["thread_id"], project_id=project_id, actor=actor)
        except Exception:
            try:
                await self._upstream.delete_thread(thread["thread_id"])
            except Exception:
                logger.exception("Failed to remove unregistered Thread %s", thread["thread_id"])
            raise
        return self._thread_with_access(actor, project_id, thread, access)

    async def _visible_threads(self, *, actor: ActorContext, project_id: str, payload: dict) -> list[dict]:
        records = await run_in_threadpool(thread_access.visible_records, self._require_session_factory(), actor=actor, project_id=project_id)
        requested_ids = payload.get("ids")
        ids = [thread_id for thread_id in records if requested_ids is None or thread_id in requested_ids]
        metadata = {key: value for key, value in ensure_dict(payload.get("metadata")).items() if key not in thread_access.ACL_KEYS}
        metadata["project_id"] = project_id
        query = {key: value for key, value in payload.items() if key not in {"limit", "offset", "select", "extract", "ids", "metadata"}}
        rows: list[dict] = []
        # ponytail: materialize authorized IDs for exact filtered counts; add a local searchable history index if project history becomes large.
        for start in range(0, len(ids), 100):
            batch_ids = ids[start:start + 100]
            for thread_id in batch_ids:
                access = records[thread_id]
                if thread_access.is_manager(actor, project_id) and not thread_access.is_owner(actor, access) and access.get("visibility") == "private":
                    await run_in_threadpool(thread_access.audit_takeover_access, self._require_session_factory(),
                                           actor=actor, project_id=project_id, thread_id=thread_id)
            batch = await self._upstream.search_threads({**query, "metadata": metadata, "ids": batch_ids, "limit": 100, "offset": 0})
            if not isinstance(batch, list):
                raise PlatformApiError(code="invalid_thread_search", status_code=502, message="Invalid Thread search response")
            for row in batch:
                thread_id = row.get("thread_id")
                if thread_id not in batch_ids:
                    raise ForbiddenError(code="thread_search_scope_denied", message="Runtime returned an unexpected Thread")
                self._assert_thread_project_scope(project_id=project_id, thread=row)
                row.pop("values", None)
                rows.append(self._thread_with_access(actor, project_id, row, records[thread_id]))
        return rows

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
        limit, offset = next_payload.get("limit", 20), next_payload.get("offset", 0)
        sort_by, order = next_payload.get("sort_by", "updated_at"), next_payload.get("sort_order", "desc")
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 10_000:
            raise BadRequestError(code="invalid_thread_page", message="Thread limit must be 1–100 and offset 0–10000")
        if sort_by not in {"created_at", "updated_at", "thread_id"} or order not in {"asc", "desc"}:
            raise BadRequestError(code="invalid_thread_sort", message="Unsupported Thread sort")
        selected = next_payload.pop("select", None)
        next_payload.pop("extract", None)
        rows = await self._visible_threads(actor=actor, project_id=project_id, payload=next_payload)
        rows.sort(key=lambda row: (str(row.get(sort_by) or ""), str(row.get("thread_id") or "")), reverse=order == "desc")
        page = rows[offset:offset + limit]
        return [{key: value for key, value in row.items() if key in selected} for row in page] if isinstance(selected, list) and selected else page

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
        rows = await self._visible_threads(actor=actor, project_id=project_id, payload=next_payload)
        return {"count": len(rows)}

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
            action="delete",
        )
        result = await self._upstream.delete_thread(thread_id)
        await run_in_threadpool(thread_access.remove, self._require_session_factory(),
                               actor=actor, project_id=project_id, thread_id=thread_id)
        return result

    async def fork_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        checkpoint_id: str,
        title: str | None,
    ) -> dict[str, Any]:
        checkpoint_id = clean_str(checkpoint_id)
        if not checkpoint_id:
            raise BadRequestError(
                code="invalid_checkpoint_id",
                message="checkpoint_id must be a non-empty string",
            )
        source = await self._load_thread(
            actor=actor, project_id=project_id, thread_id=thread_id, write=True
        )
        graph_id = _thread_graph_id(source)
        if not graph_id:
            raise BadRequestError(code="graph_id_required", message="Thread graph is missing")
        state = await self._upstream.get_thread_state(
            thread_id, {"checkpoint_id": checkpoint_id}
        )
        values = ensure_dict(ensure_dict(state).get("values"))
        if not values:
            raise PlatformApiError(
                code="runtime_invalid_checkpoint_state",
                status_code=502,
                message="Runtime returned no checkpoint state",
            )
        metadata: dict[str, Any] = {
            "project_id": project_id,
            "graph_id": graph_id,
            _ACCESS_POLICY_KEY: _thread_access_policy(source),
            "forked_from": {"thread_id": thread_id, "checkpoint_id": checkpoint_id},
        }
        source_metadata = _thread_metadata(source)
        if agent_id := clean_str(source_metadata.get("agent_id")):
            metadata["agent_id"] = agent_id
        if title := clean_str(title):
            metadata["title"] = title
        if not thread_access.is_owner(actor, source_metadata):
            metadata[_ACCESS_POLICY_KEY] = "review"
        target = await self.create_thread(
            actor=actor, project_id=project_id,
            payload={"metadata": metadata, "graph_id": graph_id},
        )
        target_id = clean_str(ensure_dict(target).get("thread_id"))
        if not target_id:
            raise PlatformApiError(
                code="runtime_invalid_fork_thread",
                status_code=502,
                message="Runtime returned no fork thread ID",
            )
        try:
            await self._upstream.update_thread_state(target_id, {"values": values})
        except Exception:
            try:
                await self._upstream.delete_thread(target_id)
                await run_in_threadpool(thread_access.remove, self._require_session_factory(),
                                       actor=actor, project_id=project_id, thread_id=target_id)
            except Exception:
                pass
            raise

        if self._delegation_headers_factory:
            try:
                fork_upstream = self._upstream.with_forwarded_headers(
                    await run_in_threadpool(self._delegation_headers_factory,
                        project_id=project_id,
                        agent_key=graph_id,
                        thread_id=target_id,
                        context_hash=empty_runtime_context_hash(),
                        operation="workspace-fork",
                    )
                )
                if hasattr(fork_upstream, "fork_thread_workspace"):
                    await fork_upstream.fork_thread_workspace(
                        target_thread_id=target_id, source_thread_id=thread_id
                    )
            except Exception:
                pass

        return ensure_dict(target)

    async def update_thread_access_policy(
        self, *, actor: ActorContext, project_id: str, thread_id: str, policy: str
    ) -> dict[str, str]:
        if not isinstance(policy, str) or policy not in _ACCESS_POLICIES:
            raise BadRequestError(code="invalid_access_policy", message="access_policy must be review, workspace_write or full_access")
        thread = await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=True)
        metadata = _thread_metadata(thread)
        thread_access.require_action(actor, project_id, metadata, "full_access" if policy == "full_access" else "share")
        await self._upstream.update_thread(thread_id, {"metadata": {_ACCESS_POLICY_KEY: policy}})
        return {"thread_id": thread_id, _ACCESS_POLICY_KEY: policy}

    async def share_thread(self, *, actor: ActorContext, project_id: str, thread_id: str,
                           user_id: str | None, actions: list[str]) -> dict:
        await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id,
                                write=False, action="share")
        access = await run_in_threadpool(thread_access.share, self._require_session_factory(),
                                        actor=actor, project_id=project_id, thread_id=thread_id,
                                        user_id=user_id, actions=actions)
        return {"thread_id": thread_id, "visibility": access["visibility"],
                "shared_actions": access["shared_actions"], "project_actions": access["project_actions"]}

    async def takeover_thread(self, *, actor: ActorContext, project_id: str, thread_id: str,
                              category: str, reason: str, reference: str, duration_minutes: int) -> dict:
        if not thread_access.is_manager(actor, project_id):
            self._authorize(actor=actor, project_id=project_id, write=False)
            raise ForbiddenError(code="thread_takeover_denied", message="Administrator permission required")
        # Validate the object without reading its private contents before granting access.
        def grant():
            with session_scope(self._require_session_factory()) as session:
                self._require_project_exists(session=session, project_id=project_id)
            return thread_access.takeover(self._require_session_factory(), actor=actor,
                project_id=project_id, thread_id=thread_id, category=category, reason=reason,
                reference=reference, duration_minutes=duration_minutes)
        return await run_in_threadpool(grant)

    async def end_thread_takeover(self, *, actor: ActorContext, project_id: str, thread_id: str) -> dict:
        if not thread_access.is_manager(actor, project_id):
            self._authorize(actor=actor, project_id=project_id, write=False)
            raise ForbiddenError(code="thread_takeover_denied", message="Administrator permission required")
        return await run_in_threadpool(thread_access.end_takeover, self._require_session_factory(),
                                       actor=actor, project_id=project_id, thread_id=thread_id)

    async def update_thread(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        metadata_updates: dict[str, Any],
    ) -> dict[str, Any]:
        thread = await self._load_thread(
            actor=actor, project_id=project_id, thread_id=thread_id, write=True
        )
        metadata = _thread_metadata(thread)
        updated_fields: dict[str, Any] = {}
        for key in ("title", "preview"):
            if key in metadata_updates:
                val = metadata_updates[key]
                if val is not None and not isinstance(val, str):
                    raise BadRequestError(
                        code="invalid_metadata", message=f"{key} must be a string"
                    )
                metadata[key] = val
                updated_fields[key] = val
        if not updated_fields:
            raise BadRequestError(
                code="invalid_metadata", message="No supported metadata fields provided"
            )
        await self._upstream.update_thread(thread_id, {"metadata": updated_fields})
        return {"thread_id": thread_id, "metadata": metadata}

    async def summarize_thread_title(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        thread = await self._load_thread(
            actor=actor, project_id=project_id, thread_id=thread_id, write=True
        )
        upstream_payload = dict(payload or {})
        if not upstream_payload.get("messages") and hasattr(self._upstream, "get_thread_state"):
            try:
                state = await self._upstream.get_thread_state(thread_id)
                if isinstance(state, dict):
                    values = state.get("values")
                    if isinstance(values, dict) and isinstance(values.get("messages"), list):
                        extracted_msgs = []
                        for m in values["messages"]:
                            if isinstance(m, dict):
                                role = m.get("type") or m.get("role") or "user"
                                content = m.get("content", "")
                                if isinstance(content, list):
                                    text_parts = [
                                        b.get("text", "")
                                        for b in content
                                        if isinstance(b, dict) and b.get("type") == "text"
                                    ]
                                    content = " ".join(text_parts)
                                if content and str(content).strip():
                                    extracted_msgs.append({"role": str(role), "content": str(content).strip()})
                            elif hasattr(m, "content"):
                                role = getattr(m, "type", "user")
                                content = getattr(m, "content", "")
                                if content and str(content).strip():
                                    extracted_msgs.append({"role": str(role), "content": str(content).strip()})
                        if extracted_msgs:
                            upstream_payload["messages"] = extracted_msgs
            except Exception as exc:
                logger.warning(
                    "summarize_thread_title: failed to extract messages from thread state: %s", exc
                )

        summary_result = await self._upstream.summarize_thread_title(
            thread_id, upstream_payload
        )
        generated_title = summary_result.get("title") if isinstance(summary_result, dict) else None
        if generated_title and isinstance(generated_title, str) and generated_title.strip():
            metadata = _thread_metadata(thread)
            metadata["title"] = generated_title.strip()
            await self._upstream.update_thread(thread_id, {"metadata": {"title": generated_title.strip()}})
            return {"thread_id": thread_id, "title": generated_title.strip(), "metadata": metadata}
        return {"thread_id": thread_id, "title": "新对话"}

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
            # Approval does not grant access to the resumed Run's private input/config.
            return {"thread_id": thread_id, "run_id": result["result"]["run_id"]}
        thread = await self._load_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            write=True,
            action="comment",
        )
        next_payload = self._inject_project_scope(
            project_id=project_id, payload=payload
        )
        next_payload = await run_in_threadpool(
            self._inject_project_default_model,
            project_id=project_id,
            payload=next_payload,
        )
        next_payload = self._inject_thread_access_policy(thread=thread, payload=next_payload, actor=actor)
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
        next_payload.setdefault("multitask_strategy", "interrupt")
        command = {"method": "run.start", "params": next_payload}
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
        await self._load_thread(actor=actor, project_id=project_id, thread_id=thread_id, write=False)
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
            action="approve" if payload.get("method") == "input.respond" else "comment",
        )
        raw_payload = dict(payload)
        raw_params = ensure_dict(raw_payload.get("params"))
        if raw_payload.get("method") == "run.start":
            raw_params = await run_in_threadpool(
                self._inject_project_default_model,
                project_id=project_id,
                payload=raw_params,
            )
            raw_params = self._inject_thread_access_policy(thread=thread, payload=raw_params, actor=actor)
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
            if set(params) - {
                "interrupt_id",
                "response",
                "resume",
                "assistant_id",
                "responses",
                "namespace",
            }:
                raise BadRequestError(
                    code="resume_configuration_override",
                    message="Resume cannot change execution configuration",
                )
            resumes = params.get("resume")
            if resumes is None:
                if isinstance(params.get("responses"), list):
                    resumes = {
                        clean_str(item.get("interrupt_id") or item.get("id")): item.get("response")
                        for item in params["responses"]
                        if isinstance(item, dict)
                        and clean_str(item.get("interrupt_id") or item.get("id"))
                        and "response" in item
                    }
                else:
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
                validate_clarification_resumes(state, resumes)
            if parent is None:
                raise ConflictError(
                    code="run_request_missing",
                    message="Original authorized request is required",
                )
            source_run_id = previous.parent_run_id if previous else parent.run_id
            parent_run = await self._upstream.get_thread_run(thread_id, source_run_id)
            if previous is None:
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
                "version": ensure_dict(ensure_dict(parent_run).get("kwargs")).get("version", "v2"),
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
            action="delete",
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

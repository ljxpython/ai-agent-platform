from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Callable
from time import perf_counter
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID

from anyio import CancelScope
from fastapi import APIRouter, Body, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    model_validator,
)
from starlette.types import Receive, Send

from platform_api.adapters.langgraph import (
    LangGraphRuntimeGatewayUpstream,
)
from platform_api.adapters.langgraph.sdk_client import (
    project_execution_error,
    redact_execution_fields,
)
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotAuthenticatedError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.core.errors.payload import safe_validation_details
from platform_api.core.observability import log_event
from platform_api.core.security import (
    create_runtime_delegation_token,
    empty_runtime_context_hash,
)
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.runtime_gateway.application.diagnostics import RunDiagnostics
from platform_api.modules.runtime_gateway.application.run_control import (
    StopBody,
    StopRequest,
    StopRequestList,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
    _normalize_protocol_lifecycle_frame,
    _redact_runtime_private_fields,
)
from platform_api.modules.runtime_gateway.application.usage import RunUsage, ThreadUsage
from platform_api.modules.runtime_policies.application import (
    RuntimePolicyOverlayService,
)

router = APIRouter(prefix="/api/langgraph", tags=["runtime-gateway"])
logger = logging.getLogger(__name__)
event_logger = logging.getLogger("uvicorn.error")


class RuntimeStreamingResponse(StreamingResponse):
    def __init__(
        self,
        *args: Any,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[str, int], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._on_open = on_open
        self._on_close = on_close
        self._client_disconnected = False

    async def listen_for_disconnect(self, receive: Receive) -> None:
        await super().listen_for_disconnect(receive)
        self._client_disconnected = True

    async def stream_response(self, send: Send) -> None:
        opened_at: float | None = None
        close_reason = "unknown"

        async def tracked_send(message: Any) -> None:
            nonlocal opened_at
            await send(message)
            if message["type"] == "http.response.start":
                opened_at = perf_counter()
                if self._on_open:
                    self._on_open()

        try:
            await super().stream_response(tracked_send)
            close_reason = "closed"
        except OSError:
            close_reason = "client_disconnect"
            raise
        except asyncio.CancelledError:
            close_reason = (
                "client_disconnect" if self._client_disconnected else "unknown"
            )
            raise
        except Exception:
            close_reason = "upstream_error"
            raise
        finally:
            # Close suspended generators before GC can finalize nested streams concurrently.
            try:
                with CancelScope(shield=True):
                    await self.body_iterator.aclose()
            finally:
                if opened_at is not None and self._on_close:
                    self._on_close(
                        close_reason, max(0, int((perf_counter() - opened_at) * 1000))
                    )


class ThreadForkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checkpoint_id: str = Field(min_length=1, max_length=512)
    title: str | None = Field(default=None, max_length=200)


class ThreadShareBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID | None = None
    actions: list[Literal["read", "comment", "edit", "share", "delete"]] = Field(
        max_length=5
    )


class ThreadTakeoverBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["security_incident", "compliance", "user_support", "handover"]
    reason: str = Field(min_length=10, max_length=1000)
    reference: str = Field(min_length=3, max_length=200)
    duration_minutes: int = Field(default=15, ge=1, le=60, strict=True)


class SuggestionMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class SuggestionsRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[SuggestionMessageBody] = Field(min_length=1, max_length=6)
    n: int = Field(default=3, ge=1, le=5, strict=True)
    model_id: str | None = Field(default=None, min_length=1, max_length=256)


class SuggestionsResponseBody(BaseModel):
    suggestions: list[str]


class SuggestionsConfigResponse(BaseModel):
    enabled: bool
    max_suggestions: int


_SENSITIVE_EVENT_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "cookie",
    "id_token",
    "password",
    "refresh_token",
    "secret",
    "token",
    "x_runtime_run_read_authorization",
}
_MAX_SSE_FRAME_BYTES = 8 * 1024 * 1024
_SSE_BOUNDARY = re.compile(rb"\r?\n\r?\n")
_SSE_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class InvalidSseFrame(ValueError):
    pass


def _normalize_ack(value: Any) -> Any:
    if value is None:
        return {"ok": True}
    if isinstance(value, dict) and not value:
        return {"ok": True}
    return _redact_runtime_private_fields(value)


def _redact_event_value(value: Any, *, _project_private: bool = True) -> Any:
    if _project_private:
        value = _redact_runtime_private_fields(value)
    if isinstance(value, list):
        return [_redact_event_value(item, _project_private=False) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: "[REDACTED]"
        if key.lower().replace("-", "_") in _SENSITIVE_EVENT_KEYS
        else _redact_event_value(item, _project_private=False)
        for key, item in value.items()
    }


def _redact_sse_frame(frame: bytes, *, protocol: bool = True) -> bytes:
    frame, _ = _normalize_protocol_lifecycle_frame(frame)
    try:
        decoded = frame.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidSseFrame("invalid_utf8") from exc
    cleaned = decoded.rstrip("\r\n")
    lines = _SSE_LINE_BREAK.split(cleaned) if cleaned else []
    if lines and all(not line or line.startswith(":") for line in lines):
        return b": heartbeat"
    data_positions = [
        index for index, line in enumerate(lines) if line.startswith("data:")
    ]
    if not data_positions:
        return "\n".join(line for line in lines if not line.startswith(":")).encode()
    data = "\n".join(lines[index][5:].lstrip() for index in data_positions)
    try:
        payload = json.loads(data)
    except ValueError as exc:
        raise InvalidSseFrame("invalid_json") from exc
    event_name = next(
        (line[6:].strip() for line in lines if line.startswith("event:")), ""
    )
    typed = (
        isinstance(payload, dict)
        and isinstance(payload.get("method"), str)
        and isinstance(payload.get("params"), dict)
    )
    method = payload.get("method") if typed else event_name.partition("|")[0]
    event_data = payload["params"].get("data") if typed else payload
    if method in {"lifecycle", "tasks"}:
        event_data = redact_execution_fields(event_data)
    elif method == "error":
        event_data = project_execution_error(event_data)
    elif method == "tools" and isinstance(event_data, dict) and "error" in event_data:
        projected = project_execution_error(event_data["error"])
        if isinstance(projected, dict) and projected.get("code") in {
            "runtime_token_budget_exhausted",
            "runtime_token_budget_unverifiable",
        }:
            event_data = {**event_data, "error": projected}
    elif (
        method == "debug"
        and isinstance(event_data, dict)
        and event_data.get("type") == "task_result"
    ):
        event_data = {
            **event_data,
            "payload": redact_execution_fields(event_data.get("payload")),
        }
    if typed:
        payload["params"] = {
            **payload["params"],
            "data": event_data,
        }
    else:
        payload = event_data
    if protocol and (
        not isinstance(payload, dict)
        or not isinstance(payload.get("method"), str)
        or not isinstance(payload.get("params"), dict)
        or not isinstance(payload["params"].get("namespace", []), list)
        or any(
            not isinstance(item, str) for item in payload["params"].get("namespace", [])
        )
    ):
        raise InvalidSseFrame("invalid_protocol")
    encoded = json.dumps(
        _redact_event_value(payload), ensure_ascii=False, separators=(",", ":")
    )
    first_data_position = data_positions[0]
    redacted_lines = [
        f"data: {encoded}" if index == first_data_position else line
        for index, line in enumerate(lines)
        if not line.startswith(":")
        if index not in data_positions[1:]
    ]
    return "\n".join(redacted_lines).encode("utf-8")


_DEFAULT_SSE_HEARTBEAT_SECONDS = 15.0


async def _redact_protocol_event_stream(
    stream: AsyncIterator[bytes],
    *,
    protocol: bool = True,
    on_close: Callable[[str], None] | None = None,
    heartbeat_seconds: float = _DEFAULT_SSE_HEARTBEAT_SECONDS,
) -> AsyncIterator[bytes]:
    buffer = bytearray()
    queue: asyncio.Queue[bytes | None | Exception] = asyncio.Queue(maxsize=16)

    async def _read_upstream() -> None:
        try:
            async for chunk in stream:
                await queue.put(chunk)
            await queue.put(None)
        except Exception as exc:
            await queue.put(exc)

    reader_task = asyncio.create_task(_read_upstream())
    try:
        while True:
            try:
                item = (
                    await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
                    if heartbeat_seconds > 0
                    else await queue.get()
                )
            except TimeoutError:
                yield b": heartbeat\n\n"
                continue

            if item is None:
                break
            if isinstance(item, Exception):
                raise item

            chunk = item
            offset = 0
            while offset < len(chunk):
                size = min(len(chunk) - offset, _MAX_SSE_FRAME_BYTES + 4 - len(buffer))
                if size <= 0:
                    raise InvalidSseFrame("frame_too_large")
                search_from = max(0, len(buffer) - 3)
                buffer.extend(chunk[offset : offset + size])
                offset += size
                while boundary := _SSE_BOUNDARY.search(buffer, search_from):
                    if boundary.start() > _MAX_SSE_FRAME_BYTES:
                        raise InvalidSseFrame("frame_too_large")
                    frame = bytes(buffer[: boundary.start()]).replace(b"\r\n", b"\n")
                    del buffer[: boundary.end()]
                    search_from = 0
                    yield _redact_sse_frame(frame, protocol=protocol) + b"\n\n"
                if len(buffer) > _MAX_SSE_FRAME_BYTES + 3:
                    raise InvalidSseFrame("frame_too_large")
        if buffer:
            raise InvalidSseFrame("truncated_frame")
        if on_close:
            on_close("eof")
    except InvalidSseFrame as exc:
        logger.warning("runtime SSE stream closed: %s", exc)
        if on_close:
            on_close("frame_rejected")
    except Exception:
        if on_close:
            on_close("upstream_error")
        raise
    finally:
        reader_task.cancel()
        with CancelScope(shield=True):
            try:
                await reader_task
            except (asyncio.CancelledError, Exception):
                pass
        if hasattr(stream, "aclose"):
            await stream.aclose()


def _runtime_sse_response(
    request: Request,
    stream: AsyncIterator[bytes],
    *,
    thread_id: str,
    stream_kind: str,
    protocol: bool,
    run_id: str | None = None,
) -> RuntimeStreamingResponse:
    context = request.state.platform_context
    metadata = getattr(request.state, "audit_metadata", None)
    if run_id is None and isinstance(metadata, dict):
        candidate = metadata.get("run_id")
        run_id = candidate if isinstance(candidate, str) else None
    fields = {
        "request_id": context.request.request_id,
        "platform_trace_id": context.request.trace_id,
        "project_id": context.project.project_id,
        "thread_id": thread_id,
        "stream_kind": stream_kind,
        **({"run_id": run_id} if run_id else {}),
    }
    frame_reason: str | None = None

    def emit(event: str, **extra: Any) -> None:
        try:
            log_event(event_logger, event, **fields, **extra)
        except Exception:
            logger.exception("runtime stream correlation log failed")

    def note_frame_close(reason: str) -> None:
        nonlocal frame_reason
        frame_reason = reason

    request.state.audit_metadata = {
        **(metadata if isinstance(metadata, dict) else {}),
        "stream_kind": stream_kind,
        "thread_id": thread_id,
        **({"run_id": run_id} if run_id else {}),
    }
    return RuntimeStreamingResponse(
        _redact_protocol_event_stream(
            stream, protocol=protocol, on_close=note_frame_close
        ),
        media_type="text/event-stream",
        on_open=lambda: emit("runtime.stream.opened"),
        on_close=lambda fallback, duration: emit(
            "runtime.stream.closed",
            close_reason=frame_reason or fallback,
            duration_ms=duration,
        ),
    )


def _require_project_id(request: Request) -> str:
    project_id = getattr(request.state.platform_context.project, "project_id", None)
    normalized = project_id.strip() if isinstance(project_id, str) else ""
    if not normalized:
        raise BadRequestError(
            code="project_id_required",
            message="x-project-id header is required",
        )
    request.state.audit_project_id = normalized
    return normalized


def _delegation_operation(request: Request) -> str:
    """Keep read and run creation credentials separate at the gateway boundary."""
    path = request.url.path
    if "/terminals" in path:
        return "terminal-read" if request.method == "GET" else "terminal-write"
    if "/images/uploads" in path:
        return "image-upload"
    if "/images/content" in path:
        return "image-read"
    if "/files/uploads" in path:
        return "workspace-file-upload"
    if "/files/content" in path or "/workspace/" in path or path.endswith("/artifacts"):
        return "workspace-file-read"
    if path.endswith("/messages"):
        return "message-enqueue" if request.method == "POST" else "message-read"
    if path.endswith("/suggestions"):
        return "suggestions-generate"
    if path.endswith("/title/summarize"):
        return "title-generate"
    if path.endswith("/diagnostics"):
        return "diagnostics-read"
    if path.endswith("/usage"):
        return "usage-read"
    if request.method == "POST" and (path.endswith("/commands") or "/runs" in path):
        return "run-create"
    return "read"


def get_runtime_gateway_service(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> RuntimeGatewayService:
    settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    project_id = _require_project_id(request)
    context = request.state.platform_context
    correlation = {
        "request_id": context.request.request_id,
        "platform_trace_id": context.request.trace_id,
    }
    subject = actor.user_id or actor.subject
    if not subject:
        raise NotAuthenticatedError()
    project_roles = actor.project_role_set(project_id)
    object_governance = (
        actor.principal_type == "user"
        and actor.has_platform_role("platform_super_admin")
        and "thread_id" in request.path_params
    )
    if not project_roles and not object_governance:
        raise ForbiddenError(
            code="project_role_missing",
            message="Project role missing",
        )
    delegation_role = (
        "platform_super_admin"
        if actor.has_platform_role("platform_super_admin")
        else "platform_operator"
        if actor.has_platform_role("platform_operator")
        else project_roles[0]
    )
    try:
        policy = RuntimePolicyOverlayService(
            session_factory=session_factory,
            runtime_base_url=settings.langgraph_upstream_url,
        ).build_delegation_policy(project_id=project_id)
        delegation = create_runtime_delegation_token(
            subject=subject,
            credential_id=actor.credential_id
            if actor.principal_type == "service_account"
            else None,
            tenant_id=context.tenant.tenant_id or "__default",
            project_id=project_id,
            role=delegation_role,
            permissions=[],
            policy_version=str(policy["version"]),
            allowed_model_ids=policy["allowed_model_ids"],
            tool_overrides={},
            tool_policy_version="unscoped-read-v2",
            scope={
                "tenant_id": context.tenant.tenant_id or "__default",
                "project_id": project_id,
                "operation": "read",
            },
            context_hash=empty_runtime_context_hash(),
            settings=settings,
            **correlation,
        )
    except ValueError as exc:
        raise ServiceUnavailableError(
            code="runtime_delegation_not_configured",
            message="Runtime delegation is not configured",
        ) from exc

    forwarded_headers = {"authorization": f"Bearer {delegation}"}
    forwarded_headers["x-request-id"] = context.request.request_id

    def delegation_headers_factory(
        *,
        project_id: str,
        agent_key: str,
        thread_id: str | None,
        context_hash: str,
        operation: str = "run-create",
    ) -> dict[str, str]:
        restrictions = (
            RuntimePolicyOverlayService(
                session_factory=session_factory,
                runtime_base_url=settings.langgraph_upstream_url,
            ).resolve_tool_overrides(
                project_id=project_id, user_id=actor.user_id, graph_id=agent_key
            )
            if agent_key
            and operation
            not in {
                "thread-create",
                "thread-reconcile",
                "suggestions-generate",
                "title-generate",
                "diagnostics-read",
                "usage-read",
            }
            else {
                "tool_overrides": {},
                "tool_policy_version": "unscoped-thread-operation",
            }
        )
        try:
            scoped = create_runtime_delegation_token(
                subject=subject,
                credential_id=actor.credential_id
                if actor.principal_type == "service_account"
                else None,
                tenant_id=context.tenant.tenant_id or "__default",
                project_id=project_id,
                role=delegation_role,
                permissions=[],
                policy_version=str(policy["version"]),
                allowed_model_ids=policy["allowed_model_ids"],
                **restrictions,
                scope={
                    "tenant_id": context.tenant.tenant_id or "__default",
                    "project_id": project_id,
                    "assistant_id": agent_key or None,
                    "thread_id": thread_id,
                    "operation": operation,
                },
                context_hash=context_hash,
                settings=settings,
                **correlation,
            )
        except ValueError as exc:
            raise ServiceUnavailableError(
                code="runtime_delegation_not_configured",
                message="Runtime delegation is not configured",
            ) from exc
        headers = {"authorization": f"Bearer {scoped}"}
        if operation in {"message-enqueue", "message-read"}:
            headers["x-runtime-run-read-authorization"] = f"Bearer {delegation}"
        return headers

    upstream = LangGraphRuntimeGatewayUpstream(
        base_url=settings.langgraph_upstream_url,
        api_key=settings.langgraph_upstream_api_key,
        timeout_seconds=settings.langgraph_upstream_timeout_seconds,
        forwarded_headers=forwarded_headers,
    )

    def on_correlation(event: str, fields: dict[str, Any]) -> None:
        safe_fields = {key: value for key, value in fields.items() if value is not None}
        safe_fields.update(
            request_id=context.request.request_id,
            platform_trace_id=context.request.trace_id,
            project_id=project_id,
            correlation_version=1,
        )
        try:
            metadata = getattr(request.state, "audit_metadata", None)
            request.state.audit_metadata = {
                **(metadata if isinstance(metadata, dict) else {}),
                **safe_fields,
            }
        except Exception:
            logger.exception("runtime audit correlation merge failed")
        try:
            log_event(event_logger, event, **safe_fields)
        except Exception:
            logger.exception("runtime correlation log failed")

    return RuntimeGatewayService(
        session_factory=session_factory,
        upstream=upstream,
        runtime_base_url=settings.langgraph_upstream_url,
        delegation_headers_factory=delegation_headers_factory,
        on_correlation=on_correlation,
        runtime_model_config_secret=(
            settings.runtime_model_config_secret or settings.runtime_delegation_secret
        ),
        suggestions_enabled=settings.suggestions_enabled,
        suggestions_max=settings.suggestions_max,
        suggestions_timeout_seconds=settings.suggestions_timeout_seconds,
        title_timeout_seconds=getattr(settings, "title_timeout_seconds", 8.0),
        title_auto_enabled=lambda: settings.title_auto_enabled,
    )


@router.get("/info")
async def get_runtime_info(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.get_info(actor=actor, project_id=project_id)
    )


@router.get("/suggestions/config", response_model=SuggestionsConfigResponse)
async def get_suggestions_config(
    request: Request,
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> SuggestionsConfigResponse:
    _require_project_id(request)
    return SuggestionsConfigResponse(**service.suggestions_config())


@router.post("/graphs/search")
async def search_graphs(
    request: Request,
    payload: dict[str, Any] | None = Body(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.search_graphs(
            actor=actor,
            project_id=project_id,
            payload=payload,
        )
    )


@router.post("/graphs/count")
async def count_graphs(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.count_graphs(
            actor=actor,
            project_id=project_id,
            payload=payload,
        )
    )


@router.post("/threads")
async def create_thread(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.create_thread(
            actor=actor,
            project_id=project_id,
            payload=payload,
        )
    )


@router.post("/threads/search")
async def search_threads(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.search_threads(
            actor=actor,
            project_id=project_id,
            payload=payload,
        )
    )


@router.post("/threads/count")
async def count_threads(
    request: Request,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.count_threads(
            actor=actor,
            project_id=project_id,
            payload=payload,
        )
    )


RESERVED_THREAD_PATH_KEYWORDS = frozenset(
    {
        "state",
        "history",
        "runs",
        "search",
        "count",
        "reconcile",
        "copy",
    }
)


def _validate_thread_id(thread_id: str) -> None:
    if not thread_id or thread_id.strip().lower() in RESERVED_THREAD_PATH_KEYWORDS:
        raise NotFoundError(message=f"Thread '{thread_id}' not found")


@router.get("/threads/{thread_id}")
async def get_thread(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    _validate_thread_id(thread_id)
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.get_thread(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
        )
    )


@router.post("/threads/{thread_id}/reconcile")
async def reconcile_pending_thread(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    _validate_thread_id(thread_id)
    return _redact_runtime_private_fields(
        await service.reconcile_pending_thread(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
        )
    )


@router.delete("/threads/{thread_id}")
async def delete_thread(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    _validate_thread_id(thread_id)
    project_id = _require_project_id(request)
    result = await service.delete_thread(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
    )
    return _normalize_ack(result)


@router.put("/threads/{thread_id}/shares")
async def share_thread(
    request: Request,
    thread_id: str,
    payload: ThreadShareBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    return _redact_runtime_private_fields(
        await service.share_thread(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
            user_id=str(payload.user_id) if payload.user_id else None,
            actions=payload.actions,
        )
    )


@router.post("/threads/{thread_id}/takeover")
async def takeover_thread(
    request: Request,
    thread_id: str,
    payload: ThreadTakeoverBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    return _redact_runtime_private_fields(
        await service.takeover_thread(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
            **payload.model_dump(),
        )
    )


@router.delete("/threads/{thread_id}/takeover")
async def end_thread_takeover(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    return _redact_runtime_private_fields(
        await service.end_thread_takeover(
            actor=actor, project_id=_require_project_id(request), thread_id=thread_id
        )
    )


@router.post("/threads/{thread_id}/fork")
async def fork_thread(
    request: Request,
    thread_id: str,
    payload: ThreadForkBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    return _redact_runtime_private_fields(
        await service.fork_thread(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
            checkpoint_id=payload.checkpoint_id,
            title=payload.title,
        )
    )


@router.patch("/threads/{thread_id}/access-policy")
async def update_thread_access_policy(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    if (
        not isinstance(payload, dict)
        or set(payload) != {"access_policy"}
        or not isinstance(payload["access_policy"], str)
    ):
        raise BadRequestError(
            code="invalid_access_policy",
            message="access_policy must be review, workspace_write or full_access",
        )
    request.state.audit_metadata = {"access_policy": payload["access_policy"]}
    return _redact_runtime_private_fields(
        await service.update_thread_access_policy(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
            policy=payload["access_policy"],
        )
    )


@router.patch("/threads/{thread_id}")
async def update_thread(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    _validate_thread_id(thread_id)
    if not isinstance(payload, dict):
        raise BadRequestError(
            code="invalid_payload", message="payload must be a JSON object"
        )
    metadata_updates: dict[str, Any] = {}
    if "metadata" in payload and isinstance(payload["metadata"], dict):
        metadata_updates.update(payload["metadata"])
    for key in ("title", "preview"):
        if key in payload:
            metadata_updates[key] = payload[key]
    if not metadata_updates:
        raise BadRequestError(
            code="invalid_payload", message="No valid fields to update"
        )
    request.state.audit_metadata = {"updated_fields": list(metadata_updates.keys())}
    return _redact_runtime_private_fields(
        await service.update_thread(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
            metadata_updates=metadata_updates,
        )
    )


@router.post("/threads/{thread_id}/title/summarize")
async def summarize_thread_title(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    _validate_thread_id(thread_id)
    request.state.audit_metadata = {"action": "summarize_title"}
    return _redact_runtime_private_fields(
        await service.summarize_thread_title(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
            payload=payload,
        )
    )


@router.post("/threads/{thread_id}/messages", status_code=202)
async def enqueue_thread_message(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    allowed = {"client_message_id", "target_run_id", "content"}
    if set(payload) - allowed:
        raise BadRequestError(
            code="invalid_message_payload", message="Only message fields are accepted"
        )
    return _redact_runtime_private_fields(
        await service.enqueue_thread_message(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=payload,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    )


@router.post(
    "/threads/{thread_id}/suggestions",
    response_model=SuggestionsResponseBody,
)
async def generate_thread_suggestions(
    request: Request,
    thread_id: str,
    payload: SuggestionsRequestBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> SuggestionsResponseBody:
    project_id = _require_project_id(request)
    request.state.audit_metadata = {
        "action": "suggestions_generate",
        "suggestion_count": payload.n,
    }
    result = await service.generate_thread_suggestions(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        messages=[item.model_dump() for item in payload.messages],
        n=payload.n,
        model_id=payload.model_id,
    )
    return SuggestionsResponseBody.model_validate(result)


@router.get("/threads/{thread_id}/messages")
async def list_thread_messages(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    return _redact_runtime_private_fields(
        await service.list_thread_messages(
            actor=actor, project_id=_require_project_id(request), thread_id=thread_id
        )
    )


@router.put("/threads/{thread_id}/images/uploads/{sha256}")
async def upload_thread_image(
    request: Request,
    thread_id: str,
    sha256: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    content_type = request.headers.get("content-type", "")
    content_length_str = request.headers.get("content-length")
    try:
        content_length = (
            int(content_length_str) if content_length_str is not None else 0
        )
    except ValueError:
        content_length = 0

    ref = await service.upload_thread_image(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        sha256=sha256,
        content_type=content_type,
        content_length=content_length,
        body=request.stream(),
    )
    return _redact_runtime_private_fields(ref)


@router.get("/threads/{thread_id}/images/content")
async def read_thread_image(
    request: Request,
    thread_id: str,
    path: str = Query(..., description="Workspace image path"),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    project_id = _require_project_id(request)
    payload = await service.read_thread_image(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        path=path,
    )
    headers: dict[str, str] = {}
    if payload.content_length is not None:
        headers["content-length"] = str(payload.content_length)
    if payload.etag:
        headers["etag"] = payload.etag
    if payload.cache_control:
        headers["cache-control"] = payload.cache_control

    return RuntimeStreamingResponse(
        payload.body,
        media_type=payload.content_type,
        headers=headers,
    )


@router.put("/threads/{thread_id}/files/uploads/{sha256}")
async def upload_thread_file(
    request: Request,
    thread_id: str,
    sha256: str,
    file_name: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    content_type = request.headers.get("content-type", "")
    content_length_str = request.headers.get("content-length")
    try:
        content_length = (
            int(content_length_str) if content_length_str is not None else 0
        )
    except ValueError:
        content_length = 0

    ref = await service.upload_thread_file(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        sha256=sha256,
        content_type=content_type,
        content_length=content_length,
        body=request.stream(),
        file_name=file_name,
    )
    return _redact_runtime_private_fields(ref)


@router.get("/threads/{thread_id}/capabilities")
async def get_thread_capabilities(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    result = await service.get_thread_capabilities(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
    )
    return _redact_runtime_private_fields(result)


class SkillUploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package_base64: str = Field(min_length=1, max_length=1398104)


class SkillUpdateBody(SkillUploadBody):
    expected_revision: str = Field(min_length=1, max_length=64)


class SkillToggleBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool
    expected_revision: str = Field(min_length=1, max_length=64)


@router.get("/dear/skills")
async def list_dear_skills(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await service.dear_skills(
        actor=actor, project_id=_require_project_id(request), method="GET"
    )


@router.post("/dear/skills/custom", status_code=201)
async def create_dear_skill(
    request: Request,
    payload: SkillUploadBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await service.dear_skills(
        actor=actor,
        project_id=_require_project_id(request),
        method="POST",
        suffix="/custom",
        payload=payload.model_dump(),
    )


@router.put("/dear/skills/custom/{slug}")
async def update_dear_skill(
    request: Request,
    slug: str,
    payload: SkillUpdateBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await service.dear_skills(
        actor=actor,
        project_id=_require_project_id(request),
        method="PUT",
        suffix="/custom/" + quote(slug, safe=""),
        payload=payload.model_dump(),
    )


@router.patch("/dear/skills/custom/{slug}")
async def toggle_dear_skill(
    request: Request,
    slug: str,
    payload: SkillToggleBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await service.dear_skills(
        actor=actor,
        project_id=_require_project_id(request),
        method="PATCH",
        suffix="/custom/" + quote(slug, safe=""),
        payload=payload.model_dump(),
    )


@router.delete("/dear/skills/custom/{slug}", status_code=204)
async def delete_dear_skill(
    request: Request,
    slug: str,
    expected_revision: str = Query(min_length=1, max_length=64),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    await service.dear_skills(
        actor=actor,
        project_id=_require_project_id(request),
        method="DELETE",
        suffix="/custom/" + quote(slug, safe=""),
        params={"expected_revision": expected_revision},
    )
    return Response(status_code=204)


@router.get("/dear/skills/{source}/{slug}")
async def detail_dear_skill(
    request: Request,
    source: Literal["public", "custom"],
    slug: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await service.dear_skills(
        actor=actor,
        project_id=_require_project_id(request),
        method="GET",
        suffix=f"/{source}/" + quote(slug, safe=""),
    )


@router.get("/dear/skills/{source}/{slug}/content")
async def content_dear_skill(
    request: Request,
    source: Literal["public", "custom"],
    slug: str,
    path: str = Query(min_length=1, max_length=1024),
    revision: str = Query(min_length=1, max_length=64),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await service.dear_skills(
        actor=actor,
        project_id=_require_project_id(request),
        method="GET",
        suffix=f"/{source}/" + quote(slug, safe="") + "/content",
        params={"path": path, "revision": revision},
    )


class MemoryFactBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1000)
    category: Literal["preference", "fact"] = "preference"
    expires_at: AwareDatetime | None = None


class MemoryCommandBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "save", "delete", "clear", "accept", "reject", "settings", "restore"
    ]
    expected_revision: int = Field(ge=0, strict=True)
    fact_id: str | None = Field(default=None, max_length=64)
    replace_fact_id: str | None = Field(default=None, max_length=64)
    fact: MemoryFactBody | None = None
    automatic_candidates: StrictBool | None = None
    facts: list[MemoryFactBody] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_action_fields(self):
        provided = self.model_fields_set - {"action", "expected_revision"}
        allowed = {
            "save": {"fact", "fact_id"},
            "delete": {"fact_id"},
            "accept": {"fact_id", "replace_fact_id"},
            "reject": {"fact_id"},
            "settings": {"automatic_candidates"},
            "restore": {"facts"},
            "clear": set(),
        }[self.action]
        required = {
            "save": {"fact"},
            "delete": {"fact_id"},
            "accept": {"fact_id"},
            "reject": {"fact_id"},
            "settings": {"automatic_candidates"},
            "restore": {"facts"},
            "clear": set(),
        }[self.action]
        if (
            provided - allowed
            or required - provided
            or any(getattr(self, key) is None for key in required)
        ):
            raise ValueError("invalid_memory_command_fields")
        if self.action == "restore" and not self.facts:
            raise ValueError("memory_restore_empty")
        return self


class MemoryFactView(MemoryFactBody):
    id: str
    origin: Literal["user", "confirmed", "inferred"]
    revision: int
    created_at: str
    updated_at: str
    source_kind: Literal["management", "user_message", "tool", "legacy"]
    source_thread_id: str | None
    source_message_id: str | None
    source_call_id: str | None
    quote: str | None


class MemoryDocumentView(BaseModel):
    schema_version: int
    revision: int
    epoch: int
    automatic_candidates: bool
    facts: list[MemoryFactView]
    candidates: list[MemoryFactView]


class MemoryExtractionView(BaseModel):
    status: Literal[
        "never",
        "running",
        "succeeded",
        "no_candidates",
        "failed",
        "skipped",
        "interrupted",
    ]
    updated_at: str | None
    source_thread_id: str | None
    candidate_count: int
    error_code: str | None
    pause_reason: str | None


class MemoryMutationView(BaseModel):
    action: str
    changed: bool
    added: int
    updated: int
    removed: int
    skipped: int


class MemoryView(BaseModel):
    status: Literal["ready", "disabled"]
    scope: dict[str, str]
    capabilities: dict[str, bool]
    limits: dict[str, int]
    document: MemoryDocumentView | None
    counts: dict[str, int] | None
    extraction: MemoryExtractionView | None
    mutation: MemoryMutationView | None


@router.get("/dear/memory", response_model=MemoryView)
async def read_dear_memory(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await service.dear_memory(
        actor=actor, project_id=_require_project_id(request)
    )


@router.post(
    "/dear/memory",
    response_model=MemoryView,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": MemoryCommandBody.model_json_schema()}
            },
        }
    },
)
async def write_dear_memory(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 1500000:
            raise PlatformApiError(
                code="memory_payload_too_large",
                status_code=413,
                message="Memory payload too large",
            )
        chunks.append(chunk)
    body = b"".join(chunks)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BadRequestError(
            code="invalid_memory_command", message="Invalid memory JSON"
        ) from exc
    try:
        command = MemoryCommandBody.model_validate(payload)
    except ValidationError as exc:
        details = safe_validation_details(exc.errors(include_input=False))
        raise PlatformApiError(
            code="validation_failed",
            status_code=422,
            message="Validation failed",
            details=details,
        ) from exc
    action = payload.get("action") if isinstance(payload, dict) else None
    if isinstance(action, str) and action in {
        "save",
        "delete",
        "clear",
        "accept",
        "reject",
        "settings",
        "restore",
    }:
        request.state.audit_metadata = {"memory_action": action}
    try:
        return await service.dear_memory(
            actor=actor,
            project_id=_require_project_id(request),
            payload=command.model_dump(mode="json", exclude_unset=True),
        )
    except PlatformApiError as exc:
        if exc.status_code == 422:
            raise PlatformApiError(
                code="validation_failed",
                status_code=422,
                message="Validation failed",
                details=exc.details,
            ) from exc
        raise


@router.get("/threads/{thread_id}/dear/{resource}")
async def read_dear_governance(
    request: Request,
    thread_id: str,
    resource: str,
    query: str = Query(default="", max_length=500),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    result = await service.dear_governance(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        resource=resource,
        query=query,
    )
    return _redact_runtime_private_fields(result)


@router.post("/threads/{thread_id}/dear/{resource}")
async def write_dear_governance(
    request: Request,
    thread_id: str,
    resource: str,
    payload: dict = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    if len(json.dumps(payload).encode()) > 1500000:
        raise BadRequestError(
            code="dear_payload_too_large", message="Dear payload too large"
        )
    result = await service.dear_governance(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        resource=resource,
        payload=payload,
    )
    return _redact_runtime_private_fields(result)


@router.get("/threads/{thread_id}/files/content")
async def read_thread_file(
    request: Request,
    thread_id: str,
    path: str = Query(..., description="Workspace file path"),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    project_id = _require_project_id(request)
    payload = await service.read_thread_file(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        path=path,
    )
    headers: dict[str, str] = {}
    if payload.content_length is not None:
        headers["content-length"] = str(payload.content_length)
    if payload.etag:
        headers["etag"] = payload.etag
    if payload.cache_control:
        headers["cache-control"] = payload.cache_control
    headers["content-disposition"] = f'attachment; filename="{path.rsplit("/", 1)[-1]}"'
    headers["x-content-type-options"] = "nosniff"
    headers["content-security-policy"] = "sandbox; default-src 'none'"
    media_type = payload.content_type
    if media_type in (
        "text/html",
        "text/css",
        "text/javascript",
        "text/plain",
        "text/markdown",
        "text/x-bibtex",
        "text/csv",
        "application/json",
    ):
        media_type = f"{media_type}; charset=utf-8"

    return RuntimeStreamingResponse(
        payload.body,
        media_type=media_type,
        headers=headers,
    )


class TerminalCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    acknowledge_execution: Literal[True]
    rows: int = Field(default=24, ge=2, le=200)
    cols: int = Field(default=80, ge=2, le=400)


class TerminalInputBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_base64: str = Field(min_length=1, max_length=5464)
    sequence: int = Field(ge=0)


class TerminalResizeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: int = Field(ge=2, le=200)
    cols: int = Field(ge=2, le=400)


async def _terminal_response(
    request,
    thread_id,
    actor,
    service,
    action,
    *,
    terminal_id=None,
    payload=None,
    offset=0,
):
    result = await service.thread_terminal(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        action=action,
        terminal_id=terminal_id,
        payload=payload,
        offset=offset,
    )
    return JSONResponse(
        _redact_runtime_private_fields(result),
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/threads/{thread_id}/terminals")
async def create_terminal(
    request: Request,
    thread_id: str,
    payload: TerminalCreateBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _terminal_response(
        request,
        thread_id,
        actor,
        service,
        "create",
        payload=payload.model_dump(mode="json"),
    )


@router.get("/threads/{thread_id}/terminals")
async def list_terminals(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _terminal_response(request, thread_id, actor, service, "list")


@router.get("/threads/{thread_id}/terminals/{terminal_id}/output")
async def terminal_output(
    request: Request,
    thread_id: str,
    terminal_id: str,
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _terminal_response(
        request,
        thread_id,
        actor,
        service,
        "output",
        terminal_id=terminal_id,
        offset=offset,
    )


@router.post("/threads/{thread_id}/terminals/{terminal_id}/input")
async def terminal_input(
    request: Request,
    thread_id: str,
    terminal_id: str,
    payload: TerminalInputBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _terminal_response(
        request,
        thread_id,
        actor,
        service,
        "input",
        terminal_id=terminal_id,
        payload=payload.model_dump(),
    )


@router.post("/threads/{thread_id}/terminals/{terminal_id}/resize")
async def terminal_resize(
    request: Request,
    thread_id: str,
    terminal_id: str,
    payload: TerminalResizeBody,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _terminal_response(
        request,
        thread_id,
        actor,
        service,
        "resize",
        terminal_id=terminal_id,
        payload=payload.model_dump(),
    )


@router.delete("/threads/{thread_id}/terminals/{terminal_id}")
async def close_terminal(
    request: Request,
    thread_id: str,
    terminal_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _terminal_response(
        request, thread_id, actor, service, "close", terminal_id=terminal_id
    )


@router.get("/threads/{thread_id}/workspace/tree")
async def workspace_tree(
    request: Request,
    thread_id: str,
    path: str = Query(default="/workspace", max_length=4096),
    cursor: str | None = Query(default=None, max_length=8192),
    limit: int = Query(default=100, ge=1, le=200),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    result = await service.thread_workspace(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        resource="workspace/tree",
        path=path,
        cursor=cursor,
        limit=limit,
    )
    return JSONResponse(
        _redact_runtime_private_fields(result),
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/threads/{thread_id}/artifacts")
async def thread_artifacts(
    request: Request,
    thread_id: str,
    cursor: str | None = Query(default=None, max_length=8192),
    limit: int = Query(default=100, ge=1, le=200),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    result = await service.thread_workspace(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        resource="artifacts",
        cursor=cursor,
        limit=limit,
    )
    return JSONResponse(
        _redact_runtime_private_fields(result),
        headers={"Cache-Control": "private, no-store"},
    )


async def _workspace_response(request, thread_id, path, actor, service, *, preview):
    payload = await service.thread_workspace(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        resource="workspace/preview" if preview else "workspace/content",
        path=path,
    )
    headers = {
        "cache-control": "private, no-store",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "content-security-policy": "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'",
        "content-disposition": "inline"
        if preview
        else "attachment; filename*=UTF-8''" + quote(path.rsplit("/", 1)[-1], safe=""),
    }
    if payload.content_length is not None:
        headers["content-length"] = str(payload.content_length)
    if payload.etag:
        headers["etag"] = payload.etag
    return RuntimeStreamingResponse(
        payload.body, media_type=payload.content_type, headers=headers
    )


@router.get("/threads/{thread_id}/workspace/content")
async def workspace_content(
    request: Request,
    thread_id: str,
    path: str = Query(..., max_length=4096),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _workspace_response(
        request, thread_id, path, actor, service, preview=False
    )


@router.get("/threads/{thread_id}/workspace/preview")
async def workspace_preview(
    request: Request,
    thread_id: str,
    path: str = Query(..., max_length=4096),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    return await _workspace_response(
        request, thread_id, path, actor, service, preview=True
    )


@router.get("/threads/{thread_id}/workspace/zip")
async def workspace_zip(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    payload = await service.thread_workspace(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        resource="workspace/zip",
    )
    headers = {
        "cache-control": "private, no-store",
        "x-content-type-options": "nosniff",
        "content-disposition": payload.content_disposition
        or f"attachment; filename*=UTF-8''workspace-{quote(thread_id[:8], safe='')}.zip",
    }
    if payload.content_length is not None:
        headers["content-length"] = str(payload.content_length)
    if payload.etag:
        headers["etag"] = payload.etag
    return RuntimeStreamingResponse(
        payload.body, media_type=payload.content_type, headers=headers
    )


@router.get("/threads/{thread_id}/state")
async def get_thread_state(
    request: Request,
    thread_id: str,
    subgraphs: bool | None = Query(default=None),
    checkpoint_id: str | None = Query(default=None),
    checkpoint_ns: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    params: dict[str, Any] = {}
    if subgraphs is not None:
        params["subgraphs"] = subgraphs
    if checkpoint_id is not None:
        params["checkpoint_id"] = checkpoint_id
    if checkpoint_ns is not None:
        params["checkpoint_ns"] = checkpoint_ns
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.get_thread_state(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            params=params,
        )
    )


@router.post("/threads/{thread_id}/state/checkpoint")
async def get_thread_state_at_checkpoint_post(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(default_factory=dict),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.get_thread_state(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            params=payload,
        )
    )


@router.post("/threads/{thread_id}/state")
async def update_thread_state(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.update_thread_state(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=payload,
        )
    )


@router.post("/threads/{thread_id}/history")
async def get_thread_history(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.get_thread_history(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=payload,
        )
    )


@router.post("/threads/{thread_id}/runs")
async def create_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.create_thread_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=payload,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    )


@router.post("/threads/{thread_id}/runs/queue")
async def manage_thread_run_queue(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    return _redact_runtime_private_fields(
        await service.manage_thread_run_queue(
            actor=actor,
            project_id=_require_project_id(request),
            thread_id=thread_id,
            payload=payload,
        )
    )


@router.post("/threads/{thread_id}/runs/stream")
async def stream_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    project_id = _require_project_id(request)
    stream = await service.stream_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )
    return _runtime_sse_response(
        request, stream, thread_id=thread_id, stream_kind="run", protocol=False
    )


@router.post("/threads/{thread_id}/commands")
async def send_thread_command(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.send_thread_command(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            payload=payload,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    )


@router.post("/threads/{thread_id}/stream/events")
async def stream_thread_events(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    project_id = _require_project_id(request)
    stream = await service.stream_thread_events(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
    )
    return _runtime_sse_response(
        request, stream, thread_id=thread_id, stream_kind="thread", protocol=True
    )


@router.get("/threads/{thread_id}/runs/{run_id}")
async def get_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.get_thread_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
        )
    )


@router.get(
    "/threads/{thread_id}/runs/{run_id}/diagnostics", response_model=RunDiagnostics
)
async def get_thread_run_diagnostics(
    request: Request,
    thread_id: UUID,
    run_id: UUID,
    response: Response,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    response.headers["Cache-Control"] = "no-store"
    return await service.get_thread_run_diagnostics(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=str(thread_id),
        run_id=str(run_id),
        request_id=request.state.platform_context.request.request_id,
    )


@router.get("/threads/{thread_id}/runs/{run_id}/usage", response_model=RunUsage)
async def get_thread_run_usage(
    request: Request,
    thread_id: str,
    run_id: str,
    response: Response,
    limit: str = "50",
    cursor: str | None = None,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    response.headers["Cache-Control"] = "no-store"
    return await service.get_thread_run_usage(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        run_id=run_id,
        request_id=request.state.platform_context.request.request_id,
        limit=limit,
        cursor=cursor,
    )


@router.get("/threads/{thread_id}/usage", response_model=ThreadUsage)
async def get_thread_usage(
    request: Request,
    thread_id: str,
    response: Response,
    created_from: str | None = None,
    created_to: str | None = None,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    response.headers["Cache-Control"] = "no-store"
    return await service.get_thread_usage(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=thread_id,
        request_id=request.state.platform_context.request.request_id,
        created_from=created_from,
        created_to=created_to,
    )


@router.get("/threads/{thread_id}/runs")
async def list_thread_runs(
    request: Request,
    thread_id: str,
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
    status: str | None = Query(default=None),
    select: list[str] | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if status is not None:
        params["status"] = status
    if select is not None:
        params["select"] = select
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.list_thread_runs(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            params=params,
        )
    )


@router.get("/threads/{thread_id}/runs/{run_id}/join")
async def join_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    return _redact_runtime_private_fields(
        await service.join_thread_run(
            actor=actor,
            project_id=project_id,
            thread_id=thread_id,
            run_id=run_id,
        )
    )


@router.get("/threads/{thread_id}/runs/{run_id}/stream")
async def join_thread_run_stream(
    request: Request,
    thread_id: str,
    run_id: str,
    cancel_on_disconnect: bool | None = Query(default=None),
    stream_mode: str | None = Query(default=None),
    last_event_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> StreamingResponse:
    params: dict[str, Any] = {}
    if cancel_on_disconnect is not None:
        params["cancel_on_disconnect"] = cancel_on_disconnect
    if stream_mode is not None:
        params["stream_mode"] = stream_mode
    if last_event_id is not None:
        params["last_event_id"] = last_event_id
    project_id = _require_project_id(request)
    stream = await service.join_thread_run_stream(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
        params=params,
    )
    return _runtime_sse_response(
        request,
        stream,
        thread_id=thread_id,
        run_id=run_id,
        stream_kind="run",
        protocol=False,
    )


@router.post("/threads/{thread_id}/cancel", status_code=202, response_model=StopRequest)
async def cancel_thread(
    request: Request,
    thread_id: UUID,
    payload: StopBody,
    response: Response,
    idempotency_key: str = Header(min_length=1, max_length=128),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    _stop_query(request, set())
    response.headers["Cache-Control"] = "no-store"
    return await service.thread_stop_action(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=str(thread_id),
        key=idempotency_key,
        request_id=request.state.platform_context.request.request_id,
    )


@router.get("/threads/{thread_id}/stop-requests/{stop_id}", response_model=StopRequest)
async def get_stop_request(
    request: Request,
    thread_id: UUID,
    stop_id: UUID,
    response: Response,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    _stop_query(request, set())
    response.headers["Cache-Control"] = "no-store"
    return await service.thread_stop_action(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=str(thread_id),
        stop_id=str(stop_id),
        request_id=request.state.platform_context.request.request_id,
    )


@router.get("/threads/{thread_id}/stop-requests", response_model=StopRequestList)
async def list_stop_requests(
    request: Request,
    thread_id: UUID,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=256),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
):
    _stop_query(request, {"limit", "cursor"})
    response.headers["Cache-Control"] = "no-store"
    return await service.thread_stop_action(
        actor=actor,
        project_id=_require_project_id(request),
        thread_id=str(thread_id),
        params={"limit": limit, **({"cursor": cursor} if cursor else {})},
        request_id=request.state.platform_context.request.request_id,
    )


def _stop_query(request, allowed):
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise PlatformApiError(
            code="invalid_stop_query", status_code=422, message="Invalid stop query"
        )


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    payload: dict[str, Any] | None = Body(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    project_id = _require_project_id(request)
    result = await service.cancel_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
        payload=payload,
    )
    return _normalize_ack(result)

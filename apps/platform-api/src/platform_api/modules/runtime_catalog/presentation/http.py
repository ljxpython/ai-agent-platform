from __future__ import annotations

import hashlib
import hmac
import json
import time

from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.identity.actors import load_user_actor

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import sessionmaker

from platform_api.adapters.langgraph import build_forward_headers
from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import BadRequestError, ForbiddenError
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.runtime_catalog.application import RuntimeCatalogService
from platform_api.modules.runtime_catalog.bootstrap import build_runtime_catalog_service
from platform_api.modules.runtime_catalog.domain import (
    RuntimeCatalogRefreshResult,
    RuntimeGraphCatalogList,
    RuntimeModelCatalogItem,
    RuntimeModelCatalogList,
    RuntimeModelCreate,
    RuntimeModelUpdate,
    RuntimeToolCatalogList,
)

router = APIRouter(prefix="/api/runtime", tags=["runtime-catalog"])


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


def _optional_project_id(request: Request) -> str:
    platform_context = getattr(request.state, "platform_context", None)
    project = getattr(platform_context, "project", None)
    project_id = getattr(project, "project_id", None)
    normalized = project_id.strip() if isinstance(project_id, str) else ""
    if normalized:
        request.state.audit_project_id = normalized
    return normalized


def get_runtime_catalog_service(request: Request) -> RuntimeCatalogService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    platform_context = getattr(request.state, "platform_context", None)
    tenant = getattr(platform_context, "tenant", None)
    return build_runtime_catalog_service(
        settings=settings,
        session_factory=session_factory,
        forwarded_headers=build_forward_headers(
            request.headers,
            request_id=getattr(request.state, "request_id", None),
        ),
        tenant_id=getattr(tenant, "tenant_id", None) or "__default",
    )


@router.get("/internal/model-config")
def get_internal_runtime_model_config(
    request: Request,
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> dict[str, str]:
    """Serve a model connection only to Runtime using a short-lived opaque reference."""
    reference = request.headers.get("x-runtime-model-ref", "").strip()
    project_id = request.headers.get("x-project-id", "").strip()
    if not reference or not project_id:
        raise BadRequestError(
            code="runtime_model_reference_required",
            message="Runtime model reference and project scope are required",
        )
    # Only a currently authenticated Runtime may redeem a reference after queue delay.
    timestamp = request.headers.get("x-runtime-model-time", "")
    signature = request.headers.get("x-runtime-model-signature", "")
    secret = request.app.state.settings.runtime_delegation_secret
    trusted_runtime = False
    if timestamp or signature:
        try:
            timely = abs(time.time() - int(timestamp)) <= 60
        except ValueError:
            timely = False
        expected = hmac.new(secret.encode(), f"{timestamp}\n{project_id}\n{reference}".encode(), hashlib.sha256).hexdigest()
        if not secret or not timely or not hmac.compare_digest(signature, expected):
            from platform_api.core.errors import ForbiddenError
            raise ForbiddenError(code="runtime_model_signature_invalid", message="Invalid Runtime signature")
        trusted_runtime = True
    return service.resolve_model_connection(
        reference=reference, project_id=project_id, trusted_runtime=trusted_runtime)



@router.get("/internal/memory-authorization")
def authorize_runtime_memory(request: Request, project_id: str, thread_id: str, user_id: str) -> dict:
    stamp = request.headers.get("x-runtime-memory-timestamp", "")
    signature = request.headers.get("x-runtime-memory-signature", "")
    secret = request.app.state.settings.runtime_delegation_secret
    try:
        timely = abs(time.time() - int(stamp)) <= 30
    except ValueError:
        timely = False
    message = f"{stamp}\n{project_id}\n{thread_id}\n{user_id}"
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not secret or not timely or not hmac.compare_digest(signature, expected):
        raise ForbiddenError(code="runtime_memory_signature_invalid", message="Invalid Runtime signature")
    factory = request.app.state.db_session_factory
    access = thread_access.get(factory, thread_id)
    return {"allowed": thread_access.personal_memory_allowed(access, project_id=project_id, user_id=user_id)}


@router.post("/internal/thread-authorization")
def authorize_runtime_threads(request: Request, payload: dict) -> dict:
    """Batch ACL lookup for Runtime; the platform database remains authoritative."""
    stamp = request.headers.get("x-runtime-acl-timestamp", "")
    signature = request.headers.get("x-runtime-acl-signature", "")
    secret = request.app.state.settings.runtime_delegation_secret
    try:
        timely = abs(time.time() - int(stamp)) <= 30
    except (TypeError, ValueError):
        timely = False
    if not isinstance(payload, dict):
        raise ForbiddenError(code="runtime_acl_invalid_request", message="Invalid ACL request")
    action = payload.get("action")
    project_id = payload.get("project_id")
    user_id = payload.get("user_id")
    targets = payload.get("thread_ids")
    if (
        action not in {"create", "read", "comment", "edit", "share", "delete", "approve", "terminal", "full_access"}
        or not isinstance(project_id, str) or not project_id
        or not isinstance(user_id, str) or not user_id
        or not isinstance(targets, list) or not 0 < len(targets) <= 100
        or any(not isinstance(item, str) or not item for item in targets)
    ):
        raise ForbiddenError(code="runtime_acl_invalid_request", message="Invalid ACL request")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        secret.encode(), f"{stamp}\nthread-authorization\n{canonical}".encode(), hashlib.sha256
    ).hexdigest()
    if not secret or not timely or not hmac.compare_digest(signature, expected):
        raise ForbiddenError(code="runtime_acl_signature_invalid", message="Invalid Runtime signature")
    factory = request.app.state.db_session_factory
    actor = load_user_actor(
        session_factory=request.app.state.db_session_factory,
        user_id=user_id,
        project_id=project_id,
    )
    if actor is None:
        return {"allowed_thread_ids": []}
    allowed = []
    for thread_id in targets:
        if action == "create":
            permitted = thread_access.pending_owner(factory, thread_id=thread_id,
                project_id=project_id, user_id=user_id) and actor.principal_type == "user"
        else:
            permitted = thread_access.allowed(actor, project_id, thread_access.get(factory, thread_id), action)
        if permitted:
            allowed.append(thread_id)
    return {"allowed_thread_ids": allowed}


@router.get("/internal/message-authorization")
def authorize_runtime_message(request: Request, thread_id: str, run_id: str,
                              service: RuntimeCatalogService = Depends(get_runtime_catalog_service)) -> dict:
    return service.authorize_message(request.headers.get("x-runtime-message-ref", ""),
                                     thread_id=thread_id, run_id=run_id)


@router.get("/models", response_model=RuntimeModelCatalogList)
def list_runtime_models(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeModelCatalogList:
    project_id = _require_project_id(request)
    return service.list_models(actor=actor, project_id=project_id)


@router.get("/platform-models", response_model=RuntimeModelCatalogList)
def list_platform_models(
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeModelCatalogList:
    return service.list_models(actor=actor, project_id="", platform=True)




@router.post("/models", response_model=RuntimeModelCatalogItem, status_code=201)
def create_runtime_model(
    request: Request,
    payload: RuntimeModelCreate,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeModelCatalogItem:
    project_id = _optional_project_id(request)
    return service.create_model(actor=actor, project_id=project_id, payload=payload)


@router.patch("/models/{model_id}", response_model=RuntimeModelCatalogItem)
def update_runtime_model(
    model_id: str,
    request: Request,
    payload: RuntimeModelUpdate,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeModelCatalogItem:
    project_id = _optional_project_id(request)
    return service.update_model(
        actor=actor,
        project_id=project_id,
        model_id=model_id,
        payload=payload,
    )


@router.delete("/models/{model_id}", status_code=204)
def delete_runtime_model(
    model_id: str,
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> None:
    project_id = _optional_project_id(request)
    service.delete_model(
        actor=actor,
        project_id=project_id,
        model_id=model_id,
    )


@router.get("/tools", response_model=RuntimeToolCatalogList)
def list_runtime_tools(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeToolCatalogList:
    project_id = _require_project_id(request)
    return service.list_tools(actor=actor, project_id=project_id)


@router.post("/tools/refresh", response_model=RuntimeCatalogRefreshResult)
async def refresh_runtime_tools(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeCatalogRefreshResult:
    project_id = _require_project_id(request)
    return await service.refresh_tools(actor=actor, project_id=project_id)


@router.get("/graphs", response_model=RuntimeGraphCatalogList)
def list_runtime_graphs(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeGraphCatalogList:
    project_id = _require_project_id(request)
    return service.list_graphs(actor=actor, project_id=project_id)


@router.post("/graphs/refresh", response_model=RuntimeCatalogRefreshResult)
async def refresh_runtime_graphs(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> RuntimeCatalogRefreshResult:
    project_id = _require_project_id(request)
    return await service.refresh_graphs(actor=actor, project_id=project_id)

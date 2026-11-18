"""Public RBAC CRUD and separately signed Runtime callbacks."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from platform_api.core.errors import BadRequestError, ForbiddenError
from platform_api.entrypoints.http.dependencies import get_platform_request_context
from platform_api.modules.runtime_policies.application.budget_notifications import (
    receive,
)
from platform_api.modules.runtime_policies.application.budget_transport import (
    decode,
    verify,
)
from platform_api.modules.runtime_policies.application.budgets import BudgetService
from platform_api.modules.runtime_policies.domain.budgets import BudgetInput
from platform_api.modules.runtime_policies.infra.sqlalchemy.budgets import (
    BudgetNonceRecord,
)

router = APIRouter(tags=["gateway-budgets"])


def get_service(request: Request):
    return BudgetService(
        request.app.state.db_session_factory, request.app.state.settings
    )


@router.get("/api/policies/budgets")
def list_budgets(
    project_id: UUID | None = None,
    context=Depends(get_platform_request_context),
    service=Depends(get_service),
):
    return service.list(context, str(project_id) if project_id else None)


@router.post("/api/policies/budgets", status_code=201)
def create_budget(
    body: BudgetInput,
    request: Request,
    context=Depends(get_platform_request_context),
    service=Depends(get_service),
):
    request.state.audit_metadata = body.model_dump(mode="json")
    return service.save(context, body)


@router.put("/api/policies/budgets/{policy_id}")
def update_budget(
    policy_id: UUID,
    body: BudgetInput,
    request: Request,
    context=Depends(get_platform_request_context),
    service=Depends(get_service),
):
    request.state.audit_metadata = body.model_dump(mode="json")
    return service.save(context, body, policy_id)


@router.delete("/api/policies/budgets/{policy_id}")
def delete_budget(
    policy_id: UUID,
    context=Depends(get_platform_request_context),
    service=Depends(get_service),
):
    return service.save(context, None, policy_id, delete=True)


async def internal(request, service, operation):
    raw = bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw) > 262144:
            raise BadRequestError(
                code="budget_request_too_large", message="Budget request too large"
            )
    try:
        if request.query_params:
            raise ValueError("unexpected_query")
        nonce = verify(
            service.settings.runtime_delegation_secret,
            request.url.path,
            request.headers,
            bytes(raw),
        )
        payload = decode(raw)
        if not isinstance(payload, dict):
            raise ValueError("object_required")
    except (ValueError, TypeError):
        raise ForbiddenError(
            code="budget_signature_invalid", message="Invalid budget signature"
        ) from None

    def apply():
        with service.factory.begin() as session:
            session.add(BudgetNonceRecord(nonce=nonce, created_at=datetime.now(UTC)))
            session.flush()
            if operation == "resolve":
                if set(payload) != {"tenant_id", "project_id"}:
                    raise BadRequestError(
                        code="budget_request_invalid", message="Invalid budget query"
                    )
                tenant = service._tenant(session, payload["tenant_id"])
                from platform_api.modules.projects.models import ProjectRecord

                project = session.get(ProjectRecord, UUID(payload["project_id"]))
                if (
                    not project
                    or project.tenant_id != tenant.id
                    or project.status != "active"
                ):
                    raise ForbiddenError(
                        code="budget_project_denied", message="Project unavailable"
                    )
                return service._snapshot(session, payload["tenant_id"])
            receive(service, session, payload)
            return {"event_id": payload["event_id"]}

    try:
        return await run_in_threadpool(apply)
    except IntegrityError:
        raise ForbiddenError(
            code="budget_replay_denied", message="Budget request replay denied"
        ) from None
    except (ValueError, KeyError, TypeError):
        raise BadRequestError(
            code="budget_request_invalid", message="Invalid budget query"
        ) from None


@router.post("/api/runtime/internal/budgets/resolve", include_in_schema=False)
async def resolve_budget(request: Request, service=Depends(get_service)):
    return await internal(request, service, "resolve")


@router.post("/api/runtime/internal/budgets/events", include_in_schema=False)
async def receive_budget_event(request: Request, service=Depends(get_service)):
    return await internal(request, service, "event")

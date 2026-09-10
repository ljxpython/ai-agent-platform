from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import sessionmaker

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.service_accounts.contracts import (
    CreateServiceAccountCommand,
    CreateServiceAccountTokenCommand,
    ListServiceAccountsQuery,
    UpdateServiceAccountCommand,
    UpsertServiceAccountProjectGrantCommand,
)
from platform_api.modules.service_accounts.service import ServiceAccountsService
from platform_api.modules.service_accounts.schemas import (
    CreatedServiceAccountToken,
    ServiceAccountItem,
    ServiceAccountPage,
    ServiceAccountTokenItem,
    ServiceAccountProjectGrantItem,
)

router = APIRouter(prefix="/api/service-accounts", tags=["service-accounts"])


def get_service_accounts_service(request: Request) -> ServiceAccountsService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    settings: Settings = request.app.state.settings
    return ServiceAccountsService(
        session_factory=session_factory,
        default_token_ttl_days=settings.service_account_token_default_ttl_days,
    )


@router.get(
    "/{service_account_id}/project-grants",
    response_model=list[ServiceAccountProjectGrantItem],
)
def list_service_account_project_grants(
    service_account_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> list[ServiceAccountProjectGrantItem]:
    return service.list_project_grants(
        actor=actor, service_account_id=service_account_id
    )


@router.put(
    "/{service_account_id}/project-grants/{project_id}",
    response_model=ServiceAccountProjectGrantItem,
)
def upsert_service_account_project_grant(
    service_account_id: str,
    project_id: str,
    payload: UpsertServiceAccountProjectGrantCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountProjectGrantItem:
    return service.upsert_project_grant(
        actor=actor,
        service_account_id=service_account_id,
        project_id=project_id,
        command=payload,
    )


@router.delete("/{service_account_id}/project-grants/{project_id}", status_code=204)
def delete_service_account_project_grant(
    service_account_id: str,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> Response:
    service.delete_project_grant(
        actor=actor,
        service_account_id=service_account_id,
        project_id=project_id,
    )
    return Response(status_code=204)


@router.get("", response_model=ServiceAccountPage)
def list_service_accounts(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountPage:
    return service.list_service_accounts(
        actor=actor,
        query=ListServiceAccountsQuery(
            limit=limit, offset=offset, query=query, status=status
        ),
    )


@router.post("", response_model=ServiceAccountItem)
def create_service_account(
    payload: CreateServiceAccountCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountItem:
    return service.create_service_account(actor=actor, command=payload)


@router.patch("/{service_account_id}", response_model=ServiceAccountItem)
def update_service_account(
    service_account_id: str,
    payload: UpdateServiceAccountCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountItem:
    return service.update_service_account(
        actor=actor,
        service_account_id=service_account_id,
        command=payload,
    )


@router.post("/{service_account_id}/tokens", response_model=CreatedServiceAccountToken)
def create_service_account_token(
    service_account_id: str,
    payload: CreateServiceAccountTokenCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> CreatedServiceAccountToken:
    return service.create_service_account_token(
        actor=actor,
        service_account_id=service_account_id,
        command=payload,
    )


@router.delete(
    "/{service_account_id}/tokens/{token_id}", response_model=ServiceAccountTokenItem
)
def revoke_service_account_token(
    service_account_id: str,
    token_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ServiceAccountsService = Depends(get_service_accounts_service),
) -> ServiceAccountTokenItem:
    return service.revoke_service_account_token(
        actor=actor,
        service_account_id=service_account_id,
        token_id=token_id,
    )

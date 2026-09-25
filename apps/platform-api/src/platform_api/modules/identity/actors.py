from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.service_accounts.models import ServiceAccountTokenRecord
from platform_api.modules.service_accounts.repository import (
    SqlAlchemyServiceAccountsRepository,
)


def load_user_actor(
    *,
    session_factory: sessionmaker[Session] | None,
    user_id: str,
    project_id: str | None,
) -> ActorContext | None:
    if session_factory is None:
        return None
    session = session_factory()
    try:
        repository = SqlAlchemyIdentityRepository(session)
        try:
            from uuid import UUID

            normalized_user_id = UUID(user_id)
        except ValueError:
            return None
        user = repository.get_user_by_id(normalized_user_id)
        if user is None or user.status != "active":
            return None
        project_roles: dict[str, tuple[str, ...]] = {}
        if project_id:
            try:
                project_uuid = UUID(project_id)
            except ValueError:
                return None
            role = SqlAlchemyProjectsRepository(session).get_project_member_role(
                project_id=project_uuid,
                user_id=normalized_user_id,
            )
            if role is not None:
                project_roles[project_id] = (role.value,)
        return ActorContext(
            user_id=str(user.id),
            subject=user.external_subject,
            email=user.email,
            platform_roles=user.platform_roles,
            must_change_password=user.must_change_password,
            project_roles=project_roles,
        )
    finally:
        session.close()


def load_service_account_actor(
    *,
    session_factory: sessionmaker[Session] | None,
    subject: str,
    credential_id: str | None,
    project_id: str,
) -> ActorContext | None:
    if (
        session_factory is None
        or not subject.startswith("service-account:")
        or not credential_id
    ):
        return None
    try:
        account_id = UUID(subject.removeprefix("service-account:"))
        token_id = UUID(credential_id)
        project_uuid = UUID(project_id)
    except ValueError:
        return None
    with session_factory() as session:
        repository = SqlAlchemyServiceAccountsRepository(session)
        account = repository.get_service_account_by_id(account_id)
        token = session.get(ServiceAccountTokenRecord, token_id)
        if (
            account is None
            or account.status != "active"
            or token is None
            or token.service_account_id != account_id
            or token.status != "active"
            or (
                token.expires_at is not None
                and token.expires_at.replace(
                    tzinfo=token.expires_at.tzinfo or timezone.utc
                )
                <= datetime.now(timezone.utc)
            )
        ):
            return None
        if token.revoked_at is not None:
            return None
        role = repository.get_project_grant_role(
            credential_id=credential_id,
            project_id=project_uuid,
        )
        return ActorContext(
            subject=subject,
            principal_type="service_account",
            credential_id=credential_id,
            platform_roles=account.platform_roles,
            project_roles={project_id: (role.value,)} if role else {},
        )

from sqlalchemy.orm import Session, sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository


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

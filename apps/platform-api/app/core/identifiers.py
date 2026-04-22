from __future__ import annotations

from uuid import UUID

from app.core.context.models import ActorContext
from app.core.errors import NotAuthenticatedError, PlatformApiError


def parse_uuid(
    value: str,
    *,
    code: str,
    message: str | None = None,
) -> UUID:
    try:
        return UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise PlatformApiError(
            code=code,
            status_code=400,
            message=message or code.replace("_", " "),
        ) from exc


def parse_actor_user_id(actor: ActorContext) -> UUID:
    if not actor.user_id:
        raise NotAuthenticatedError()
    return parse_uuid(actor.user_id, code="invalid_actor_user_id")

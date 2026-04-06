from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.context.models import ActorContext
from app.core.errors import ForbiddenError, NotAuthenticatedError
from app.modules.iam.domain.roles import PlatformRole, ProjectRole


class PermissionCode(StrEnum):
    PLATFORM_USER_READ = "platform.user.read"
    PLATFORM_USER_WRITE = "platform.user.write"
    PLATFORM_AUDIT_READ = "platform.audit.read"
    PLATFORM_CATALOG_REFRESH = "platform.catalog.refresh"
    PLATFORM_ANNOUNCEMENT_WRITE = "platform.announcement.write"
    PLATFORM_OPERATION_READ = "platform.operation.read"
    PLATFORM_OPERATION_WRITE = "platform.operation.write"
    PLATFORM_CONFIG_READ = "platform.config.read"
    PLATFORM_CONFIG_WRITE = "platform.config.write"
    PROJECT_MEMBER_READ = "project.member.read"
    PROJECT_MEMBER_WRITE = "project.member.write"
    PROJECT_AUDIT_READ = "project.audit.read"
    PROJECT_ANNOUNCEMENT_READ = "project.announcement.read"
    PROJECT_ANNOUNCEMENT_WRITE = "project.announcement.write"
    PROJECT_ASSISTANT_READ = "project.assistant.read"
    PROJECT_ASSISTANT_WRITE = "project.assistant.write"
    PROJECT_RUNTIME_READ = "project.runtime.read"
    PROJECT_RUNTIME_WRITE = "project.runtime.write"
    PROJECT_TESTCASE_READ = "project.testcase.read"
    PROJECT_TESTCASE_WRITE = "project.testcase.write"
    PROJECT_OPERATION_READ = "project.operation.read"
    PROJECT_OPERATION_WRITE = "project.operation.write"


PLATFORM_PERMISSION_MAP: dict[PermissionCode, frozenset[PlatformRole]] = {
    PermissionCode.PLATFORM_USER_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_USER_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_AUDIT_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_CATALOG_REFRESH: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_ANNOUNCEMENT_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_OPERATION_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_OPERATION_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
    PermissionCode.PLATFORM_CONFIG_READ: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR, PlatformRole.VIEWER}
    ),
    PermissionCode.PLATFORM_CONFIG_WRITE: frozenset(
        {PlatformRole.SUPER_ADMIN, PlatformRole.OPERATOR}
    ),
}

PROJECT_PERMISSION_MAP: dict[PermissionCode, frozenset[ProjectRole]] = {
    PermissionCode.PROJECT_MEMBER_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_MEMBER_WRITE: frozenset(
        {ProjectRole.ADMIN}
    ),
    PermissionCode.PROJECT_AUDIT_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_ANNOUNCEMENT_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_ANNOUNCEMENT_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_ASSISTANT_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_ASSISTANT_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_RUNTIME_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_RUNTIME_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_TESTCASE_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_TESTCASE_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR}
    ),
    PermissionCode.PROJECT_OPERATION_READ: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
    PermissionCode.PROJECT_OPERATION_WRITE: frozenset(
        {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}
    ),
}


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    permission: PermissionCode
    project_id: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str


class IamPolicyEngine:
    def evaluate(
        self,
        *,
        actor: ActorContext,
        authorization: AuthorizationRequest,
    ) -> PolicyDecision:
        if not actor.is_authenticated:
            return PolicyDecision(allowed=False, reason="not_authenticated")

        if actor.has_platform_role(PlatformRole.SUPER_ADMIN.value):
            return PolicyDecision(allowed=True, reason="platform_super_admin")

        permission = authorization.permission
        if permission in PLATFORM_PERMISSION_MAP:
            required_roles = PLATFORM_PERMISSION_MAP[permission]
            matched = {PlatformRole(role) for role in actor.platform_roles if role in required_roles}
            if matched:
                return PolicyDecision(allowed=True, reason="platform_role_allowed")
            return PolicyDecision(allowed=False, reason="missing_platform_role")

        if permission in PROJECT_PERMISSION_MAP:
            if not authorization.project_id:
                return PolicyDecision(allowed=False, reason="project_scope_required")
            actor_roles = actor.project_role_set(authorization.project_id)
            required_roles = PROJECT_PERMISSION_MAP[permission]
            matched = {ProjectRole(role) for role in actor_roles if role in required_roles}
            if matched:
                return PolicyDecision(allowed=True, reason="project_role_allowed")
            return PolicyDecision(allowed=False, reason="missing_project_role")

        return PolicyDecision(allowed=False, reason="permission_not_registered")

    def require(
        self,
        *,
        actor: ActorContext,
        authorization: AuthorizationRequest,
    ) -> None:
        decision = self.evaluate(actor=actor, authorization=authorization)
        if decision.allowed:
            return
        if decision.reason == "not_authenticated":
            raise NotAuthenticatedError()
        raise ForbiddenError(code="policy_denied", message=decision.reason)

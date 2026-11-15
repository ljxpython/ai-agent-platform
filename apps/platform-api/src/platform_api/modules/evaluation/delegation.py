"""Short-lived, body-bound commands; live project membership is checked on receipt."""

import hashlib
import time
from uuid import UUID

import jwt

from platform_api.core.errors import ForbiddenError
from platform_api.modules.evaluation.service import digest
from platform_api.modules.iam.application.policies import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.identity.actors import load_user_actor

OPERATIONS = {
    "list": PermissionCode.PROJECT_EVALUATION_READ,
    "read": PermissionCode.PROJECT_EVALUATION_READ,
    "create": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "revise": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "generate": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "assistant_result": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "assistant_bind": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "assistant_status": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "approve": PermissionCode.PROJECT_EVALUATION_REVIEW,
    "edit": PermissionCode.PROJECT_EVALUATION_REVIEW,
    "run": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "cancel": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "dispute": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "defer": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "withdraw": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "assign": PermissionCode.PROJECT_EVALUATION_MANAGE,
    "tool_decision": PermissionCode.PROJECT_EVALUATION_REVIEW,
    "grant": PermissionCode.PROJECT_EVALUATION_MANAGE,
    "revoke": PermissionCode.PROJECT_EVALUATION_MANAGE,
    "regression": PermissionCode.PROJECT_EVALUATION_REVIEW,
    "summary": PermissionCode.PROJECT_EVALUATION_REVIEW,
    "explain": PermissionCode.PROJECT_EVALUATION_EXECUTE,
    "compare": PermissionCode.PROJECT_EVALUATION_READ,
}


def require_action(actor, project_id, operation):
    if (
        actor is None
        or actor.principal_type != "user"
        or not actor.user_id
        or operation not in OPERATIONS
    ):
        raise ForbiddenError(
            code="evaluation_identity_denied", message="需要有效平台用户和评测操作。"
        )
    IamPolicyEngine().require(
        actor=actor,
        authorization=AuthorizationRequest(OPERATIONS[operation], project_id),
    )


def _key(secret):
    if not secret:
        raise ForbiddenError(
            code="evaluation_service_unconfigured", message="评测服务身份尚未配置。"
        )
    return hashlib.sha256(("evalflow-workbench-v1:" + secret).encode()).digest()


def issue_command(secret, actor, project_id, operation, item_id, request_id, body):
    require_action(actor, project_id, operation)
    now = int(time.time())
    return jwt.encode(
        {
            "iss": "platform-evaluation",
            "aud": "evalflow-workbench",
            "sub": actor.user_id,
            "project_id": str(UUID(project_id)),
            "operation": operation,
            "item_id": str(UUID(item_id)) if item_id else None,
            "jti": str(UUID(request_id)),
            "body_hash": digest(body),
            "iat": now,
            "nbf": now,
            "exp": now + 60,
        },
        _key(secret),
        algorithm="HS256",
    )


def verify_command(secret, token, body, factory):
    try:
        claims = jwt.decode(
            token,
            _key(secret),
            algorithms=["HS256"],
            audience="evalflow-workbench",
            issuer="platform-evaluation",
            options={
                "require": [
                    "sub",
                    "project_id",
                    "operation",
                    "jti",
                    "body_hash",
                    "iat",
                    "nbf",
                    "exp",
                ]
            },
        )
        if claims["exp"] - claims["iat"] > 60 or claims["body_hash"] != digest(body):
            raise ValueError("command binding")
        UUID(claims["jti"])
        UUID(claims["project_id"])
        UUID(claims["sub"])
        if claims["item_id"] is not None:
            UUID(claims["item_id"])
        elif claims["operation"] not in {"list", "summary"}:
            raise ValueError("missing work item")
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise ForbiddenError(
            code="evaluation_command_invalid", message="评测命令已过期或与内容不符。"
        ) from None
    actor = load_user_actor(
        session_factory=factory, user_id=claims["sub"], project_id=claims["project_id"]
    )
    from platform_api.core.db import session_scope
    from platform_api.modules.projects.models import ProjectRecord

    with session_scope(factory) as session:
        project = session.get(ProjectRecord, UUID(claims["project_id"]))
        if not project or project.status != "active" or project.deleted_at is not None:
            raise ForbiddenError(
                code="evaluation_project_denied", message="评测项目已停用。"
            )
    require_action(actor, claims["project_id"], claims["operation"])
    return {**claims, "roles": sorted(actor.project_role_set(claims["project_id"]))}

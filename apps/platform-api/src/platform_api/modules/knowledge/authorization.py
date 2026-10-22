"""Exact HMAC operations; a short grant is a lease, not an IAM transaction."""

import hashlib
import hmac
import json
import time
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ForbiddenError, ServiceUnavailableError
from platform_api.modules.knowledge.schemas import FileName, JobId, Mime, Size
from platform_api.modules.knowledge.service import require_scope
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.infra.sqlalchemy.repository import (
    RunRequestsRepository,
)

SUBMIT_TOOL = "mcp_submit_project_knowledge_document"
JOB_TOOL = "mcp_get_project_knowledge_ingest_job"
ISSUED_AT_CLOCK_SKEW_SECONDS = 5
Revision = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def signature(values, secret, key_id, purpose):
    return hmac.new(
        secret.encode(), f"{purpose}\n{canonical(values)}".encode(), hashlib.sha256
    ).hexdigest()


def mint_knowledge_jwt(
    secret: str,
    tenant_id: str,
    project_id: str,
    knowledge_base_id: str,
    ttl_seconds: int = 86400,
    project_name: str | None = None,
) -> str:
    import jwt

    now = int(time.time())
    payload = {
        "tenant_id": str(tenant_id),
        "project_id": str(project_id),
        "knowledge_base_id": str(knowledge_base_id),
        "iat": now,
        "exp": now + ttl_seconds,
        "iss": "platform-api",
        "aud": "rag-service",
    }
    if project_name:
        payload["project_name"] = str(project_name)
    return jwt.encode(payload, secret, algorithm="HS256")


def request_id(values):
    scope = [
        values[k]
        for k in ("tenant_id", "project_id", "thread_id", "run_id", "tool_call_id")
    ]
    return "kr_" + hashlib.sha256(canonical(scope).encode()).hexdigest()[:32]


class KnowledgeIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issuer: Literal["runtime-service", "rag-anything-use"]
    audience: Literal["platform-api"]
    tenant_id: Annotated[str, Field(min_length=1, max_length=64)]
    project_id: UUID
    resource_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
    knowledge_base_id: Annotated[str, Field(pattern=r"^kb_[a-f0-9]{32}$")] | None = None
    subject: Annotated[str, Field(min_length=1, max_length=255)]
    principal_type: Literal["user", "service_account"]
    credential_id: str
    graph_id: Literal["showcase_demo", "dearflow_agent"]
    thread_id: UUID
    run_id: UUID
    tool_call_id: Annotated[
        str, Field(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$")
    ]
    request_id: Annotated[str, Field(pattern=r"^kr_[a-f0-9]{32}$")]
    iat: Annotated[int, Field(strict=True)]
    exp: Annotated[int, Field(strict=True)]
    nonce: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]

    @model_validator(mode="after")
    def exact_identity(self):
        if self.principal_type == "service_account":
            UUID(self.subject.removeprefix("service-account:"))
            if (
                not self.subject.startswith("service-account:")
                or str(UUID(self.credential_id)) != self.credential_id
            ):
                raise ValueError("invalid_knowledge_identity")
        elif self.credential_id != "" or str(UUID(self.subject)) != self.subject:
            raise ValueError("invalid_knowledge_identity")
        return self


class KnowledgeRead(KnowledgeIdentity):
    issuer: Literal["runtime-service"]
    operation: Literal["read"]
    job_id: JobId


class KnowledgeOperation(KnowledgeIdentity):
    operation: Literal["upload", "start", "activate"]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    size_bytes: Size
    file_name: FileName
    mime_type: Mime
    job_id: JobId | None = None
    target_revision: Revision | None = None
    base_revision: Annotated[int, Field(strict=True, ge=0)] | None = None

    @model_validator(mode="after")
    def exact_operation(self):
        expected_issuer = (
            "runtime-service" if self.operation == "upload" else "rag-anything-use"
        )
        if self.issuer != expected_issuer:
            raise ValueError("wrong_knowledge_issuer")
        if (self.operation == "upload") != (self.job_id is None):
            raise ValueError("wrong_knowledge_job")
        if self.operation != "upload" and self.knowledge_base_id is None:
            raise ValueError("missing_knowledge_base")
        if self.operation == "activate":
            if self.target_revision is None or self.base_revision is None:
                raise ValueError("invalid_knowledge_revision")
        elif self.target_revision is not None or self.base_revision is not None:
            raise ValueError("unexpected_knowledge_revision")
        return self


def parse_operation(settings, envelope):
    if (
        not settings.knowledge_upload_enabled
        and isinstance(envelope, dict)
        and isinstance(envelope.get("values"), dict)
        and envelope["values"].get("operation") == "upload"
    ):
        raise ServiceUnavailableError(
            code="knowledge_upload_disabled", message="Knowledge upload disabled"
        )
    if len(settings.knowledge_secret.encode()) < 32:
        raise ServiceUnavailableError(
            code="knowledge_authorization_unavailable",
            message="Knowledge authorization unavailable",
        )
    try:
        if (
            not isinstance(envelope, dict)
            or set(envelope) != {"version", "key_id", "values", "signature"}
            or type(envelope["version"]) is not int
            or envelope["version"] != 1
        ):
            raise ValueError()
        if envelope["key_id"] != settings.knowledge_key_id or not isinstance(
            envelope["signature"], str
        ):
            raise ValueError()
        expected = signature(
            envelope["values"],
            settings.knowledge_secret,
            envelope["key_id"],
            "knowledge-operation-request",
        )
        if not hmac.compare_digest(envelope["signature"], expected):
            raise ValueError()
        model = (
            KnowledgeRead
            if isinstance(envelope["values"], dict)
            and envelope["values"].get("operation") == "read"
            else KnowledgeOperation
        )
        operation = model.model_validate(envelope["values"])
        now = time.time()
        if (
            operation.iat > now + ISSUED_AT_CLOCK_SKEW_SECONDS
            or now >= operation.exp
            or not 0 < operation.exp - operation.iat <= 30
        ):
            raise ValueError()
        values = operation.model_dump(mode="json", exclude_none=True)
        if request_id(values) != operation.request_id:
            raise ValueError()
        return operation
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise ForbiddenError(
            code="knowledge_upload_denied", message="Invalid knowledge authorization"
        ) from exc


def authorize_operation(factory, settings, operation):
    from platform_api.modules.runtime_policies.application import (
        RuntimePolicyOverlayService,
    )

    values = operation.model_dump(mode="json")
    actor = ActorContext(
        user_id=operation.subject if operation.principal_type == "user" else None,
        subject=operation.subject,
        principal_type=operation.principal_type,
        credential_id=values["credential_id"] or None,
    )
    is_read = operation.operation == "read"
    actor = require_scope(
        factory, actor, values["project_id"], operation.tenant_id, upload=not is_read
    )
    resource = settings.knowledge_mcp_bindings.get(
        f"{operation.tenant_id}:{operation.project_id}"
    )
    connection = settings.knowledge_connections.get(resource) if resource else None
    if connection is not None and connection.scope != {
        "tenant_id": operation.tenant_id,
        "project_id": values["project_id"],
    }:
        raise ForbiddenError(
            code="knowledge_upload_denied", message="Knowledge scope denied"
        )
    if connection is None and settings.knowledge_secret:
        from platform_api.config import KnowledgeConnection

        kb_id = "kb_" + UUID(str(operation.project_id)).hex
        dynamic_resource = resource or f"knowledge_{operation.project_id}"
        if operation.resource_id == dynamic_resource:
            resource = dynamic_resource
            token = mint_knowledge_jwt(
                secret=settings.knowledge_secret,
                tenant_id=operation.tenant_id,
                project_id=str(operation.project_id),
                knowledge_base_id=kb_id,
            )
            connection = KnowledgeConnection(
                base_url=getattr(
                    settings,
                    "knowledge_gateway_base_url",
                    "http://152.136.27.196:8000",
                ),
                token=token,
                scope={
                    "tenant_id": operation.tenant_id,
                    "project_id": values["project_id"],
                },
                knowledge_base_id=kb_id,
            )

    if (
        connection is None
        or resource != operation.resource_id
        or connection.scope
        != {"tenant_id": operation.tenant_id, "project_id": values["project_id"]}
        or connection.knowledge_base_id is None
        or operation.knowledge_base_id not in {None, connection.knowledge_base_id}
    ):
        raise ForbiddenError(
            code="knowledge_upload_denied", message="Knowledge scope denied"
        )
    policy = RuntimePolicyOverlayService(
        session_factory=factory, runtime_base_url="default"
    ).resolve_tool_overrides(
        project_id=values["project_id"],
        user_id=actor.user_id,
        graph_id=operation.graph_id,
    )
    if (JOB_TOOL if is_read else SUBMIT_TOOL) in policy["tool_overrides"]:
        raise ForbiddenError(
            code="knowledge_upload_denied", message="Knowledge tool denied"
        )
    if operation.operation in {"upload", "read"}:
        thread_access.require_action(
            actor,
            values["project_id"],
            thread_access.get(factory, values["thread_id"]),
            "read" if is_read else "comment",
        )
    with factory() as session:
        source = RunRequestsRepository(session).for_run(
            project_id=values["project_id"],
            thread_id=values["thread_id"],
            run_id=values["run_id"],
        )
        if (
            source is None
            or source.requested_by != (values["credential_id"] or operation.subject)
            or source.agent_key != operation.graph_id
            or source.context_snapshot.get("plan_mode")
            or source.context_snapshot.get("offload_conversation")
        ):
            raise ForbiddenError(
                code="knowledge_upload_denied", message="Knowledge Run source denied"
            )
    now = int(time.time())
    grant_values = {
        **values,
        "knowledge_base_id": connection.knowledge_base_id,
        "issuer": "platform-api",
        "audience": "rag-knowledge",
        "iat": now,
        "exp": now + 30,
        "nonce": uuid4().hex,
    }
    envelope = {
        "version": 1,
        "key_id": settings.knowledge_key_id,
        "values": grant_values,
        "signature": signature(
            grant_values,
            settings.knowledge_secret,
            settings.knowledge_key_id,
            "knowledge-operation-grant",
        ),
    }
    return envelope, actor

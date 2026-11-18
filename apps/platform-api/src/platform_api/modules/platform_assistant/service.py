"""All assistant reads recheck current identity; evidence IDs refer to audit events."""

import hashlib
import logging
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

from starlette.concurrency import run_in_threadpool

from platform_api.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.platform_assistant import database
from platform_api.modules.platform_assistant.contracts import AssistantDatabase
from platform_api.modules.platform_assistant.diagnostics import (
    identifier,
    read_checkpoint,
)
from platform_api.modules.platform_assistant.materials import read_material
from platform_api.modules.projects.models import ProjectRecord

logger = logging.getLogger(__name__)


def require_scope(factory, actor, project_id):
    if not project_id:
        raise BadRequestError(
            code="assistant_project_required", message="请先初始化助手并传入项目编号。"
        )
    if (
        not actor
        or not actor.user_id
        or not actor.is_authenticated
        or actor.must_change_password
    ):
        raise ForbiddenError(
            code="assistant_identity_denied", message="需要有效用户身份。"
        )
    if not actor.project_role_set(project_id):
        raise ForbiddenError(
            code="assistant_project_denied", message="当前用户没有此项目的读取权限。"
        )
    with factory() as session:
        project = session.get(ProjectRecord, UUID(project_id))
        if project is None or project.status != "active":
            raise ForbiddenError(
                code="assistant_project_denied", message="项目不可用。"
            )
        return str(project.tenant_id)


def sources(settings, actor, project_id):
    result = {}
    for key, raw in settings.assistant_databases.items():
        source = AssistantDatabase.model_validate(raw)
        if str(source.project_id) == project_id and (
            actor.user_id in {str(x) for x in source.user_ids}
            or set(actor.project_role_set(project_id)) & set(source.project_roles)
        ):
            result[key] = source
    return result


def readable_capabilities(settings, actor, project_id, overrides):
    databases = sources(settings, actor, project_id)
    return {
        "scope": "current_identity_and_project",
        "run_diagnostics": "denied"
        if overrides.get("read_run_diagnostics") is False
        else "on_request",
        "databases": {
            "availability": "denied"
            if overrides.get("list_databases") is False
            else "available"
            if databases
            else "empty",
            "reason": "no_readable_sources" if not databases else None,
            "includes_platform_system_database": False,
        },
        "logs": {
            "availability": "denied"
            if overrides.get("read_run_logs") is False
            else "not_checked",
            "source": "fixed_files" if settings.assistant_log_files else "loki",
            "services": [
                name for name in settings.assistant_log_files if identifier(name)
            ]
            if overrides.get("read_run_logs") is not False
            else [],
            "coverage": "bounded_structured_project_thread_run_time",
            "project_search_allowed": actor.user_id in settings.assistant_log_users
            and overrides.get("search_project_logs") is not False,
        },
        "source": "allowed"
        if actor.user_id in settings.assistant_source_users
        and overrides.get("search_source") is not False
        else "denied",
        "shell": False,
    }


def require_target_project(factory, actor, thread_id):
    from platform_api.modules.identity.actors import load_user_actor
    from platform_api.modules.runtime_gateway.application import thread_access

    metadata = thread_access.get(factory, thread_id)
    target_project = metadata.get("project_id")
    # Internal callbacks load roles for the assistant project, not the target project.
    target_actor = (
        load_user_actor(
            session_factory=factory, user_id=actor.user_id, project_id=target_project
        )
        if target_project
        else None
    )
    if not target_actor or not thread_access.allowed(
        target_actor, target_project, metadata, "read"
    ):
        raise ForbiddenError(code="thread_action_denied", message="无权读取目标会话。")
    require_scope(factory, target_actor, target_project)
    return target_project, target_actor


def write_audit(
    factory,
    actor,
    project_id,
    evidence_id,
    body,
    outcome,
    elapsed,
    correlation,
    status_code=200,
):
    try:
        with factory.begin() as session:
            session.add(
                AuditLogRecord(
                    id=UUID(evidence_id),
                    request_id=correlation.get("request_id", evidence_id)[:64],
                    plane="runtime_gateway",
                    action="assistant.read." + body.operation,
                    target_type="assistant_evidence",
                    target_id=evidence_id,
                    actor_user_id=actor.user_id if actor else None,
                    actor_subject=None,
                    tenant_id=None,
                    project_id=project_id,
                    result="success" if outcome == "success" else "failed",
                    method="POST",
                    path="/api/platform-assistant/read",
                    status_code=status_code,
                    duration_ms=int(elapsed * 1000),
                    metadata_json={
                        **correlation,
                        "outcome": outcome,
                        "database_id": body.database_id,
                        "target_thread_id": str(body.target_thread_id)
                        if body.target_thread_id
                        else None,
                        "target_run_id": str(body.target_run_id)
                        if body.target_run_id
                        else None,
                        "document_id": body.document_id,
                        "query_fingerprint": hashlib.sha256(
                            body.query.encode()
                        ).hexdigest(),
                    },
                )
            )
        return True
    except Exception:
        logger.warning("assistant.audit_unavailable", exc_info=False)
        return False


async def read(
    request,
    actor,
    project_id,
    body,
    gateway,
    *,
    correlation=None,
    target_gateway_factory=None,
):
    settings = request.app.state.settings
    if not settings.platform_assistant_enabled:
        raise ServiceUnavailableError(
            code="assistant_disabled", message="平台助手已关闭。"
        )
    factory = request.app.state.db_session_factory
    evidence_id, started = str(uuid4()), time.monotonic()
    correlation = correlation or {}
    scope = {"project_id": project_id}
    try:
        await run_in_threadpool(require_scope, factory, actor, project_id)
        from platform_api.modules.runtime_policies.application.service import (
            RuntimePolicyOverlayService,
        )

        tool_name = {
            "sql_sources": "list_databases",
            "sql_schema": "sql_db_schema",
            "sql_query": "sql_db_query",
            "documents": "search_documents",
            "source": "search_source",
            "diagnostics": "read_run_diagnostics",
            "logs": "read_run_logs" if body.target_run_id else "search_project_logs",
            "authorize_search": "search_public_web",
        }.get(body.operation)
        if tool_name or body.operation == "authorize":
            policy = await run_in_threadpool(
                RuntimePolicyOverlayService(
                    session_factory=factory,
                    runtime_base_url=settings.langgraph_upstream_url,
                ).resolve_tool_overrides,
                project_id=project_id,
                user_id=actor.user_id,
                graph_id="platform_assistant",
            )
            if policy["tool_overrides"].get(tool_name) is False:
                raise ForbiddenError(
                    code="assistant_tool_denied", message="此工具权限已被撤销。"
                )
        if body.operation in {"authorize", "authorize_search"}:
            data = {"authorized": True}
            if body.operation == "authorize":
                data["capabilities"] = readable_capabilities(
                    settings, actor, project_id, policy["tool_overrides"]
                )
                data["document_catalog"] = []
                data["document_status"] = "denied"
                if policy["tool_overrides"].get("search_documents") is not False:
                    try:
                        catalog = await run_in_threadpool(
                            read_material, settings.assistant_document_root, body
                        )
                        data["document_catalog"] = catalog["catalog"]
                        data["document_status"] = (
                            "available" if catalog["catalog"] else "empty"
                        )
                    except ServiceUnavailableError:
                        data["document_status"] = "unavailable"
        elif body.operation == "record_citations":
            from platform_api.modules.platform_assistant.evidence import check_citations

            data = await run_in_threadpool(
                check_citations,
                factory,
                actor,
                project_id,
                correlation.get("assistant_thread_id", ""),
                body.evidence_ids,
            )
            correlation = {**correlation, **data}
        elif body.operation == "sql_sources":
            readable = sources(settings, actor, project_id)
            data = {
                "availability": "available" if readable else "empty",
                "scope": "current_identity_and_project",
                "empty_reason": "no_readable_sources" if not readable else None,
                "includes_platform_system_database": False,
                "databases": [
                    {"database_id": key, "revision": value.revision}
                    for key, value in readable.items()
                ],
            }
        elif body.operation in {"sql_schema", "sql_query"}:
            source = sources(settings, actor, project_id).get(body.database_id)
            if not source:
                raise ForbiddenError(
                    code="assistant_database_denied",
                    message="该数据源尚未接入或当前用户未获准读取。",
                )
            data = await run_in_threadpool(
                database.schema if body.operation == "sql_schema" else database.query,
                source,
                *(
                    [body.query]
                    if body.operation == "sql_query"
                    else [body.table_names, body.table_offset]
                ),
            )
        elif body.operation in {"documents", "source"}:
            if (
                body.operation == "source"
                and actor.user_id not in settings.assistant_source_users
            ):
                raise ForbiddenError(
                    code="assistant_source_denied",
                    message="源码仅向明确获准的研发开放。",
                )
            root = (
                settings.assistant_source_root
                if body.operation == "source"
                else settings.assistant_document_root
            )
            data = await run_in_threadpool(
                read_material, root, body, source=body.operation == "source"
            )
        elif (
            body.operation == "logs"
            and not body.target_thread_id
            and not body.target_run_id
        ):
            from platform_api.modules.platform_assistant.logs import authorized_logs

            if actor.user_id not in settings.assistant_log_users:
                raise ForbiddenError(
                    code="assistant_logs_denied",
                    message="无运行关联的调查需要明确的项目日志授权。",
                )
            data = (
                await authorized_logs(
                    request,
                    actor,
                    project_id,
                    body.query,
                    start=body.log_start,
                    end=body.log_end,
                    service=body.log_service,
                )
            ).model_dump(mode="json")
        elif body.operation in {"diagnostics", "logs"}:
            if not body.target_thread_id or not body.target_run_id:
                raise BadRequestError(
                    code="assistant_run_required",
                    message="请提供目标 Thread 和 Run 编号。",
                )
            target_project_id, target_actor = await run_in_threadpool(
                require_target_project, factory, actor, str(body.target_thread_id)
            )
            scope["target_project_id"] = target_project_id
            if target_gateway_factory is not None:
                gateway = await run_in_threadpool(
                    target_gateway_factory, target_actor, target_project_id
                )

            snapshot = await gateway.get_thread_run(
                actor=target_actor,
                project_id=target_project_id,
                thread_id=str(body.target_thread_id),
                run_id=str(body.target_run_id),
            )
            if (
                not isinstance(snapshot, dict)
                or snapshot.get("thread_id") != str(body.target_thread_id)
                or snapshot.get("run_id") != str(body.target_run_id)
            ):
                raise NotFoundError(code="run_not_found", message="未找到目标运行。")
            try:
                data = await gateway.get_thread_run_diagnostics(
                    actor=target_actor,
                    project_id=target_project_id,
                    thread_id=str(body.target_thread_id),
                    run_id=str(body.target_run_id),
                    request_id=correlation.get("request_id", evidence_id),
                )
            except PlatformApiError as exc:
                if exc.status_code < 500:
                    raise
                data = {
                    "availability": "unavailable",
                    "unavailable_reason": "backend_unavailable",
                    "correlation": {},
                }
            if body.operation == "diagnostics":
                status = snapshot.get("status")
                data["run_status"] = (
                    status
                    if isinstance(status, str)
                    and status
                    in {
                        "pending",
                        "running",
                        "success",
                        "error",
                        "timeout",
                        "interrupted",
                        "cancelled",
                    }
                    else "unknown"
                )
                data["request_id_scope"] = "diagnostic_query_not_execution"
                data["availability_scope"] = "current_trace_query_client"
                data["historical_collection"] = "unknown"
                data["execution_request_id_scope"] = (
                    "platform_execution_not_provider_request"
                )
                # Observation IDs locate telemetry, not graph nodes; the assistant needs facts.
                for key in (
                    "graph_executions",
                    "model_errors",
                    "retries",
                    "preparations",
                    "workspace_executions",
                    "loop_detections",
                ):
                    for item in data.get(key, []):
                        item.pop("observation_id", None)
                data["persistent_state"] = await read_checkpoint(
                    gateway,
                    actor=target_actor,
                    project_id=target_project_id,
                    thread_id=str(body.target_thread_id),
                    run_id=str(body.target_run_id),
                )
                data["run_time"] = {
                    key: value.isoformat() if isinstance(value, datetime) else value
                    for key in ("created_at", "updated_at")
                    if isinstance(value := snapshot.get(key), (str, datetime))
                }
                context = (snapshot.get("kwargs") or {}).get("context") or {}
                data["configuration"] = {
                    key: value
                    for key, value in context.items()
                    if key in {"model_id", "access_policy", "plan_mode"}
                    and isinstance(value, (str, bool))
                }
            if body.operation == "logs":
                from platform_api.modules.platform_assistant.logs import (
                    authorized_logs,
                    run_log_window,
                )

                trace_id = data.get("correlation", {}).get("platform_trace_id") or ""
                execution_request_id = (
                    data.get("correlation", {}).get("execution_request_id") or ""
                )
                start, end = run_log_window(snapshot, body.log_start, body.log_end)
                data = (
                    await authorized_logs(
                        request,
                        target_actor,
                        target_project_id,
                        trace_id,
                        verified=True,
                        execution_request_id=execution_request_id,
                        target_thread_id=str(body.target_thread_id),
                        target_run_id=str(body.target_run_id),
                        start=start,
                        end=end,
                        service=body.log_service,
                    )
                ).model_dump(mode="json")
        else:
            raise BadRequestError(
                code="assistant_operation_denied", message="不支持此操作。"
            )
        from platform_api.modules.platform_assistant.evidence import save_evidence

        await run_in_threadpool(
            save_evidence,
            factory,
            actor,
            project_id,
            evidence_id,
            body,
            correlation,
            data,
        )
    except Exception as exc:
        await run_in_threadpool(
            write_audit,
            factory,
            actor,
            project_id,
            evidence_id,
            body,
            getattr(exc, "code", "unavailable"),
            time.monotonic() - started,
            correlation,
            status_code=getattr(exc, "status_code", 503),
        )
        raise
    recorded = await run_in_threadpool(
        write_audit,
        factory,
        actor,
        project_id,
        evidence_id,
        body,
        "success",
        time.monotonic() - started,
        correlation,
    )
    return {
        "evidence_id": evidence_id,
        "operation": body.operation,
        "observed_at": datetime.now(UTC).isoformat(),
        "scope": scope,
        "audit_recorded": recorded,
        "data": data,
    }

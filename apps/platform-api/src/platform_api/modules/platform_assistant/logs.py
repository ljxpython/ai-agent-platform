"""Legacy and assistant log reads share the same project/trace proof."""

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from platform_api.core.errors import BadRequestError, ForbiddenError
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.observability.service import ObservabilityService
from platform_api.modules.platform_assistant.service import require_scope
from platform_api.modules.runtime_gateway.application import thread_access

SAFE_FIELDS = {
    "service",
    "level",
    "event",
    "span_id",
    "duration_ms",
    "status_code",
    "error_code",
    "code",
    "thread_id",
    "run_id",
    "project_id",
    "trace_id",
    "platform_trace_id",
    "request_id",
}


def run_log_window(snapshot, start="", end=""):
    if start and end:
        return start, end
    if not start and not end:
        try:
            created = snapshot["created_at"]
            updated = snapshot["updated_at"]
            created = (
                created
                if isinstance(created, datetime)
                else datetime.fromisoformat(created)
            )
            updated = (
                updated
                if isinstance(updated, datetime)
                else datetime.fromisoformat(updated)
            )
            if created.tzinfo and updated.tzinfo and created <= updated:
                begin, finish = (
                    created - timedelta(minutes=5),
                    updated + timedelta(minutes=5),
                )
                if finish - begin <= timedelta(hours=24):
                    return begin.isoformat(), finish.isoformat()
        except (KeyError, TypeError, ValueError):
            pass
    raise BadRequestError(
        code="assistant_log_window_required",
        message="运行时间未知或跨度超过24小时；请补充含时区、跨度不超过24小时的起止时间，不能默认查询最近一小时。",
    )


def file_logs(paths, trace_id):
    streams = []
    unreadable = False
    for service, filename in paths.items():
        path = Path(filename)
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            unreadable = True
            continue
        try:
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - 512000))
                lines = (
                    handle.read(512000).decode("utf-8", errors="replace").splitlines()
                )
        except OSError:
            unreadable = True
            continue
        values = []
        for line in lines:
            if trace_id not in line:
                continue
            try:
                payload = json.loads(line[line.index("{") :])
                if not isinstance(payload, dict):
                    continue
                stamp = datetime.fromisoformat(
                    payload.get("ts") or payload["timestamp"]
                )
                if stamp.tzinfo is None:
                    continue
                values.append([str(int(stamp.timestamp() * 1e9)), line])
            except (ValueError, KeyError, TypeError):
                continue
        streams.append({"stream": {"service": service}, "values": values[-100:]})
    result = ObservabilityService.parse_results(trace_id, streams)
    if unreadable:
        result.error = (
            "assistant_log_source_partial"
            if streams
            else "assistant_log_source_unavailable"
        )
    return result


def trace_owned(factory, actor, project_id, trace_id):
    with factory() as session:
        rows = session.scalars(
            select(AuditLogRecord)
            .where(
                AuditLogRecord.project_id == project_id,
                AuditLogRecord.actor_user_id == actor.user_id,
            )
            .order_by(AuditLogRecord.created_at.desc())
            .limit(2000)
        )
        return any(
            r.metadata_json.get("platform_trace_id") == trace_id
            or r.metadata_json.get("trace_id") == trace_id
            for r in rows
        )


async def authorized_logs(
    request,
    actor,
    project_id,
    trace_id,
    *,
    verified=False,
    execution_request_id="",
    target_thread_id=None,
    target_run_id=None,
    start="",
    end="",
    service="",
):
    factory, settings = request.app.state.db_session_factory, request.app.state.settings
    await run_in_threadpool(require_scope, factory, actor, project_id)
    if (
        not verified
        and actor.user_id not in settings.assistant_log_users
        and not await run_in_threadpool(
            trace_owned, factory, actor, project_id, trace_id
        )
    ):
        raise ForbiddenError(
            code="trace_scope_denied",
            message="日志关联尚未验证，请从获准运行诊断进入，或申请项目日志调查授权。",
        )
    if trace_id and not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", trace_id):
        raise ForbiddenError(code="trace_scope_denied", message="日志关联编号无效。")
    if execution_request_id and (
        not verified
        or not target_thread_id
        or not target_run_id
        or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", execution_request_id)
    ):
        raise ForbiddenError(code="trace_scope_denied", message="请求关联未验证。")
    if not trace_id and target_run_id and (not verified or not target_thread_id):
        raise ForbiddenError(code="trace_scope_denied", message="运行关联未验证。")
    try:
        end_time = datetime.fromisoformat(end) if end else datetime.now(UTC)
        start_time = (
            datetime.fromisoformat(start) if start else end_time - timedelta(hours=1)
        )
        if (
            not start_time.tzinfo
            or not end_time.tzinfo
            or not timedelta(0) < end_time - start_time <= timedelta(hours=24)
        ):
            raise ValueError()
    except ValueError:
        from platform_api.core.errors import BadRequestError

        raise BadRequestError(
            code="assistant_log_window_invalid",
            message="请提供含时区且跨度不超过24小时的日志时间范围。",
        ) from None
    search_id = trace_id or execution_request_id or target_run_id or project_id
    correlation_type = (
        "platform_trace_id"
        if trace_id
        else "execution_request_id"
        if execution_request_id
        else "run_id"
        if target_run_id
        else "project_id"
    )
    result = (
        await run_in_threadpool(file_logs, settings.assistant_log_files, search_id)
        if settings.assistant_log_files
        else await ObservabilityService(settings).get_trace_logs(
            search_id, start=start_time.timestamp(), end=end_time.timestamp()
        )
    )
    result.trace_id = trace_id
    logs = []
    thread_grants = {}
    result_bytes = 0
    for entry in result.logs:
        payload = entry.payload
        if not isinstance(payload, dict):
            continue
        # Text matches are candidates, not authorization evidence.
        if payload.get("project_id") != project_id or (
            trace_id
            and trace_id
            not in {
                payload.get("platform_trace_id"),
                payload.get("trace_id"),
            }
        ):
            continue
        if target_thread_id and payload.get("thread_id") != target_thread_id:
            continue
        if target_run_id and payload.get("run_id") != target_run_id:
            continue
        if (
            not trace_id
            and execution_request_id
            and payload.get("request_id") != execution_request_id
        ):
            continue
        if actor.user_id not in settings.assistant_log_users:
            target = payload.get("thread_id")
            if not isinstance(target, str) or not target:
                continue
            if target not in thread_grants:
                access = await run_in_threadpool(thread_access.get, factory, target)
                thread_grants[target] = thread_access.allowed(
                    actor, project_id, access, "read"
                )
            if not thread_grants[target]:
                continue
        if service and entry.service != service:
            continue
        if (
            not start_time.timestamp() * 1e9
            <= int(entry.nanos)
            <= end_time.timestamp() * 1e9
        ):
            continue
        safe = {
            key: value
            for key, value in payload.items()
            if key in SAFE_FIELDS and isinstance(value, (str, int, float, bool))
        }
        # Structured identifiers must not turn into a second raw-message channel.
        safe = {
            key: value
            for key, value in safe.items()
            if not isinstance(value, str)
            or re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}", value)
        }
        entry.payload = safe
        entry.raw = json.dumps(safe, ensure_ascii=False)
        entry.summary = str(safe.get("event", ""))[:160]
        entry.event = str(safe.get("event", ""))
        entry.level = str(safe.get("level", "info"))
        entry.span_id = str(safe.get("span_id", ""))
        entry.service = str(safe.get("service", entry.service))[:100]
        entry_bytes = len(entry.model_dump_json().encode())
        if result_bytes + entry_bytes > 64000:
            break
        result_bytes += entry_bytes
        logs.append(entry)
        if len(logs) >= 100:
            break
    result.logs = logs
    result.total = len(logs)
    result.services = sorted({entry.service for entry in logs})
    result.duration_ms = None
    result.partial = True
    result.coverage = "bounded_structured_project_logs_only"
    result.query_start = start_time.isoformat()
    result.query_end = end_time.isoformat()
    result.correlation_type = correlation_type
    result.source = "fixed_files" if settings.assistant_log_files else "loki"
    result.availability = (
        "partial"
        if result.error and logs
        else "unavailable"
        if result.error
        else "available"
        if logs
        else "empty"
    )
    return result

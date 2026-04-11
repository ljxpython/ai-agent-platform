"""Scaffold router for SDK-backed runs endpoints."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.services.langgraph_sdk.runs_service import LangGraphRunsService
from app.services.langgraph_sdk.scope_guard import (
    assert_assistant_belongs_project,
    assert_thread_belongs_project,
    get_optional_project_id,
    inject_project_scope,
)
from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from httpx import HTTPStatusError

router = APIRouter()


def _require_assistant_id(payload: dict[str, Any]) -> None:
    assistant_id = payload.get("assistant_id")
    if not isinstance(assistant_id, str) or not assistant_id:
        raise HTTPException(status_code=400, detail="assistant_id is required")


def _to_sse_chunk(event: Any) -> bytes:
    if isinstance(event, bytes):
        if event.endswith(b"\n\n"):
            return event
        if event.endswith(b"\n"):
            return event + b"\n"
        return event + b"\n\n"

    if isinstance(event, str):
        if event.startswith(("data:", "event:", "id:", "retry:", ":")):
            if event.endswith("\n\n"):
                return event.encode("utf-8")
            if event.endswith("\n"):
                return f"{event}\n".encode("utf-8")
            return f"{event}\n\n".encode("utf-8")
        return f"data: {event}\n\n".encode("utf-8")

    if isinstance(event, (list, tuple)):
        if len(event) >= 2 and isinstance(event[0], str):
            event_name = event[0]
            event_data = event[1]
            event_id = event[2] if len(event) >= 3 else None
            encoded_data = json.dumps(
                jsonable_encoder(event_data), separators=(",", ":"), ensure_ascii=False
            )
            chunks = [f"event: {event_name}\n", f"data: {encoded_data}\n"]
            if event_id is not None:
                chunks.append(f"id: {event_id}\n")
            chunks.append("\n")
            return "".join(chunks).encode("utf-8")

    encoded = json.dumps(
        jsonable_encoder(event), separators=(",", ":"), ensure_ascii=False
    )
    return f"data: {encoded}\n\n".encode("utf-8")


async def _sse_stream(events: Any) -> AsyncIterator[bytes]:
    if hasattr(events, "__aiter__"):
        async for event in events:
            yield _to_sse_chunk(event)
        return

    for event in events:
        yield _to_sse_chunk(event)


def _raise_langgraph_request_error(exc: Exception, *, fallback_detail: str) -> None:
    if isinstance(exc, HTTPStatusError):
        response = exc.response
        try:
            detail: Any = response.json()
        except Exception:
            detail = response.text or fallback_detail
        raise HTTPException(status_code=response.status_code, detail=detail) from exc
    message = str(exc).strip()
    if message.startswith("ValueError:"):
        detail = message.split(":", 1)[1].strip() or fallback_detail
        raise HTTPException(status_code=400, detail=detail) from exc
    raise HTTPException(status_code=502, detail=fallback_detail) from exc


async def _assert_cron_query_scope(
    request: Request,
    payload: dict[str, Any],
) -> None:
    assistant_id = payload.get("assistant_id")
    thread_id = payload.get("thread_id")

    if isinstance(assistant_id, str) and assistant_id:
        await assert_assistant_belongs_project(request, assistant_id)
    if isinstance(thread_id, str) and thread_id:
        await assert_thread_belongs_project(request, thread_id)

    if get_optional_project_id(request) is not None:
        has_target = (
            isinstance(assistant_id, str)
            and bool(assistant_id)
        ) or (
            isinstance(thread_id, str)
            and bool(thread_id)
        )
        if not has_target:
            raise HTTPException(
                status_code=400,
                detail="assistant_id or thread_id is required for project-scoped cron query",
            )


async def _assert_bulk_cancel_scope(
    request: Request,
    payload: dict[str, Any],
) -> None:
    thread_id = payload.get("thread_id")
    if isinstance(thread_id, str) and thread_id:
        await assert_thread_belongs_project(request, thread_id)
        return

    if get_optional_project_id(request) is not None:
        raise HTTPException(
            status_code=400,
            detail="thread_id is required for project-scoped bulk cancel",
        )


@router.post("/runs")
async def create_run(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    """
    在全局范围创建一次 run（不绑定指定 thread_id），触发 assistant 执行。

    参数说明：
    - request: 当前 HTTP 请求上下文，用于构造 LangGraph SDK 客户端。
    - payload: run 创建参数；assistant_id 必填，其余字段按 LangGraph 原生字段透传。

    返回语义：
    - 返回上游 create run 的结果对象，并通过 jsonable_encoder 序列化。
    """
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    try:
        run = await service.create_global(scoped_payload)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_langgraph_request_error(exc, fallback_detail="langgraph_run_request_failed")
    return jsonable_encoder(run)


@router.post("/runs/stream")
async def stream_run(
    request: Request, payload: dict[str, Any] = Body(...)
) -> StreamingResponse:
    """
    在全局范围以流式模式执行 run，实时返回事件流（SSE）。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 流式运行参数；assistant_id 必填，其余字段按 LangGraph 原生字段透传。

    返回语义：
    - 返回 text/event-stream；逐条消费 SDK 迭代器并输出 SSE chunk。
    """
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    try:
        event_iter = await service.stream_global(scoped_payload)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_langgraph_request_error(exc, fallback_detail="langgraph_run_stream_failed")
    return StreamingResponse(_sse_stream(event_iter), media_type="text/event-stream")


@router.post("/runs/wait")
async def wait_run(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    """
    在全局范围创建 run 并等待执行完成后返回最终结果。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 同步等待参数；assistant_id 必填，其余字段按 LangGraph 原生字段透传。

    返回语义：
    - 返回上游 wait 结果对象，并通过 jsonable_encoder 序列化。
    """
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    try:
        result = await service.wait_global(scoped_payload)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_langgraph_request_error(exc, fallback_detail="langgraph_run_request_failed")
    return jsonable_encoder(result)


@router.post("/runs/batch")
async def batch_create_runs(request: Request, payload: Any = Body(...)) -> Any:
    """
    批量创建 runs，支持数组体或包含 payloads 字段的对象体。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 可以是 run payload 数组，或形如 {"payloads": [...]} 的对象。

    返回语义：
    - 返回上游 create_batch 结果列表，并通过 jsonable_encoder 序列化。
    """
    payloads: Any
    if isinstance(payload, list):
        payloads = payload
    elif isinstance(payload, dict):
        payloads = payload.get("payloads")
    else:
        raise HTTPException(status_code=400, detail="payload must be array or object")

    if not isinstance(payloads, list):
        raise HTTPException(status_code=400, detail="payloads must be array")

    scoped_payloads: list[dict[str, Any]] = []
    for item in payloads:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="each payload must be object")
        scoped_payload = inject_project_scope(request, item)
        _require_assistant_id(scoped_payload)
        await assert_assistant_belongs_project(request, scoped_payload["assistant_id"])
        scoped_payloads.append(scoped_payload)

    service = LangGraphRunsService(request)
    result = await service.create_batch(scoped_payloads)
    return jsonable_encoder(result)


@router.post("/runs/cancel")
async def cancel_runs(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    """
    按条件批量取消 runs。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 取消参数对象，支持 status、thread_id、run_ids，action 可选。

    返回语义：
    - 若上游返回 None，则返回 {"ok": true} 语义。
    - 若上游返回对象，则原样序列化返回。
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be object")

    await _assert_bulk_cancel_scope(request, payload)
    service = LangGraphRunsService(request)
    result = await service.cancel_many(payload)
    if result is None:
        return {"ok": True}
    return jsonable_encoder(result)


@router.post("/runs/crons")
async def create_cron(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    """
    创建全局 cron 任务，用于按 schedule 触发 run。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: cron 创建参数；assistant_id 必填，其他字段按 LangGraph 原生字段透传。

    返回语义：
    - 返回上游 cron 创建结果，并通过 jsonable_encoder 序列化。
    """
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    cron = await service.create_cron(scoped_payload)
    return jsonable_encoder(cron)


@router.post("/runs/crons/search")
async def search_crons(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    """
    按条件检索 cron 列表。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 检索过滤与分页参数，按 LangGraph 原生字段透传。

    返回语义：
    - 返回上游 cron 搜索结果，并通过 jsonable_encoder 序列化。
    """
    await _assert_cron_query_scope(request, payload)
    service = LangGraphRunsService(request)
    crons = await service.search_crons(payload)
    return jsonable_encoder(crons)


@router.post("/runs/crons/count")
async def count_crons(request: Request, payload: dict[str, Any] = Body(...)) -> Any:
    """
    统计符合条件的 cron 数量。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 计数过滤参数，按 LangGraph 原生字段透传。

    返回语义：
    - 返回上游 cron count 结果，并通过 jsonable_encoder 序列化。
    """
    await _assert_cron_query_scope(request, payload)
    service = LangGraphRunsService(request)
    count = await service.count_crons(payload)
    return jsonable_encoder(count)


@router.patch("/runs/crons/{cron_id}")
async def update_cron(
    request: Request, cron_id: str, payload: dict[str, Any] = Body(...)
) -> Any:
    """
    更新指定 cron 的可变字段。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - cron_id: 目标 cron 标识。
    - payload: 更新参数，按 LangGraph 原生字段透传。

    返回语义：
    - 返回上游 cron 更新后的结果对象，并通过 jsonable_encoder 序列化。
    """
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    cron = await service.update_cron(cron_id, scoped_payload)
    return jsonable_encoder(cron)


@router.delete("/runs/crons/{cron_id}")
async def delete_cron(request: Request, cron_id: str) -> Any:
    """
    删除指定 cron。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - cron_id: 要删除的 cron 标识。

    返回语义：
    - 若上游返回 None，则返回 {"ok": true} 语义。
    - 若上游返回对象，则原样序列化返回。
    """
    service = LangGraphRunsService(request)
    result = await service.delete_cron(cron_id)
    if result is None:
        return {"ok": True}
    return jsonable_encoder(result)


@router.post("/threads/{thread_id}/runs")
async def create_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
) -> Any:
    """
    在指定 thread 下创建一次 run，用于触发 assistant 执行。

    参数说明：
    - request: 当前 HTTP 请求上下文，用于构造 LangGraph SDK 客户端。
    - thread_id: 目标 thread 唯一标识。
    - payload: run 创建参数；assistant_id 必填，其余字段按 LangGraph 原生字段透传（如 input、command、stream_mode、config、context、checkpoint 等）。

    返回语义：
    - 返回上游 create run 的结果对象，并通过 jsonable_encoder 序列化。
    """
    await assert_thread_belongs_project(request, thread_id)
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    try:
        run = await service.create(thread_id, scoped_payload)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_langgraph_request_error(exc, fallback_detail="langgraph_run_request_failed")
    return jsonable_encoder(run)


@router.post("/threads/{thread_id}/runs/stream")
async def stream_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
) -> StreamingResponse:
    """
    以流式模式创建并执行 run，实时返回事件流（SSE）。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 目标 thread 唯一标识。
    - payload: 流式运行参数；assistant_id 必填，可选包含 input、command、stream_mode、stream_subgraphs、stream_resumable、feedback_keys、on_disconnect 等 LangGraph 原生字段。

    返回语义：
    - 返回 text/event-stream；逐条消费 SDK 迭代器并输出 SSE chunk。
    """
    await assert_thread_belongs_project(request, thread_id)
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    try:
        event_iter = await service.stream(thread_id, scoped_payload)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_langgraph_request_error(exc, fallback_detail="langgraph_run_stream_failed")
    return StreamingResponse(_sse_stream(event_iter), media_type="text/event-stream")


@router.post("/threads/{thread_id}/runs/wait")
async def wait_thread_run(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
) -> Any:
    """
    创建 run 并等待执行完成后再返回最终结果。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 目标 thread 唯一标识。
    - payload: 同步等待参数；assistant_id 必填，可选包含 input、command、stream_mode、raise_error、on_disconnect、checkpoint、interrupt_before/after 等 LangGraph 原生字段。

    返回语义：
    - 返回上游 wait 结果对象，并通过 jsonable_encoder 序列化。
    """
    await assert_thread_belongs_project(request, thread_id)
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    try:
        result = await service.wait(thread_id, scoped_payload)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_langgraph_request_error(exc, fallback_detail="langgraph_run_request_failed")
    return jsonable_encoder(result)


@router.get("/threads/{thread_id}/runs/{run_id}")
async def get_thread_run(request: Request, thread_id: str, run_id: str) -> Any:
    """
    查询指定 thread 下某个 run 的当前详情。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 所属 thread 标识。
    - run_id: 目标 run 标识。

    返回语义：
    - 返回 run 详情对象，并通过 jsonable_encoder 序列化。
    """
    await assert_thread_belongs_project(request, thread_id)
    service = LangGraphRunsService(request)
    run = await service.get(thread_id, run_id)
    return jsonable_encoder(run)


@router.get("/threads/{thread_id}/runs")
async def list_thread_runs(
    request: Request,
    thread_id: str,
    limit: int | None = Query(default=None),
    offset: int | None = Query(default=None),
    status: str | None = Query(default=None),
    select: list[str] | None = Query(default=None),
) -> Any:
    """
    查询指定 thread 下的 runs 列表。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 所属 thread 标识。
    - limit: 可选，返回条数上限。
    - offset: 可选，分页偏移量。
    - status: 可选，按 run 状态过滤。
    - select: 可选，仅返回指定字段集合。

    返回语义：
    - 返回上游 run 列表结果，并通过 jsonable_encoder 序列化。
    """
    await assert_thread_belongs_project(request, thread_id)
    query_payload: dict[str, Any] = {}
    if limit is not None:
        query_payload["limit"] = limit
    if offset is not None:
        query_payload["offset"] = offset
    if status is not None:
        query_payload["status"] = status
    if select is not None:
        query_payload["select"] = select

    service = LangGraphRunsService(request)
    runs = await service.list(thread_id, query_payload)
    return jsonable_encoder(runs)


@router.delete("/threads/{thread_id}/runs/{run_id}")
async def delete_thread_run(request: Request, thread_id: str, run_id: str) -> Any:
    """
    删除指定 thread 下的 run。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 所属 thread 标识。
    - run_id: 目标 run 标识。

    返回语义：
    - 若上游返回 None，则返回 {"ok": true} 语义。
    - 若上游返回对象，则原样序列化返回。
    """
    await assert_thread_belongs_project(request, thread_id)
    service = LangGraphRunsService(request)
    result = await service.delete(thread_id, run_id)
    if result is None:
        return {"ok": True}
    return jsonable_encoder(result)


@router.get("/threads/{thread_id}/runs/{run_id}/join")
async def join_thread_run(request: Request, thread_id: str, run_id: str) -> Any:
    """
    等待并获取已存在 run 的最终 join 结果（非流式）。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 所属 thread 标识。
    - run_id: 目标 run 标识。

    返回语义：
    - 返回上游 join 结果对象，并通过 jsonable_encoder 序列化。
    """
    await assert_thread_belongs_project(request, thread_id)
    service = LangGraphRunsService(request)
    result = await service.join(thread_id, run_id)
    return jsonable_encoder(result)


@router.post("/threads/{thread_id}/runs/crons")
async def create_thread_run_cron(
    request: Request,
    thread_id: str,
    payload: dict[str, Any] = Body(...),
) -> Any:
    """
    在指定 thread 下创建 cron 任务，按计划触发 run。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 所属 thread 标识。
    - payload: cron 创建参数；assistant_id 必填，其他字段按 LangGraph 原生字段透传。

    返回语义：
    - 返回上游 create_for_thread 结果，并通过 jsonable_encoder 序列化。
    """
    await assert_thread_belongs_project(request, thread_id)
    _require_assistant_id(payload)
    await assert_assistant_belongs_project(request, payload["assistant_id"])
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphRunsService(request)
    cron = await service.create_cron_for_thread(thread_id, scoped_payload)
    return jsonable_encoder(cron)


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_thread_run(
    request: Request,
    thread_id: str,
    run_id: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> Any:
    """
    取消指定 run，可选等待取消完成或指定取消动作。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 所属 thread 标识。
    - run_id: 目标 run 标识。
    - payload: 可选取消参数，仅支持 wait 与 action 两个 LangGraph 原生字段。

    返回语义：
    - 若上游返回对象，则原样序列化返回。
    - 若上游返回 None，则返回 {"ok": true} 语义。
    """
    await assert_thread_belongs_project(request, thread_id)
    if payload is not None and not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be object")

    service = LangGraphRunsService(request)
    result = await service.cancel(thread_id, run_id, payload)
    if result is None:
        return {"ok": True}
    return jsonable_encoder(result)


@router.get("/threads/{thread_id}/runs/{run_id}/stream")
async def join_thread_run_stream(
    request: Request,
    thread_id: str,
    run_id: str,
    cancel_on_disconnect: bool | None = Query(default=None),
    stream_mode: str | None = Query(default=None),
    last_event_id: str | None = Query(default=None),
) -> StreamingResponse:
    """
    加入已存在 run 的事件流，持续接收后续执行事件（SSE）。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - thread_id: 所属 thread 标识。
    - run_id: 目标 run 标识。
    - cancel_on_disconnect: 可选，客户端断开时是否触发取消。
    - stream_mode: 可选，流式模式字段（按 LangGraph 原生命名透传）。
    - last_event_id: 可选，SSE 断线重连时用于续传游标。

    返回语义：
    - 返回 text/event-stream；逐条消费 SDK join_stream 迭代器并输出 SSE chunk。
    """
    await assert_thread_belongs_project(request, thread_id)
    stream_payload: dict[str, Any] = {}
    if cancel_on_disconnect is not None:
        stream_payload["cancel_on_disconnect"] = cancel_on_disconnect
    if stream_mode is not None:
        stream_payload["stream_mode"] = stream_mode
    if last_event_id is not None:
        stream_payload["last_event_id"] = last_event_id

    service = LangGraphRunsService(request)
    event_iter = await service.join_stream(thread_id, run_id, stream_payload)
    return StreamingResponse(_sse_stream(event_iter), media_type="text/event-stream")

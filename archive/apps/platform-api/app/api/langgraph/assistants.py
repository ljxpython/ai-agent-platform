"""Scaffold router for SDK-backed assistants endpoints."""

from __future__ import annotations

from typing import Any

from app.services.langgraph_sdk.assistants_service import LangGraphAssistantsService
from app.services.langgraph_sdk.scope_guard import (
    assert_assistant_belongs_project,
    inject_project_metadata,
    inject_project_scope,
)
from fastapi import APIRouter, Body, Query, Request
from fastapi.encoders import jsonable_encoder

router = APIRouter(prefix="/assistants")


@router.post("")
async def create_assistant(
    request: Request, payload: dict[str, Any] = Body(...)
) -> Any:
    """
    创建 assistant 资源。

    参数说明：
    - request: 当前 HTTP 请求上下文，用于构造 SDK 客户端。
    - payload: 创建参数对象，常见字段包括 graph_id、config、context、metadata、assistant_id、if_exists、name、description。

    返回语义：
    - 返回上游创建后的 assistant 对象（经 jsonable_encoder 序列化）。
    """
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphAssistantsService(request)
    assistant = await service.create(scoped_payload)
    return jsonable_encoder(assistant)


@router.post("/search")
async def search_assistants(
    request: Request, payload: dict[str, Any] = Body(...)
) -> Any:
    """
    按条件检索 assistants 列表。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 检索过滤与分页参数，主要字段包括 metadata、graph_id、name、limit、offset、sort_by、sort_order、select、response_format。

    返回语义：
    - 返回符合过滤条件的 assistant 列表或上游定义的数据结构（已序列化）。
    """
    scoped_payload = inject_project_metadata(request, payload)
    service = LangGraphAssistantsService(request)
    assistants = await service.search(scoped_payload)
    return jsonable_encoder(assistants)


@router.get("/{assistant_id}")
async def get_assistant(request: Request, assistant_id: str) -> Any:
    """
    按 assistant_id 获取单个 assistant 详情。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - assistant_id: assistant 的唯一标识。

    返回语义：
    - 返回对应 assistant 的完整信息（已序列化）。
    """
    await assert_assistant_belongs_project(request, assistant_id)
    service = LangGraphAssistantsService(request)
    assistant = await service.get(assistant_id)
    return jsonable_encoder(assistant)


@router.patch("/{assistant_id}")
async def update_assistant(
    request: Request,
    assistant_id: str,
    payload: dict[str, Any] = Body(...),
) -> Any:
    """
    更新指定 assistant 的可变字段。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - assistant_id: 目标 assistant 的唯一标识。
    - payload: 更新参数对象，常见字段包括 graph_id、config、context、metadata、name、description。

    返回语义：
    - 返回更新后的 assistant 对象（已序列化）。
    """
    await assert_assistant_belongs_project(request, assistant_id)
    scoped_payload = inject_project_scope(request, payload)
    service = LangGraphAssistantsService(request)
    assistant = await service.update(assistant_id, scoped_payload)
    return jsonable_encoder(assistant)


@router.delete("/{assistant_id}")
async def delete_assistant(
    request: Request,
    assistant_id: str,
    delete_threads: bool = Query(default=False),
) -> Any:
    """
    删除指定 assistant。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - assistant_id: 要删除的 assistant 标识。
    - delete_threads: 是否同时删除与该 assistant 关联的 threads，默认 false。

    返回语义：
    - 若上游返回具体结果，则透传并序列化该结果。
    - 若上游返回 None，则回退为 {"ok": true} 语义（本实现中为 Python 布尔值 True）。
    """
    await assert_assistant_belongs_project(request, assistant_id)
    service = LangGraphAssistantsService(request)
    result = await service.delete(assistant_id, delete_threads=delete_threads)
    if result is None:
        return {"ok": True}
    return jsonable_encoder(result)


@router.post("/count")
async def count_assistants(
    request: Request, payload: dict[str, Any] = Body(...)
) -> Any:
    """
    统计符合条件的 assistants 数量。

    参数说明：
    - request: 当前 HTTP 请求上下文。
    - payload: 计数过滤参数，主要字段包括 metadata、graph_id、name。

    返回语义：
    - 返回上游 count 接口结果（通常包含总数信息，已序列化）。
    """
    scoped_payload = inject_project_metadata(request, payload)
    service = LangGraphAssistantsService(request)
    count = await service.count(scoped_payload)
    return jsonable_encoder(count)

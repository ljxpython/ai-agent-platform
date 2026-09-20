from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from runtime_service.auth.platform import authenticate
from runtime_service.runtime.tool_access import require_tool_access
from runtime_service.tools.images import ImageWorkspace, ImageWorkspaceError
from runtime_service.workspace.image_refs import UPLOAD_MAX_BYTES, ImageRef
from runtime_service.workspace.scoped import resolve_thread_workspace

router = APIRouter(prefix="/internal/threads/{thread_id}/images", tags=["images"])


async def _authorize_image_request(
    thread_id: str,
    authorization: str | None,
    expected_operation: str,
) -> tuple[str, str, str]:
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    if scope.get("operation") != expected_operation:
        raise HTTPException(
            status_code=403,
            detail={"code": "image_scope_denied", "message": "Scope operation mismatch"},
        )
    if scope.get("thread_id") != thread_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "runtime_target_denied", "message": "Thread ID mismatch"},
        )
    if scope.get("assistant_id") not in {"showcase_demo", "dearflow_agent"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "image_capability_unavailable",
                "message": "Graph does not support image workspace",
            },
        )
    require_tool_access(facts, "write_file" if expected_operation == "image-upload" else "read_file")
    tenant_id = scope.get("tenant_id")
    project_id = scope.get("project_id")
    if not tenant_id or not project_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "thread_project_denied", "message": "Tenant and project required"},
        )
    return tenant_id, project_id, scope["assistant_id"]


@router.put("/uploads/{sha256}")
async def upload_thread_image(
    thread_id: str,
    sha256: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> ImageRef:
    tenant_id, project_id, graph_id = await _authorize_image_request(
        thread_id, authorization, "image-upload"
    )

    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "image_too_large", "message": f"Upload exceeds {UPLOAD_MAX_BYTES} bytes limit"},
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    workspace_root = resolve_thread_workspace(tenant_id, project_id, thread_id, graph_id)
    ws = ImageWorkspace(workspace_root)

    try:
        ref = await asyncio.to_thread(ws.put_upload, data, sha256)
        return ref
    except ImageWorkspaceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/content")
async def read_thread_image(
    thread_id: str,
    path: str = Query(...),
    authorization: str | None = Header(default=None),
) -> Response:
    tenant_id, project_id, graph_id = await _authorize_image_request(
        thread_id, authorization, "image-read"
    )

    workspace_root = resolve_thread_workspace(tenant_id, project_id, thread_id, graph_id)
    ws = ImageWorkspace(workspace_root)

    try:
        data, ref = await asyncio.to_thread(ws.read_asset, path)
        return Response(
            content=data,
            media_type=ref["mime_type"],
            headers={
                "Content-Length": str(ref["size_bytes"]),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except ImageWorkspaceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

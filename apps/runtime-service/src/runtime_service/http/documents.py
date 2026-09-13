from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from runtime_service.auth.platform import authenticate
from runtime_service.workspace.scoped import get_showcase_workspace_root
from runtime_service.workspace.documents import DocumentError, DocumentWorkspace
from runtime_service.workspace.file_refs import MAX_FILE_BYTES as MAX_BYTES, MIME_EXT

router = APIRouter(prefix="/internal/threads/{thread_id}/files", tags=["documents"])


async def _auth(thread_id: str, authorization: str | None, operation: str) -> tuple[str, str]:
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    if scope.get("operation") != operation or scope.get("thread_id") != thread_id:
        raise HTTPException(403, {"code": "file_scope_denied", "message": "File scope denied"})
    if not scope.get("assistant_id") or not scope.get("tenant_id") or not scope.get("project_id"):
        raise HTTPException(403, {"code": "file_target_denied", "message": "File target denied"})
    return scope["tenant_id"], scope["project_id"]


@router.put("/uploads/{sha256}")
async def upload_thread_file(thread_id: str, sha256: str, request: Request, authorization: str | None = Header(default=None)) -> dict:
    tenant, project = await _auth(thread_id, authorization, "workspace-file-upload")
    mime = request.headers.get("content-type", "").split(";", 1)[0].lower()
    suffix = MIME_EXT.get(mime)
    if suffix is None:
        raise HTTPException(415, {"code": "unsupported_file_type", "message": "Unsupported document type"})
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(413, {"code": "file_too_large", "message": "File exceeds 20 MiB"})
        chunks.append(chunk)
    data = b"".join(chunks)
    root = get_showcase_workspace_root(tenant, project, thread_id)
    try:
        return await asyncio.to_thread(DocumentWorkspace(root).put, data, sha256, mime,
                                       request.query_params.get("file_name"))
    except DocumentError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from exc


TEXT_CHARSET_MIMES = {
    "text/plain": "text/plain; charset=utf-8",
    "text/markdown": "text/markdown; charset=utf-8",
    "text/csv": "text/csv; charset=utf-8",
    "application/json": "application/json; charset=utf-8",
}


@router.get("/content")
async def read_thread_file(thread_id: str, path: str = Query(...), authorization: str | None = Header(default=None)) -> Response:
    tenant, project = await _auth(thread_id, authorization, "workspace-file-read")
    root = get_showcase_workspace_root(tenant, project, thread_id)
    try:
        data, ref = await asyncio.to_thread(DocumentWorkspace(root).read, path)
    except DocumentError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from exc
    media_type = TEXT_CHARSET_MIMES.get(ref["mime_type"], ref["mime_type"])
    return Response(data, media_type=media_type, headers={"Content-Length": str(len(data)), "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

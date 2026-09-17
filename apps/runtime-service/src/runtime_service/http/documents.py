from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from runtime_service.auth.platform import authenticate
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.documents import DocumentError, DocumentWorkspace
from runtime_service.workspace.file_refs import MAX_FILE_BYTES as MAX_BYTES
from runtime_service.workspace.file_refs import MIME_EXT
from runtime_service.workspace.scoped import resolve_thread_workspace

router = APIRouter(prefix="/internal/threads/{thread_id}/files", tags=["documents"])


async def _auth(thread_id: str, authorization: str | None, operation: str) -> Path:
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    if scope.get("operation") != operation or scope.get("thread_id") != thread_id:
        raise HTTPException(403, {"code": "file_scope_denied", "message": "File scope denied"})
    if not scope.get("assistant_id") or not scope.get("tenant_id") or not scope.get("project_id"):
        raise HTTPException(403, {"code": "file_target_denied", "message": "File target denied"})
    try:
        return resolve_thread_workspace(scope["tenant_id"], scope["project_id"], thread_id, scope["assistant_id"])
    except ValueError as exc:
        raise HTTPException(409, {"code": "workspace_capability_unavailable"}) from exc


@router.put("/uploads/{sha256}")
async def upload_thread_file(thread_id: str, sha256: str, request: Request, authorization: str | None = Header(default=None)) -> dict:
    root = await _auth(thread_id, authorization, "workspace-file-upload")
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
    try:
        return await asyncio.to_thread(DocumentWorkspace(root).put, data, sha256, mime,
                                       request.query_params.get("file_name"))
    except DocumentError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from exc


TEXT_CHARSET_MIMES = {
    "text/html": "text/html; charset=utf-8",
    "text/css": "text/css; charset=utf-8",
    "text/javascript": "text/javascript; charset=utf-8",
    "text/plain": "text/plain; charset=utf-8",
    "text/markdown": "text/markdown; charset=utf-8",
    "text/x-bibtex": "text/x-bibtex; charset=utf-8",
    "text/csv": "text/csv; charset=utf-8",
    "application/json": "application/json; charset=utf-8",
    "application/yaml": "application/yaml; charset=utf-8",
    "text/yaml": "text/yaml; charset=utf-8",
    "application/toml": "application/toml; charset=utf-8",
    "application/xml": "application/xml; charset=utf-8",
    "text/xml": "text/xml; charset=utf-8",
    "text/x-python": "text/x-python; charset=utf-8",
    "text/x-shellscript": "text/x-shellscript; charset=utf-8",
    "application/sql": "application/sql; charset=utf-8",
    "text/x-sql": "text/x-sql; charset=utf-8",
    "text/typescript": "text/typescript; charset=utf-8",
}


@router.get("/content")
async def read_thread_file(thread_id: str, path: str = Query(...), authorization: str | None = Header(default=None)) -> Response:
    root = await _auth(thread_id, authorization, "workspace-file-read")
    try:
        reader = ArtifactWorkspace(root) if path.startswith("/workspace/outputs/") else DocumentWorkspace(root)
        data, ref = await asyncio.to_thread(reader.read, path)
    except DocumentError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from exc
    media_type = TEXT_CHARSET_MIMES.get(ref["mime_type"], ref["mime_type"])
    return Response(data, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{ref["file_name"]}"', "Content-Length": str(len(data)), "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'"})

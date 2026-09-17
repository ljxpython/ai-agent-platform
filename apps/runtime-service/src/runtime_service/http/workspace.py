"""Thread-scoped workspace browsing and immutable artifact discovery."""

import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Query, Response

from runtime_service.http.documents import _auth
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.browser import WorkspaceBrowser
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.html_preview import HTML_CSP
from runtime_service.workspace.schemas import ArtifactPage, WorkspacePage

router = APIRouter(prefix="/internal/threads/{thread_id}", tags=["workspace"])


async def _call(thread_id, authorization, method, **kwargs):
    root = await _auth(thread_id, authorization, "workspace-file-read")
    try:
        return await asyncio.to_thread(method, root, **kwargs)
    except DocumentError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": str(exc)}
        ) from exc


@router.get("/workspace/tree", response_model=WorkspacePage)
async def tree(
    thread_id: str,
    response: Response,
    path: str = Query(default="/workspace", max_length=4096),
    cursor: str | None = Query(default=None, max_length=8192),
    limit: int = Query(default=100, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await _call(
        thread_id,
        authorization,
        lambda root, **kw: WorkspaceBrowser(root).list_directory(**kw),
        path=path,
        cursor=cursor,
        limit=limit,
    )


@router.get("/artifacts", response_model=ArtifactPage)
async def artifacts(
    thread_id: str,
    response: Response,
    cursor: str | None = Query(default=None, max_length=8192),
    limit: int = Query(default=100, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    response.headers["Cache-Control"] = "private, no-store"
    return await _call(
        thread_id,
        authorization,
        lambda root, **kw: ArtifactWorkspace(root).list_artifacts(**kw),
        cursor=cursor,
        limit=limit,
    )


@router.get("/workspace/content")
async def content(
    thread_id: str,
    path: str = Query(..., max_length=4096),
    authorization: str | None = Header(default=None),
):
    data, ref = await _call(
        thread_id,
        authorization,
        lambda root, **kw: WorkspaceBrowser(root).read_file(**kw),
        path=path,
    )
    return Response(
        data,
        media_type=ref["mime_type"],
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(ref["file_name"], safe=""),
            "ETag": '"' + ref["sha256"] + '"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


@router.get("/workspace/preview")
async def preview(
    thread_id: str,
    path: str = Query(..., max_length=4096),
    authorization: str | None = Header(default=None),
):
    data, mime = await _call(
        thread_id,
        authorization,
        lambda root, **kw: WorkspaceBrowser(root).preview(**kw),
        path=path,
    )
    return Response(
        data,
        media_type=mime,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "sandbox; " + HTML_CSP,
        },
    )

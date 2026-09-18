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


@router.get("/workspace/zip")
async def zip_archive(
    thread_id: str,
    authorization: str | None = Header(default=None),
):
    data, file_name = await _call(
        thread_id,
        authorization,
        lambda root, **kw: WorkspaceBrowser(root).create_archive(**kw),
    )
    return Response(
        data,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(file_name, safe=""),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
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


from pydantic import BaseModel, Field


class ForkWorkspacePayload(BaseModel):
    source_thread_id: str = Field(..., min_length=1, max_length=256)


@router.post("/workspace/fork")
async def fork_workspace(
    thread_id: str,
    payload: ForkWorkspacePayload,
    authorization: str | None = Header(default=None),
) -> dict:
    import shutil
    from runtime_service.workspace.scoped import resolve_thread_workspace
    from runtime_service.http.documents import _auth_scope

    target_root, scope = await _auth_scope(thread_id, authorization, "workspace-fork")
    source_thread_id = payload.source_thread_id.strip()
    if not source_thread_id:
        raise HTTPException(400, {"code": "invalid_source_thread_id", "message": "source_thread_id is required"})

    if source_thread_id == thread_id:
        return {
            "forked": True,
            "source_thread_id": source_thread_id,
            "target_thread_id": thread_id,
            "files_copied": 0,
        }

    try:
        source_root = resolve_thread_workspace(
            scope["tenant_id"], scope["project_id"], source_thread_id, scope["assistant_id"]
        )
    except ValueError as exc:
        raise HTTPException(409, {"code": "workspace_capability_unavailable"}) from exc

    def _do_copy() -> int:
        target_root.mkdir(parents=True, exist_ok=True)
        if source_root.exists() and source_root.is_dir():
            shutil.copytree(
                source_root,
                target_root,
                dirs_exist_ok=True,
                symlinks=False,
                ignore_dangling_symlinks=True,
            )
            return sum(1 for p in target_root.rglob("*") if p.is_file())
        return 0

    copied = await asyncio.to_thread(_do_copy)
    return {
        "forked": True,
        "source_thread_id": source_thread_id,
        "target_thread_id": thread_id,
        "files_copied": copied,
    }


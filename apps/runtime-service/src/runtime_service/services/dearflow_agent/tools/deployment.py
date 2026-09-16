"""Explicit, digest-bound preview deployment; no host builds or automatic resubmission."""
import asyncio
import hashlib
import io
import os
import re
import tarfile
from pathlib import PurePosixPath
from urllib.parse import urlsplit

import httpx
from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from runtime_service.services.dearflow_agent.external_task_storage import (
    ExternalTaskStorage,
)
from runtime_service.services.dearflow_agent.tools.memory import memory_scope
from runtime_service.workspace.archives import read_zip
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.documents import DocumentError

DEPLOY_ENDPOINT = "https://claude-skills-deploy.vercel.com/api/deploy"


def deployment_package(raw, approved_files):
    try:
        entries = dict(read_zip(raw))
    except ValueError as exc:
        raise DocumentError("unsafe_deployment_archive") from exc
    names = sorted(entries)
    if names != sorted(approved_files) or len(names) != len(set(names)) or not names:
        raise DocumentError("deployment_manifest_mismatch")
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        for name in names:
            path = PurePosixPath(name)
            if any(p.startswith(".") or p in {"node_modules", "__pycache__"} for p in path.parts):
                raise DocumentError("deployment_private_file")
            if path.suffix.lower() not in {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".txt"}:
                raise DocumentError("deployment_file_type")
            data = entries[name]
            if path.suffix in {".html", ".css", ".js", ".json", ".txt"} and re.search(
                rb"(?i)(BEGIN .*PRIVATE KEY|(?:api[_-]?key|secret|password)\s*[:=]\s*['\"]?[^\s'\"]{12,})", data
            ):
                raise DocumentError("deployment_secret_detected")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            bundle.addfile(info, io.BytesIO(data))
    return output.getvalue()


def build_deployment_tool(workspace):
    @tool
    async def deploy_preview(file_path: str, sha256: str, approved_files: list[str], idempotency_key: str, runtime: ToolRuntime) -> dict:
        """After human approval upload precisely these files from a published ZIP to https://claude-skills-deploy.vercel.com/api/deploy. Returns private claim URL. Unknown outcomes must not be resubmitted."""
        if os.environ.get("RUNTIME_DEAR_PREVIEW_DEPLOY_ENABLED") != "1":
            raise DocumentError("preview_deployment_not_enabled", 409)
        if workspace is None:
            raise DocumentError("workspace_unavailable")
        raw, ref = await asyncio.to_thread(ArtifactWorkspace(workspace.root).read, file_path)
        if ref["mime_type"] != "application/zip" or hashlib.sha256(raw).hexdigest() != sha256:
            raise DocumentError("deployment_digest_mismatch")
        package = await asyncio.to_thread(deployment_package, raw, approved_files)
        scope = (*memory_scope(runtime), str(runtime.execution_info.thread_id))
        store = ExternalTaskStorage(os.environ["DATABASE_URI"])
        row, _ = await asyncio.to_thread(store.create, scope, idempotency_key, "deploy_preview",
            {"sha256": sha256, "files": sorted(approved_files), "target": DEPLOY_ENDPOINT},
            run_id=str(runtime.execution_info.run_id), approval_ref=runtime.tool_call_id)
        claimed = await asyncio.to_thread(store.claim, str(row["id"])) if row["status"] == "intent" else None
        if claimed:
            try:
                async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
                    response = await client.post(DEPLOY_ENDPOINT, files={"file": ("site.tgz", package, "application/gzip")}, data={"framework": "null"})
                    response.raise_for_status()
                    result = response.json()
                for field in ("previewUrl", "claimUrl"):
                    parsed = urlsplit(result.get(field, ""))
                    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                        raise ValueError("invalid_deployment_result")
                await asyncio.to_thread(store.finish, claimed, status="succeeded", result={k: result[k] for k in ("previewUrl", "claimUrl")})
            except (Exception, asyncio.CancelledError) as exc:
                await asyncio.shield(asyncio.to_thread(store.finish, claimed, status="unknown", error="deployment_" + type(exc).__name__))
                if isinstance(exc, asyncio.CancelledError):
                    raise
        row = await asyncio.to_thread(store.get, scope, str(row["id"]))
        return {"task_id": str(row["id"]), "status": row["status"], "result": row["result"], "error_code": row["error_code"]}
    deploy_preview.handle_tool_error = True
    return deploy_preview

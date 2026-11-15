"""Opt-in input snapshots; never copy generated outputs or personal memory."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

from runtime_service.db import connect
from runtime_service.workspace.attachment_receipts import AttachmentReceipts
from runtime_service.workspace.documents import DocumentWorkspace


def snapshot_inputs(workspace, capture):
    expiry = datetime.fromisoformat(capture["expires_at"])
    if (
        expiry.tzinfo is None
        or expiry <= datetime.now(UTC)
        or capture.get("data_class") not in {"synthetic", "business"}
    ):
        return None
    result = {
        "status": "captured_inputs",
        "capture_id": capture.get("id"),
        "expires_at": capture["expires_at"],
        "initial_files": {},
        "attachments": [],
        "missing": [],
        "memory": "not_copied",
        "external_resources": "live_versions_not_frozen",
    }
    if workspace is None:
        result["missing"].append("workspace_unavailable")
        return result
    receipts = AttachmentReceipts(workspace)
    try:
        descriptor = receipts.io._directory(("refs",))
    except Exception:
        result["missing"].append("upload_receipts_unavailable")
        return result
    try:
        names = sorted(os.listdir(descriptor))
    finally:
        os.close(descriptor)
    if len(names) > 20:
        result["missing"].append("attachment_limit_exceeded")
    size = 0
    for name in names[:20]:
        try:
            ref = json.loads(receipts._read("refs", name))
            if not receipts.require(ref):
                raise ValueError("receipt_missing")
            data, actual = DocumentWorkspace(workspace).read(ref["path"])
            if len(data) + size > 200_000:
                raise ValueError("snapshot_limit")
            content = data.decode("utf-8")
            size += len(data)
            result["initial_files"][ref["path"]] = content
            result["attachments"].append(ref)
        except Exception as exc:
            result["missing"].append({"receipt": name, "reason": type(exc).__name__})
    return result


def purge_expired():
    with connect() as connection:
        connection.execute("""UPDATE runtime_evaluation_execution
            SET manifest = manifest - 'environment'
            WHERE manifest ? 'environment' AND (
              (manifest->'environment'->>'expires_at')::timestamptz <= now()
              OR NOT EXISTS (SELECT 1 FROM threads t
                WHERE t.thread_id = runtime_evaluation_execution.thread_id
                  AND t.metadata->'evaluation_material_capture'->>'id' = manifest->'environment'->>'capture_id'
                  AND (t.metadata->'evaluation_material_capture'->>'expires_at')::timestamptz > now()))""")


@asynccontextmanager
async def environment_retention_lifespan():
    if os.environ.get("RUNTIME_EVALUATION_EVIDENCE_ENABLED") != "1":
        yield
        return

    async def loop():
        while True:
            try:
                await asyncio.to_thread(purge_expired)
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "evaluation_environment_retention:%s", type(exc).__name__
                )
            await asyncio.sleep(60)

    task = asyncio.create_task(loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

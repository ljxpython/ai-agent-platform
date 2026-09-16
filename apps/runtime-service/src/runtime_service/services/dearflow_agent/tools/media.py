"""Approved media calls with durable receipts; no keys enter the sandbox."""
from __future__ import annotations

import asyncio
import os

from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool

from runtime_service.runtime import verified_delegation_from_user
from runtime_service.services.dearflow_agent.external_task_storage import (
    ExternalTaskStorage,
)
from runtime_service.tools.images import ImageWorkspace, build_image_tools

MEDIA_TOOLS = ("generate_image", "edit_image", "get_media_task")


def receipt(row):
    return {"task_id": str(row["id"]), "operation": row["operation"], "status": row["status"],
            "result": row["result"], "error_code": row["error_code"],
            "notice": "Outcome unknown. No background recovery is running. Stop polling, report missing output and task_id; do not resubmit." if row["status"] == "unknown" else None}



def build_media_tools(workspace: ImageWorkspace):
    images = {item.name: item for item in build_image_tools(workspace)}

    def context(runtime):
        facts = verified_delegation_from_user(runtime.server_info.user)
        info = runtime.execution_info
        if facts.scope.assistant_id != "dearflow_agent" or not info or not info.thread_id:
            raise ToolException("Media requires a trusted Dear Agent Run.")
        if facts.scope.thread_id and facts.scope.thread_id != str(info.thread_id):
            raise ToolException("Media thread scope mismatch.")
        scope = (facts.principal.tenant_id, facts.principal.project_id, facts.principal.user_id, str(info.thread_id))
        if not os.environ.get("DATABASE_URI"):
            raise ToolException("Media task storage is not configured.")
        return ExternalTaskStorage(os.environ["DATABASE_URI"]), scope, str(info.run_id)

    async def submit(runtime, key, operation, request, invoke):
        storage, scope, run = context(runtime)
        try:
            row, _ = await asyncio.to_thread(storage.create, scope, key, operation, request,
                run_id=run, approval_ref=runtime.tool_call_id)
            claimed = await asyncio.to_thread(storage.claim, str(row["id"])) if row["status"] == "intent" else None
            if claimed:
                try:
                    status, result = await invoke()
                    await asyncio.to_thread(storage.finish, claimed, status=status, result=result)
                except (Exception, asyncio.CancelledError) as exc:
                    # Even a timeout may follow a charge. Never automatically resubmit.
                    await asyncio.shield(asyncio.to_thread(storage.finish, claimed, status="unknown",
                        error=getattr(exc, "code", "submission_or_delivery_unknown")))
                    if isinstance(exc, asyncio.CancelledError):
                        raise
            return receipt(await asyncio.to_thread(storage.get, scope, str(row["id"])))
        except ValueError as exc:
            raise ToolException(str(exc)) from exc

    @tool
    async def generate_image(prompt: str, idempotency_key: str, runtime: ToolRuntime) -> dict:
        """Generate one image after approval. Reuse the same idempotency_key after interruptions."""
        if not prompt.strip() or len(prompt) > 8000:
            raise ToolException("Prompt must contain 1 to 8000 characters.")
        if not all(os.environ.get(k) for k in ("IMAGE_25_KEY", "IMAGE_25_URL", "IMAGE_25_MODEL")):
            raise ToolException("Image provider is not configured; no submission.")
        async def invoke():
            _, result = await images["generate_image"].coroutine(prompt=prompt)
            return "succeeded", result
        return await submit(runtime, idempotency_key, "generate_image", {"prompt": prompt, "model": os.environ["IMAGE_25_MODEL"]}, invoke)

    @tool
    async def edit_image(image_path: str, prompt: str, idempotency_key: str, runtime: ToolRuntime,
                         reference_images: list[str] | None = None) -> dict:
        """Edit a trusted image with up to three additional reference images after approval."""
        references = reference_images or []
        if len(references) > 3 or not prompt.strip() or len(prompt) > 8000:
            raise ToolException("At most 4 images and 1 to 8000 prompt characters.")
        for path in [image_path, *references]:
            await asyncio.to_thread(workspace.read_asset, path)
        if not all(os.environ.get(k) for k in ("IMAGE_25_KEY", "IMAGE_25_URL", "IMAGE_25_MODEL")):
            raise ToolException("Image provider is not configured; no submission.")
        async def invoke():
            _, result = await images["edit_image"].coroutine(image_path=image_path, prompt=prompt, reference_images=references)
            return "succeeded", result
        return await submit(runtime, idempotency_key, "edit_image", {"prompt": prompt, "image_path": image_path,
            "reference_images": references, "model": os.environ["IMAGE_25_MODEL"]}, invoke)

    @tool
    async def get_media_task(task_id: str, runtime: ToolRuntime) -> dict:
        """Read the durable receipt of an authorized image request; never resubmit an unknown purchase."""
        storage, scope, _ = context(runtime)
        try:
            return receipt(await asyncio.to_thread(storage.get, scope, task_id))
        except ValueError as exc:
            raise ToolException("Invalid or inaccessible media task.") from exc

    result = [generate_image, edit_image, get_media_task]
    for item in result:
        item.handle_tool_error = True
    return result

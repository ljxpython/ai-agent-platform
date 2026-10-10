"""Three public tools shared by Workspace Agents; capability is never a grant."""

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import ToolException
from pydantic import Field

from runtime_service.background_tasks import repository
from runtime_service.background_tasks.capabilities import query_enabled
from runtime_service.background_tasks.output import read_output
from runtime_service.background_tasks.schemas import list_view, output_view, task_view
from runtime_service.background_tasks.service import start_task
from runtime_service.middlewares.conversation_offloading import (
    is_conversation_maintenance,
)
from runtime_service.runtime.auth import verified_delegation_from_user

BACKGROUND_TOOLS = ("background_execute", "background_task", "cancel_background_task")


def build_background_tools(binding, *, completion=False):
    def identity(runtime, *names):
        current = binding() if callable(binding) else binding
        if current is None:
            raise ToolException("background_task_not_supported")
        if runtime.server_info is None or runtime.execution_info is None:
            raise ToolException("background_task_denied")
        facts = verified_delegation_from_user(runtime.server_info.user)
        info = runtime.execution_info
        execution_id = info.run_id
        metadata_id = (runtime.config.get("metadata") or {}).get("run_id")
        try:
            run_id = str(UUID(str(execution_id or metadata_id)))
            thread_id = str(UUID(str(info.thread_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ToolException("background_task_denied") from exc
        scope = (
            facts.principal.tenant_id,
            facts.principal.project_id,
            thread_id,
        )
        if (
            scope != current.scope
            or facts.scope.assistant_id != current.graph_id
            or execution_id
            and metadata_id
            and str(execution_id) != str(metadata_id)
            or facts.scope.operation != "run-create"
            or (facts.scope.thread_id and facts.scope.thread_id != scope[2])
            or set(names) & set(facts.policy.denied_tool_names)
        ):
            raise ToolException("background_task_denied")
        return {
            "tenant_id": scope[0],
            "project_id": scope[1],
            "thread_id": scope[2],
            "graph_id": current.graph_id,
            "assistant_id": current.graph_id,
            "owner_id": facts.principal.user_id,
            "credential_id": facts.credential_id,
            "origin_run_id": run_id,
            "checkpoint_ns": str(
                runtime.config.get("configurable", {}).get("checkpoint_ns") or ""
            ),
            "tool_call_id": runtime.tool_call_id,
            "request_id": facts.request_id,
            "platform_trace_id": facts.platform_trace_id,
        }, current

    @tool
    async def background_execute(
        command: str,
        runtime: ToolRuntime,
        timeout: Annotated[int, Field(strict=True)] = 900,
    ):
        """Start a bounded Workspace command and return a task ID without awaiting completion."""
        values, current = identity(runtime, "background_execute", "execute")
        if (
            completion
            or "platform_background_completion"
            in runtime.config.get("configurable", {})
            or is_conversation_maintenance(runtime)
        ):
            raise ToolException("background_task_denied")
        if not values["tool_call_id"] or not values["origin_run_id"]:
            raise ToolException("background_task_denied")
        row = await start_task(values, current, command, timeout)
        return task_view(row)

    @tool
    async def background_task(
        action: Literal["status", "list", "output"],
        runtime: ToolRuntime,
        task_id: str | None = None,
    ):
        """Read task status, the latest task page, or a bounded text output snapshot."""
        scope, _ = identity(runtime, "background_task")
        if action == "list":
            if task_id is not None:
                raise ValueError("task_id is not accepted for list")
            return list_view(
                scope, await asyncio.to_thread(repository.list_tasks, scope), 20
            )
        UUID(task_id or "")
        row = await asyncio.to_thread(repository.read_task, scope, task_id)
        if row is None:
            raise ToolException("background_task_not_found")
        if action == "status":
            return task_view(row)
        return output_view(row, await asyncio.to_thread(read_output, row, 16384))

    @tool
    async def cancel_background_task(task_id: str, runtime: ToolRuntime):
        """Request cancellation of one owned task; an ACK does not confirm process cleanup."""
        scope, _ = identity(runtime, "cancel_background_task")
        if is_conversation_maintenance(runtime):
            raise ToolException("background_task_denied")
        UUID(task_id)
        row = await asyncio.to_thread(repository.request_cancel, scope, task_id)
        if row is None:
            raise ToolException("background_task_not_found")
        return task_view(row)

    return [
        # Keep the receipt route for checkpoint replay; model visibility is gated.
        *([background_execute] if not completion else []),
        *([background_task, cancel_background_task] if query_enabled() else []),
    ]

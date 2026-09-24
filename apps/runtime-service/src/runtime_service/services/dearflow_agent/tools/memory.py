"""Explicit memory actions use the same scoped storage as the management API."""
import asyncio

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from runtime_service.runtime import verified_delegation_from_user
from runtime_service.services.dearflow_agent.memory import MemoryCommand, MemoryStorage
from runtime_service.services.dearflow_agent.memory_access import memory_allowed
from runtime_service.workspace.documents import DocumentError


def memory_scope(runtime):
    facts = verified_delegation_from_user(runtime.server_info.user)
    if facts.scope.assistant_id != "dearflow_agent" or not runtime.execution_info:
        raise DocumentError("memory_scope_denied", 403)
    return (facts.principal.tenant_id, facts.principal.project_id, facts.principal.user_id)


def build_memory_tools():
    @tool
    async def search_memory(runtime: ToolRuntime, query: str = "") -> dict:
        """Read this user's current-project facts, candidates and current revision. Never grants permissions."""
        if not await memory_allowed(runtime):
            raise DocumentError("memory_thread_shared", 403)
        return await asyncio.to_thread(MemoryStorage().read, memory_scope(runtime), query)

    @tool
    async def manage_memory(command: MemoryCommand, runtime: ToolRuntime) -> dict:
        """After approval save/edit/delete/clear/restore facts or accept/reject a candidate. Use search_memory's revision; preferences do not change permissions."""
        if not await memory_allowed(runtime):
            raise DocumentError("memory_thread_shared", 403)
        return await asyncio.to_thread(MemoryStorage().change, memory_scope(runtime), command,
                                       thread_id=str(runtime.execution_info.thread_id), source_id=runtime.tool_call_id)

    for item in (search_memory, manage_memory):
        item.handle_tool_error = True
    return [search_memory, manage_memory]

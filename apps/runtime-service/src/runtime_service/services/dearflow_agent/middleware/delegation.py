"""Limit concurrent task calls within one parent graph; durable counts use official middleware."""
import asyncio
from langchain.agents.middleware import AgentMiddleware


class DelegationConcurrencyMiddleware(AgentMiddleware):
    def __init__(self):
        self._slots = asyncio.Semaphore(3)

    async def awrap_tool_call(self, request, handler):
        if request.tool_call["name"] != "task":
            return await handler(request)
        async with self._slots:
            return await handler(request)

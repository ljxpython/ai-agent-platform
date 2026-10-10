"""Run token decisions layered on the existing usage and budget notices."""

from contextvars import copy_context

from langchain.agents.middleware import AgentMiddleware

from runtime_service.middlewares.execution_budget import add_wrapup_instruction
from runtime_service.observability.usage import current_runtime_usage_callback
from runtime_service.runtime.errors import TokenBudgetUnverifiableError
from runtime_service.runtime.token_budget import token_budget_enabled


class TokenBudgetMiddleware(AgentMiddleware):
    def __init__(self, *, root=True, writer=None):
        super().__init__()
        self.root = root
        self.writer = writer

    def before_agent(self, state, runtime):
        usage = current_runtime_usage_callback()
        if self.root and usage is not None and usage.token_budget is not None:
            context = copy_context()
            writer = self.writer or runtime.stream_writer
            usage.bind_budget_writer(lambda notice: context.run(writer, notice))

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    def _check(self):
        usage = current_runtime_usage_callback()
        if usage is not None:
            return usage.check_budget()
        if token_budget_enabled():
            raise TokenBudgetUnverifiableError()
        return "ok"

    def wrap_model_call(self, request, handler):
        return handler(
            add_wrapup_instruction(request)
            if self._check() == "approaching"
            else request
        )

    async def awrap_model_call(self, request, handler):
        return await handler(
            add_wrapup_instruction(request)
            if self._check() == "approaching"
            else request
        )

    def wrap_tool_call(self, request, handler):
        self._check()
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        self._check()
        return await handler(request)


__all__ = ["TokenBudgetMiddleware"]

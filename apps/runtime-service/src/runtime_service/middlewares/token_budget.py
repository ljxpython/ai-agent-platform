"""Run token decisions layered on the existing usage and budget notices."""

from __future__ import annotations

import os
from contextvars import copy_context
from typing import Literal

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, ToolMessage

from runtime_service.errors import TokenBudgetUnverifiableError
from runtime_service.middlewares.execution_budget import add_wrapup_instruction
from runtime_service.observability.usage import current_runtime_usage_callback
from runtime_service.runtime.token_budget import token_budget_enabled

TOKEN_BUDGET_EXHAUSTED_WRAPUP_NOTICE = (
    "\n\n⚠️ Token 额度已达到运行预算上限，已安全停止后续工具调用与额外执行。"
    "以上为当前已完成的执行和分析成果。"
)


class TokenBudgetMiddleware(AgentMiddleware):
    def __init__(
        self,
        *,
        root: bool = True,
        writer=None,
        exit_behavior: Literal["end", "error"] | None = None,
    ):
        super().__init__()
        self.root = root
        self.writer = writer
        resolved_exit = (
            exit_behavior
            or os.getenv("RUNTIME_TOKEN_BUDGET_EXIT_BEHAVIOR", "error").strip().lower()
        )
        self.exit_behavior: Literal["end", "error"] = (
            "end" if resolved_exit == "end" else "error"
        )

    def before_agent(self, state, runtime):
        usage = current_runtime_usage_callback()
        if self.root and usage is not None and usage.token_budget is not None:
            context = copy_context()
            writer = self.writer or runtime.stream_writer
            usage.bind_budget_writer(lambda notice: context.run(writer, notice))

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    def _check(self, *, optional: bool = False) -> str:
        usage = current_runtime_usage_callback()
        if usage is not None:
            return usage.check_budget(optional=optional)
        if token_budget_enabled():
            raise TokenBudgetUnverifiableError()
        return "ok"

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):
        if self.exit_behavior != "end":
            return None
        usage = current_runtime_usage_callback()
        if usage is not None and usage.token_budget is not None:
            status = usage.check_budget(optional=True)
            if status == "exhausted":
                msg = AIMessage(
                    content=(
                        "⚠️ 本次任务 Token 消耗已达到运行预算上限。已停止新的模型调用与工具执行，"
                        "请检查当前已完成的输出成果。"
                    )
                )
                return {"jump_to": "end", "messages": [msg]}
        return None

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state, runtime):
        return self.before_model(state, runtime)

    def wrap_model_call(self, request, handler):
        if self.exit_behavior == "end":
            status = self._check(optional=True)
            req = (
                add_wrapup_instruction(request) if status == "approaching" else request
            )
            response = handler(req)
            usage = current_runtime_usage_callback()
            if usage is not None and usage.token_budget is not None:
                post_status = usage.check_budget(optional=True)
                if post_status == "exhausted" and isinstance(response, AIMessage):
                    if response.tool_calls:
                        return response.model_copy(
                            update={
                                "tool_calls": [],
                                "content": (
                                    (
                                        str(response.content or "")
                                        + TOKEN_BUDGET_EXHAUSTED_WRAPUP_NOTICE
                                    ).strip()
                                ),
                            }
                        )
            return response

        # exit_behavior == "error": traditional rigid check
        return handler(
            add_wrapup_instruction(request)
            if self._check(optional=False) == "approaching"
            else request
        )

    async def awrap_model_call(self, request, handler):
        if self.exit_behavior == "end":
            status = self._check(optional=True)
            req = (
                add_wrapup_instruction(request) if status == "approaching" else request
            )
            response = await handler(req)
            usage = current_runtime_usage_callback()
            if usage is not None and usage.token_budget is not None:
                post_status = usage.check_budget(optional=True)
                if post_status == "exhausted" and isinstance(response, AIMessage):
                    if response.tool_calls:
                        return response.model_copy(
                            update={
                                "tool_calls": [],
                                "content": (
                                    (
                                        str(response.content or "")
                                        + TOKEN_BUDGET_EXHAUSTED_WRAPUP_NOTICE
                                    ).strip()
                                ),
                            }
                        )
            return response

        return await handler(
            add_wrapup_instruction(request)
            if self._check(optional=False) == "approaching"
            else request
        )

    def wrap_tool_call(self, request, handler):
        if self.exit_behavior == "end":
            usage = current_runtime_usage_callback()
            if usage is not None and usage.token_budget is not None:
                if usage.check_budget(optional=True) == "exhausted":
                    tool_call = (
                        request.tool_call if isinstance(request.tool_call, dict) else {}
                    )
                    return ToolMessage(
                        content="⚠️ Token 预算已达上限，已安全停止执行后续工具调用。",
                        tool_call_id=str(tool_call.get("id", "blocked")),
                        name=str(tool_call.get("name", "")),
                    )
        self._check(optional=False)
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        if self.exit_behavior == "end":
            usage = current_runtime_usage_callback()
            if usage is not None and usage.token_budget is not None:
                if usage.check_budget(optional=True) == "exhausted":
                    tool_call = (
                        request.tool_call if isinstance(request.tool_call, dict) else {}
                    )
                    return ToolMessage(
                        content="⚠️ Token 预算已达上限，已安全停止执行后续工具调用。",
                        tool_call_id=str(tool_call.get("id", "blocked")),
                        name=str(tool_call.get("name", "")),
                    )
        self._check(optional=False)
        return await handler(request)


__all__ = ["TokenBudgetMiddleware", "TOKEN_BUDGET_EXHAUSTED_WRAPUP_NOTICE"]

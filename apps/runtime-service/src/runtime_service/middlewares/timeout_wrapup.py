"""Best-effort model wrapup before the Worker's shared hard deadline."""

from __future__ import annotations

from time import monotonic

from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain_core.messages import SystemMessage

from runtime_service.runtime.run_budget import RunBudget

TIMEOUT_WRAPUP_INSTRUCTION = (
    "The current run is nearing its execution deadline. Stop starting new investigations "
    "or long-running work and wrap up now. Report completed work, unfinished work, "
    "verified artifact paths, and any necessary next steps. Preserve progress only through "
    "available authorized actions. Keep all approval and permission requirements. "
    "Do not claim unverified writes, remote actions, or a complete result succeeded."
)


class TimeoutWrapupMiddleware(AgentMiddleware):
    def __init__(self, budget: RunBudget | None) -> None:
        super().__init__()
        self.budget = budget

    async def awrap_model_call(self, request: ModelRequest, handler):
        if (
            self.budget is None
            or self.budget.wrapup_reserve_seconds == 0
            or monotonic() < self.budget.soft_deadline_monotonic
        ):
            return await handler(request)
        original = request.system_message
        blocks = (
            list(original.content)
            if original is not None and isinstance(original.content, list)
            else [{"type": "text", "text": original.content}]
            if original is not None
            else []
        )
        if not any(
            TIMEOUT_WRAPUP_INSTRUCTION
            in (block if isinstance(block, str) else block.get("text", ""))
            for block in blocks
        ):
            blocks.append({"type": "text", "text": TIMEOUT_WRAPUP_INSTRUCTION})
            system_message = (
                original.model_copy(update={"content": blocks})
                if original is not None
                else SystemMessage(content=blocks)
            )
            request = request.override(system_message=system_message)
        return await handler(request)

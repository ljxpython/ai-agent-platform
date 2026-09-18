from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from runtime_service.runtime.errors import RuntimeResolutionError

ModeName = Literal["flash", "standard", "pro", "ultra"]


@dataclass(frozen=True)
class AgentMode:
    name: ModeName
    planning: bool
    delegation: bool
    reasoning_effort: str | None
    model_limit: int
    tool_limit: int


MODES: dict[ModeName, AgentMode] = {
    "flash": AgentMode("flash", False, False, None, 24, 50),
    "standard": AgentMode("standard", False, False, None, 50, 100),
    "pro": AgentMode("pro", True, False, "medium", 100, 200),
    "ultra": AgentMode("ultra", True, True, "high", 200, 500),
}


def resolve_mode(value: str | None) -> AgentMode:
    if value is not None and value not in MODES:
        raise RuntimeResolutionError("runtime.context.invalid_value", "execution_mode")
    return MODES[value or "standard"]


def apply_reasoning(model, mode: AgentMode):
    """Only set parameters for an explicitly supported provider/model family."""
    from langchain_deepseek import ChatDeepSeek
    name = str(getattr(model, "model_name", "")).lower()
    if mode.name == "standard":
        return model, {"reasoning": "model_default"}
    if isinstance(model, ChatDeepSeek) and name.startswith("deepseek-v4"):
        applied = {"thinking": {"type": "disabled" if mode.name == "flash" else "enabled"}}
        if mode.reasoning_effort:
            applied["reasoning_effort"] = mode.reasoning_effort
        return model.model_copy(update={"extra_body": {**(model.extra_body or {}), **applied}}), {"reasoning": applied}
    return model, {"reasoning": "model_default", "reason": "model_reasoning_control_not_supported"}

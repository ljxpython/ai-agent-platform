"""Only stable codes leave the Runtime; no Thread metadata or provider text is used."""

from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langgraph.errors import GraphRecursionError

from runtime_service.observability.errors import MODEL_ERROR_CODES, is_control_flow
from runtime_service.runtime.errors import WORKSPACE_ERROR_CODES, RuntimeErrorBase

MODEL_FAILURE_CODES = frozenset(
    {
        "runtime.model.retry_exhausted",
        "runtime.model.retry_budget_exceeded",
        "runtime.model.stream_interrupted",
        "runtime.model.provider_rejected",
        "runtime.model.fallback_incompatible",
    }
)


def project_terminal_outcome(exc: BaseException) -> dict[str, str | None]:
    if is_control_flow(exc):
        return {}
    for kind, code in (
        (GraphRecursionError, "runtime_graph_step_limit_reached"),
        (ModelCallLimitExceededError, "runtime_model_call_limit_reached"),
        (ToolCallLimitExceededError, "runtime_tool_call_limit_reached"),
    ):
        if isinstance(exc, kind):
            return {"reason_code": code, "model_error_code": None}
    code = getattr(exc, "code", None)
    if code in WORKSPACE_ERROR_CODES or code in MODEL_FAILURE_CODES:
        model = getattr(exc, "model_error_code", None)
        return {
            "reason_code": code,
            "model_error_code": model if model in MODEL_ERROR_CODES else None,
        }
    if isinstance(exc, RuntimeErrorBase) and code in MODEL_ERROR_CODES:
        return {"reason_code": "runtime_execution_failed", "model_error_code": code}
    return {"reason_code": "runtime_execution_failed", "model_error_code": None}

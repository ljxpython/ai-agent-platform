"""Workflow StateGraph topology around the model-backed Agent."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Literal

from langchain_core.runnables.config import var_child_runnable_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from runtime_service.runtime.contracts import RuntimeContext
from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.services.demo.workflow_demo.schemas import WorkflowState


def _message_text(value: object) -> str:
    if isinstance(value, Mapping):
        content = value.get("content")
    else:
        content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, Mapping) and isinstance(block.get("text"), str)
        )
    return "" if content is None else str(content)


def _is_user_message(value: object) -> bool:
    if isinstance(value, Mapping):
        return value.get("type") in {"human", "user"} or value.get("role") in {
            "human",
            "user",
        }
    return getattr(value, "type", None) in {"human", "user"} or getattr(
        value, "role", None
    ) in {"human", "user"}


def _requires_confirmation(message: str) -> bool:
    """Expose a stable browser-triggerable HITL path for this demo graph."""
    return "需要人工确认" in message


def prepare(state: WorkflowState) -> dict[str, object]:
    message = state.get("message", "").strip()
    for candidate in reversed(state.get("messages", [])):
        if _is_user_message(candidate):
            latest_message = _message_text(candidate).strip()
            if latest_message:
                message = latest_message
                break
    return {
        "prepared_count": state.get("prepared_count", 0) + 1,
        "message": message,
        "requires_confirmation": bool(state.get("requires_confirmation"))
        or _requires_confirmation(message),
    }


def confirm(state: WorkflowState) -> dict[str, object]:
    decision = interrupt(
        {
            "kind": "workflow_confirmation",
            "message": state["message"],
            "action_requests": [
                {
                    "name": "workflow_confirmation",
                    "args": {"message": state["message"]},
                }
            ],
            "review_configs": [
                {
                    "action_name": "workflow_confirmation",
                    "allowed_decisions": ["approve", "reject"],
                }
            ],
            "error": state.get("resume_error"),
        }
    )

    # The web HITL panel resumes with {decisions: [{type: ...}]}; keep the
    # string form for local/runtime compatibility tests and direct callers.
    if isinstance(decision, str):
        normalized_decision = decision
    elif isinstance(decision, Mapping):
        decisions = decision.get("decisions")
        first_decision = decisions[0] if isinstance(decisions, list) and decisions else None
        normalized_decision = (
            first_decision.get("type")
            if isinstance(first_decision, Mapping)
            else ""
        )
    else:
        normalized_decision = ""

    if normalized_decision not in {"approve", "reject"}:
        return {"resume_error": "workflow.invalid_resume"}
    model_ref = decision.get("_runtime_model_ref") if isinstance(decision, Mapping) else None
    result: dict[str, object] = {
        "confirmation": normalized_decision,
        "resume_error": None,
    }
    if isinstance(model_ref, str) and model_ref:
        result["_runtime_model_ref"] = model_ref
    return result


def select_route(state: WorkflowState) -> dict[str, Literal["approve", "reject", "respond"]]:
    return {"route": state.get("confirmation") or state.get("route", "respond")}


def choose_route(state: WorkflowState) -> Literal["approve", "reject", "respond"]:
    return state["route"]


def after_confirm(state: WorkflowState) -> Literal["confirm", "route"]:
    return "confirm" if state.get("resume_error") else "route"


def approve(state: WorkflowState) -> dict[str, object]:
    return {"confirmation": "approve"}


def reject(state: WorkflowState) -> dict[str, object]:
    return {"confirmation": "reject"}


def build_graph(
    model_agent: Callable[[WorkflowState], Awaitable[object]],
    *,
    model_config: Mapping[str, object] | None = None,
    runtime_context: RuntimeContext | None = None,
    probe_only: bool = False,
):
    async def respond(state: WorkflowState, runtime) -> dict[str, object]:
        messages = state.get("messages", [])
        if not messages and state.get("message"):
            messages = [{"role": "user", "content": state["message"]}]
        invoke_config = dict(model_config or {})
        current_config = var_child_runnable_config.get() or {}
        invoke_config.update(current_config)
        if model_config is not None:
            configurable = dict(model_config.get("configurable") or {})
            configurable.update(current_config.get("configurable") or {})
            invoke_config["configurable"] = configurable
        result = await (await model_agent(state)).ainvoke(  # type: ignore[attr-defined]
            {"messages": messages},
            config=invoke_config,
            # The outer GraphHarbor runtime may omit Context when entering a
            # nested graph. Keep the signed, resolved context for the inner
            # model middleware so its context hash remains consistent.
            context=runtime_context or runtime.context,
        )
        response_message = result["messages"][-1]
        response = _message_text(response_message).strip()
        return {"response": response, "messages": [response_message]}

    def after_prepare(state: WorkflowState) -> Literal["confirm", "route"]:
        return "confirm" if state.get("requires_confirmation", False) else "route"

    def unavailable_node(state: WorkflowState) -> dict[str, object]:
        raise RuntimeAuthError("runtime.graph.probe_only")

    graph = StateGraph(WorkflowState, context_schema=RuntimeContext)
    for name, node in (
        ("prepare", prepare), ("confirm", confirm), ("route", select_route),
        ("approve", approve), ("reject", reject), ("respond", respond),
    ):
        graph.add_node(name, unavailable_node if probe_only else node)
    graph.add_edge(START, "prepare")
    graph.add_conditional_edges(
        "prepare",
        after_prepare,
        {"confirm": "confirm", "route": "route"},
    )
    graph.add_conditional_edges(
        "confirm",
        after_confirm,
        {"confirm": "confirm", "route": "route"},
    )
    graph.add_conditional_edges(
        "route",
        choose_route,
        {"approve": "approve", "reject": "reject", "respond": "respond"},
    )
    graph.add_edge("approve", "respond")
    graph.add_edge("reject", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=InMemorySaver())

"""Plan tools only mutate checkpoint state; approval is a native interrupt."""

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command, interrupt

from runtime_service.observability.diagnostics import log_diagnostic
from runtime_service.observability.langfuse import record_diagnostic_event
from runtime_service.runtime.auth import verified_delegation_from_user
from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.runtime.planning import (
    PlanSnapshot,
    apply_plan_reply,
    bound_plan,
    new_plan,
    plan_content_hash,
    plan_interrupt,
    read_plan,
    validate_plan_text,
)
from runtime_service.runtime.resolver import parse_runtime_context


def _update(plan: PlanSnapshot, runtime: ToolRuntime, message: str) -> Command:
    server = runtime.server_info
    if server is not None:
        facts = verified_delegation_from_user(server.user)
        info = runtime.execution_info
        fields = {
            "tenant_id": facts.principal.tenant_id,
            "project_id": facts.principal.project_id,
            "thread_id": info.thread_id,
            "run_id": info.run_id,
            "request_id": facts.request_id,
            "platform_trace_id": facts.platform_trace_id,
            "plan_id": plan.plan_id,
            "revision": plan.revision,
            "content_hash": plan.content_hash,
            "actor_id": facts.principal.user_id,
            "decision": plan.decision.decision if plan.decision else None,
            "outcome": "prepared",
        }
        log_diagnostic("runtime.plan.transition_prepared", fields)
        record_diagnostic_event("runtime.plan.transition_prepared", fields)
    return Command(
        update={
            "runtime_plan": plan.model_dump(),
            "messages": [
                ToolMessage(content=message, tool_call_id=runtime.tool_call_id)
            ],
        }
    )


@tool
def enter_plan_mode(runtime: ToolRuntime) -> Command:
    """Enter planning before business writes. Save and submit a plan for human review."""
    context = parse_runtime_context(runtime.context)
    current = read_plan(runtime.state)
    plan = (
        current
        if current
        and current.active
        and current.bound_execution_id == context.plan_execution_id
        else new_plan(context.plan_execution_id)
    )
    return _update(
        plan,
        runtime,
        "Planning restriction is active. Research, save_plan, then submit_plan for human review.",
    )


@tool
def save_plan(title: str, markdown: str, runtime: ToolRuntime) -> Command:
    """Save a Markdown plan draft in checkpoint state without writing workspace files."""
    plan = bound_plan(runtime.state, runtime.context)
    if not plan.active:
        raise RuntimeResolutionError("runtime.plan.state_invalid")
    title, markdown = title.strip(), markdown.replace("\r\n", "\n").replace("\r", "\n")
    validate_plan_text(title, markdown)
    if (title, markdown) != (plan.title, plan.markdown):
        plan = plan.model_copy(
            update={
                "title": title,
                "markdown": markdown,
                "revision": plan.revision + 1,
                "decision": None,
                "approved_by": None,
                "approved_at": None,
            }
        )
        plan.content_hash = plan_content_hash(plan)
    return _update(
        plan,
        runtime,
        f"Plan draft saved at revision {plan.revision}. Submit it for human review before execution.",
    )


@tool
def submit_plan(runtime: ToolRuntime) -> Command:
    """Pause on a saved plan. Only the authenticated human reply can approve execution."""
    plan = bound_plan(runtime.state, runtime.context)
    if not plan.active or plan.revision == 0 or plan.decision is not None:
        raise RuntimeResolutionError("runtime.plan.state_invalid")
    reply = interrupt(plan_interrupt(plan))
    server = runtime.server_info
    facts = verified_delegation_from_user(None if server is None else server.user)
    if facts.credential_id is not None:
        raise RuntimeResolutionError("runtime.plan.response_invalid")
    plan = apply_plan_reply(plan, reply, facts.principal.user_id)
    message = {
        "approve": "Plan approved. Continue under the original execution mode and tool approval policy.",
        "request_changes": "Plan changes requested. Keep planning restrictions and revise the draft. Feedback: "
        + (plan.decision.feedback or ""),
        "abandon": "Plan abandoned. This run ends and planning restrictions remain active.",
    }[plan.decision.decision]
    return _update(plan, runtime, message)


PLAN_TOOLS = (enter_plan_mode, save_plan, submit_plan)

# pyright: reportMissingImports=false, reportMissingModuleSource=false
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from graph_src_v2.devtools.multimodal_frontend_compat import build_human_message_from_paths
from graph_src_v2.middlewares.multimodal import MultimodalMiddleware
from graph_src_v2.runtime.modeling import apply_model_runtime_params, resolve_model
from graph_src_v2.runtime.options import build_runtime_config, merge_trusted_auth_context
from graph_src_v2.services.usecase_workflow_agent.graph import (
    SYSTEM_PROMPT,
    UsecaseWorkflowState,
    WorkflowToolSelectionMiddleware,
    _bind_non_streaming_model,
)
from graph_src_v2.services.usecase_workflow_agent.tools import (
    build_usecase_workflow_tools,
)


def _load_first_pdf_message() -> Any:
    test_data_dir = Path(__file__).resolve().parents[1] / "test_data"

    try:
        pdf_path = next(test_data_dir.glob("*.pdf"))
    except StopIteration as exc:
        raise FileNotFoundError(f"No PDF found in {test_data_dir}") from exc

    return build_human_message_from_paths(
        "请分析这个 PDF 的需求内容，先告诉我你看到了什么，不要持久化。",
        [pdf_path],
    )


async def _build_local_agent(config: RunnableConfig) -> Any:
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)
    model = _bind_non_streaming_model(model)
    tools = build_usecase_workflow_tools(model)
    system_prompt = options.system_prompt or SYSTEM_PROMPT

    # This debug REPL builds the agent locally with MemorySaver so Command(resume=...)
    # can continue the same thread after a local interrupt.
    return create_agent(
        model=model,
        name="usecase_workflow_agent",
        tools=tools,
        middleware=[
            WorkflowToolSelectionMiddleware(),
            MultimodalMiddleware(),
        ],
        system_prompt=system_prompt,
        state_schema=UsecaseWorkflowState,
        checkpointer=MemorySaver(),
    )


def _chunk_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _extract_interrupt(update: Any) -> Any | None:
    if isinstance(update, dict) and "__interrupt__" in update:
        return update["__interrupt__"]
    return None


def _interrupt_value(interrupt: Any) -> dict[str, Any]:
    value = getattr(interrupt, "value", None)
    return value if isinstance(value, dict) else {}


def _interrupt_action_name(interrupts: Any) -> str:
    if not isinstance(interrupts, list | tuple):
        return "persist_approved_usecases"
    for interrupt in interrupts:
        for action_request in _interrupt_value(interrupt).get("action_requests", []):
            action_name = action_request.get("name")
            if isinstance(action_name, str) and action_name:
                return action_name
    return "persist_approved_usecases"


def _interrupt_allowed_decisions(interrupts: Any) -> list[str]:
    if not isinstance(interrupts, list | tuple):
        return ["approve", "edit", "reject"]
    for interrupt in interrupts:
        for review_config in _interrupt_value(interrupt).get("review_configs", []):
            decisions = review_config.get("allowed_decisions")
            if (
                isinstance(decisions, list)
                and decisions
                and all(isinstance(item, str) and item for item in decisions)
            ):
                return list(decisions)
    return ["approve", "edit", "reject"]


def _print_interrupt_details(interrupts: Any) -> None:
    if not isinstance(interrupts, list | tuple):
        print("interrupt payload is not a list/tuple:", interrupts)
        return

    for index, interrupt in enumerate(interrupts, start=1):
        value = _interrupt_value(interrupt)
        print(f"interrupt[{index}]")
        action_requests = value.get("action_requests")
        if isinstance(action_requests, list):
            for action_index, action_request in enumerate(action_requests, start=1):
                print(
                    f"  action[{action_index}]",
                    json.dumps(action_request, ensure_ascii=False, indent=2),
                )
        review_configs = value.get("review_configs")
        if isinstance(review_configs, list):
            for review_index, review_config in enumerate(review_configs, start=1):
                print(
                    f"  review[{review_index}]",
                    json.dumps(review_config, ensure_ascii=False, indent=2),
                )


def _build_free_text_turn_status() -> dict[str, Any]:
    return {
        "needs_user_input": True,
        "input_mode": "free_text",
        "interrupts": None,
        "allowed_decisions": [],
        "action_name": None,
    }


def _build_interrupt_turn_status(interrupts: Any) -> dict[str, Any]:
    return {
        "needs_user_input": True,
        "input_mode": "interrupt_decision",
        "interrupts": interrupts,
        "allowed_decisions": _interrupt_allowed_decisions(interrupts),
        "action_name": _interrupt_action_name(interrupts),
    }


def _print_turn_status(turn_status: dict[str, Any]) -> None:
    if turn_status.get("input_mode") == "interrupt_decision":
        print(
            "turn_status",
            {
                "needs_user_input": True,
                "input_mode": "interrupt_decision",
                "allowed_decisions": turn_status.get("allowed_decisions", []),
                "action_name": turn_status.get("action_name"),
            },
        )
        return
    print(
        "turn_status",
        {
            "needs_user_input": True,
            "input_mode": "free_text",
        },
    )


async def _stream_turn(agent: Any, payload: Any, config: RunnableConfig) -> dict[str, Any]:
    saw_stream_text = False

    async for mode, event in agent.astream(
        payload,
        config=config,
        stream_mode=["messages", "updates"],
    ):
        if mode == "messages":
            message, _metadata = event
            text = _chunk_text(getattr(message, "content", ""))
            if text:
                if not saw_stream_text:
                    print("stream", end=" ", flush=True)
                    saw_stream_text = True
                print(text, end="", flush=True)
            continue

        if saw_stream_text:
            print()
            saw_stream_text = False

        print("update", event)
        interrupts = _extract_interrupt(event)
        if interrupts is not None:
            _print_interrupt_details(interrupts)
            turn_status = _build_interrupt_turn_status(interrupts)
            _print_turn_status(turn_status)
            return turn_status

    if saw_stream_text:
        print()

    turn_status = _build_free_text_turn_status()
    _print_turn_status(turn_status)
    return turn_status


def _build_interrupt_resume_payload(
    decision: str,
    feedback: str = "",
    action_name: str = "persist_approved_usecases",
) -> dict[str, Any]:
    if decision == "edit":
        feedback_text = feedback.strip()
        if not feedback_text:
            raise ValueError("edit feedback is required")
        return {
            "decisions": [
                {
                    "type": "edit",
                    "edited_action": {
                        "name": action_name,
                        "args": {"revision_feedback": feedback_text},
                    },
                }
            ]
        }
    if decision == "reject":
        reason = feedback.strip()
        if reason:
            return {"decisions": [{"type": "reject", "message": reason}]}
    return {"decisions": [{"type": decision}]}


def _prompt_interrupt_decision(allowed_decisions: list[str]) -> tuple[str, str]:
    allowed = [decision for decision in allowed_decisions if isinstance(decision, str)]
    prompt = " | ".join([*allowed, "quit"]) if allowed else "approve | edit | reject | quit"

    while True:
        decision = input("you ").strip().lower()
        if decision == "quit":
            return decision, ""
        if decision not in allowed:
            print(f"interrupt {prompt}")
            continue
        if decision == "edit":
            feedback = input("edit feedback ").strip()
            if feedback:
                return decision, feedback
            print("edit feedback required")
            continue
        if decision == "reject":
            feedback = input("reject reason (optional) ").strip()
            return decision, feedback
        return decision, ""


async def _run_repl() -> None:
    thread_id = str(uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    agent = await _build_local_agent(config)

    first_message = _load_first_pdf_message()
    turn_status = await _stream_turn(agent, {"messages": [first_message]}, config)

    while True:
        if turn_status.get("input_mode") == "interrupt_decision":
            decision, feedback = _prompt_interrupt_decision(
                list(turn_status.get("allowed_decisions") or [])
            )
            if decision == "quit":
                return
            turn_status = await _stream_turn(
                agent,
                Command(
                    resume=_build_interrupt_resume_payload(
                        decision,
                        feedback,
                        action_name=str(turn_status.get("action_name") or "persist_approved_usecases"),
                    )
                ),
                config,
            )
            continue

        user_text = input("you ").strip()
        if not user_text:
            continue
        if user_text.lower() == "quit":
            return

        turn_status = await _stream_turn(agent, {"messages": [user_text]}, config)


def graph_local() -> None:
    asyncio.run(_run_repl())


if __name__ == "__main__":
    graph_local()

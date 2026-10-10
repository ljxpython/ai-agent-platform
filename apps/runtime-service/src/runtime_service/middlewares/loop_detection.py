"""Bounded, checkpointed protection against consecutive identical read batches."""

from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Annotated, Any, NotRequired
from uuid import uuid4

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.config import get_config

from runtime_service.middlewares.conversation_offloading import (
    is_conversation_maintenance,
)
from runtime_service.middlewares.execution_budget import (
    add_wrapup_instruction,
    build_budget_notice,
    emit_budget_notice,
)
from runtime_service.observability.diagnostics import log_diagnostic
from runtime_service.observability.langfuse import record_diagnostic_event
from runtime_service.runtime.errors import RuntimeExecutionError

READ_TOOLS = frozenset({"ls", "read_file", "glob", "grep", "read_reference"})
WARN_THRESHOLD = 3
HARD_LIMIT = 5
MAX_MESSAGES = 64
MAX_CALLS = 32
MAX_TEXT = 65536
MAX_BATCH_TEXT = 262144


class LoopDetectionState(AgentState):
    runtime_loop_state: NotRequired[Annotated[dict[str, Any], PrivateStateAttr]]


def loop_detection_enabled() -> bool:
    value = os.getenv("AGENT_LOOP_DETECTION_ENABLED", "0")
    if value not in {"0", "1"}:
        raise ValueError("AGENT_LOOP_DETECTION_ENABLED must be 0 or 1")
    return value == "1"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode(errors="surrogatepass")).hexdigest()


def _message_id(message) -> str | None:
    return _hash(message.id) if isinstance(message.id, str) and message.id else None


def _json_signature(args: dict) -> str | None:
    pending, visited = [(args, 0)], 0
    while pending:
        value, depth = pending.pop()
        visited += 1
        if visited > 1024 or depth > 16:
            return None
        if isinstance(value, dict):
            if len(value) > 1024 or any(type(key) is not str for key in value):
                return None
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            if len(value) > 1024:
                return None
            pending.extend((item, depth + 1) for item in value)
        elif type(value) not in (str, int, float, bool, type(None)) or (
            type(value) is float and not math.isfinite(value)
        ):
            return None
        elif isinstance(value, str) and len(value) > 16384:
            return None
    try:
        encoded = json.dumps(
            args, sort_keys=True, allow_nan=False, separators=(",", ":")
        )
        return _hash(encoded) if len(encoded) <= 16384 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _result_text(message: ToolMessage) -> str | None:
    content = message.content
    if (
        not isinstance(content, str)
        or len(content) > MAX_TEXT
        or message.artifact is not None
        or message.additional_kwargs.get("lc_evicted_to")
        or message.additional_kwargs.get("_runtime_tool_call_repaired")
        or any(
            marker in content
            for marker in (
                "Tool result too large, the result of this tool call ",
                "[Output was truncated",
                "[results truncated",
                "Note: the search stopped early",
            )
        )
    ):
        return None
    return content


# Only inspect the tail: missing or oversized evidence must not cause a hard stop.
def _completed_batch(messages, observed_tools) -> tuple[str, str] | None:
    results = {}
    ai = None
    for message in reversed(messages[-MAX_MESSAGES:]):
        if isinstance(message, ToolMessage):
            if message.tool_call_id in results or len(results) >= MAX_CALLS:
                return None
            results[message.tool_call_id] = message
        elif isinstance(message, AIMessage):
            ai = message
            break
        else:
            return None
    if ai is None or ai.invalid_tool_calls or not 0 < len(ai.tool_calls) <= MAX_CALLS:
        return None
    cursor = _message_id(ai)
    ids = [call.get("id") for call in ai.tool_calls]
    if not cursor or len(set(ids)) != len(ids) or set(ids) != set(results):
        return None
    rows, text_size = [], 0
    for call in ai.tool_calls:
        name, args = call.get("name"), call.get("args")
        if name not in observed_tools or not isinstance(args, dict):
            return None
        args = {"offset": 0, "limit": 100, **args} if name == "read_file" else args
        args_hash = _json_signature(args)
        result = results[call["id"]]
        text = _result_text(result)
        if (
            args_hash is None
            or text is None
            or result.status not in {"success", "error"}
        ):
            return None
        if result.name is not None and result.name != name:
            return None
        text_size += len(text)
        if text_size > MAX_BATCH_TEXT:
            return None
        rows.append((name, args_hash, result.status, _hash(text)))
    return cursor, _hash(json.dumps(sorted(rows), separators=(",", ":")))


def _last_user(messages) -> str | None:
    return next(
        (
            _message_id(message)
            for message in reversed(messages[-MAX_MESSAGES:])
            if isinstance(message, HumanMessage)
            and message.additional_kwargs.get("lc_source") != "summarization"
        ),
        None,
    )


def _graph_namespace(config) -> str:
    namespace = str((config.get("configurable") or {}).get("checkpoint_ns", ""))
    return namespace.rpartition("|")[0]


class LoopDetectionMiddleware(AgentMiddleware):
    state_schema = LoopDetectionState

    def __init__(
        self, tool_names, *, scope="primary", graph_key="agent", metadata=None
    ):
        self.observed_tools = READ_TOOLS.intersection(tool_names)
        self.scope = scope
        self.graph_key = graph_key
        self.metadata = dict(metadata or {})

    def _owner(self, runtime, config) -> str | None:
        info = runtime.execution_info
        run_id = (getattr(info, "run_id", None) if info else None) or (
            config.get("metadata") or {}
        ).get("run_id")
        return (
            _hash(f"{run_id}:{self.graph_key}:{_graph_namespace(config)}")
            if run_id
            else None
        )

    def before_agent(self, state, runtime):
        if is_conversation_maintenance(runtime):
            return None
        owner = self._owner(runtime, get_config())
        previous = state.get("runtime_loop_state", {})
        if owner is not None and previous.get("owner") == owner:
            return None
        messages = state.get("messages", [])
        completed = _completed_batch(messages, self.observed_tools)
        return {
            "runtime_loop_state": {
                "owner": owner or uuid4().hex,
                "cursor": completed[0]
                if completed
                else _message_id(messages[-1])
                if messages
                else None,
                "user": _last_user(messages),
                "signature": None,
                "sequence": None,
                "repetitions": 0,
            }
        }

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    def _transition(self, marker, runtime, config):
        repetitions = marker["repetitions"]
        code = (
            "tool_loop_reached"
            if repetitions == HARD_LIMIT
            else "tool_loop_approaching"
        )
        emit_budget_notice(
            build_budget_notice(
                code=code,
                budget_scope="run",
                unit="tool_rounds",
                scope=self.scope,
                graph_key=f"{self.graph_key}:{marker['sequence']}",
                limit=HARD_LIMIT,
                used=repetitions,
                remaining=HARD_LIMIT - repetitions,
            ),
            runtime,
        )
        fields = {
            **self.metadata,
            "run_id": (config.get("metadata") or {}).get("run_id"),
            "scope": self.scope,
            "namespace": _graph_namespace(config).split("|")
            if _graph_namespace(config)
            else [],
            "code": code,
            "repetitions": repetitions,
            "threshold": repetitions,
        }
        log_diagnostic("runtime.loop.transition", fields)
        try:
            record_diagnostic_event("runtime.loop.transition", fields)
        except Exception:
            pass

    def before_model(self, state, runtime):
        if is_conversation_maintenance(runtime):
            return None
        config = get_config()
        marker = dict(state.get("runtime_loop_state", {}))
        owner = self._owner(runtime, config)
        if not marker or owner is not None and marker.get("owner") != owner:
            return self.before_agent(state, runtime)
        messages = state.get("messages", [])
        user = _last_user(messages)
        if user is not None and user != marker.get("user"):
            marker.update(user=user, signature=None, sequence=None, repetitions=0)
        batch = _completed_batch(messages, self.observed_tools)
        if batch is None:
            marker.update(signature=None, sequence=None, repetitions=0)
        elif batch[0] != marker.get("cursor"):
            cursor, signature = batch
            repeated = signature == marker.get("signature")
            marker.update(
                cursor=cursor,
                signature=signature,
                sequence=marker.get("sequence") if repeated else cursor,
                repetitions=marker["repetitions"] + 1 if repeated else 1,
            )
            if marker["repetitions"] in {WARN_THRESHOLD, HARD_LIMIT}:
                self._transition(marker, runtime, config)
        if marker["repetitions"] >= HARD_LIMIT:
            raise RuntimeExecutionError("runtime.loop.detected")
        return (
            {"runtime_loop_state": marker}
            if marker != state.get("runtime_loop_state")
            else None
        )

    async def abefore_model(self, state, runtime):
        return self.before_model(state, runtime)

    def wrap_model_call(self, request, handler):
        warned = (
            request.state.get("runtime_loop_state", {}).get("repetitions", 0)
            >= WARN_THRESHOLD
        )
        return handler(add_wrapup_instruction(request) if warned else request)

    async def awrap_model_call(self, request, handler):
        warned = (
            request.state.get("runtime_loop_state", {}).get("repetitions", 0)
            >= WARN_THRESHOLD
        )
        return await handler(add_wrapup_instruction(request) if warned else request)


__all__ = ["LoopDetectionMiddleware", "LoopDetectionState", "loop_detection_enabled"]

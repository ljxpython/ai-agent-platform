"""Runtime contract enforcement at LangChain model and tool boundaries."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ToolCallRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, RemoveMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from runtime_service.runtime import (
    AgentDefaults,
    ResolvedRuntimeConfig,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    build_model,
    parse_runtime_context,
    resolve_runtime_config,
    runtime_context_hash,
    verified_delegation_from_user,
)
from runtime_service.runtime.auth import VerifiedDelegation
from runtime_service.runtime.errors import RuntimeAuthError, RuntimeResolutionError

ModelBuilder = Callable[[ResolvedRuntimeConfig], BaseChatModel]


def _tool_name(tool: BaseTool | Callable[..., object] | dict[str, object]) -> str | None:
    if isinstance(tool, dict):
        value = tool.get("name")
    else:
        value = getattr(tool, "name", None) or getattr(tool, "__name__", None)
    return value if isinstance(value, str) else None


def _is_synthetic_cancelled_tool_message(msg: ToolMessage) -> bool:
    content = getattr(msg, "content", None)
    return isinstance(content, str) and (
        "was cancelled" in content or "could not be executed" in content
    )


def _normalize_ai_message_tool_calls(
    msg: AIMessage,
) -> tuple[AIMessage, list[tuple[str, str, bool]]]:
    """Ensure AIMessage only carries tool calls with valid string IDs and return (tc_id, name, is_invalid)."""
    valid_tool_calls: list[dict[str, Any]] = []
    valid_invalid_calls: list[dict[str, Any]] = []
    extracted: list[tuple[str, str, bool]] = []
    seen_ids: set[str] = set()
    mutated = False

    for tc in getattr(msg, "tool_calls", None) or ():
        tc_id = tc.get("id") if isinstance(tc, Mapping) else getattr(tc, "id", None)
        tc_name = (
            (tc.get("name") if isinstance(tc, Mapping) else getattr(tc, "name", None))
            or "unknown"
        )
        if isinstance(tc_id, str) and tc_id.strip():
            valid_tool_calls.append(tc)
            if tc_id not in seen_ids:
                seen_ids.add(tc_id)
                extracted.append((tc_id, str(tc_name), False))
        else:
            mutated = True

    for tc in getattr(msg, "invalid_tool_calls", None) or ():
        tc_id = tc.get("id") if isinstance(tc, Mapping) else getattr(tc, "id", None)
        tc_name = (
            (tc.get("name") if isinstance(tc, Mapping) else getattr(tc, "name", None))
            or "unknown"
        )
        if isinstance(tc_id, str) and tc_id.strip():
            valid_invalid_calls.append(tc)
            if tc_id not in seen_ids:
                seen_ids.add(tc_id)
                extracted.append((tc_id, str(tc_name), True))
        else:
            mutated = True

    additional = dict(getattr(msg, "additional_kwargs", None) or {})
    if not extracted and ("tool_calls" in additional or "function_call" in additional):
        raw_calls = additional.get("tool_calls")
        if isinstance(raw_calls, Sequence):
            for raw_tc in raw_calls:
                if not isinstance(raw_tc, Mapping):
                    continue
                tc_id = raw_tc.get("id")
                fn = raw_tc.get("function")
                tc_name = (
                    fn.get("name")
                    if isinstance(fn, Mapping) and isinstance(fn.get("name"), str)
                    else "unknown"
                )
                if isinstance(tc_id, str) and tc_id.strip() and tc_id not in seen_ids:
                    seen_ids.add(tc_id)
                    extracted.append((tc_id, tc_name, False))
        if not extracted:
            additional.pop("tool_calls", None)
            additional.pop("function_call", None)
            mutated = True
    elif not valid_tool_calls and not valid_invalid_calls and (
        "tool_calls" in additional or "function_call" in additional
    ):
        additional.pop("tool_calls", None)
        additional.pop("function_call", None)
        mutated = True

    if mutated:
        fallback_content = msg.content if msg.content else "[Interrupted tool call]"
        msg = msg.model_copy(
            update={
                "content": fallback_content,
                "tool_calls": valid_tool_calls,
                "invalid_tool_calls": valid_invalid_calls,
                "additional_kwargs": additional,
            }
        )
    return msg, extracted


def sanitize_tool_call_messages(
    messages: Sequence[BaseMessage],
) -> tuple[list[BaseMessage], bool]:
    """Repair interrupted, non-contiguous, duplicate, or orphaned tool-call message sequences."""
    if not messages:
        return [], False

    tool_messages_by_id: dict[str, ToolMessage] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tc_id = getattr(msg, "tool_call_id", None)
            if isinstance(tc_id, str) and tc_id.strip():
                existing = tool_messages_by_id.get(tc_id)
                if existing is None or (
                    _is_synthetic_cancelled_tool_message(existing)
                    and not _is_synthetic_cancelled_tool_message(msg)
                ):
                    tool_messages_by_id[tc_id] = msg

    sanitized: list[BaseMessage] = []
    emitted_tool_call_ids: set[str] = set()

    for msg in messages:
        if isinstance(msg, ToolMessage):
            # All valid ToolMessages are emitted contiguously right after their parent AIMessage.
            continue
        if isinstance(msg, AIMessage):
            norm_msg, tool_calls = _normalize_ai_message_tool_calls(msg)
            sanitized.append(norm_msg)
            for tc_id, tc_name, is_invalid in tool_calls:
                if tc_id in emitted_tool_call_ids:
                    continue
                emitted_tool_call_ids.add(tc_id)
                existing_tool_msg = tool_messages_by_id.get(tc_id)
                if existing_tool_msg is not None:
                    sanitized.append(existing_tool_msg)
                else:
                    content = (
                        f"Tool call {tc_name} with id {tc_id} could not be executed - arguments were malformed or truncated."
                        if is_invalid
                        else f"Tool call {tc_name} with id {tc_id} was cancelled - another message came in before it could be completed."
                    )
                    sanitized.append(
                        ToolMessage(
                            content=content,
                            name=tc_name,
                            tool_call_id=tc_id,
                            status="error",
                        )
                    )
        else:
            sanitized.append(msg)

    changed = len(sanitized) != len(messages) or any(
        a is not b for a, b in zip(sanitized, messages)
    )
    return sanitized, changed


class RuntimeConfigMiddleware(AgentMiddleware[object, RuntimeContext, object]):
    """Re-resolve immutable Runtime values before model and tool execution."""

    def __init__(
        self,
        *,
        principal: RuntimePrincipal | None = None,
        policy: RuntimePolicy | None = None,
        defaults: AgentDefaults,
        base_model: BaseChatModel,
        model_builder: ModelBuilder = build_model,
        local_fallback: bool = False,
        tool_names: Sequence[str] | None = None,
        probe_only: bool = False,
    ) -> None:
        super().__init__()
        self._principal = principal
        self._policy = policy
        self._defaults = defaults
        self._base_model = base_model
        self._model_builder = model_builder
        self._local_fallback = local_fallback
        self._tool_names = None if tool_names is None else frozenset(tool_names)
        self._probe_only = probe_only
    @staticmethod
    def _user(runtime: object) -> object | None:
        server_info = getattr(runtime, "server_info", None)
        return None if server_info is None else getattr(server_info, "user", None)

    def _facts(self, runtime: object) -> VerifiedDelegation | None:
        user = self._user(runtime)
        if user is None:
            if not self._local_fallback:
                raise RuntimeAuthError("runtime.auth.missing_principal")
            return None
        try:
            return verified_delegation_from_user(user)
        except RuntimeAuthError:
            raise
        except Exception as exc:
            raise RuntimeAuthError("runtime.auth.invalid_principal") from exc

    @staticmethod
    def _check_scope(runtime: object, facts: VerifiedDelegation) -> None:
        server_info = getattr(runtime, "server_info", None)
        execution_info = getattr(runtime, "execution_info", None)
        if facts.scope.assistant_id is not None and (
            server_info is None or facts.scope.assistant_id not in {
                getattr(server_info, "assistant_id", None),
                getattr(server_info, "graph_id", None),
            }
        ):
            raise RuntimeAuthError("runtime.auth.invalid_principal", "assistant_id")
        if facts.scope.thread_id is not None and (
            execution_info is None or facts.scope.thread_id != getattr(execution_info, "thread_id", None)
        ):
            raise RuntimeAuthError("runtime.auth.invalid_principal", "thread_id")

    def _resolve(self, runtime: object) -> ResolvedRuntimeConfig:
        if self._probe_only:
            raise RuntimeAuthError("runtime.graph.probe_only")
        context = parse_runtime_context(getattr(runtime, "context", None))
        facts = self._facts(runtime)
        if facts is None:
            principal, policy = self._principal, self._policy
            if principal is None or policy is None:
                raise RuntimeAuthError("runtime.auth.missing_principal")
        else:
            if facts.context_hash != runtime_context_hash(context):
                raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
            self._check_scope(runtime, facts)
            if facts.scope.operation != "run-create":
                raise RuntimeAuthError("runtime.auth.invalid_principal", "operation")
            principal, policy = facts.principal, facts.policy
        return resolve_runtime_config(
            principal=principal,
            context=context,
            policy=policy,
            defaults=self._defaults,
            available_tool_names=self._tool_names,
        )

    @staticmethod
    def _sanitize_state_messages(state: object) -> dict[str, Any] | None:
        if not isinstance(state, Mapping):
            return None
        raw_messages = state.get("messages")
        if not isinstance(raw_messages, Sequence):
            return None
        sanitized, changed = sanitize_tool_call_messages(raw_messages)
        if not changed:
            return None
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *sanitized]}

    def before_agent(self, state: object, runtime: object) -> dict[str, Any] | None:
        self._resolve(runtime)
        return self._sanitize_state_messages(state)

    async def abefore_agent(self, state: object, runtime: object) -> dict[str, Any] | None:
        self._resolve(runtime)
        return self._sanitize_state_messages(state)

    def before_model(self, state: object, runtime: object) -> dict[str, Any] | None:
        return self._sanitize_state_messages(state)

    async def abefore_model(self, state: object, runtime: object) -> dict[str, Any] | None:
        return self._sanitize_state_messages(state)

    def _allowed_tools(self, resolved: ResolvedRuntimeConfig) -> set[str]:
        return set(resolved.required_tool_names) | set(resolved.optional_tool_names)

    async def awrap_model_call(self, request: ModelRequest, handler):
        resolved = self._resolve(request.runtime)
        model = self._base_model
        if (
            resolved.model_id != self._defaults.model_id
            or resolved.temperature != self._defaults.temperature
            or resolved.max_tokens != self._defaults.max_tokens
            or resolved.top_p != self._defaults.top_p
        ):
            model = self._model_builder(resolved)

        allowed = self._allowed_tools(resolved)
        tools = request.tools
        if tools is not None:
            filtered = []
            for tool in tools:
                name = _tool_name(tool)
                if name is None or name not in allowed:
                    continue
                filtered.append(tool)
            tools = filtered
        sanitized_messages, messages_changed = sanitize_tool_call_messages(
            getattr(request, "messages", None) or ()
        )
        override_kwargs: dict[str, Any] = {"model": model, "tools": tools}
        if messages_changed:
            override_kwargs["messages"] = sanitized_messages
        response = await handler(request.override(**override_kwargs))
        messages = getattr(response, "result", None)
        if messages is None:
            messages = [response]
        for message in messages:
            for tool_call in getattr(message, "tool_calls", []):
                name = tool_call.get("name")
                if not isinstance(name, str) or name not in allowed:
                    raise RuntimeResolutionError("runtime.tool.not_allowed", "tool_name")
        return response

    async def awrap_tool_call(self, request: ToolCallRequest, handler):
        resolved = self._resolve(request.runtime)
        name = request.tool_call.get("name")
        allowed = self._allowed_tools(resolved)
        if not isinstance(name, str) or name not in allowed:
            raise RuntimeResolutionError("runtime.tool.not_allowed", "tool_name")
        return await handler(request)


__all__ = ["RuntimeConfigMiddleware", "sanitize_tool_call_messages"]

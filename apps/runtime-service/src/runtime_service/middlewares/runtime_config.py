"""Runtime contract enforcement at LangChain model and tool boundaries."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ToolCallRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

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
        tool_permissions: Mapping[str, str] | None = None,
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
        self._tool_permissions = tool_permissions
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
            tool_permissions=self._tool_permissions,
        )

    async def abefore_agent(self, state: object, runtime: object) -> None:
        self._resolve(runtime)

    def _allowed_tools(self, resolved: ResolvedRuntimeConfig) -> set[str]:
        allowed = set(resolved.required_tool_names) | set(resolved.optional_tool_names)
        return allowed if self._tool_names is None else allowed & self._tool_names

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
        response = await handler(request.override(model=model, tools=tools))
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


__all__ = ["RuntimeConfigMiddleware"]

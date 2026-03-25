# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

from graph_src_v2.middlewares.multimodal import MultimodalMiddleware
from graph_src_v2.runtime.modeling import apply_model_runtime_params, resolve_model
from graph_src_v2.runtime.options import build_runtime_config, merge_trusted_auth_context
from graph_src_v2.services.usecase_workflow_agent.prompts import SYSTEM_PROMPT
from graph_src_v2.services.usecase_workflow_agent.schemas import UsecaseWorkflowState
from graph_src_v2.services.usecase_workflow_agent.tools import (
    build_usecase_workflow_tools,
)
from graph_src_v2.services.usecase_workflow_agent.workflow_policy import (
    GREETING_GUARD_SYSTEM_INSTRUCTION,
    STAGE_ALLOWED_TOOLS,
    allowed_names_for_request,
    allowed_names_for_stage,
    build_stage_system_message,
    get_latest_user_text,
    get_system_message_text,
    infer_stage,
    normalize_tool_call_messages,
    sanitize_model_response,
    should_guard_greeting_only_turn,
)
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain.messages import AIMessage
from langchain.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime


class WorkflowToolSelectionMiddleware(AgentMiddleware):
    _MODEL_RESPONSE_RETRYABLE_MARKERS = (
        "null value for 'choices'",
        "no generations found in stream",
    )
    _MODEL_RESPONSE_ERROR_TEXT = (
        "当前模型服务返回了不兼容的响应格式，我暂时无法继续这一轮处理。"
        "请稍后重试，或检查模型网关 / OpenAI-compatible 配置。"
    )

    @staticmethod
    def _allowed_names_for_stage(stage: str) -> list[str]:
        return allowed_names_for_stage(stage)

    @staticmethod
    def _infer_stage_from_messages(messages: Any) -> str | None:
        from graph_src_v2.services.usecase_workflow_agent.workflow_policy import infer_stage_from_messages

        return infer_stage_from_messages(messages)

    @staticmethod
    def _infer_stage(request: ModelRequest) -> str:
        return infer_stage(request.state)

    @staticmethod
    def _allowed_names_for_request(request: ModelRequest) -> list[str]:
        names: list[str] = []
        for tool in request.tools:
            name = getattr(tool, "name", "")
            if isinstance(name, str) and name.strip():
                names.append(name)
        stage = request.state.get("current_stage") if isinstance(request.state, Mapping) else None
        latest_user_text = get_latest_user_text(request.messages, request.state.get("messages"))
        return allowed_names_for_request(
            names,
            stage,
            latest_user_text,
            request.state.get("messages"),
            request.messages,
        )

    @staticmethod
    def _dedupe_tools_by_name(tools: list[Any]) -> list[Any]:
        unique_tools: list[Any] = []
        seen: set[str] = set()
        for tool in tools:
            name = getattr(tool, "name", "")
            if not isinstance(name, str) or not name.strip() or name in seen:
                continue
            unique_tools.append(tool)
            seen.add(name)
        return unique_tools

    @staticmethod
    def _apply_stage(request: ModelRequest) -> ModelRequest:
        normalized_messages = normalize_tool_call_messages(list(request.messages))
        system_text = get_system_message_text(request.system_message)

        if should_guard_greeting_only_turn(request.state, request.messages):
            next_system = (
                f"{system_text}\n\n{GREETING_GUARD_SYSTEM_INSTRUCTION}"
                if system_text
                else GREETING_GUARD_SYSTEM_INSTRUCTION
            )
            return request.override(
                messages=normalized_messages,
                system_message=SystemMessage(content=next_system),
                tools=[],
                state=cast(UsecaseWorkflowState, dict(request.state)),
            )

        stage = WorkflowToolSelectionMiddleware._infer_stage(request)
        stage_allowed_names = WorkflowToolSelectionMiddleware._allowed_names_for_stage(stage)
        stage_filtered_tools = WorkflowToolSelectionMiddleware._dedupe_tools_by_name([
            tool for tool in request.tools if getattr(tool, "name", "") in stage_allowed_names
        ])
        next_state = cast(UsecaseWorkflowState, {**request.state, "current_stage": stage})
        stage_scoped_request = request.override(
            messages=normalized_messages,
            system_message=request.system_message,
            tools=stage_filtered_tools,
            state=next_state,
        )
        allowed_names = WorkflowToolSelectionMiddleware._allowed_names_for_request(
            stage_scoped_request
        )
        filtered_tools = WorkflowToolSelectionMiddleware._dedupe_tools_by_name([
            tool for tool in stage_filtered_tools if getattr(tool, "name", "") in allowed_names
        ])
        next_system = build_stage_system_message(system_text, stage, allowed_names)
        return request.override(
            messages=normalized_messages,
            system_message=SystemMessage(content=next_system),
            tools=filtered_tools,
            state=next_state,
        )

    @staticmethod
    def _sanitize_model_response(
        response: ModelResponse, allowed_names: list[str]
    ) -> ModelResponse:
        return sanitize_model_response(response, allowed_names)

    @staticmethod
    def _response_has_tool_calls(response: ModelResponse) -> bool:
        result = getattr(response, "result", None)
        if not isinstance(result, list):
            return False
        return any(getattr(message, "tool_calls", None) for message in result)

    @staticmethod
    def _synthesize_required_tool_response(allowed_names: list[str]) -> ModelResponse | None:
        if not allowed_names:
            return None
        tool_name = allowed_names[0]
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": tool_name,
                            "args": {},
                            "id": f"synthesized_{tool_name}",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        )

    @classmethod
    def _is_retryable_model_error(cls, exc: Exception) -> bool:
        message = str(exc).lower()
        return any(marker in message for marker in cls._MODEL_RESPONSE_RETRYABLE_MARKERS)

    @classmethod
    def _fallback_model_error_response(
        cls, *, stage: str | None, allowed_names: list[str]
    ) -> ModelResponse:
        del stage
        synthesized = cls._synthesize_required_tool_response(allowed_names)
        if synthesized is not None:
            return cls._sanitize_model_response(synthesized, allowed_names)
        return ModelResponse(result=[AIMessage(content=cls._MODEL_RESPONSE_ERROR_TEXT)])

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        updated_request = self._apply_stage(request)
        allowed_names = self._allowed_names_for_request(updated_request)
        stage = (
            updated_request.state.get("current_stage")
            if isinstance(updated_request.state, Mapping)
            else None
        )
        try:
            response = handler(updated_request)
        except Exception as exc:
            if not self._is_retryable_model_error(exc):
                raise
            try:
                response = handler(updated_request)
            except Exception as retry_exc:
                if not self._is_retryable_model_error(retry_exc):
                    raise
                response = self._fallback_model_error_response(
                    stage=stage,
                    allowed_names=allowed_names,
                )
        sanitized = self._sanitize_model_response(
            response,
            allowed_names,
        )
        if self._response_has_tool_calls(sanitized):
            return sanitized
        synthesized = self._synthesize_required_tool_response(allowed_names)
        if synthesized is None:
            return sanitized
        return self._sanitize_model_response(synthesized, allowed_names)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        updated_request = self._apply_stage(request)
        allowed_names = self._allowed_names_for_request(updated_request)
        stage = (
            updated_request.state.get("current_stage")
            if isinstance(updated_request.state, Mapping)
            else None
        )
        try:
            response = await handler(updated_request)
        except Exception as exc:
            if not self._is_retryable_model_error(exc):
                raise
            try:
                response = await handler(updated_request)
            except Exception as retry_exc:
                if not self._is_retryable_model_error(retry_exc):
                    raise
                response = self._fallback_model_error_response(
                    stage=stage,
                    allowed_names=allowed_names,
                )
        sanitized = self._sanitize_model_response(
            response,
            allowed_names,
        )
        if self._response_has_tool_calls(sanitized):
            return sanitized
        synthesized = self._synthesize_required_tool_response(allowed_names)
        if synthesized is None:
            return sanitized
        return self._sanitize_model_response(synthesized, allowed_names)


def _bind_non_streaming_model(model: Any) -> Any:
    if hasattr(model, "disable_streaming"):
        setattr(model, "disable_streaming", True)
    return model


async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    del runtime
    runtime_context = merge_trusted_auth_context(config, {})
    options = build_runtime_config(config, runtime_context)
    model = apply_model_runtime_params(resolve_model(options.model_spec), options)
    tools = build_usecase_workflow_tools(model)
    system_prompt = options.system_prompt or SYSTEM_PROMPT

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
    )


graph = make_graph

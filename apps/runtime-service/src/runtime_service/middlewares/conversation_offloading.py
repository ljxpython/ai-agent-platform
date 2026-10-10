"""Runtime budgets and safe status around the official DeepAgents summarizer."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping
from contextvars import ContextVar
from copy import copy
from dataclasses import dataclass, field
from typing import Annotated, Any, NotRequired

import openai
from deepagents.graph import DeepAgentState
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.summarization import (
    SummarizationMiddleware,
    SummarizationState,
)
from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
    hook_config,
)
from langchain_core.callbacks import (
    BaseCallbackHandler,
    CallbackManager,
    UsageMetadataCallbackHandler,
)
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import HumanMessage, get_buffer_string
from langgraph.config import get_config, get_stream_writer
from langgraph.runtime import Runtime
from langgraph.types import Command

from runtime_service.middlewares.model_call_timeout import (
    resolve_model_call_timeout_seconds,
)
from runtime_service.runtime.errors import RuntimeResolutionError

logger = logging.getLogger(__name__)


@dataclass
class _Operation:
    manual: bool
    run_id: str | None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: bool = False
    compacted: bool = False
    history_saved: bool = False
    pending: set[asyncio.Task] = field(default_factory=set)
    usage: UsageMetadataCallbackHandler = field(
        default_factory=UsageMetadataCallbackHandler
    )


# gather() inherits this reference, so archive and summary tasks share one operation.
_operation: ContextVar[_Operation | None] = ContextVar(
    "conversation_offloading", default=None
)


class _SummaryUsageCallback(BaseCallbackHandler):
    run_inline = True

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        operation = _operation.get()
        if operation is not None:
            operation.usage.on_llm_end(response, **kwargs)


class OffloadingState(SummarizationState, DeepAgentState):
    # Do not copy operation state into children or merge child status into the root.
    conversation_offloading: Annotated[NotRequired[dict[str, Any]], PrivateStateAttr]


def context_management_enabled() -> bool:
    return os.environ.get("AGENT_CONTEXT_MANAGEMENT_ENABLED") == "1"


def is_conversation_maintenance(runtime: Any) -> bool:
    context = getattr(runtime, "context", None)
    return (
        context.get("offload_conversation") is True
        if isinstance(context, Mapping)
        else getattr(context, "offload_conversation", False) is True
    )


class MaintenanceSafeToolCallsMiddleware(PatchToolCallsMiddleware):
    @property
    def name(self) -> str:
        return "PatchToolCallsMiddleware"

    def before_agent(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        return (
            None
            if is_conversation_maintenance(runtime)
            else super().before_agent(state, runtime)
        )


def _positive_int(value: Any) -> int | None:
    return value if type(value) is int and value > 0 else None


def _input_budget(model: Any, capacity: int | None, output: int | None) -> int:
    profile = getattr(model, "profile", None) or {}
    capacity = _positive_int(capacity) or _positive_int(profile.get("max_input_tokens"))
    if capacity is None:
        raise RuntimeResolutionError("runtime.context.capacity_unknown")
    maximum_output = _positive_int(profile.get("max_output_tokens"))
    output = (
        _positive_int(output)
        or _positive_int(getattr(model, "max_tokens", None))
        or maximum_output
    )
    if output is None:
        raise RuntimeResolutionError("runtime.context.output_budget_unknown")
    if maximum_output is not None and output > maximum_output:
        raise RuntimeResolutionError("runtime.context.output_budget_exceeded")
    budget = capacity - output - max(1024, math.ceil(capacity * 0.05))
    if budget <= 0:
        raise RuntimeResolutionError("runtime.context.input_budget_exceeded")
    return budget


def resolve_tool_output_limit(
    models: Iterable[Any], output_budget_tokens: int | None
) -> int:
    """Keep one large result below a conservative fraction of model input budget."""

    budgets = [
        _input_budget(model, None, output_budget_tokens)
        for model in models
        if model is not None
    ]
    if not budgets:
        raise RuntimeResolutionError("runtime.context.input_budget_unknown")
    return max(1, min(20_000, min(budgets) // 16))


class _CheckedArchiveBackend:
    """Make official overflow-tail writes fail before they can emit a bad pointer."""

    def __init__(self, backend: Any) -> None:
        self.backend = backend

    def __getattr__(self, name: str) -> Any:
        return getattr(self.backend, name)

    async def awrite(self, path: str, content: str) -> Any:
        operation = _operation.get()
        task = asyncio.current_task()
        track = operation is not None and task not in operation.pending
        if track:
            operation.pending.add(task)
        try:
            result = await self.backend.awrite(path, content)
            if result is None or result.error:
                raise RuntimeResolutionError("runtime.context.history_save_failed")
            return result
        finally:
            if track:
                operation.pending.discard(task)


class ConversationOffloadingMiddleware(SummarizationMiddleware):
    """Keep official cutoff, pairing, archive and checkpoint semantics."""

    state_schema = OffloadingState

    @property
    def name(self) -> str:
        return "SummarizationMiddleware"

    def __init__(
        self,
        model: Any,
        backend: Any,
        *,
        context_window_tokens: int | None = None,
        output_budget_tokens: int | None = None,
        manual: bool = False,
    ) -> None:
        self.manual = manual
        self.capacity = context_window_tokens
        self.output = output_budget_tokens
        self.input_budget = _input_budget(model, self.capacity, self.output)
        callbacks = CallbackManager.configure(local_callbacks=model.callbacks)
        callbacks.add_handler(_SummaryUsageCallback(), inherit=False)
        summary_model = model.model_copy(
            update={
                "tags": [
                    *(getattr(model, "tags", None) or []),
                    "nostream",
                    "langsmith:hidden",
                ],
                "callbacks": callbacks,
            }
        )
        super().__init__(
            model=summary_model,
            backend=backend,
            trigger=("tokens", max(1, math.floor(0.85 * self.input_budget))),
            keep=("tokens", max(1, math.floor(0.10 * self.input_budget))),
            trim_tokens_to_summarize=self.input_budget,
            truncate_args_settings={
                "trigger": ("tokens", max(1, math.floor(0.85 * self.input_budget))),
                "keep": ("tokens", max(1, math.floor(0.10 * self.input_budget))),
                "max_length": 2000,
            },
        )
        prompt_tokens = self._count_tokens(
            [HumanMessage(content=self._lc_helper.summary_prompt.format(messages=""))],
            None,
            [],
        )
        self._lc_helper.trim_tokens_to_summarize = max(
            1, self.input_budget - prompt_tokens - 128
        )
        self._backend = _CheckedArchiveBackend(backend)

    def _status(self, status: str, *, reason_code: str | None = None) -> dict[str, Any]:
        operation = _operation.get()
        assert operation is not None
        payload: dict[str, Any] = {
            "type": "conversation_offloading",
            "operation_id": operation.id,
            "status": status,
            "trigger": "manual" if operation.manual else "automatic",
        }
        if operation.run_id:
            payload["run_id"] = operation.run_id
        if status in {"completed", "failed"}:
            payload["history_saved"] = operation.history_saved
        if reason_code:
            payload["reason_code"] = reason_code
        try:
            get_stream_writer()(payload)
        except RuntimeError:
            pass  # Direct middleware calls have no graph stream writer.
        return payload

    def _should_summarize(self, messages: list[Any], total_tokens: int) -> bool:
        operation = _operation.get()
        return bool(operation and operation.manual) or super()._should_summarize(
            messages, total_tokens
        )

    def _determine_cutoff_index(self, messages: list[Any]) -> int:
        cutoff = super()._determine_cutoff_index(messages)
        return cutoff if self._filter_summary_messages(messages[:cutoff]) else 0

    def _partition_messages(
        self, messages: list[Any], cutoff: int
    ) -> tuple[list[Any], list[Any]]:
        operation = _operation.get()
        assert operation is not None
        operation.started = True
        self._status("started")
        return super()._partition_messages(messages, cutoff)

    async def _aoffload_inline_media(
        self, backend: Any, messages: list[Any]
    ) -> tuple[list[Any], int]:
        result, failed = await super()._aoffload_inline_media(backend, messages)
        if failed:
            raise RuntimeResolutionError("runtime.context.media_save_failed")
        return result, failed

    async def _aoffload_to_backend(
        self, backend: Any, messages: list[Any], session_id: str
    ) -> str:
        operation = _operation.get()
        assert operation is not None
        task = asyncio.current_task()
        operation.pending.add(task)
        try:
            path = await super()._aoffload_to_backend(backend, messages, session_id)
            if not path:
                raise RuntimeResolutionError("runtime.context.history_save_failed")
            operation.history_saved = True
            return path
        finally:
            operation.pending.discard(task)

    async def _acreate_summary(self, messages_to_summarize: list[Any]) -> str:
        operation = _operation.get()
        assert operation is not None
        task = asyncio.current_task()
        operation.pending.add(task)
        started = time.monotonic()
        prompt_tokens = None
        try:
            limit = self._lc_helper.trim_tokens_to_summarize
            if (
                messages_to_summarize
                and isinstance(messages_to_summarize[0], HumanMessage)
                and self._lc_helper.token_counter(messages_to_summarize) > limit
            ):
                # Keep the prior summary/initial goal when a large batch needs trimming.
                lead = messages_to_summarize[0]
                helper = copy(self._lc_helper)
                helper.trim_tokens_to_summarize = (
                    limit - helper.token_counter([lead]) - 128
                )
                if helper.trim_tokens_to_summarize <= 0:
                    raise RuntimeResolutionError(
                        "runtime.context.summary_input_budget_exceeded"
                    )
                messages_to_summarize = [
                    lead,
                    *helper._trim_messages_for_summary(messages_to_summarize[1:]),
                ]
            # Verify the serialized prompt before the official helper invokes it.
            prompt = self._lc_helper.summary_prompt.format(
                messages=get_buffer_string(
                    self._lc_helper._trim_messages_for_summary(messages_to_summarize),
                    format="xml",
                )
            ).rstrip()
            prompt_tokens = self._count_tokens([HumanMessage(content=prompt)], None, [])
            if prompt_tokens > self.input_budget:
                raise RuntimeResolutionError(
                    "runtime.context.summary_input_budget_exceeded"
                )
            async with asyncio.timeout(resolve_model_call_timeout_seconds()):
                return await super()._acreate_summary(messages_to_summarize)
        finally:
            operation.pending.discard(task)
            logger.info(
                "runtime_context_summary",
                extra={
                    "operation_id": operation.id,
                    "run_id": operation.run_id,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "input_budget_tokens": self.input_budget,
                    "estimated_input_tokens": prompt_tokens,
                    "usage_tokens": {
                        key: sum(
                            usage[key]
                            for usage in operation.usage.usage_metadata.values()
                        )
                        for key in ("input_tokens", "output_tokens", "total_tokens")
                    }
                    if operation.usage.usage_metadata
                    else None,
                },
            )

    def _build_new_messages_with_path(
        self, summary: str, file_path: str | None
    ) -> list[Any]:
        operation = _operation.get()
        assert operation is not None
        operation.compacted = True
        return super()._build_new_messages_with_path(summary, file_path)

    async def _invoke(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
        *,
        manual: bool,
    ) -> ModelResponse | ExtendedModelResponse:
        info = getattr(request.runtime, "execution_info", None)
        run_id = getattr(info, "run_id", None)
        if run_id is None:
            try:
                run_id = get_config().get("metadata", {}).get("run_id")
            except RuntimeError:
                pass  # Direct middleware calls have no graph config.
        operation = _Operation(
            manual=manual, run_id=str(run_id) if run_id is not None else None
        )
        token = _operation.set(operation)
        try:
            response = await super().awrap_model_call(request, handler)
            if (
                operation.compacted
                and isinstance(response, ExtendedModelResponse)
                and response.command
            ):
                response.command.update["conversation_offloading"] = self._status(
                    "completed"
                )
            elif manual:
                response = ExtendedModelResponse(
                    model_response=response,
                    command=Command(
                        update={
                            "conversation_offloading": self._status(
                                "skipped", reason_code="nothing_to_offload"
                            )
                        }
                    ),
                )
            return response
        except BaseException as exc:
            if operation.started or manual:
                reason = (
                    "cancelled"
                    if isinstance(exc, asyncio.CancelledError)
                    else "summary_timeout"
                    if isinstance(exc, TimeoutError)
                    else exc.code.removeprefix("runtime.context.")
                    if isinstance(exc, RuntimeResolutionError)
                    else "run_failed"
                )
                self._status("failed", reason_code=reason)
            if isinstance(exc, ContextOverflowError):
                raise RuntimeResolutionError(
                    "runtime.context.input_budget_exceeded"
                ) from exc
            raise
        finally:
            pending = list(operation.pending)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            _operation.reset(token)

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable
    ) -> ModelResponse | ExtendedModelResponse:
        return await self._invoke(request, handler, manual=False)

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable
    ) -> ModelResponse:
        raise RuntimeResolutionError("runtime.context.async_required")

    @hook_config(can_jump_to=["end"])
    async def abefore_model(
        self, state: AgentState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        if not self.manual:
            return None

        async def finish(request: ModelRequest) -> ModelResponse:
            return ModelResponse(result=[])

        response = await self._invoke(
            ModelRequest(
                model=self.model,
                messages=state.get("messages", []),
                tools=[],
                state=state,
                runtime=runtime,
            ),
            finish,
            manual=True,
        )
        return {**response.command.update, "jump_to": "end"}


class ContextBudgetMiddleware(AgentMiddleware):
    """Check the final request after Runtime model/tool and memory/skill changes."""

    def __init__(self, summarizer: ConversationOffloadingMiddleware) -> None:
        self.summarizer = summarizer

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable
    ) -> ModelResponse:
        budget = _input_budget(
            request.model, self.summarizer.capacity, self.summarizer.output
        )
        if (
            self.summarizer._count_tokens(
                request.messages, request.system_message, request.tools
            )
            > budget
        ):
            operation = _operation.get()
            if operation is not None and operation.compacted:
                raise RuntimeResolutionError("runtime.context.input_budget_exceeded")
            raise ContextOverflowError("runtime.context.input_budget_exceeded")
        try:
            return await handler(request)
        except openai.BadRequestError as exc:
            if exc.code != "context_length_exceeded":
                raise
            operation = _operation.get()
            if operation is not None and operation.compacted:
                raise RuntimeResolutionError(
                    "runtime.context.input_budget_exceeded"
                ) from exc
            raise ContextOverflowError("runtime.context.input_budget_exceeded") from exc


__all__ = [
    "ConversationOffloadingMiddleware",
    "ContextBudgetMiddleware",
    "MaintenanceSafeToolCallsMiddleware",
    "context_management_enabled",
    "is_conversation_maintenance",
    "resolve_tool_output_limit",
]

"""Model-bound PII redaction middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from deepagents.middleware.summarization import (
    SummarizationMiddleware,
    compute_summarization_defaults,
)
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    ModelCallResult,
    ModelRequest,
    ModelResponse,
)
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import AIMessage, ToolMessage

from runtime_service.runtime.errors import RuntimePrivacyError
from runtime_service.runtime.pii import (
    PII_REDACTION_ERROR,
    PiiRedactionConfig,
    contains_pii,
    redact_messages,
    redact_model_request,
    redact_text,
)


class PiiRedactionMiddleware(AgentMiddleware):
    """Apply one immutable policy to every request before it reaches a model handler."""

    def __init__(self, config: PiiRedactionConfig | None) -> None:
        super().__init__()
        self.config = config

    def _request(self, request: ModelRequest) -> ModelRequest:
        return redact_model_request(request, self.config)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        return handler(self._request(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        return await handler(self._request(request))


class PiiSummarizationMiddleware(SummarizationMiddleware):
    """Protect summary inputs while retaining official history and state semantics."""

    @property
    def name(self) -> str:
        return "SummarizationMiddleware"

    def __init__(self, model, backend, *, pii_config=None, **kwargs) -> None:
        self.pii_config = pii_config
        if not kwargs:
            defaults = compute_summarization_defaults(model)
            kwargs = {
                "trigger": defaults["trigger"],
                "keep": defaults["keep"],
                "truncate_args_settings": defaults["truncate_args_settings"],
            }
        super().__init__(model=model, backend=backend, **kwargs)
        self._lc_helper.summary_prompt = redact_text(
            self._lc_helper.summary_prompt, pii_config
        )

    def _truncate_tool_call(self, tool_call):
        truncated = super()._truncate_tool_call(tool_call)
        if truncated == tool_call:
            return truncated
        projected = redact_messages(
            [AIMessage(content="", tool_calls=[tool_call])], self.pii_config
        )[0].tool_calls[0]
        args = dict(truncated["args"])
        for key, value in tool_call["args"].items():
            # Keep matched values whole until the final model projection; archives stay factual.
            if args.get(key) != value and projected["args"][key] != value:
                args[key] = value
        return {**truncated, "args": args}

    def _create_summary(self, messages_to_summarize):
        return super()._create_summary(
            redact_messages(messages_to_summarize, self.pii_config)
        )

    def _check_overflow_tail(self, request):
        # Official recovery head-slices large read_file results before the final wrapper.
        for message in reversed(request.messages):
            if not isinstance(message, ToolMessage):
                break
            if (
                isinstance(message.content, str)
                and len(message.content) > 4000
                and contains_pii(message.content, self.pii_config)
            ):
                raise RuntimePrivacyError(PII_REDACTION_ERROR)

    def wrap_model_call(self, request, handler):
        def guarded(candidate):
            try:
                return handler(candidate)
            except ContextOverflowError as exc:
                overflow = exc
            self._check_overflow_tail(candidate)
            raise overflow

        return super().wrap_model_call(request, guarded)

    async def awrap_model_call(self, request, handler):
        async def guarded(candidate):
            try:
                return await handler(candidate)
            except ContextOverflowError as exc:
                overflow = exc
            self._check_overflow_tail(candidate)
            raise overflow

        return await super().awrap_model_call(request, guarded)

    async def _acreate_summary(self, messages_to_summarize):
        return await super()._acreate_summary(
            redact_messages(messages_to_summarize, self.pii_config)
        )


__all__ = ["PiiRedactionMiddleware", "PiiSummarizationMiddleware"]

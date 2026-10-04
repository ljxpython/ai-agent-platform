"""Reject mixed clarification batches before any tool can execute."""

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage

from runtime_service.middlewares.runtime_config import repair_model_tool_calls
from runtime_service.services.dearflow_agent.schemas import ClarificationRequest


class ClarificationBatchGuard(AgentMiddleware):
    @staticmethod
    def _validate(message):
        if isinstance(message, AIMessage):
            calls = [*message.tool_calls, *message.invalid_tool_calls]
            questions = [c for c in calls if c.get("name") == "request_information"]
            if questions and (len(calls) != 1 or message.invalid_tool_calls):
                raise ValueError("clarification_requires_single_valid_tool_call")
            if questions:
                # Fail before HITL or other side effects; never silently drop fields.
                ClarificationRequest.model_validate(questions[0]["args"])

    def wrap_model_call(self, request, handler):
        response = handler(request)
        for i, message in enumerate(response.result):
            if isinstance(message, AIMessage):
                message = repair_model_tool_calls(message)
                response.result[i] = message
            self._validate(message)
        return response

    async def awrap_model_call(self, request, handler):
        response = await handler(request)
        for i, message in enumerate(response.result):
            if isinstance(message, AIMessage):
                message = repair_model_tool_calls(message)
                response.result[i] = message
            self._validate(message)
        return response

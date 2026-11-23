"""Project fresh context near the current turn without writing it to agent state."""

from datetime import UTC, datetime
from typing import Literal

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage

from runtime_service.middlewares.conversation_offloading import (
    is_conversation_maintenance,
)

_CONTEXT_KEY = "dearflow_context"


def is_turn_context(message):
    return (
        isinstance(message, HumanMessage)
        and message.name in {"runtime_date", "user_memory"}
        and message.additional_kwargs.get(_CONTEXT_KEY) == message.name
    )


def with_turn_context(messages, name: Literal["runtime_date", "user_memory"], content):
    """Return an outbound-only copy; never split an assistant/tool-result pair."""
    projected = [
        message
        for message in messages
        if not (is_turn_context(message) and message.name == name)
    ]
    index = next(
        (
            i
            for i in range(len(projected) - 1, -1, -1)
            if isinstance(projected[i], HumanMessage)
            and not is_turn_context(projected[i])
        ),
        0,
    )
    projected.insert(
        index,
        HumanMessage(
            content=content,
            name=name,
            additional_kwargs={_CONTEXT_KEY: name},
        ),
    )
    return projected


class CurrentDateMiddleware(AgentMiddleware):
    async def awrap_model_call(self, request, handler):
        if is_conversation_maintenance(request.runtime):
            return await handler(request)
        date = datetime.now(UTC).date().isoformat()
        return await handler(
            request.override(
                messages=with_turn_context(
                    request.messages,
                    "runtime_date",
                    f"<current_date>{date} UTC</current_date>",
                )
            )
        )

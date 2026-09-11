"""Deterministic slow-tool fixture for network queue acceptance, never deployed."""

import asyncio

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.types import interrupt
from runtime_service.middlewares.message_queue import MessageQueueMiddleware


@tool
async def long_task() -> str:
    """Wait for independent user input during external work."""
    await asyncio.sleep(12)
    return "finished"


@tool
async def review_task() -> str:
    """Pause for a human decision after allowing an in-flight supplement."""
    await asyncio.sleep(12)
    result = interrupt(
        {
            "action_requests": [{"name": "confirm", "args": {}}],
            "review_configs": [
                {"action_name": "confirm", "allowed_decisions": ["approve", "reject"]}
            ],
        }
    )
    return str(result)


class QueueModel(FakeMessagesListChatModel):
    def bind_tools(self, *args, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        completed = sum(isinstance(message, ToolMessage) for message in messages)
        received = "received: " + " | ".join(
            str(item.content) for item in messages if item.type == "human"
        )
        if completed < 2:
            name = (
                "review_task"
                if completed == 1
                and any(
                    "approval" in str(item.content)
                    for item in messages
                    if item.type == "human"
                )
                else "long_task"
            )
            message = AIMessage(
                content=received if completed else "",
                tool_calls=[
                    {
                        "id": f"long-task-{completed}",
                        "name": name,
                        "args": {},
                        "type": "tool_call",
                    }
                ],
            )
        else:
            message = AIMessage(content=received)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(self, messages, **kwargs):
        return self._generate(messages, **kwargs)


def get_agent(config):
    return create_agent(
        QueueModel(responses=[AIMessage(content="done")]),
        tools=[long_task, review_task],
        middleware=[MessageQueueMiddleware()],
    )

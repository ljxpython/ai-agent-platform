"""Deterministic streaming fixture, loaded only by the registered acceptance stack."""

import asyncio
import json
from uuid import uuid4

from deepagents.graph import DeepAgentState
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import ToolException, tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class BrowserModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "v3-browser-fixture"

    def bind_tools(self, tools, **kwargs):
        return self

    def answer(self, messages):
        index = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        prompt = messages[index].text
        results = [m for m in messages[index + 1 :] if isinstance(m, ToolMessage)]
        if results:
            if prompt == "V3_TOOLS" and len(results) == 2:
                return AIMessage(
                    "", tool_calls=[self.call("lookup", {"value": "retry"})]
                )
            return AIMessage(
                content="父任务继续完成" if prompt == "V3_CHILD" else "验收完成"
            )
        calls = {
            "V3_TOOLS": [self.call("lookup", {"value": v}) for v in ("first", "fail")],
            "V3_CHILD": [
                self.call(
                    "task", {"description": "子图失败隔离", "subagent_type": "fixture"}
                )
            ],
            "V3_APPROVAL": [self.call("confirm", {"value": "original"})],
            "V3_SLOW": [self.call("long_task", {})],
        }
        if prompt in calls:
            return AIMessage("", tool_calls=calls[prompt])
        return AIMessage(content="**正文验收完成**")

    @staticmethod
    def call(name, args):
        return {
            "name": name,
            "args": args,
            "id": "call-" + uuid4().hex,
            "type": "tool_call",
        }

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self.answer(messages))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        answer = self.answer(messages)
        message_id = "answer-" + uuid4().hex
        prompt = next(m.text for m in reversed(messages) if isinstance(m, HumanMessage))
        chunks = []
        if prompt == "V3_REASONING":
            chunks.append(
                AIMessageChunk(
                    content=[
                        {"type": "reasoning", "reasoning": "公开思考验收", "index": 0}
                    ]
                )
            )
        if answer.tool_calls:
            for i, call in enumerate(answer.tool_calls):
                args = json.dumps(call["args"], ensure_ascii=False)
                split = max(1, len(args) // 2)
                chunks.extend(
                    [
                        AIMessageChunk(
                            content="",
                            tool_call_chunks=[
                                {
                                    "name": call["name"],
                                    "args": args[:split],
                                    "id": call["id"],
                                    "index": i,
                                }
                            ],
                        ),
                        AIMessageChunk(
                            content="",
                            tool_call_chunks=[
                                {
                                    "name": None,
                                    "args": args[split:],
                                    "id": None,
                                    "index": i,
                                }
                            ],
                        ),
                    ]
                )
        else:
            for part in (answer.text[:4], answer.text[4:]):
                chunks.append(
                    AIMessageChunk(
                        content=[
                            {
                                "type": "text",
                                "text": part,
                                "index": 1 if prompt == "V3_REASONING" else 0,
                            }
                        ]
                    )
                )
        if prompt == "V3_USAGE":
            chunks.append(
                AIMessageChunk(
                    content="",
                    usage_metadata={
                        "input_tokens": 7,
                        "output_tokens": 11,
                        "total_tokens": 18,
                    },
                )
            )
        for chunk in chunks:
            chunk.id = message_id
            await asyncio.sleep(0.04)
            yield ChatGenerationChunk(message=chunk)


async def get_agent(config):
    @tool
    def lookup(value: str) -> str:
        """Return a deterministic value or a recoverable tool failure."""
        if value == "fail":
            raise ToolException("fixture lookup failed")
        return "result:" + value

    lookup.handle_tool_error = True

    async def child_message(state, config):
        await BrowserModel().ainvoke([HumanMessage("V3_CHILD_MESSAGE")], config)
        raise ValueError("fixture child failed")

    child = (
        StateGraph(DeepAgentState)
        .add_node("child", child_message)
        .add_edge(START, "child")
        .add_edge("child", END)
        .compile()
    )

    @tool
    async def task(description: str, subagent_type: str) -> str:
        """Run a failing child graph and preserve the parent execution."""
        try:
            await child.ainvoke({"messages": [HumanMessage(description)]})
        except ValueError as error:
            raise ToolException(str(error)) from error
        return "child completed"

    task.handle_tool_error = True

    @tool
    def confirm(value: str) -> str:
        """Pause for an explicit approval of the original arguments."""
        result = interrupt(
            {
                "action_requests": [
                    {
                        "name": "confirm",
                        "args": {"value": value},
                        "description": "验收审批",
                    }
                ],
                "review_configs": [
                    {
                        "action_name": "confirm",
                        "allowed_decisions": ["approve", "reject"],
                    }
                ],
            }
        )
        return json.dumps(result, ensure_ascii=False)

    @tool
    async def long_task() -> str:
        """Wait long enough for browser cancellation and reconnection."""
        await asyncio.sleep(30)
        return "slow completed"

    return create_agent(
        BrowserModel(), [lookup, task, confirm, long_task], state_schema=DeepAgentState
    )

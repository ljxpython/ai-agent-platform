import asyncio
import hashlib

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from runtime_service.middlewares.documents import DocumentToolsMiddleware
from runtime_service.workspace.documents import DocumentWorkspace


def test_document_tool_registration_preserves_message_refs_and_does_not_scan(
    tmp_path, monkeypatch
):
    from langchain.agents import create_agent
    from support import BindableFakeMessagesChatModel

    raw = b"prompt injection is document data"
    ref = DocumentWorkspace(tmp_path).put(
        raw, hashlib.sha256(raw).hexdigest(), "text/plain"
    )
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": "[Document attachment] source.txt\n" + ref["path"],
                "extras": {"runtime_file": ref},
            }
        ]
    )
    middleware = DocumentToolsMiddleware(tmp_path)
    assert [tool.name for tool in middleware.tools] == ["parse_document"]
    monkeypatch.setattr(
        type(tmp_path),
        "iterdir",
        lambda *args: (_ for _ in ()).throw(AssertionError("directory scan")),
    )
    model = BindableFakeMessagesChatModel(responses=[AIMessage(content="ack")])
    agent = create_agent(
        model,
        middleware=[middleware],
        system_prompt="system",
        checkpointer=InMemorySaver(),
    )
    result = asyncio.run(
        agent.ainvoke(
            {"messages": [message]}, {"configurable": {"thread_id": "test-documents"}}
        )
    )
    assert result["messages"][0].content == message.content
    assert not any(isinstance(item, SystemMessage) for item in result["messages"])

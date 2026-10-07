import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import WriteResult
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares import (
    ContextBudgetMiddleware,
    ConversationOffloadingMiddleware,
    MaintenanceSafeToolCallsMiddleware,
    MessageQueueMiddleware,
)
from runtime_service.middlewares import conversation_offloading as module
from runtime_service.runtime import RuntimeContext, RuntimeResolutionError


class RecordingModel(BindableFakeMessagesChatModel):
    calls: list = Field(default_factory=list)
    max_tokens: int = 256

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(
            ("summary" if "nostream" in (self.tags or []) else "normal", messages)
        )
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def model():
    return RecordingModel(
        responses=[
            AIMessage(
                content="Goal: preserve constraints. Source https://docs.python.org. Next report.",
                response_metadata={"model_name": "test-model"},
                usage_metadata={
                    "input_tokens": 20,
                    "output_tokens": 10,
                    "total_tokens": 30,
                },
            )
        ],
        profile={"max_input_tokens": 12000, "max_output_tokens": 1024},
    )


def history():
    return [
        message
        for i in range(8)
        for message in (
            HumanMessage(content="constraint source " + "word " * 600, id=f"h{i}"),
            AIMessage(content="answer " * 300, id=f"a{i}"),
        )
    ]


def test_budget_sources_and_boundaries(tmp_path):
    instance = model()
    mw = ConversationOffloadingMiddleware(
        instance, FilesystemBackend(root_dir=str(tmp_path))
    )
    assert mw.input_budget == 12000 - 256 - 1024
    assert "nostream" not in (instance.tags or [])
    assert {"nostream", "langsmith:hidden"} <= set(mw.model.tags)
    boundary = mw._lc_helper.trigger[1]
    assert not mw._should_summarize([], boundary - 1)
    assert mw._should_summarize([], boundary)
    for profile, output, code in (
        ({}, 10, "capacity_unknown"),
        ({"max_input_tokens": 12000}, None, "output_budget_unknown"),
        (
            {"max_input_tokens": 12000, "max_output_tokens": 10},
            20,
            "output_budget_exceeded",
        ),
    ):
        instance = BindableFakeMessagesChatModel(
            responses=[AIMessage(content="ok")], profile=profile
        )
        with pytest.raises(RuntimeResolutionError, match=code):
            ConversationOffloadingMiddleware(
                instance,
                FilesystemBackend(root_dir=str(tmp_path)),
                output_budget_tokens=output,
            )


def test_manual_preserves_messages_and_rebuilt_graph_returns_to_automatic(
    tmp_path, caplog
):
    async def run():
        saver = InMemorySaver()
        cfg = {
            "configurable": {"thread_id": "manual"},
            "metadata": {"run_id": "worker-maintenance"},
        }
        instance = model()
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        seed = create_deep_agent(model=instance, checkpointer=saver)
        await seed.aupdate_state(cfg, {"messages": history()})
        before = (await seed.aget_state(cfg)).values["messages"]
        mw = ConversationOffloadingMiddleware(instance, backend, manual=True)
        graph = create_deep_agent(
            model=instance,
            backend=backend,
            checkpointer=saver,
            context_schema=RuntimeContext,
            middleware=[mw, MessageQueueMiddleware(), ContextBudgetMiddleware(mw)],
        )
        chunks = [
            chunk
            async for chunk in graph.astream(
                {},
                cfg,
                context={"offload_conversation": True},
                stream_mode=["messages", "custom"],
            )
        ]
        after = (await graph.aget_state(cfg)).values
        assert after["messages"] == before
        assert after["conversation_offloading"]["status"] == "completed"
        assert after["conversation_offloading"]["run_id"] == "worker-maintenance"
        assert [kind for kind, _ in instance.calls] == ["summary"]
        assert all(mode != "messages" for mode, _ in chunks)
        events = [value for mode, value in chunks if mode == "custom"]
        assert [e["status"] for e in events] == ["started", "completed"]
        assert events[0]["operation_id"] == events[1]["operation_id"]
        usage = next(
            record
            for record in caplog.records
            if record.message == "runtime_context_summary"
        )
        assert usage.usage_tokens == {
            "input_tokens": 20,
            "output_tokens": 10,
            "total_tokens": 30,
        }
        assert usage.estimated_input_tokens <= usage.input_budget_tokens
        assert instance.callbacks is None
        restored = ConversationOffloadingMiddleware(instance, backend)
        normal = create_deep_agent(
            model=instance,
            backend=backend,
            checkpointer=saver,
            middleware=[restored, ContextBudgetMiddleware(restored)],
        )
        await normal.ainvoke(
            {"messages": [("user", "continue")]},
            {**cfg, "metadata": {"run_id": "worker-followup"}},
        )
        assert instance.calls[-1][0] == "normal"
        assert len(instance.calls[-1][1]) < len(before)
        assert "summary" in str(instance.calls[-1][1])

    with caplog.at_level("INFO", logger=module.__name__):
        asyncio.run(run())


def test_final_dynamic_prompt_guard_falls_back_once_and_fails_without_provider(
    tmp_path,
    monkeypatch,
):
    async def run():
        instance = model()
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        mw = ConversationOffloadingMiddleware(instance, backend)
        monkeypatch.setattr(mw, "_should_summarize", lambda *_: False)

        class InjectMemory(AgentMiddleware):
            async def awrap_model_call(self, request, handler):
                return await handler(
                    request.override(
                        system_message=SystemMessage(content="memory " * 10000)
                    )
                )

        graph = create_deep_agent(
            model=instance,
            backend=backend,
            middleware=[mw, InjectMemory(), ContextBudgetMiddleware(mw)],
        )
        with pytest.raises(RuntimeResolutionError, match="input_budget_exceeded"):
            await graph.ainvoke({"messages": history()[:8]})
        assert [kind for kind, _ in instance.calls] == ["summary"]

    asyncio.run(run())


def test_summary_trimming_preserves_prior_summary_and_initial_goal(tmp_path):
    async def run():
        for prior_summary in (False, True):
            instance = model()
            mw = ConversationOffloadingMiddleware(
                instance, FilesystemBackend(root_dir=str(tmp_path)), manual=True
            )
            lead = HumanMessage(
                content="ANCHOR_NO_DELETE Keep unfinished ANCHOR_TODO.",
                additional_kwargs={"lc_source": "summarization"}
                if prior_summary
                else {},
            )
            messages = [lead, *history() * 5]
            request = ModelRequest(
                model=instance,
                messages=messages,
                tools=[],
                state={"messages": messages},
                runtime=SimpleNamespace(execution_info=None),
            )
            await mw._invoke(
                request, AsyncMock(return_value=ModelResponse(result=[])), manual=True
            )
            assert len(instance.calls) == 1
            prompt = str(instance.calls[0][1])
            assert "ANCHOR_NO_DELETE" in prompt and "ANCHOR_TODO" in prompt
            assert request.state["messages"][0] is lead

    asyncio.run(run())


@pytest.mark.parametrize(
    ("code", "always_fails"),
    [
        ("context_length_exceeded", False),
        ("context_length_exceeded", True),
        ("invalid_request_error", False),
    ],
)
def test_provider_overflow_uses_exact_code_and_retries_once(
    tmp_path, monkeypatch, code, always_fails
):
    async def run():
        instance = model()
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        mw = ConversationOffloadingMiddleware(instance, backend)
        monkeypatch.setattr(mw, "_should_summarize", lambda *_: False)
        guard = ContextBudgetMiddleware(mw)
        calls = []

        async def provider(request):
            calls.append(request.messages)
            if len(calls) == 1 or always_fails:
                raise openai.BadRequestError(
                    "context_length_exceeded appears in unrelated error text too",
                    response=httpx.Response(
                        400, request=httpx.Request("POST", "https://model.test")
                    ),
                    body={"code": code},
                )
            return ModelResponse(result=[AIMessage(content="continued")])

        async def handler(request):
            return await guard.awrap_model_call(request, provider)

        request = ModelRequest(
            model=instance,
            messages=history()[:4],
            tools=[],
            state={},
            runtime=SimpleNamespace(execution_info=None),
        )
        if code != "context_length_exceeded":
            with pytest.raises(openai.BadRequestError):
                await mw.awrap_model_call(request, handler)
            assert len(calls) == 1 and not instance.calls
        elif always_fails:
            with pytest.raises(RuntimeResolutionError, match="input_budget_exceeded"):
                await mw.awrap_model_call(request, handler)
            assert len(calls) == 2
        else:
            result = await mw.awrap_model_call(request, handler)
            assert len(calls) == 2
            assert (
                result.command.update["conversation_offloading"]["status"]
                == "completed"
            )
            assert len(calls[-1]) < len(calls[0])

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["archive", "handler", "cancel"])
def test_failure_has_no_completed_or_new_state(tmp_path, monkeypatch, failure):
    async def run():
        events = []
        monkeypatch.setattr(module, "get_stream_writer", lambda: events.append)
        instance = model()
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        mw = ConversationOffloadingMiddleware(instance, backend)
        mw._lc_helper.trigger = ("messages", 2)
        if failure == "archive":
            monkeypatch.setattr(
                backend,
                "awrite",
                AsyncMock(return_value=WriteResult(error="disk failure")),
            )
        error = (
            asyncio.CancelledError()
            if failure == "cancel"
            else ValueError("provider failure")
        )
        handler = AsyncMock(side_effect=error)
        request = ModelRequest(
            model=instance,
            messages=history(),
            tools=[],
            state={"messages": history()},
            runtime=SimpleNamespace(execution_info=SimpleNamespace(run_id="run-1")),
        )
        with pytest.raises(
            (RuntimeResolutionError, ValueError, asyncio.CancelledError)
        ):
            await mw.awrap_model_call(request, handler)
        assert "completed" not in [e["status"] for e in events]
        assert events[-1]["status"] == "failed"
        assert len({e["operation_id"] for e in events}) == 1
        assert "_summarization_event" not in request.state
        assert module._operation.get() is None

    asyncio.run(run())


def test_short_manual_history_skips_and_queue_guard_precedes_config(
    tmp_path, monkeypatch
):
    async def run():
        events = []
        monkeypatch.setattr(module, "get_stream_writer", lambda: events.append)
        instance = model()
        mw = ConversationOffloadingMiddleware(
            instance, FilesystemBackend(root_dir=str(tmp_path)), manual=True
        )
        runtime = SimpleNamespace(
            context=RuntimeContext(offload_conversation=True), execution_info=None
        )
        assert await MessageQueueMiddleware().abefore_model({}, runtime) is None
        result = await mw.abefore_model(
            {"messages": [HumanMessage(content="short")]}, runtime
        )
        assert result["jump_to"] == "end"
        assert result["conversation_offloading"]["status"] == "skipped"
        assert not instance.calls

    asyncio.run(run())


def test_maintenance_does_not_patch_unpaired_tool_history():
    middleware = MaintenanceSafeToolCallsMiddleware()
    messages = [
        HumanMessage(content="old", id="human"),
        AIMessage(
            content="",
            id="tool-call",
            tool_calls=[{"name": "search", "args": {}, "id": "call-1"}],
        ),
    ]
    assert (
        middleware.before_agent(
            {"messages": messages},
            SimpleNamespace(context=RuntimeContext(offload_conversation=True)),
        )
        is None
    )
    assert len(messages) == 2
    repaired = middleware.before_agent(
        {"messages": messages}, SimpleNamespace(context=RuntimeContext())
    )
    assert repaired["messages"][-1].tool_call_id == "call-1"


@pytest.mark.parametrize("failure", ["timeout", "media", "overflow_archive"])
def test_offloading_auxiliary_failures_stop_without_provider(
    tmp_path, monkeypatch, failure
):
    async def run():
        instance = model()
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        mw = ConversationOffloadingMiddleware(instance, backend)
        mw._lc_helper.trigger = ("messages", 2)
        mw._lc_helper.keep = ("messages", 2)
        events = []
        monkeypatch.setattr(module, "get_stream_writer", lambda: events.append)
        if failure == "timeout":

            async def blocked(*args):
                await asyncio.sleep(30)

            monkeypatch.setattr(mw._lc_helper, "_acreate_summary", blocked)
            monkeypatch.setattr(
                module, "resolve_model_call_timeout_seconds", lambda: 0.01
            )
        elif failure == "media":
            monkeypatch.setattr(
                module.SummarizationMiddleware,
                "_aoffload_inline_media",
                AsyncMock(return_value=(history(), 1)),
            )
        else:
            monkeypatch.setattr(
                backend,
                "awrite",
                AsyncMock(return_value=WriteResult(error="unavailable")),
            )
        request = ModelRequest(
            model=instance,
            messages=history(),
            tools=[],
            state={},
            runtime=SimpleNamespace(execution_info=None),
        )
        handler = AsyncMock()
        with pytest.raises((RuntimeResolutionError, TimeoutError)):
            if failure == "overflow_archive":
                # The same checked backend is used by the official overflow-tail writer.
                await mw._backend.awrite("/large_tool_results/call.txt", "original")
            else:
                await mw.awrap_model_call(request, handler)
        handler.assert_not_awaited()
        assert not any(event["status"] == "completed" for event in events)
        assert module._operation.get() is None

    asyncio.run(run())


def test_summary_cutoff_keeps_parallel_tool_batch_paired(tmp_path):
    instance = model()
    mw = ConversationOffloadingMiddleware(
        instance, FilesystemBackend(root_dir=str(tmp_path))
    )
    mw._lc_helper.keep = ("messages", 2)
    messages = [
        HumanMessage(content="old"),
        AIMessage(content="old answer"),
        HumanMessage(content="parallel"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "lookup", "args": {}, "id": "one"},
                {"name": "lookup", "args": {}, "id": "two"},
            ],
        ),
        ToolMessage(content="a", tool_call_id="one"),
        ToolMessage(content="b", tool_call_id="two"),
    ]
    tail = messages[mw._determine_cutoff_index(messages) :]
    calls = {
        call["id"]
        for message in tail
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    assert {
        message.tool_call_id for message in tail if isinstance(message, ToolMessage)
    } <= calls


def test_parallel_child_compaction_is_namespaced_and_does_not_overwrite_root(
    monkeypatch,
):
    from runtime_service.services.dearflow_agent.workspace.backend import build_backend

    async def run():
        class DispatchModel(RecordingModel):
            async def _agenerate(self, messages, **kwargs):
                human = next(m.content for m in messages if isinstance(m, HumanMessage))
                if "nostream" in (self.tags or []):
                    result = AIMessage(content="Child goal preserved.")
                elif human == "ROOT_PRIVATE":
                    result = (
                        AIMessage(content="root done")
                        if any(isinstance(m, ToolMessage) for m in messages)
                        else AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "task",
                                    "args": {
                                        "description": name,
                                        "subagent_type": "worker",
                                    },
                                    "id": name,
                                }
                                for name in ("alpha", "beta")
                            ],
                        )
                    )
                elif any(isinstance(m, ToolMessage) for m in messages):
                    assert "ROOT_PRIVATE" not in str(messages)
                    result = AIMessage(content="child done")
                else:
                    result = AIMessage(
                        content="",
                        tool_calls=[{"name": "lookup", "args": {}, "id": "lookup"}],
                    )
                return ChatResult(generations=[ChatGeneration(message=result)])

        @tool
        def lookup() -> str:
            """Fetch fixed task evidence."""
            return "evidence"

        instance = DispatchModel(
            responses=[], profile={"max_input_tokens": 12000, "max_output_tokens": 1024}
        )
        backend = build_backend(None)
        root = ConversationOffloadingMiddleware(instance, backend)
        child = ConversationOffloadingMiddleware(instance, backend)
        monkeypatch.setattr(
            child, "_should_summarize", lambda messages, *_: len(messages) >= 3
        )
        child._lc_helper.keep = ("messages", 2)
        graph = create_deep_agent(
            model=instance,
            backend=backend,
            checkpointer=InMemorySaver(),
            middleware=[root, ContextBudgetMiddleware(root)],
            state_schema=ConversationOffloadingMiddleware.state_schema,
            subagents=[
                {
                    "name": "worker",
                    "description": "worker",
                    "system_prompt": "Return task evidence.",
                    "model": instance,
                    "tools": [lookup],
                    "middleware": [child, ContextBudgetMiddleware(child)],
                }
            ],
        )
        cfg = {"configurable": {"thread_id": "child-offload"}}
        status = {
            "type": "conversation_offloading",
            "status": "completed",
            "trigger": "automatic",
            "operation_id": "prior-root",
        }
        await graph.aupdate_state(
            cfg, {"conversation_offloading": status}, as_node="model"
        )
        events = [
            part
            async for part in graph.astream(
                {"messages": [("user", "ROOT_PRIVATE")]},
                cfg,
                stream_mode=["custom", "values"],
                subgraphs=True,
            )
        ]
        child_events = [
            (ns, data)
            for ns, mode, data in events
            if mode == "custom" and data.get("type") == "conversation_offloading"
        ]
        assert len(child_events) == 4 and all(ns for ns, _ in child_events)
        assert len({e["operation_id"] for _, e in child_events}) == 2
        values = (await graph.aget_state(cfg)).values
        assert values["conversation_offloading"] == status
        assert values["messages"][-1].content == "root done"
        archives = list(values["files"].values())
        assert len(archives) == 2
        assert "ROOT_PRIVATE" not in str(archives)
        assert sum("alpha" in str(archive) for archive in archives) == 1
        assert sum("beta" in str(archive) for archive in archives) == 1
        assert any(
            mode == "values"
            and not ns
            and data.get("conversation_offloading") == status
            for ns, mode, data in events
        )

    asyncio.run(run())


@pytest.mark.parametrize("write_fails", [False, True])
def test_official_overflow_tail_preserves_originals_and_pairs(
    tmp_path, monkeypatch, write_fails
):
    async def run():
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        instance = model()
        mw = ConversationOffloadingMiddleware(instance, backend)
        monkeypatch.setattr(mw, "_should_summarize", lambda *_: False)
        mw._lc_helper.keep = ("messages", 4)
        raw = "original-tool-result " * 6000
        messages = [
            HumanMessage(content="old constraint", id="old-h"),
            AIMessage(content="old answer", id="old-a"),
            HumanMessage(content="parallel lookup", id="lookup-h"),
            AIMessage(
                content="",
                id="lookup-a",
                tool_calls=[
                    {"name": "lookup", "args": {}, "id": "one"},
                    {"name": "lookup", "args": {}, "id": "two"},
                ],
            ),
            ToolMessage(content=raw, tool_call_id="one", id="t-one"),
            ToolMessage(content=raw, tool_call_id="two", id="t-two"),
        ]
        if write_fails:
            monkeypatch.setattr(
                backend,
                "awrite",
                AsyncMock(return_value=WriteResult(error="unavailable")),
            )
        seen = []

        async def handler(request):
            seen.append(request.messages)
            if len(seen) == 1:
                raise ContextOverflowError("provider overflow")
            return ModelResponse(result=[AIMessage(content="continued")])

        request = ModelRequest(
            model=instance,
            messages=messages,
            tools=[],
            state={},
            runtime=SimpleNamespace(execution_info=None),
        )
        if write_fails:
            with pytest.raises(RuntimeResolutionError, match="history_save_failed"):
                await mw.awrap_model_call(request, handler)
            assert len(seen) == 1
        else:
            response = await mw.awrap_model_call(request, handler)
            assert len(seen) == 2
            for message in response.command.update["messages"]:
                assert message.id == "t-" + message.tool_call_id
                path = "/large_tool_results/" + message.tool_call_id
                assert path in message.content
                downloaded = await backend.adownload_files([path])
                assert downloaded[0].content.decode() == raw
            assert (
                response.command.update["conversation_offloading"]["status"]
                == "completed"
            )
        assert messages[-1].content == raw
        assert not request.state

    asyncio.run(run())

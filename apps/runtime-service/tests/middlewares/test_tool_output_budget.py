from __future__ import annotations

import asyncio
import json
import time
from hashlib import sha256
from types import SimpleNamespace

import pytest
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.backends.protocol import WriteResult
from deepagents.middleware import FilesystemMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares import (
    ConversationOffloadingMiddleware,
    ResultFilesystemMiddleware,
    resolve_tool_output_limit,
)


def result_path(raw, call_id):
    return f"/large_tool_results/{sha256(raw.encode()).hexdigest()}/{call_id}"


def _model(*responses: AIMessage) -> BindableFakeMessagesChatModel:
    return BindableFakeMessagesChatModel(
        responses=list(responses),
        profile={"max_input_tokens": 12_000, "max_output_tokens": 1_024},
    )


def _filesystem_graph(model, backend, saver):
    return create_deep_agent(
        model=model,
        tools=[large_result],
        backend=backend,
        checkpointer=saver,
        middleware=[
            ResultFilesystemMiddleware(
                backend=backend,
                tool_token_limit_before_evict=100,
            )
        ],
    )


@tool
def large_result(label: str = "evidence") -> str:
    """Return deterministic multi-line evidence for offloading tests."""
    return "\n".join(f"line-{index:03d} {label}" for index in range(120))


LARGE_PATH = result_path(large_result.invoke({}), "large-1")


def test_capacity_concurrency_and_preview_cost_matrix(tmp_path):
    rows = []
    for capacity in (12_000, 32_000, 128_000):
        instance = BindableFakeMessagesChatModel(
            responses=[AIMessage(content="ok")], profile={"max_input_tokens": capacity}
        )
        for shape, text in (
            ("ascii", "a"),
            ("cjk", "\u4e2d"),
            ("json", '{"key":"a"}'),
            ("lines", "source evidence " * 12 + "\n"),
            ("long-lines", "a" * 4000 + "\n"),
        ):
            raw = (text * 50_000)[:50_000]
            for count in (1, 5, 10):
                for limit in (
                    resolve_tool_output_limit((instance,), 256),
                    3000,
                    12500,
                    20000,
                ):
                    backend = FilesystemBackend(
                        root_dir=tmp_path / f"{capacity}-{shape}-{count}-{limit}"
                    )
                    mw = ResultFilesystemMiddleware(
                        backend=backend, tool_token_limit_before_evict=limit
                    )
                    messages = []
                    started = time.monotonic()
                    originals = [
                        ToolMessage(
                            content=raw,
                            tool_call_id=f"output-{index}",
                            name="synthetic",
                        )
                        for index in range(count)
                    ]

                    async def concurrent_results(mw=mw, originals=originals):
                        async def process(original):
                            async def handler(_):
                                return original

                            return await mw.awrap_tool_call(
                                SimpleNamespace(tool_call={"name": "synthetic"}),
                                handler,
                            )

                        return await asyncio.gather(
                            *(process(original) for original in originals)
                        )

                    messages = asyncio.run(concurrent_results())
                    for original, result in zip(originals, messages, strict=True):
                        if len(raw) > 4 * limit:
                            assert (
                                backend.download_files(
                                    [result_path(raw, original.tool_call_id)]
                                )[0].content.decode()
                                == raw
                            )
                        else:
                            assert result is original
                    budget = ConversationOffloadingMiddleware(
                        instance, backend, output_budget_tokens=256
                    ).input_budget
                    estimated = count_tokens_approximately(messages)
                    rows.append(
                        {
                            "capacity": capacity,
                            "shape": shape,
                            "count": count,
                            "limit": limit,
                            "raw_bytes": len(raw.encode()) * count,
                            "preview_chars": sum(len(str(m.content)) for m in messages),
                            "estimated_tool_tokens": estimated,
                            "input_budget": budget,
                            "tool_text_within_budget": estimated <= budget,
                            "duration_seconds": round(time.monotonic() - started, 4),
                        }
                    )
    calibrated = [
        r
        for r in rows
        if r["limit"]
        == resolve_tool_output_limit(
            (SimpleNamespace(profile={"max_input_tokens": r["capacity"]}),), 256
        )
    ]
    assert all(r["preview_chars"] < 50_000 * r["count"] for r in calibrated)
    assert all(
        r["tool_text_within_budget"] for r in calibrated if r["shape"] != "long-lines"
    )
    assert any(
        not r["tool_text_within_budget"]
        for r in calibrated
        if r["shape"] == "long-lines"
    )
    artifact = tmp_path / "f04-budget-matrix.json"
    artifact.write_text(json.dumps(rows, indent=2))
    print(
        json.dumps(
            {
                "matrix_file": str(artifact),
                "cases": len(rows),
                "calibrated_cases": len(calibrated),
                "calibrated_oversize_tool_text_cases": sum(
                    not r["tool_text_within_budget"] for r in calibrated
                ),
            }
        ),
        flush=True,
    )


def test_old_result_reference_is_readable_by_new_filesystem(tmp_path):
    backend = FilesystemBackend(root_dir=tmp_path)
    raw = large_result.invoke({})
    legacy = FilesystemMiddleware(backend=backend, tool_token_limit_before_evict=100)
    message = ToolMessage(content=raw, tool_call_id="legacy")
    legacy.wrap_tool_call(
        SimpleNamespace(tool_call={"name": "synthetic"}), lambda _: message
    )
    mw = ResultFilesystemMiddleware(backend=backend, tool_token_limit_before_evict=100)
    read = next(t for t in mw.tools if t.name == "read_file")
    assert "line-055" in str(
        read.func(
            file_path="/large_tool_results/legacy",
            offset=55,
            limit=1,
            runtime=SimpleNamespace(tool_call_id="legacy-read"),
        )
    )


def test_large_single_line_read_warns_instead_of_reoffloading(tmp_path):
    backend = FilesystemBackend(root_dir=tmp_path)
    raw = json.dumps({"evidence": "x" * 40_000 + "MIDDLE_CANARY" + "x" * 40_000})
    mw = ResultFilesystemMiddleware(backend=backend, tool_token_limit_before_evict=100)
    message = ToolMessage(content=raw, tool_call_id="long-line")
    path = result_path(raw, "long-line")
    mw.wrap_tool_call(
        SimpleNamespace(tool_call={"name": "synthetic"}), lambda _: message
    )
    read = next(t for t in mw.tools if t.name == "read_file")
    result = read.func(
        file_path=path,
        offset=0,
        limit=1,
        runtime=SimpleNamespace(tool_call_id="single-read"),
    )
    assert "truncated due to size limits" in str(result.content)
    assert "saved in the filesystem" not in str(result.content)
    assert "MIDDLE_CANARY" not in str(result.content)
    assert (
        mw.wrap_tool_call(
            SimpleNamespace(tool_call={"name": "read_file"}), lambda _: result
        )
        is result
    )
    assert backend.download_files([path])[0].content.decode() == raw


def test_large_result_is_previewed_read_back_and_restored_from_state():
    async def run():
        raw = large_result.invoke({})
        saver = InMemorySaver()
        backend = CompositeBackend(
            default=StateBackend(),
            routes={"/large_tool_results/": StateBackend()},
        )
        graph = _filesystem_graph(
            _model(
                AIMessage(
                    content="",
                    tool_calls=[{"name": "large_result", "args": {}, "id": "large-1"}],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {
                                "file_path": LARGE_PATH,
                                "offset": 55,
                                "limit": 5,
                            },
                            "id": "read-1",
                        }
                    ],
                ),
                AIMessage(content="middle evidence recovered"),
            ),
            backend,
            saver,
        )
        config = {"configurable": {"thread_id": "large-result"}}
        await graph.ainvoke({"messages": [("user", "collect evidence")]}, config)
        state = (await graph.aget_state(config)).values
        messages = state["messages"]
        archived = next(
            message
            for message in messages
            if isinstance(message, ToolMessage) and message.tool_call_id == "large-1"
        )
        read_back = next(
            message
            for message in messages
            if isinstance(message, ToolMessage) and message.tool_call_id == "read-1"
        )
        assert LARGE_PATH in str(archived.content)
        assert "line-000" in str(archived.content)
        assert "line-119" in str(archived.content)
        assert "line-055" in str(read_back.content)
        assert "line-059" in str(read_back.content)
        # CompositeBackend strips the route prefix in the StateBackend key.
        stored = state["files"][LARGE_PATH.removeprefix("/large_tool_results")][
            "content"
        ]
        assert sha256(stored.encode()).hexdigest() == sha256(raw.encode()).hexdigest()

        restored = _filesystem_graph(
            _model(
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_file",
                            "args": {
                                "file_path": LARGE_PATH,
                                "offset": 100,
                                "limit": 5,
                            },
                            "id": "read-restored",
                        }
                    ],
                ),
                AIMessage(content="restored evidence recovered"),
            ),
            backend,
            saver,
        )
        await restored.ainvoke({"messages": [("user", "recover evidence")]}, config)
        restored_state = (await restored.aget_state(config)).values
        restored_read = next(
            message
            for message in restored_state["messages"]
            if isinstance(message, ToolMessage)
            and message.tool_call_id == "read-restored"
        )
        assert "line-100" in str(restored_read.content)
        assert "line-104" in str(restored_read.content)

    asyncio.run(run())


@pytest.mark.parametrize("text", ["a", "\u4e2d", "a\n", '{"key":"a"}'])
@pytest.mark.parametrize("extra_chars", [-1, 0, 1])
def test_existing_offloader_respects_character_boundary(tmp_path, text, extra_chars):
    backend = FilesystemBackend(root_dir=tmp_path)
    limit = resolve_tool_output_limit((_model(AIMessage(content="ok")),), 256)
    size = 4 * limit + extra_chars
    raw = (text * size)[:size]
    original = ToolMessage(content=raw, tool_call_id="boundary", name="synthetic")
    mw = ResultFilesystemMiddleware(
        backend=backend, tool_token_limit_before_evict=limit
    )
    result = mw.wrap_tool_call(
        SimpleNamespace(tool_call={"name": "synthetic"}), lambda _: original
    )
    path = result_path(raw, "boundary")
    downloads = backend.download_files([path])
    if extra_chars > 0:
        assert downloads[0].content.decode() == raw
        assert path in str(result.content)
    else:
        assert result is original
        assert downloads[0].error


@pytest.mark.parametrize("as_command", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_offloading_keeps_multimodal_metadata_and_command(
    tmp_path, as_command, asynchronous
):
    backend = FilesystemBackend(root_dir=tmp_path)
    raw = large_result.invoke({})
    image = {"type": "image", "base64": "aW1hZ2U=", "mime_type": "image/png"}
    original = ToolMessage(
        content=[{"type": "text", "text": raw}, image],
        tool_call_id="media",
        name="synthetic",
        id="message-id",
        status="success",
        artifact={"source": "fixture"},
        additional_kwargs={"fixture": True},
        response_metadata={"trace": "fixture"},
    )
    mw = ResultFilesystemMiddleware(backend=backend, tool_token_limit_before_evict=100)
    response = (
        Command(update={"messages": [original], "fixture": 1})
        if as_command
        else original
    )
    request = SimpleNamespace(tool_call={"name": "synthetic"})
    if asynchronous:

        async def handler(_):
            return response

        result = asyncio.run(mw.awrap_tool_call(request, handler))
    else:
        result = mw.wrap_tool_call(request, lambda _: response)
    if as_command:
        assert result.update["fixture"] == 1
        result = result.update["messages"][0]
    assert result.content[1] == image
    assert result.model_dump(exclude={"content"}) == original.model_dump(
        exclude={"content"}
    )
    assert (
        backend.download_files([result_path(raw, "media")])[0].content.decode() == raw
    )
    assert original.content[0]["text"] == raw


@pytest.mark.parametrize("failure", ["error", "exception", "cancel"])
def test_archive_failure_does_not_retry_the_tool(tmp_path, failure, monkeypatch):
    async def run():
        backend = FilesystemBackend(root_dir=tmp_path)

        async def write(*args):
            if failure == "error":
                return WriteResult(error="unavailable")
            if failure == "cancel":
                raise asyncio.CancelledError
            raise OSError("storage unavailable")

        monkeypatch.setattr(backend, "awrite", write)
        mw = ResultFilesystemMiddleware(
            backend=backend, tool_token_limit_before_evict=100
        )
        calls = []
        original = ToolMessage(content=large_result.invoke({}), tool_call_id="failure")

        async def handler(request):
            calls.append(request)
            return original

        request = SimpleNamespace(tool_call={"name": "synthetic"})
        if failure == "error":
            assert await mw.awrap_tool_call(request, handler) is original
        else:
            with pytest.raises(
                asyncio.CancelledError if failure == "cancel" else OSError
            ):
                await mw.awrap_tool_call(request, handler)
        assert len(calls) == 1
        assert backend.download_files([result_path(original.content, "failure")])[
            0
        ].error

    asyncio.run(run())


def test_same_call_id_on_two_threads_does_not_share_results():
    async def run():
        saver = InMemorySaver()
        backend = CompositeBackend(
            default=StateBackend(), routes={"/large_tool_results/": StateBackend()}
        )

        async def invoke(label):
            graph = _filesystem_graph(
                _model(
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "large_result",
                                "args": {"label": label},
                                "id": "shared",
                            }
                        ],
                    ),
                    AIMessage(content="done"),
                ),
                backend,
                saver,
            )
            config = {"configurable": {"thread_id": label}}
            await graph.ainvoke({"messages": [("user", label)]}, config)
            state = (await graph.aget_state(config)).values
            raw = large_result.invoke({"label": label})
            key = result_path(raw, "shared").removeprefix("/large_tool_results")
            assert state["files"][key]["content"] == raw

        await asyncio.gather(invoke("first-thread"), invoke("second-thread"))

    asyncio.run(run())


@pytest.mark.parametrize(
    "filesystem_cls", [FilesystemMiddleware, ResultFilesystemMiddleware]
)
def test_reused_parent_child_call_id_archive_collision(filesystem_cls):
    async def run():
        backend = CompositeBackend(
            default=StateBackend(), routes={"/large_tool_results/": StateBackend()}
        )
        instance = _model(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "large_result",
                        "args": {"label": "parent"},
                        "id": "shared",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {"subagent_type": "worker", "description": "child"},
                        "id": "delegate",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "large_result", "args": {"label": "child"}, "id": "shared"}
                ],
            ),
            AIMessage(content="child completed"),
            AIMessage(content="parent completed"),
        )
        graph = create_deep_agent(
            model=instance,
            tools=[large_result],
            backend=backend,
            checkpointer=InMemorySaver(),
            middleware=[
                filesystem_cls(backend=backend, tool_token_limit_before_evict=100)
            ],
            subagents=[
                {
                    "name": "worker",
                    "description": "collect evidence",
                    "system_prompt": "Collect evidence.",
                    "model": instance,
                    "tools": [large_result],
                    "middleware": [
                        filesystem_cls(
                            backend=backend, tool_token_limit_before_evict=100
                        )
                    ],
                }
            ],
        )
        config = {"configurable": {"thread_id": "collision"}}
        await graph.ainvoke({"messages": [("user", "collect both")]}, config)
        state = (await graph.aget_state(config)).values
        parent_message = next(
            m
            for m in state["messages"]
            if isinstance(m, ToolMessage) and m.tool_call_id == "shared"
        )
        assert "parent" in str(parent_message.content)
        if filesystem_cls is FilesystemMiddleware:
            assert state["files"]["/shared"]["content"] == large_result.invoke(
                {"label": "child"}
            )
        else:
            for label in ("parent", "child"):
                raw = large_result.invoke({"label": label})
                key = result_path(raw, "shared").removeprefix("/large_tool_results")
                assert state["files"][key]["content"] == raw

    asyncio.run(run())


def test_parallel_children_reusing_call_id_keep_each_original():
    class RoutingModel(BindableFakeMessagesChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            last = messages[-1]
            if isinstance(last, HumanMessage):
                response = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "args": {"subagent_type": "worker", "description": label},
                            "id": label,
                        }
                        for label in ("one", "two")
                    ]
                    if last.content == "collect"
                    else [
                        {
                            "name": "large_result",
                            "args": {"label": last.content},
                            "id": "shared",
                        }
                    ],
                )
            else:
                response = AIMessage(content="completed")
            return ChatResult(generations=[ChatGeneration(message=response)])

    async def run():
        backend = CompositeBackend(
            default=StateBackend(), routes={"/large_tool_results/": StateBackend()}
        )
        instance = RoutingModel(responses=[AIMessage(content="unused")])
        graph = create_deep_agent(
            model=instance,
            backend=backend,
            checkpointer=InMemorySaver(),
            subagents=[
                {
                    "name": "worker",
                    "description": "Collect evidence.",
                    "system_prompt": "Collect evidence.",
                    "model": instance,
                    "tools": [large_result],
                    "middleware": [
                        ResultFilesystemMiddleware(
                            backend=backend, tool_token_limit_before_evict=100
                        )
                    ],
                }
            ],
            middleware=[
                ResultFilesystemMiddleware(
                    backend=backend, tool_token_limit_before_evict=100
                )
            ],
        )
        config = {"configurable": {"thread_id": "parallel-children"}}
        await graph.ainvoke({"messages": [("user", "collect")]}, config)
        state = (await graph.aget_state(config)).values
        for label in ("one", "two"):
            raw = large_result.invoke({"label": label})
            key = result_path(raw, "shared").removeprefix("/large_tool_results")
            assert state["files"][key]["content"] == raw

    asyncio.run(run())


def test_failed_archive_keeps_original_result_without_fake_reference():
    class FailingStateBackend(StateBackend):
        async def awrite(self, file_path: str, content: str) -> WriteResult:
            return WriteResult(error="disk full")

    async def run():
        failing = FailingStateBackend()
        backend = CompositeBackend(
            default=StateBackend(),
            routes={"/large_tool_results/": failing},
        )
        graph = _filesystem_graph(
            _model(
                AIMessage(
                    content="",
                    tool_calls=[{"name": "large_result", "args": {}, "id": "failed-1"}],
                ),
                AIMessage(content="finished with original result"),
            ),
            backend,
            InMemorySaver(),
        )
        config = {"configurable": {"thread_id": "failed-large-result"}}
        await graph.ainvoke({"messages": [("user", "collect evidence")]}, config)
        state = (await graph.aget_state(config)).values
        result = next(
            message
            for message in state["messages"]
            if isinstance(message, ToolMessage) and message.tool_call_id == "failed-1"
        )
        assert str(result.content) == large_result.invoke({})
        assert "/failed-1" not in state.get("files", {})

    asyncio.run(run())

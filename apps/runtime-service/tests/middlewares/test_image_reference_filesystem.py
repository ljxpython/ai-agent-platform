import asyncio
import base64
import hashlib
import json
from types import SimpleNamespace

import pytest
from deepagents.backends import FilesystemBackend
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolRuntime

from runtime_service.middlewares.filesystem import ImageReferenceFilesystemMiddleware
from runtime_service.tools.images import ImageWorkspace


def _png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )


def _pdf() -> bytes:
    import fitz

    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((50, 50), "DOCUMENT_REFERENCE_OK")
        return document.tobytes()


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        state={},
        context={},
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-1",
        store=None,
        execution_info=SimpleNamespace(
            thread_id="thread", run_id="run", checkpoint_ns=""
        ),
    )


def test_read_file_image_is_replaced_by_runtime_reference(tmp_path):
    (tmp_path / "files" / "workspace" / "work").mkdir(parents=True)
    (tmp_path / "files" / "workspace" / "work" / "pixel.png").write_bytes(_png())
    (tmp_path / "workspace").mkdir()
    middleware = ImageReferenceFilesystemMiddleware(
        backend=FilesystemBackend(root_dir=tmp_path / "files"),
        image_workspace=ImageWorkspace(tmp_path / "workspace"),
    )
    read_file = next(tool for tool in middleware.tools if tool.name == "read_file")

    results = [
        read_file.func(file_path="/workspace/work/pixel.png", runtime=_runtime()),
        asyncio.run(
            read_file.coroutine(
                file_path="/workspace/work/pixel.png", runtime=_runtime()
            )
        ),
    ]
    assert results[0].content == results[1].content
    for result in results:
        block = result.content[0]
        assert block["type"] == "text"
        assert block["extras"]["runtime_image"]["path"].startswith(
            "/workspace/generated/"
        )
        assert "base64" not in str(result.content)


def test_model_expansion_only_changes_request_copy(tmp_path):
    (tmp_path / "workspace").mkdir()
    middleware = ImageReferenceFilesystemMiddleware(
        backend=FilesystemBackend(root_dir=tmp_path / "files"),
        image_workspace=ImageWorkspace(tmp_path / "workspace"),
    )
    ref = middleware.image_workspace.put_upload(
        _png(), hashlib.sha256(_png()).hexdigest()
    )
    message = ToolMessage(
        name="read_file",
        tool_call_id="call-2",
        content=[
            {"type": "text", "text": "[图片附件]", "extras": {"runtime_image": ref}}
        ],
    )
    request = SimpleNamespace(
        messages=[message], override=lambda **kwargs: SimpleNamespace(**kwargs)
    )
    seen = {}

    async def handler(clean):
        seen["content"] = clean.messages[0].content
        return clean

    asyncio.run(middleware.awrap_model_call(request, handler))
    assert seen["content"][0]["text"] == "[图片附件]"
    assert seen["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert message.content[0]["type"] == "text"


@pytest.fixture
def middleware(tmp_path):
    return ImageReferenceFilesystemMiddleware(
        backend=FilesystemBackend(root_dir=tmp_path),
        image_workspace=ImageWorkspace(tmp_path),
    )


def image_message(mime="image/png"):
    return ToolMessage(
        id="result",
        name="read_file",
        tool_call_id="call",
        content=[
            {"type": "text", "text": "source image"},
            {
                "type": "image",
                "mime_type": mime,
                "base64": base64.b64encode(_png()).decode(),
            },
        ],
    )


def test_bad_mime_does_not_write_or_publish(middleware, tmp_path):
    with pytest.raises(ValueError, match="Unable to externalize"):
        middleware._externalize_blocks(image_message("image/jpeg"))
    assert not (tmp_path / "generated").exists()


def test_pdf_read_uses_existing_file_reference_and_expands_only_model_copy(
    middleware, tmp_path
):
    data = _pdf()
    source = tmp_path / "source.pdf"
    source.write_bytes(data)
    tool = next(tool for tool in middleware.tools if tool.name == "read_file")
    result = tool.func(file_path="/source.pdf", runtime=_runtime())
    result_async = asyncio.run(
        tool.coroutine(file_path="/source.pdf", runtime=_runtime())
    )
    assert result.content == result_async.content
    ref = result.content[0]["extras"]["runtime_file"]
    assert ref["mime_type"] == "application/pdf"
    assert len(json.dumps(result.content[0]).encode()) <= 1024
    assert "base64" not in json.dumps(result.content)
    source.write_bytes(b"changed")
    expanded = middleware._expand_messages([result])
    assert base64.b64decode(expanded[0].content[1]["base64"]) == data
    assert "base64" not in json.dumps(result.content)
    ref["size_bytes"] += 1
    with pytest.raises(ValueError, match="no longer matches"):
        middleware._expand_messages([result])


def test_unopened_binary_type_never_leaks_inline(middleware):
    message = ToolMessage(
        tool_call_id="call",
        content=[{"type": "audio", "mime_type": "audio/wav", "base64": "YWJj"}],
    )
    with pytest.raises(ValueError, match="Unable to externalize"):
        middleware._externalize_blocks(message)


def test_write_failure_never_returns_inline_or_reference(middleware, monkeypatch):
    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(middleware.image_workspace, "save_asset", fail)
    with pytest.raises(ValueError, match="Unable to externalize"):
        middleware._externalize_blocks(image_message())


@pytest.mark.parametrize(
    "field,value",
    [
        ("sha256", "0" * 64),
        ("size_bytes", 1),
        ("mime_type", "image/webp"),
    ],
)
def test_model_rejects_mismatched_reference(middleware, field, value):
    result = middleware._externalize_blocks(image_message())
    result.content[1]["extras"]["runtime_image"][field] = value
    with pytest.raises(ValueError, match="no longer matches"):
        middleware._expand_messages([result])


@pytest.mark.parametrize("corrupt", [True, False])
def test_model_rejects_corrupt_or_missing_file(middleware, tmp_path, corrupt):
    from langchain_core.tools import ToolException

    result = middleware._externalize_blocks(image_message())
    ref = result.content[1]["extras"]["runtime_image"]
    path = tmp_path / ref["path"].removeprefix("/workspace/")
    if corrupt:
        path.write_bytes(b"corrupt")
    else:
        path.unlink()
    with pytest.raises(ToolException):
        middleware._expand_messages([result])


def test_atomic_dedup_and_failure_cleanup(middleware, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        refs = list(
            pool.map(
                lambda _: middleware.image_workspace.save_asset(_png(), "generated"),
                range(12),
            )
        )
    assert all(ref == refs[0] for ref in refs)
    assert len(list((tmp_path / "generated").iterdir())) == 1
    monkeypatch.setattr(
        "runtime_service.workspace.image_io.os.link",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError, match="disk full"):
        middleware.image_workspace.save_asset(_png(), "charts")
    assert list((tmp_path / "charts").iterdir()) == []


@pytest.mark.parametrize(
    "extension,make_data,ref_key",
    [("png", _png, "runtime_image"), ("pdf", _pdf, "runtime_file")],
)
def test_v3_public_events_checkpoint_and_followup_have_only_references(
    tmp_path, extension, make_data, ref_key
):
    from langchain.agents import create_agent
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from support import BindableFakeMessagesChatModel

    (tmp_path / "workspace" / "work").mkdir(parents=True)
    source = tmp_path / "workspace" / "work" / f"source.{extension}"
    data = make_data()
    encoded = base64.b64encode(data).decode()
    source.write_bytes(data)
    seen = []

    class Model(BindableFakeMessagesChatModel):
        def _generate(self, messages, *args, **kwargs):
            seen.append(messages)
            return super()._generate(messages, *args, **kwargs)

    middleware = ImageReferenceFilesystemMiddleware(
        backend=FilesystemBackend(root_dir=tmp_path),
        image_workspace=ImageWorkspace(tmp_path / "workspace"),
    )
    model = Model(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {"file_path": f"/workspace/work/source.{extension}"},
                        "id": "read-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="image seen"),
            AIMessage(content="still seen"),
        ]
    )
    graph = create_agent(model, middleware=[middleware], checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "image-reference"}}

    async def run():
        events = [
            event
            async for event in graph.astream(
                {"messages": [HumanMessage(content="read image")]},
                config,
                version="v3",
                stream_mode=["messages", "tools", "values"],
            )
        ]
        serialized = json.dumps(events, default=str)
        assert ref_key in serialized
        assert "tool-finished" in serialized
        assert encoded not in serialized
        state = await graph.aget_state(config)
        tool = next(m for m in state.values["messages"] if isinstance(m, ToolMessage))
        ref = tool.content[0]["extras"][ref_key]
        assert len(json.dumps(tool.content[0]).encode()) <= 1024
        source.write_bytes(b"overwritten source")
        store = (
            middleware.image_workspace
            if extension == "png"
            else middleware.document_workspace
        )
        assert (
            store.read(ref["path"]) == data
            if extension == "png"
            else store.read(ref["path"])[0] == data
        )
        await graph.ainvoke(
            {"messages": [HumanMessage(content="what did you see?")]}, config
        )
        assert "base64" not in str((await graph.aget_state(config)).values)

    asyncio.run(run())
    assert len(seen) == 3
    for messages in seen[1:]:
        assert encoded in str(messages)

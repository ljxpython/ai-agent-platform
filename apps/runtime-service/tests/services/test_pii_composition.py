"""Exercise actual composition roots and their child/recovery handlers."""

import asyncio
from unittest.mock import AsyncMock, Mock

import deepagents.graph as deep_graph
import deepagents.middleware.subagents as subagent_graph
import pytest
from deepagents.backends import FilesystemBackend
from langchain.agents import create_agent
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from middlewares.test_conversation_offloading import history, model
from services.test_model_resilience_composition import (
    A,
    B,
    dearflow,
    install_models,
    managed_config,
    outage,
    reference,
    showcase,
    workflow,
)
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.conversation_offloading import (
    ConversationOffloadingMiddleware,
)
from runtime_service.middlewares.pii_redaction import (
    PiiRedactionMiddleware,
    PiiSummarizationMiddleware,
)
from runtime_service.runtime import ModelConnectionBundle, ModelResiliencePolicy
from runtime_service.runtime.errors import RuntimePrivacyError
from runtime_service.runtime.pii import PiiRedactionConfig

EMAIL = "alice@example.test"
SECRET = "synthetic-redaction-secret-32-bytes"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("RUNTIME_PII_REDACTION_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_PII_TOKEN_SECRET", SECRET)


@pytest.mark.parametrize(
    "module,graph_id",
    [
        (reference, "reference_agent"),
        (workflow, "workflow_demo"),
        (dearflow, "dearflow_agent"),
        (showcase, "showcase_demo"),
    ],
)
def test_all_roots_primary_and_fallback_protect_provider_and_keep_state(
    enabled, monkeypatch, tmp_path, module, graph_id
):
    expected = 1
    models, _ = install_models(
        monkeypatch,
        module,
        tmp_path,
        [outage() for _ in range(expected)],
        [AIMessage("done")],
    )

    async def run():
        cfg = managed_config(graph_id)
        graph = await module.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        return await graph.ainvoke(
            {"messages": [HumanMessage(EMAIL)]}, cfg, context=cfg["context"]
        )

    result = asyncio.run(run())
    assert result["messages"][0].content == EMAIL
    assert len(models[A].seen) == expected and len(models[B].seen) == 1
    for candidate_model in models.values():
        assert EMAIL not in str(candidate_model.seen) and "[EMAIL_" in str(
            candidate_model.seen
        )


@pytest.mark.parametrize(
    "module,graph_id,role",
    [
        (dearflow, "dearflow_agent", "general-purpose"),
        (showcase, "showcase_demo", "research"),
        (showcase, "showcase_demo", "general-purpose"),
        (showcase, "showcase_demo", "chart-agent"),
    ],
)
def test_each_declared_child_uses_same_policy(
    enabled, monkeypatch, tmp_path, module, graph_id, role
):
    dispatch = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "task",
                "args": {"description": "Research " + EMAIL, "subagent_type": role},
                "id": "dispatch",
            }
        ],
    )
    models, _ = install_models(
        monkeypatch,
        module,
        tmp_path,
        [dispatch, AIMessage("child done"), AIMessage("parent done")],
        [],
    )

    async def run():
        cfg = managed_config(graph_id)
        graph = await module.get_agent(cfg)
        return await graph.ainvoke(
            {"messages": [HumanMessage("parent " + EMAIL)]}, cfg, context=cfg["context"]
        )

    result = asyncio.run(run())
    assert len(models[A].seen) == 3
    assert EMAIL not in str(models[A].seen)
    assert EMAIL in str(result["messages"][1].tool_calls)


def test_protection_failure_never_uses_fallback_or_provider(
    enabled, monkeypatch, tmp_path
):
    models, _ = install_models(
        monkeypatch,
        dearflow,
        tmp_path,
        [AIMessage("unsafe")],
        [AIMessage("unsafe backup")],
    )

    async def run():
        cfg = managed_config("dearflow_agent")
        graph = await dearflow.get_agent(cfg)
        return await graph.ainvoke(
            {"messages": [HumanMessage(content=[{"type": "unknown", "text": EMAIL}])]},
            cfg,
            context=cfg["context"],
        )

    with pytest.raises(RuntimePrivacyError):
        asyncio.run(run())
    assert not models[A].seen and not models[B].seen


def test_summary_precedes_trimming_and_keeps_original_archive(tmp_path):
    policy = PiiRedactionConfig(True, SECRET, scope=("tenant", "project", "thread"))
    model = BindableFakeMessagesChatModel(responses=[AIMessage("safe summary")])
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
    mw = PiiSummarizationMiddleware(
        model,
        backend,
        pii_config=policy,
        trigger=("messages", 3),
        keep=("messages", 1),
        truncate_args_settings={
            "trigger": ("messages", 1),
            "keep": ("messages", 0),
            "max_length": 30,
        },
    )
    mw._lc_helper._summary_model = AsyncMock()
    mw._lc_helper._summary_model.ainvoke.return_value = AIMessage("safe summary")
    call = {
        "name": "write_file",
        "args": {
            "content": EMAIL + " " + "x" * 100,
            "file_path": "/workspace/work/a.txt",
        },
        "id": "c",
        "type": "tool_call",
    }
    assert mw._truncate_tool_call(call)["args"]["content"] == call["args"]["content"]
    messages = [HumanMessage(EMAIL), AIMessage("answer"), HumanMessage("new prompt")]
    request = ModelRequest(model=model, messages=messages, state={"messages": messages})
    handler = AsyncMock(return_value=ModelResponse(result=[AIMessage("done")]))
    asyncio.run(mw.awrap_model_call(request, handler))
    assert EMAIL not in str(mw._lc_helper._summary_model.ainvoke.call_args)
    archived = "".join(path.read_text() for path in tmp_path.rglob("*.md"))
    assert EMAIL in archived and request.messages[0].content == EMAIL
    assert mw.name == "SummarizationMiddleware"


@pytest.mark.parametrize(
    "engineering,resilience",
    [(False, False), (False, True), (True, False), (True, True)],
)
@pytest.mark.parametrize(
    "module,graph_id", [(dearflow, "dearflow_agent"), (showcase, "showcase_demo")]
)
def test_roots_compile_exactly_one_protected_summary(
    enabled, monkeypatch, tmp_path, engineering, resilience, module, graph_id
):
    models, _ = install_models(monkeypatch, module, tmp_path, [AIMessage("done")], [])
    models[A].profile = {"max_input_tokens": 128000, "max_output_tokens": 1024}
    monkeypatch.setenv("AGENT_CONTEXT_MANAGEMENT_ENABLED", "1" if engineering else "0")
    if not resilience:
        module.fetch_model_bundle.return_value = ModelConnectionBundle(
            primary={"model_id": A}, policy=ModelResiliencePolicy()
        )
    compiled = {}

    def capture(*args, **kwargs):
        compiled[kwargs["name"]] = kwargs["middleware"]
        return create_agent(*args, **kwargs)

    monkeypatch.setattr(deep_graph, "create_agent", capture)
    monkeypatch.setattr(subagent_graph, "create_agent", capture)

    async def run():
        cfg = managed_config(graph_id)
        cfg["context"]["max_tokens"] = 256
        from runtime_service.runtime.resolver import runtime_context_hash

        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph = await module.get_agent(cfg)
        return await graph.ainvoke(
            {"messages": [HumanMessage(EMAIL)]}, cfg, context=cfg["context"]
        )

    asyncio.run(run())
    for middleware in compiled.values():
        summaries = [
            item for item in middleware if item.name == "SummarizationMiddleware"
        ]
        assert len(summaries) == 1
        summary = summaries[0]
        if hasattr(summary, "summary"):
            summary = summary.summary
        assert isinstance(summary, PiiSummarizationMiddleware)
        assert summary.pii_config.enabled and summary.pii_config.scope is not None
    assert EMAIL not in str(models[A].seen)


@pytest.mark.parametrize("manual", [False, True])
def test_engineering_summary_protects_inputs_and_preserves_archive(tmp_path, manual):
    policy = PiiRedactionConfig(True, SECRET, scope=("tenant", "project", "thread"))
    instance = model()
    backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
    mw = ConversationOffloadingMiddleware(
        instance, backend, manual=manual, pii_config=policy
    )
    messages = history()
    messages[0].content = "original " + EMAIL + " " + messages[0].content
    request = ModelRequest(
        model=instance, messages=messages, state={"messages": messages}
    )
    sent = []

    async def provider(candidate):
        sent.append(candidate.messages)
        return ModelResponse(result=[AIMessage("done")])

    async def handler(candidate):
        return await PiiRedactionMiddleware(policy).awrap_model_call(
            candidate, provider
        )

    result = asyncio.run(mw._invoke(request, handler, manual=manual))
    assert result.command.update["_summarization_event"]
    assert EMAIL not in str(instance.calls) and EMAIL not in str(sent)
    assert EMAIL in messages[0].content
    assert EMAIL in "".join(path.read_text() for path in tmp_path.rglob("*.md"))


def test_overflow_recovery_protects_summary_and_tail_without_changing_state(tmp_path):
    policy = PiiRedactionConfig(True, SECRET, scope=("tenant", "project", "thread"))
    instance = model()
    mw = PiiSummarizationMiddleware(
        instance,
        FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True),
        pii_config=policy,
        trigger=("messages", 100),
        keep=("messages", 1),
    )
    messages = [
        m
        for i in range(10)
        for m in (HumanMessage(EMAIL + " question"), AIMessage("answer"))
    ]
    request = ModelRequest(
        model=instance, messages=messages, state={"messages": messages}
    )
    attempts = []

    async def provider(candidate):
        attempts.append(candidate.messages)
        if len(attempts) == 1:
            raise ContextOverflowError("synthetic overflow")
        return ModelResponse(result=[AIMessage("done")])

    async def handler(candidate):
        return await PiiRedactionMiddleware(policy).awrap_model_call(
            candidate, provider
        )

    result = asyncio.run(mw.awrap_model_call(request, handler))
    assert result.command.update["_summarization_event"] and len(attempts) == 2
    assert EMAIL not in str(attempts) and EMAIL not in str(instance.calls)
    assert messages[0].content == EMAIL + " question"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_overflow_large_sensitive_tool_tail_stops_before_lossy_recovery(
    tmp_path, asynchronous
):
    policy = PiiRedactionConfig(True, SECRET, scope=("tenant", "project", "thread"))
    instance = model()
    mw = PiiSummarizationMiddleware(
        instance,
        FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True),
        pii_config=policy,
    )
    content = "x" * 3998 + " " + EMAIL + " " * 100
    messages = [
        HumanMessage("old"),
        AIMessage(
            "",
            tool_calls=[
                {"name": "read_file", "id": "c", "args": {"file_path": "/work.txt"}}
            ],
        ),
        ToolMessage(content, tool_call_id="c", name="read_file"),
    ]
    request = ModelRequest(
        model=instance, messages=messages, state={"messages": messages}
    )
    handler = (
        AsyncMock(side_effect=ContextOverflowError("synthetic"))
        if asynchronous
        else Mock(side_effect=ContextOverflowError("synthetic"))
    )
    with pytest.raises(RuntimePrivacyError):
        if asynchronous:
            asyncio.run(mw.awrap_model_call(request, handler))
        else:
            mw.wrap_model_call(request, handler)
    assert handler.call_count == 1 and messages[-1].content == content
    assert not instance.calls

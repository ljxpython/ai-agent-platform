from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

research_agent_graph = importlib.import_module("runtime_service.agents.research_agent.graph")


def test_async_backend_root_dir_creation_uses_to_thread(monkeypatch: Any) -> None:
    calls: list[tuple[Any, tuple[Any, ...], dict[str, Any]]] = []

    async def fake_to_thread(func: Any, /, *args: Any, **kwargs: Any) -> Any:
        calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(research_agent_graph.asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(
        research_agent_graph._aresolve_filesystem_backend_root_dir(
            {}, agent_name="research-demo-test"
        )
    )

    assert result.endswith("research-demo-test")
    assert len(calls) == 1
    _, args, kwargs = calls[0]
    assert args == ()
    assert kwargs == {"parents": True, "exist_ok": True}


def test_make_graph_builds_research_agent(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = object()
        system_prompt = ""

    async def fake_build_tools(options: Any) -> list[Any]:
        del options
        return ["base_tool"]

    async def fake_private_tools(config: dict[str, Any]) -> list[Any]:
        del config
        return ["private_tool"]

    class DummyMultimodalMiddleware:
        def __init__(
            self,
            *,
            parser_model_id: str = "iflow_qwen3-vl-plus",
            detail_mode: bool = False,
            detail_text_max_chars: int = 2000,
        ) -> None:
            self.parser_model_id = parser_model_id
            self.detail_mode = detail_mode
            self.detail_text_max_chars = detail_text_max_chars

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"name": kwargs.get("name"), "tools": kwargs.get("tools")}

    monkeypatch.setattr(
        research_agent_graph, "merge_trusted_auth_context", lambda config, ctx: ctx
    )
    monkeypatch.setattr(
        research_agent_graph, "build_runtime_config", lambda config, ctx: DummyOptions()
    )
    monkeypatch.setattr(research_agent_graph, "resolve_model", lambda spec: spec)
    monkeypatch.setattr(
        research_agent_graph, "apply_model_runtime_params", lambda model, options: model
    )
    monkeypatch.setattr(research_agent_graph, "build_tools", fake_build_tools)
    monkeypatch.setattr(
        research_agent_graph, "read_configurable", lambda config: config["configurable"]
    )
    monkeypatch.setattr(
        research_agent_graph, "aget_research_private_tools", fake_private_tools
    )
    monkeypatch.setattr(
        research_agent_graph,
        "list_research_subagents",
        lambda: [
            {
                "name": "research-subagent",
                "description": "desc",
                "system_prompt": "prompt",
                "skills": ["web-research"],
            }
        ],
    )
    monkeypatch.setattr(
        research_agent_graph,
        "list_research_agent_skills",
        lambda: ["/tmp/research-skills"],
    )
    monkeypatch.setattr(
        research_agent_graph,
        "build_research_runtime_tools",
        lambda: ["runtime_tool"],
    )
    monkeypatch.setattr(
        research_agent_graph,
        "MultimodalMiddleware",
        DummyMultimodalMiddleware,
    )
    monkeypatch.setattr(research_agent_graph, "create_deep_agent", fake_create_deep_agent)

    result = asyncio.run(
        research_agent_graph.make_graph(
            {
                "configurable": {
                    "research_multimodal_parser_model_id": "iflow_qwen3-vl-plus",
                    "research_multimodal_detail_mode": "true",
                    "research_multimodal_detail_text_max_chars": "1234",
                }
            },
            object(),
        )
    )

    assert result["name"] == "research-demo"
    assert captured["tools"] == ["base_tool", "runtime_tool", "private_tool"]
    assert captured["skills"] == ["/tmp/research-skills"]
    assert captured["subagents"][0]["name"] == "research-subagent"
    middleware = captured["middleware"]
    assert len(middleware) == 1
    assert middleware[0].parser_model_id == "iflow_qwen3-vl-plus"
    assert middleware[0].detail_mode is True
    assert middleware[0].detail_text_max_chars == 1234

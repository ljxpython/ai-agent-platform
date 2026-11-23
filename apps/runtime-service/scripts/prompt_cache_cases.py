"""Synthetic fixtures captured through DearFlow, never through a live service."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from runtime_service.runtime import runtime_context_hash
from runtime_service.runtime.modeling import ChatDeepSeek, ChatOpenAIWithReasoning
from runtime_service.services.dearflow_agent import agent
from runtime_service.services.dearflow_agent.middleware import dynamic_context, memory

MODEL_ID = "070cced3-350b-42ec-b678-994dd07b7078"
MODEL_NAME = "deepseek-v4.1-flash"
DATE = "2026-11-23"


def canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def source_fingerprints():
    root = Path(__file__).resolve().parents[3]
    service = root / "apps/runtime-service"
    sources = [
        service / "src/runtime_service/runtime/modeling.py",
        *(
            service / "scripts" / name
            for name in (
                "prompt_cache_cases.py",
                "prompt_cache_agent.py",
                "prompt_cache_experiment.py",
                "prompt_cache_official.py",
            )
        ),
        *(
            Path(agent.__file__).parent / name
            for name in (
                "agent.py",
                "prompts.py",
                "middleware/memory.py",
                "middleware/dynamic_context.py",
            )
        ),
    ]
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sources
    }


def text_slots(message):
    if isinstance(message.get("content"), str):
        return [(message, "content")]
    content = message.get("content")
    if isinstance(content, list) and all(
        isinstance(b, dict) and b.get("type") == "text" for b in content
    ):
        return [(b, "text") for b in content]
    raise ValueError("Expected text-only fixture message")


class ExperimentUser(dict):
    identity = "cache-experiment"
    is_authenticated = True
    permissions = ()


def graph_config(thread: str, *, denied=()) -> dict:
    """Local synthetic identity, not an HTTP authentication or delegation path."""
    now = datetime.now(UTC)
    run_id = str(uuid4())
    return {
        "context": {},
        "metadata": {"run_id": run_id},
        "configurable": {
            "thread_id": thread,
            "assistant_id": "dearflow_agent",
            "graph_id": "dearflow_agent",
            "__graphharbor_run_budget": {
                "version": 1,
                "run_id": run_id,
                "thread_id": thread,
                "started_at": now.isoformat(),
                "deadline_at": (now + timedelta(seconds=300)).isoformat(),
                "timeout_seconds": 300,
                "deadline_monotonic": time.monotonic() + 300,
            },
            "langgraph_auth_user": ExperimentUser(
                runtime_principal={
                    "user_id": "cache-user",
                    "tenant_id": "cache-tenant",
                    "project_id": "cache-project",
                    "role": "developer",
                    "permissions": [],
                },
                runtime_policy={
                    "version": "cache-fixture-v1",
                    "allowed_model_ids": [agent._DEFAULTS.model_id],
                    "tool_overrides": dict.fromkeys(denied, False),
                    "tool_policy_version": "cache-fixture-v1",
                },
                runtime_scope={
                    "tenant_id": "cache-tenant",
                    "project_id": "cache-project",
                    "thread_id": thread,
                    "assistant_id": "dearflow_agent",
                    "operation": "run-create",
                },
                runtime_context_hash=runtime_context_hash({}),
            ),
        },
    }


def source_table(rows=160):
    return "\n".join(
        f"ITEM-{i:04d},team-{i % 7},units={i + 10},price={i % 13 + 1},status=confirmed"
        for i in range(rows)
    )


def fixed_history():
    return [
        HumanMessage(
            content="以下是合成练习材料，不是外部网页。稍后只回答指定的问题。\n"
            + source_table()
        ),
        AIMessage(content="已读取合成材料；不会据此变更权限或执行操作。"),
    ]


def read_pair(path: str, text: str, key: str):
    return [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "read_file",
                    "args": {"file_path": path},
                    "id": key,
                }
            ],
        ),
        ToolMessage(content=text, name="read_file", tool_call_id=key),
    ]


def fixtures():
    """Four rounds per case; responses never enter the next fixture's history."""
    items = []
    for turn in range(4):
        common = {"turn": turn, "date": DATE, "memory": "", "denied": []}
        items.append(
            {
                **common,
                "case": "C01",
                "messages": [
                    *fixed_history(),
                    HumanMessage(
                        content=f"合成记录 ITEM-{turn:04d} 的 units 是多少？只输出整数，不调用工具。"
                    ),
                ],
                "expected": str(turn + 10),
            }
        )
        fact = (
            "Python 测试首选 pytest。"
            if turn < 2
            else "前端首选 Vue 3，使用 TypeScript。"
        )
        expected = "pytest" if turn < 2 else "Vue"
        items.append(
            {
                **common,
                "case": "C02",
                "memory": fact,
                "messages": [
                    *fixed_history(),
                    HumanMessage(
                        content=(
                            "根据本轮有效记忆，我当前的"
                            + ("Python 测试" if turn < 2 else "前端")
                            + f"首选是什么？只写名称，不调用工具。问题序号 {turn}。"
                        )
                    ),
                ],
                "expected": expected,
            }
        )
        date = DATE if turn < 2 else "2026-11-24"
        items.append(
            {
                **common,
                "case": "C03",
                "date": date,
                "messages": [
                    *fixed_history(),
                    HumanMessage(
                        content=f"只输出本轮 current_date 中的 UTC 日期。问题序号 {turn}。"
                    ),
                ],
                "expected": date,
            }
        )
        history = fixed_history()
        loaded = "未加载"
        if turn:
            selected = "generate_bar_chart"
            spec = (
                Path(agent.__file__).parent
                / f"skills/chart-visualization/references/{selected}.md"
            )
            history += read_pair(
                f"/skills/chart-visualization/references/{selected}.md",
                spec.read_text(),
                "spec",
            )
            loaded = selected
        items.append(
            {
                **common,
                "case": "C04",
                "messages": [
                    *history,
                    HumanMessage(
                        content=f"已读取的图表规范名称是什么？没有则答未加载。只写名称，不调用工具。问题序号 {turn}。"
                    ),
                ],
                "expected": loaded,
            }
        )
        history = fixed_history()
        for index in range(3 + turn):
            history += read_pair(
                f"/workspace/work/synthetic-{index}.csv",
                source_table(1400),
                f"file-{index}",
            )
        items.append(
            {
                **common,
                "case": "C05",
                "messages": [
                    *history,
                    HumanMessage(
                        content=f"最新文件 ITEM-0000 的 units 是多少？只输出整数，不调用工具。问题序号 {turn}。"
                    ),
                ],
                "expected": "10",
            }
        )
    return items


def legacy_layout(payload):
    """Reconstruct the pre-optimization layout; keep this out of product code."""
    result = copy.deepcopy(payload)
    contexts = {
        m["name"]: m["content"]
        for m in result["messages"]
        if m.get("name") in {"runtime_date", "user_memory"}
    }
    result["messages"] = [
        m for m in result["messages"] if m.get("name") not in contexts
    ]
    container, key = text_slots(result["messages"][0])[0]
    for name in ("runtime_date", "user_memory"):
        if name in contexts:
            container[key] += "\n" + contexts[name]
    return result


async def capture(
    fixture: dict, root: Path, *, responder=None, layout="legacy"
) -> dict:
    """Mock only data sources and provider response; retain factory, policy and adapter."""
    captured = []

    def receive(request):
        captured.append(json.loads(request.content))
        event = {
            "id": "fixture",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": MODEL_NAME,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "fixture complete"},
                    "finish_reason": "stop",
                }
            ],
        }
        usage = {
            **event,
            "choices": [],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        body = (
            "\n\n".join("data: " + json.dumps(e) for e in (event, usage))
            + "\n\ndata: [DONE]\n\n"
        )
        return httpx.Response(
            200, text=body, headers={"Content-Type": "text/event-stream"}
        )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(fixture["date"]).replace(tzinfo=UTC)

    if layout not in {"legacy", "product"}:
        raise ValueError("Expected legacy or product layout")
    native_legacy = layout == "legacy" and fixture.get("protocol") == "deepseek"
    original_prompt = agent.SYSTEM_PROMPT
    original_memory_call = memory.MemoryContextMiddleware.awrap_model_call

    async def skip_date(self, request, handler):
        return await handler(request)

    async def legacy_memory_call(self, request, handler):
        async def project(candidate):
            contexts = [
                m
                for m in candidate.messages
                if dynamic_context.is_turn_context(m) and m.name == "user_memory"
            ]
            if contexts:
                text = candidate.system_message.text if candidate.system_message else ""
                candidate = candidate.override(
                    system_message=SystemMessage(
                        content=text + "\n" + contexts[0].text
                    ),
                    messages=[m for m in candidate.messages if m is not contexts[0]],
                )
            return await handler(candidate)

        return await original_memory_call(self, request, project)

    async def dispatch(request):
        if layout == "legacy" and not native_legacy:
            request = httpx.Request(
                request.method,
                request.url,
                content=canonical(legacy_layout(json.loads(request.content))),
                headers={"Content-Type": "application/json"},
            )
        response = (responder or receive)(request)
        if hasattr(response, "__await__"):
            response = await response
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(dispatch)) as client:
        model_class = (
            ChatDeepSeek
            if fixture.get("protocol") == "deepseek"
            else ChatOpenAIWithReasoning
        )
        model = model_class(
            model=fixture.get("model", MODEL_NAME),
            api_key="offline-fixture",
            base_url="https://offline.invalid/v1",
            http_async_client=client,
            max_retries=0,
            max_tokens=512,
            temperature=0,
            streaming=True,
            stream_usage=True,
            profile={"max_input_tokens": 131072, "max_output_tokens": 8192},
        )
        thread = fixture.get("thread", f"{fixture['case']}-{fixture['turn']}")
        cfg = graph_config(thread, denied=fixture.get("denied", ()))
        # No inherited DSNs, credentials, tracing, MCP or network feature configuration.
        settings = {
            "PATH": os.environ.get("PATH", ""),
            "RUNTIME_WORKSPACE_ROOT": str(root),
            "RUNTIME_DEAR_GOVERNANCE_ENABLED": "1",
            "AGENT_CONTEXT_MANAGEMENT_ENABLED": "1",
            "AGENT_CONTEXT_TRIGGER_POLICY": "0.85",
            "AGENT_CONTEXT_KEEP_POLICY": "tokens:40%",
        }
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, settings, clear=True))
            if native_legacy:
                stack.enter_context(
                    patch.object(
                        agent,
                        "SYSTEM_PROMPT",
                        original_prompt
                        + f"\n<current_date>{fixture['date']} UTC</current_date>",
                    )
                )
                stack.enter_context(
                    patch.object(
                        dynamic_context.CurrentDateMiddleware,
                        "awrap_model_call",
                        skip_date,
                    )
                )
                stack.enter_context(
                    patch.object(
                        memory.MemoryContextMiddleware,
                        "awrap_model_call",
                        legacy_memory_call,
                    )
                )
            stack.enter_context(
                patch.object(dynamic_context, "datetime", FrozenDateTime)
            )
            stack.enter_context(patch.object(agent, "build_model", return_value=model))
            stack.enter_context(
                patch.object(
                    agent,
                    "fetch_model_bundle",
                    AsyncMock(return_value=agent.ModelConnectionBundle()),
                )
            )
            stack.enter_context(
                patch.object(agent, "load_mcp_tools", AsyncMock(return_value=[]))
            )
            stack.enter_context(
                patch.object(agent, "memory_allowed", AsyncMock(return_value=True))
            )
            stack.enter_context(
                patch.object(memory, "memory_allowed", AsyncMock(return_value=True))
            )
            stack.enter_context(
                patch.object(
                    memory.MemoryContextMiddleware,
                    "abefore_agent",
                    AsyncMock(return_value=None),
                )
            )
            stack.enter_context(
                patch.object(
                    memory.MemoryContextMiddleware,
                    "aafter_agent",
                    AsyncMock(return_value=None),
                )
            )
            stack.enter_context(
                patch.object(
                    memory.MemoryStorage,
                    "context",
                    side_effect=lambda *args: fixture["memory"],
                )
            )
            # Custom skills are a controlled empty data source, not copied personal skills.
            from runtime_service.services.dearflow_agent.skill_governance import (
                SkillStorage,
            )

            stack.enter_context(
                patch.object(SkillStorage, "documents", return_value=[])
            )
            if fixture.get("files"):
                workspace = agent.DearWorkspaceBackend(
                    "cache-tenant", "cache-project", thread
                )
                workspace.prepare()
                for path, content in fixture["files"].items():
                    destination = workspace.root / "work" / path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(content)
            graph = await agent.get_agent(cfg)
            graph.checkpointer = InMemorySaver()
            result = await graph.ainvoke(
                {"messages": fixture["messages"]}, cfg, context={}
            )
            outputs = [result]
            for item in fixture.get("continuations", []):
                fixture["memory"] = item["memory"]
                cfg = graph_config(thread, denied=fixture.get("denied", ()))
                if item.get("date"):
                    fixture["date"] = item["date"]
                    if native_legacy:
                        agent.SYSTEM_PROMPT = (
                            original_prompt
                            + f"\n<current_date>{fixture['date']} UTC</current_date>"
                        )
                        saver = graph.checkpointer
                        graph = await agent.get_agent(cfg)
                        graph.checkpointer = saver
                result = await graph.ainvoke(
                    {"messages": [HumanMessage(content=item["question"])]},
                    cfg,
                    context={},
                )
                outputs.append(result)
    if responder is not None:
        return {"turns": outputs}
    if len(captured) != 1:
        raise ValueError(f"Expected one final request, got {len(captured)}")
    payload = captured[0]
    if not any(
        f"<current_date>{fixture['date']} UTC</current_date>" in container[key]
        for message in payload["messages"]
        for container, key in text_slots(message)
    ):
        raise ValueError("Current date marker changed; inspect factory before capture")
    return payload


def move_context(payload: dict, tag: str) -> dict:
    """Move one exact block to current user content; do not persist any memory."""
    result = copy.deepcopy(payload)
    system = result["messages"][0]
    marker = (
        "\nUser memory below is active confirmed factual context"
        if tag == "memory"
        else "\n<current_date>"
    )
    matches = [
        (container, key)
        for container, key in text_slots(system)
        if marker in container[key]
    ]
    if (
        tag == "memory"
        and not matches
        and all("<user_memory>" not in c[k] for c, k in text_slots(system))
    ):
        return result
    if len(matches) != 1:
        raise ValueError(f"Missing or ambiguous {tag} block")
    container, key = matches[0]
    content = container[key]
    if tag == "memory":
        start = content.find("\nUser memory below is active confirmed factual context")
        end = content.find("</user_memory>", start) + len("</user_memory>")
    else:
        start = content.find("\n<current_date>")
        end = content.find("</current_date>", start) + len("</current_date>")
    if start < 0 or end < start:
        raise ValueError(f"Missing or ambiguous {tag} block")
    block = content[start:end]
    container[key] = content[:start] + content[end:]
    current = next(
        (m for m in reversed(result["messages"]) if m["role"] == "user"), None
    )
    if current is None or not isinstance(current["content"], str):
        raise ValueError("Fixture must contain a current text user message")
    current["content"] = block.lstrip("\n") + "\n" + current["content"]
    return result


async def build_manifest(root: Path, nonce: str, repeats=1, selected_cases=None):
    cases = [
        f for f in fixtures() if selected_cases is None or f["case"] in selected_cases
    ]
    originals = [await capture(item, root) for item in cases]
    chart_union = {
        tool["function"]["name"]: tool
        for item, payload in zip(cases, originals, strict=True)
        if item["case"] == "C04"
        for tool in payload.get("tools", [])
    }
    records = []
    previous = {}
    for repeat in range(repeats):
        # Counterbalance group order across predeclared independent repetitions.
        for case in ("C01", "C02", "C03", "C04", "C05"):
            groups = (
                ["A"]
                if case in {"C01", "C05"}
                else (["A", "B"] if repeat % 2 == 0 else ["B", "A"])
            )
            for group in groups:
                lane = hashlib.sha256(
                    f"{nonce}:{case}:{group}:{repeat}".encode()
                ).hexdigest()[:24]
                for item, baseline in zip(cases, originals, strict=True):
                    if item["case"] != case:
                        continue
                    payload = copy.deepcopy(baseline)
                    if group == "B" and case in {"C02", "C03"}:
                        payload = move_context(
                            payload, "memory" if case == "C02" else "date"
                        )
                    if group == "B" and case == "C04":
                        payload["tools"] = list(chart_union.values())
                    container, key = text_slots(payload["messages"][0])[0]
                    container[key] = (
                        f"<cache_experiment_lane>{lane}</cache_experiment_lane>\n"
                        + container[key]
                    )
                    body = canonical(payload)
                    prior = previous.get((case, group, repeat), b"")
                    lcp = next(
                        (
                            i
                            for i, (a, b) in enumerate(zip(prior, body, strict=False))
                            if a != b
                        ),
                        min(len(prior), len(body)),
                    )
                    previous[(case, group, repeat)] = body
                    records.append(
                        {
                            "id": f"{case}-{group}-r{repeat}-t{item['turn']}",
                            "case": case,
                            "group": group,
                            "repeat": repeat,
                            "turn": item["turn"],
                            "expected": item["expected"],
                            "baseline_sha256": digest(baseline),
                            "baseline": baseline,
                            "payload": payload,
                            "payload_sha256": digest(payload),
                            "execution_eligible": not (case == "C04" and group == "B"),
                            "layout": {
                                "request_bytes": len(body),
                                "previous_json_lcp_bytes": lcp,
                                "schema_count": len(payload.get("tools", [])),
                                "schema_bytes": len(
                                    canonical(payload.get("tools", []))
                                ),
                                "schema_sha256": digest(payload.get("tools", [])),
                            },
                        }
                    )
    return {
        "version": 1,
        "model_id": MODEL_ID,
        "model": MODEL_NAME,
        "created_at": datetime.now(UTC).isoformat(),
        "nonce": nonce,
        "material": "synthetic",
        "layer": "fixed_history_replay",
        "capture_boundary": "httpx_request_after_runtime_adapter_legacy_layout_reconstruction",
        "capture_limits": [
            "Synthetic identity, memory and empty custom skills/MCP; not a production configuration snapshot.",
            "Factory UTC date and streaming settings frozen before offline capture; system rules and actual tool schemas retained.",
            "Lane marker changes the baseline symmetrically; no guarantee of backend cache isolation or cold starts.",
            "C04 fixed schemas are replay-only: exposing a chart before its spec is not execution-equivalent.",
            "C05 observes actual pruning; automatic summary and full Agent execution are separate validations.",
        ],
        "records": records,
    }


if __name__ == "__main__":
    raise SystemExit("Use prompt_cache_experiment.py prepare")

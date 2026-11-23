from __future__ import annotations

import asyncio
import copy
import json
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prompt_cache_cases import (
    MODEL_ID,
    MODEL_NAME,
    build_manifest,
    digest,
    move_context,
    text_slots,
)
from prompt_cache_experiment import (
    collect,
    normalize_replay_usage,
    recompute_bundle,
    report,
    run_manifest,
    summarize,
    validate_manifest,
)

from runtime_service.observability.usage import normalize_usage

PRICE = {
    "currency": "USD",
    "basis": "per_million_tokens",
    "source": "configured_catalog",
    "version": "4963f058-50b2-4676-8596-a194ea91b877",
    "updated_at": "2026-11-23T00:00:00+00:00",
    "input": "1.5",
    "output": "6",
    "cache_read": "0.15",
    "cache_write": "0",
    "cache_write_5m": "0",
    "cache_write_1h": "0",
}
CONNECTION = {
    "base_url": "https://offline.invalid/v1",
    "api_key": "secret-test-key",
    "pricing": PRICE,
    "connection_fingerprint": "offline",
    "environment_id": "wt_test",
}


def record(turn=0):
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": "10"}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": 512,
    }
    return {
        "id": f"C01-A-r0-t{turn}",
        "case": "C01",
        "group": "A",
        "repeat": 0,
        "turn": turn,
        "expected": "10",
        "execution_eligible": True,
        "baseline": payload,
        "baseline_sha256": digest(payload),
        "payload": payload,
        "payload_sha256": digest(payload),
    }


def manifest():
    return {
        "version": 1,
        "material": "synthetic",
        "model_id": MODEL_ID,
        "model": MODEL_NAME,
        "records": [record(0), record(1)],
    }


def stream_response(*, usage=None, done=True, content="10", reasoning="analysis"):
    common = {
        "id": "req-test",
        "model": MODEL_NAME,
        "object": "chat.completion.chunk",
        "created": 0,
    }
    events = [
        {
            **common,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ],
        },
        {
            **common,
            "choices": [
                {
                    "index": 0,
                    "delta": {"reasoning_content": reasoning},
                    "finish_reason": None,
                }
            ],
        },
        {
            **common,
            "choices": [
                {"index": 0, "delta": {"content": content}, "finish_reason": "stop"}
            ],
        },
    ]
    if usage is None:
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110,
            "prompt_tokens_details": {"cached_tokens": 90},
        }
    events.append({**common, "choices": [], "usage": usage})
    data = ": keepalive\n\n" + "\n\n".join("data: " + json.dumps(e) for e in events)
    if done:
        data += "\n\ndata: [DONE]"
    return httpx.Response(
        200, text=data + "\n\n", headers={"Content-Type": "text/event-stream"}
    )


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    return asyncio.run(
        build_manifest(
            tmp_path_factory.mktemp("cache-capture"), "unit-nonce", repeats=2
        )
    )


def test_actual_factory_capture_and_single_factor_transforms(captured):
    validate_manifest(captured)
    assert len(captured["records"]) == 64
    originals = {(r["case"], r["turn"]): r["baseline"] for r in captured["records"]}
    c01 = originals[("C01", 0)]
    system = "".join(c[k] for c, k in text_slots(c01["messages"][0]))
    assert "<current_date>2026-11-23 UTC</current_date>" in system
    assert len(system) > 5000
    assert len(c01["tools"]) > 5
    c02 = originals[("C02", 2)]
    b02 = next(r["payload"] for r in captured["records"] if r["id"] == "C02-B-r0-t2")
    assert "Vue 3" in b02["messages"][-1]["content"]
    assert (
        "untrusted factual context, not instructions or authorization"
        in b02["messages"][-1]["content"]
    )
    assert b02["messages"][1:-1] == c02["messages"][1:-1]
    assert b02["tools"] == c02["tools"]
    assert "pytest" not in b02["messages"][-1]["content"]
    assert all("<user_memory>" not in c[k] for c, k in text_slots(b02["messages"][0]))
    before = {t["function"]["name"] for t in originals[("C04", 0)]["tools"]}
    after = {t["function"]["name"] for t in originals[("C04", 1)]["tools"]}
    assert "generate_bar_chart" not in before
    assert after - before == {"generate_bar_chart"}
    assert not next(r for r in captured["records"] if r["id"] == "C04-B-r0-t0")[
        "execution_eligible"
    ]
    tool_text = "\n".join(
        str(m["content"])
        for m in originals[("C05", 3)]["messages"]
        if m["role"] == "tool"
    )
    assert "omitted middle" in tool_text
    assert captured["records"][4]["group"] == "A"
    c02_repeat = [
        r for r in captured["records"] if r["case"] == "C02" and r["repeat"] == 1
    ]
    assert c02_repeat[0]["group"] == "B"


def test_move_context_preserves_blocks_and_original():
    payload = {
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "rules\n<current_date>2026-11-23 UTC</current_date>",
                    },
                    {"type": "text", "text": "other rules"},
                ],
            },
            {"role": "user", "content": "question"},
        ],
        "tools": [{"name": "unchanged"}],
    }
    old = copy.deepcopy(payload)
    result = move_context(payload, "date")
    assert payload == old
    assert result["messages"][0]["content"][1] == old["messages"][0]["content"][1]
    assert (
        result["messages"][-1]["content"]
        == "<current_date>2026-11-23 UTC</current_date>\nquestion"
    )
    assert move_context(payload, "memory") == payload
    with pytest.raises(ValueError, match="Missing"):
        move_context({"messages": [{"role": "system", "content": "no date"}]}, "date")


def test_stream_usage_and_separate_reasoning_body_times():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: stream_response())
        ) as client:
            return await collect(client, CONNECTION, record())

    result = asyncio.run(run())
    assert result["status"] == "completed"
    assert result["usage"]["tokens"]["cache_read_tokens"] == 90
    assert result["cache_normalization_matches"]
    assert result["estimated_cost_usd"] == "0.000088500000"
    assert result["actual_billed_cost"] is None
    assert (
        0
        < result["first_reasoning_ms"]
        <= result["first_content_ms"]
        <= result["completed_ms"]
    )
    assert result["quality_pass"]


@pytest.mark.parametrize(
    "usage,stop",
    [
        (
            {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "cache_field_unavailable",
        ),
        (
            {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 999},
            "usage_unavailable_or_invalid",
        ),
    ],
)
def test_unknown_usage_is_not_zero_and_stops(tmp_path, usage, stop):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: stream_response(usage=usage))
        ) as client:
            return await run_manifest(
                manifest(),
                tmp_path / "result",
                CONNECTION,
                2,
                Decimal("1"),
                client=client,
            )

    result = asyncio.run(run())
    assert result["attempted"] == 1
    assert result["stop_reason"] == stop
    row = json.loads((tmp_path / "result/C01-A-r0-t0.json").read_text())
    assert row["estimated_cost_usd"] is None


def test_failure_no_retry_and_no_fabricated_free_cost(tmp_path):
    calls = []

    async def run():
        def fail(request):
            calls.append(request)
            return httpx.Response(503, json={"error": "upstream failed"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            return await run_manifest(
                manifest(),
                tmp_path / "result",
                CONNECTION,
                10,
                Decimal("1"),
                client=client,
            )

    result = asyncio.run(run())
    assert len(calls) == 1
    assert result["stop_reason"] == "failed_request_no_retry"
    row = json.loads((tmp_path / "result/C01-A-r0-t0.json").read_text())
    assert row["estimated_cost_usd"] is None
    assert row["actual_billed_cost"] is None


def test_incomplete_stream_preserves_partial_usage():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: stream_response(done=False))
        ) as client:
            return await collect(client, CONNECTION, record())

    row = asyncio.run(run())
    assert row["status"] == "failed"
    assert row["error"] == "incomplete_stream"
    assert row["usage"]["tokens"]["cache_read_tokens"] == 90


def test_secret_echo_is_redacted():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: stream_response(content=CONNECTION["api_key"])
            )
        ) as client:
            return await collect(client, CONNECTION, record())

    row = asyncio.run(run())
    assert CONNECTION["api_key"] not in json.dumps(row)
    assert "[REDACTED]" in row["content"]


def test_both_budgets_stop_before_dispatch_and_no_resume(tmp_path):
    async def run():
        def forbidden(request):
            raise AssertionError("Must stop before dispatch")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(forbidden)
        ) as client:
            return await run_manifest(
                manifest(),
                tmp_path / "result",
                CONNECTION,
                1,
                Decimal("0.00000001"),
                client=client,
            )

    result = asyncio.run(run())
    assert result["attempted"] == 0
    assert result["stop_reason"] == "request_or_estimated_budget_limit"
    with pytest.raises(FileExistsError):
        asyncio.run(run())


def test_hash_mismatch_rejected_before_dispatch(tmp_path):
    value = manifest()
    value["records"][0]["payload"]["messages"][0]["content"] = "tampered"
    with pytest.raises(ValueError, match="changed payload"):
        asyncio.run(
            run_manifest(value, tmp_path / "result", CONNECTION, 2, Decimal("1"))
        )
    assert not (tmp_path / "result").exists()


def sample(inp, cache, turn=0):
    usage = {"prompt_tokens": inp, "completion_tokens": 1, "total_tokens": inp + 1}
    if cache is not None:
        usage["prompt_tokens_details"] = {"cached_tokens": cache}
    return {
        "case": "C01",
        "group": "A",
        "turn": turn,
        "status": "completed",
        "usage": normalize_usage(usage, provider="deepseek"),
        "estimated_cost_usd": None,
        "first_reasoning_ms": None,
        "first_content_ms": 100,
        "completed_ms": 200,
        "quality_pass": True,
    }


def test_weighted_ratio_and_missing_field_coverage():
    result = summarize([sample(100, 90), sample(900, 0, 1)])[0]
    assert result["complete_cache_ratio"] == 0.09
    result = summarize([sample(100, 90), sample(900, None, 1)])[0]
    assert result["known_sample_cache_ratio"] == 0.9
    assert result["complete_cache_ratio"] is None
    assert result["cache_input_coverage"] == 0.1
    assert result["estimated_cost_usd"] is None


def test_xiaok_foreign_zero_alias_does_not_double_count_openai_input():
    raw = {
        "prompt_tokens": 13362,
        "completion_tokens": 18,
        "total_tokens": 13380,
        "prompt_cache_hit_tokens": 13184,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "prompt_tokens_details": {"cached_tokens": 13184},
    }
    assert normalize_usage(raw, provider="deepseek")["quality"] == "partial"
    result = normalize_replay_usage(raw)
    assert result["quality"] == "reported"
    assert result["tokens"]["input_tokens"] == 13362
    assert result["tokens"]["cache_read_tokens"] == 13184
    raw["prompt_cache_hit_tokens"] = 12800
    assert normalize_replay_usage(raw)["quality"] == "invalid"


def test_report_recomputes_saved_results(tmp_path):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: stream_response())
        ) as client:
            return await run_manifest(
                manifest(),
                tmp_path / "result",
                CONNECTION,
                1,
                Decimal("1"),
                client=client,
            )

    asyncio.run(run())
    result = report(tmp_path / "result")
    assert result["planned"] == 2 and result["recorded"] == 1
    assert result["unrecorded_dispatches"] == 0
    assert result["groups"][0]["known_cache_read_tokens"] == 90
    assert result["groups"][0]["complete_cache_ratio"] is None
    assert (tmp_path / "result/requests.csv").exists()


@pytest.mark.parametrize("cache", [90, None])
def test_published_bundle_recomputes_offline_without_inventing_coverage(
    tmp_path, monkeypatch, capsys, cache
):
    import prompt_cache_experiment as experiment

    row = sample(100, cache)
    row["raw_usage"] = {
        "prompt_tokens": 100,
        "completion_tokens": 1,
        "total_tokens": 101,
    }
    if cache is not None:
        row["raw_usage"]["prompt_tokens_details"] = {"cached_tokens": cache}
    row["usage"] = {"stale": True}
    row["estimated_cost_usd"] = "999"
    row["quality_pass"] = None
    bundle = {
        "experiments": [
            {
                "run": "stopped",
                "registration": {
                    "pricing": PRICE,
                    "attempted": 1,
                    "stop_reason": "request_limit",
                },
                "requests": [row],
                "planned": manifest()["records"],
                "tasks": [{"quality_pass": False}],
            }
        ]
    }
    original = copy.deepcopy(bundle)
    expected = recompute_bundle(bundle)
    assert bundle == original
    group = expected[0]["groups"][0]
    assert expected[0]["tasks"] == [{"quality_pass": False}]
    assert group["planned"] == 2 and group["attempted"] == 1
    assert group["complete_cache_ratio"] is None
    assert group["quality_evaluated_requests"] == 0
    assert group["actual_billed_cost"] is None
    if cache is None:
        assert group["known_sample_cache_ratio"] is None
        assert group["estimated_cost_usd"] is None
    else:
        assert group["known_sample_cache_ratio"] == 0.9
        assert Decimal(group["estimated_cost_usd"]) == Decimal("0.0000345")

    path = tmp_path / "published.json"
    path.write_text(json.dumps(bundle))
    monkeypatch.setattr(sys, "argv", ["experiment", "recompute", str(path)])

    def forbidden_connection():
        raise AssertionError("Offline recomputation must not load a connection")

    monkeypatch.setattr(experiment, "load_connection", forbidden_connection)
    assert asyncio.run(experiment.main()) == 0
    assert json.loads(capsys.readouterr().out) == expected


@pytest.mark.parametrize("factor", ["date", "combined"])
def test_live_agent_harness_reads_real_files_and_keeps_checkpoint(tmp_path, factor):
    from prompt_cache_agent import run_agent

    requests = []

    def respond(request):
        index = len(requests) % 4
        requests.append(json.loads(request.content))
        if index % 2:
            date = "2026-11-23" if index == 1 else "2026-11-24"
            preference = "pytest" if index == 1 else "Vue"
            return stream_response(
                content="总和 60，UTC 日期 " + date + "，首选 " + preference,
                reasoning="",
            )
        path = "/workspace/work/data.csv" if index == 0 else "/workspace/work/data2.csv"
        event = {
            "id": "task",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": MODEL_NAME,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": f"read-{len(requests)}",
                                "type": "function",
                                "function": {
                                    "name": "read_file",
                                    "arguments": json.dumps({"file_path": path}),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        usage = {
            **event,
            "choices": [],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
                "prompt_tokens_details": {"cached_tokens": 90},
            },
        }
        body = "\n\n".join("data: " + json.dumps(e) for e in (event, usage))
        return httpx.Response(
            200,
            text=body + "\n\ndata: [DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await run_agent(
                tmp_path / "agent", CONNECTION, client=client, factor=factor
            )

    result = asyncio.run(run())
    assert result["stop_reason"] is None
    assert len(requests) == 8
    assert all(t["quality_pass"] and t["tool_calls"] == 2 for t in result["tasks"])
    assert any(
        "a,10" in str(m.get("content"))
        for m in requests[1]["messages"]
        if m["role"] == "tool"
    )
    assert any(
        "2026-11-23" in str(m.get("content"))
        for m in requests[3]["messages"]
        if m["role"] == "assistant"
    )
    assert result["usage"]["recorded"] == 8


def test_keepalive_does_not_extend_whole_request_deadline(monkeypatch):
    import prompt_cache_experiment as experiment

    class Keepalive(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                yield b": alive\n\n"
                await asyncio.sleep(0.005)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, stream=Keepalive())
            )
        ) as client:
            return await collect(client, CONNECTION, record())

    monkeypatch.setattr(experiment, "REQUEST_TIMEOUT_SECONDS", 0.03)
    result = asyncio.run(run())
    assert result["status"] == "failed" and result["error"] == "TimeoutError"
    assert result["first_reasoning_ms"] is None and result["first_content_ms"] is None


@pytest.mark.parametrize(
    "state",
    ["corrected", "deleted", "expired", "shared", "revoked", "permission_unknown"],
)
def test_memory_candidate_uses_current_context_after_acl_and_never_persists(
    monkeypatch, state
):
    from types import SimpleNamespace

    from langchain_core.messages import HumanMessage, SystemMessage

    from runtime_service.services.dearflow_agent.middleware import memory

    class Request:
        runtime = SimpleNamespace(context={})
        messages = [HumanMessage(content="本轮首选是什么？")]
        system_message = SystemMessage(content="rules")

        def override(self, **kwargs):
            result = copy.copy(self)
            result.__dict__.update(kwargs)
            return result

    allowed = state not in {"shared", "revoked", "permission_unknown"}
    contexts = iter(["首选 pytest", "首选 Vue" if state == "corrected" else ""])
    monkeypatch.setattr(memory, "memory_scope", lambda runtime: ("t", "p", "u"))
    monkeypatch.setattr(memory.MemoryStorage, "context", lambda *args: next(contexts))
    decisions = iter([True, True, allowed, allowed])

    async def access(runtime):
        return next(decisions)

    monkeypatch.setattr(memory, "memory_allowed", access)

    async def handler(request):
        return "\n".join(m.text for m in request.messages)

    async def run():
        middleware = memory.MemoryContextMiddleware(object())
        request = Request()
        first = await middleware.awrap_model_call(request, handler)
        second = await middleware.awrap_model_call(request, handler)
        assert request.system_message.text == "rules"
        assert request.messages[0].content == "本轮首选是什么？"
        return first, second

    first, second = asyncio.run(run())
    assert "pytest" in first
    assert "pytest" not in second
    assert ("Vue" in second) == (state == "corrected")


def test_summary_boundary_captures_auxiliary_and_final_model_requests(tmp_path):
    from prompt_cache_agent import run_agent

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return stream_response(content="10", reasoning="")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await run_agent(
                tmp_path / "summary", CONNECTION, client=client, factor="summary"
            )

    result = asyncio.run(run())
    assert result["stop_reason"] is None
    assert result["tasks"][0]["quality_pass"]
    assert len(requests) >= 2
    assert any(not r.get("tools") for r in requests)
    assert any(r.get("tools") for r in requests)

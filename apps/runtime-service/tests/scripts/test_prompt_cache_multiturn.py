import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prompt_cache_multiturn import (
    analyze,
    check_answer,
    prepare,
    requested_tools,
    run,
    task_spec,
)
from prompt_cache_official import BASE_URL, MODEL, PRICE


def connection():
    return {
        "route": "deepseek_official",
        "model": MODEL,
        "model_id": "official:" + MODEL,
        "base_url": BASE_URL,
        "api_key": "synthetic-key",
        "pricing": PRICE,
        "environment_id": "wt_test",
        "connection_fingerprint": "offline",
    }


def responder(request, *, unsafe=False):
    payload = json.loads(request.content)
    question = next(
        m["content"]
        for m in reversed(payload["messages"])
        if m["role"] == "user" and m.get("name") not in {"runtime_date", "user_memory"}
    )
    index = int(re.search(r"实验第(\d+)轮", question)[1]) - 1
    item = task_spec()["turns"][index]
    if item["read_path"] and payload["messages"][-1]["role"] != "tool":
        delta = {
            "tool_calls": [
                {
                    "index": 0,
                    "id": f"read-{index}",
                    "type": "function",
                    "function": {
                        "name": "write_file" if unsafe else "read_file",
                        "arguments": json.dumps(
                            {
                                "file_path": item["read_path"],
                                **({"content": "unsafe"} if unsafe else {}),
                            }
                        ),
                    },
                }
            ]
        }
        finish = "tool_calls"
    else:
        delta = {"content": json.dumps(item["expected"], ensure_ascii=False)}
        finish = "stop"
    chunk = {
        "id": "mock",
        "object": "chat.completion.chunk",
        "model": MODEL,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    usage = {
        **chunk,
        "choices": [],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_cache_hit_tokens": 64,
            "prompt_cache_miss_tokens": 36,
            "prompt_tokens_details": {"cached_tokens": 64},
        },
    }
    return httpx.Response(
        200,
        text="\n\n".join("data: " + json.dumps(e) for e in [chunk, usage])
        + "\n\ndata: [DONE]\n\n",
        headers={"Content-Type": "text/event-stream"},
    )


def test_eight_turn_agent_uses_real_files_and_preserves_all_history(tmp_path):
    payloads = []

    def respond(request):
        payloads.append(json.loads(request.content))
        return responder(request)

    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await run(tmp_path / "multi", connection(), prepare(), client=client)

    result = asyncio.run(execute())
    assert result["stop_reason"] is None
    assert len(payloads) == 22
    for task in result["tasks"]:
        assert task["quality_pass"] and task["model_calls"] == 11
        assert task["tool_calls"] == 3 and task["read_results_succeeded"]
        assert len(task["turns"]) == 8
        assert not task["temporary_context_persisted"]
    for i, payload in enumerate(payloads):
        assert ("<current_date>" in payload["messages"][0]["content"]) is (i < 11)
        assert payload["thinking"] == {"type": "disabled"}
    for payload in [payloads[10], payloads[21]]:
        assert (
            sum(
                m["role"] == "assistant" and bool(m.get("content"))
                for m in payload["messages"]
            )
            == 7
        )
        assert not any(m.get("name") == "user_memory" for m in payload["messages"])
        assert "<user_memory>" not in payload["messages"][0]["content"]


def test_tool_guard_stops_before_write_and_never_runs_second_group(tmp_path):
    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: responder(r, unsafe=True))
        ) as client:
            return await run(tmp_path / "bad", connection(), prepare(), client=client)

    result = asyncio.run(execute())
    assert result["stop_reason"] == "unexpected_tool_or_path"
    assert result["usage"]["attempted"] == 1
    assert len(result["tasks"]) == 1 and not result["tasks"][0]["quality_pass"]
    assert not any(
        p.read_text() == "unsafe" for p in (tmp_path / "bad/workspaces").rglob("*.csv")
    )


def test_explicit_diagnostic_runs_only_b_and_keeps_failed_a_reference(tmp_path):
    plan = prepare()
    plan["task"]["group_order"] = ["B"]
    plan["diagnostic_of"] = {
        "run": "prior-failed-a",
        "stop_reason": "answer_quality_failed",
    }

    async def execute():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(responder)
        ) as client:
            return await run(tmp_path / "diagnostic", connection(), plan, client=client)

    result = asyncio.run(execute())
    assert result["stop_reason"] is None
    assert [t["group"] for t in result["tasks"]] == ["B"]
    assert result["tasks"][0]["quality_pass"]
    registration = json.loads((tmp_path / "diagnostic/registration.json").read_text())
    assert registration["diagnostic_of"] == plan["diagnostic_of"]


def test_changed_sources_or_gateway_fail_before_output_or_dispatch(tmp_path):
    plan = prepare()
    plan["source_sha256"] = {}
    with pytest.raises(ValueError, match="frozen source mismatch"):
        asyncio.run(run(tmp_path / "no-output", connection(), plan))
    assert not (tmp_path / "no-output").exists()
    other = {**connection(), "base_url": "https://example.invalid"}
    with pytest.raises(ValueError, match="Official connection"):
        asyncio.run(run(tmp_path / "no-output", other, prepare()))


def test_quality_checks_latest_date_memory_and_historical_numbers():
    expected = task_spec()["turns"][6]["expected"]
    assert check_answer(json.dumps(expected), expected)["pass"]
    for key, value in [
        ("preference", "React + TypeScript"),
        ("date", "2026-11-23"),
        ("delta", 15),
    ]:
        assert not check_answer(json.dumps({**expected, key: value}), expected)["pass"]
    assert not check_answer("not JSON", expected)["pass"]
    assert not check_answer("[]", expected)["pass"]


def test_preference_name_does_not_require_unasked_programming_language():
    expected = task_spec()["turns"][3]["expected"]
    for name in ["Vue 3", "Vue 3 + TypeScript"]:
        assert check_answer(json.dumps({**expected, "preference": name}), expected)[
            "pass"
        ]
    for name in ["pytest", "React", "Vue 3，之前的 pytest"]:
        assert not check_answer(json.dumps({**expected, "preference": name}), expected)[
            "pass"
        ]


def test_after_first_excludes_by_sequence_and_keeps_later_zero_cache():
    rows = []
    for index, cache in enumerate([50, 0, 80]):
        rows.append(
            {
                "id": str(index),
                "case": "test",
                "group": "A",
                "turn": index,
                "status": "completed",
                "quality_pass": None,
                "first_content_ms": 1,
                "first_reasoning_ms": None,
                "completed_ms": 2,
                "raw_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 1,
                    "total_tokens": 101,
                    "prompt_cache_hit_tokens": cache,
                    "prompt_cache_miss_tokens": 100 - cache,
                },
            }
        )
    result = analyze(
        {
            "experiments": [
                {
                    "run": "test",
                    "requests": rows,
                    "planned": rows,
                    "registration": {
                        "attempted": 3,
                        "stop_reason": None,
                        "pricing": PRICE,
                    },
                }
            ]
        }
    )[0]
    assert result["excluded_request_ids"] == {"A": "0"}
    assert result["after_first"][0]["attempted"] == 2
    assert result["after_first"][0]["complete_cache_ratio"] == 0.4
    assert result["groups"][0]["input_tokens"] == 300


def test_fragmented_tool_arguments_are_checked_after_assembly():
    events = [
        {
            "data": {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "name": "read_",
                                        "arguments": '{"file_',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        },
        {
            "data": {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "name": "file",
                                        "arguments": 'path":"a"}',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        },
    ]
    assert requested_tools(events) == [
        {"name": "read_file", "arguments": '{"file_path":"a"}'}
    ]

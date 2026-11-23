import asyncio
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from prompt_cache_agent import run_agent
from prompt_cache_cases import capture, fixtures, text_slots
from prompt_cache_experiment import run_manifest, validate_manifest
from prompt_cache_official import (
    BASE_URL,
    MODEL,
    PRICE,
    load_official_connection,
    prepare,
)


def test_official_key_source_is_explicit_and_never_falls_back(tmp_path, monkeypatch):
    state = tmp_path / ".local-stack"
    state.mkdir()
    (state / "environment.json").write_text(
        json.dumps({"root": str(tmp_path), "id": "wt_test"})
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "official-test-key")
    connection = load_official_connection(root=tmp_path)
    assert connection["base_url"] == BASE_URL
    assert connection["model"] == MODEL
    private = tmp_path / "private.env"
    private.write_text("OTHER_KEY=private-key\n")
    with pytest.raises(ValueError, match="missing"):
        load_official_connection(root=tmp_path, env_file=private)
    assert (
        load_official_connection(root=tmp_path, env_file=private, key_env="OTHER_KEY")[
            "api_key"
        ]
        == "private-key"
    )


@pytest.fixture(scope="module")
def official_manifest(tmp_path_factory):
    return asyncio.run(
        prepare(tmp_path_factory.mktemp("official-capture"), "unit-nonce")
    )


def test_official_comparison_captures_product_and_only_reconstructs_baseline(
    official_manifest,
):
    validate_manifest(official_manifest)
    assert len(official_manifest["records"]) == 8
    rows = official_manifest["records"]
    for a, b in zip(rows[:4], rows[4:], strict=True):
        product = b["payload"]
        assert "<current_date>" not in "".join(
            c[k] for c, k in text_slots(product["messages"][0])
        )
        assert [m.get("name") for m in product["messages"][-3:-1]] == [
            "runtime_date",
            "user_memory",
        ]
        assert (
            "2026-11-24" in product["messages"][-3]["content"]
            if b["turn"] >= 2
            else "2026-11-23" in product["messages"][-3]["content"]
        )
        assert isinstance(product["messages"][0]["content"], str)
        actual_a = a["payload"]
        assert isinstance(actual_a["messages"][0]["content"], str)
        assert (
            actual_a["messages"][1:]
            == product["messages"][1:-3] + product["messages"][-1:]
        )
        static_a = actual_a["messages"][0]["content"].split("\n", 1)[1]
        static_a = re.sub(
            r"\n<current_date>.*?</current_date>", "", static_a, flags=re.S
        )
        static_a = re.sub(
            r"\nUser memory below.*?</user_memory>", "", static_a, flags=re.S
        )
        static_b = product["messages"][0]["content"].split("\n", 1)[1]
        assert re.sub(r"\s+", " ", static_a) == re.sub(r"\s+", " ", static_b)
        assert product["tools"] == a["payload"]["tools"]
    assert rows[4]["payload"]["messages"][:-3] == rows[6]["payload"]["messages"][:-3]


def test_official_manifest_cannot_dispatch_to_gateway(official_manifest, tmp_path):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: pytest.fail("must not dispatch"))
        ) as client:
            await run_manifest(
                official_manifest,
                tmp_path / "run",
                {
                    "base_url": "https://xiaok.lol/v1",
                    "route": "deepseek_official",
                    "model": MODEL,
                },
                8,
                Decimal(1),
                client=client,
            )

    with pytest.raises(ValueError, match="official connection"):
        asyncio.run(run())
    assert not (tmp_path / "run").exists()


def test_same_graph_cross_day_and_memory_change_never_persist_context(tmp_path):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        event = {
            "id": "test",
            "object": "chat.completion.chunk",
            "model": MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
        }
        return httpx.Response(
            200,
            text="data: " + json.dumps(event) + "\n\ndata: [DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )

    fixture = next(f for f in fixtures() if f["case"] == "C02")
    fixture["continuations"] = [
        {"date": "2026-11-24", "memory": "现在首选 Vue", "question": "当前首选？"}
    ]
    result = asyncio.run(
        capture(fixture, tmp_path, responder=respond, layout="product")
    )
    assert len(requests) == 2
    assert requests[0]["messages"][0] == requests[1]["messages"][0]
    assert "2026-11-24" in requests[1]["messages"][-3]["content"]
    assert "Vue" in requests[1]["messages"][-2]["content"]
    assert "pytest" not in json.dumps(requests[1]["messages"], ensure_ascii=False)
    for turn in result["turns"]:
        assert not any(
            m.name in {"runtime_date", "user_memory"} for m in turn["messages"]
        )


def test_official_agent_runner_uses_product_layout_and_real_local_read_file(tmp_path):
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        question = next(
            m["content"]
            for m in reversed(payload["messages"])
            if m["role"] == "user"
            and m.get("name") not in {"runtime_date", "user_memory"}
        )
        second = "data2.csv" in question
        path = "/workspace/work/" + ("data2.csv" if second else "data.csv")
        if payload["messages"][-1]["role"] == "tool":
            assert "name,units" in payload["messages"][-1]["content"]
            assert (
                "60" not in payload["messages"][-1]["content"]
            )  # The CSV contains 3 rows, not a precomputed total.
            delta = {
                "content": "60 " + ("2026-11-24 Vue" if second else "2026-11-23 pytest")
            }
            finish = "stop"
        else:
            delta = {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "read-" + str(second),
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps({"file_path": path}),
                        },
                    }
                ]
            }
            finish = "tool_calls"
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
            },
        }
        return httpx.Response(
            200,
            text="\n\n".join("data: " + json.dumps(e) for e in [chunk, usage])
            + "\n\ndata: [DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )

    connection = {
        "route": "deepseek_official",
        "model": MODEL,
        "model_id": "official:" + MODEL,
        "base_url": BASE_URL,
        "api_key": "synthetic-key",
        "pricing": PRICE,
        "environment_id": "wt_test",
        "connection_fingerprint": "offline",
    }

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await run_agent(
                tmp_path / "agent",
                connection,
                client=client,
                factor="combined",
                product_layout=True,
            )

    result = asyncio.run(run())
    assert result["stop_reason"] is None
    assert len(requests) == 8
    measurements = [
        json.loads(p.read_text())
        for p in (tmp_path / "agent").glob("AGENT-combined-*.json")
    ]
    assert all(
        row["usage"]["tokens"]["cache_read_tokens"] == 64 for row in measurements
    )
    for row in measurements:
        if row["adapter_usage"]["tokens"]["cache_read_tokens"] is None:
            assert row["cache_normalization_matches"] is None
            assert row["adapter_cache_comparison"].startswith("not_exposed_by_sdk")
    assert all(
        t["quality_pass"] and t["model_calls"] == 4 and t["tool_calls"] == 2
        for t in result["tasks"]
    )
    for index, payload in enumerate(requests):
        system = "".join(c[k] for c, k in text_slots(payload["messages"][0]))
        assert ("<current_date>" in system) is (index < 4)
        assert payload["thinking"] == {"type": "disabled"}

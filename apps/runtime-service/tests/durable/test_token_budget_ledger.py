"""Budget recovery, real provider and timing evidence on disposable PostgreSQL."""

import asyncio
import io
import json
import os
import statistics
import subprocess
import sys
import tarfile
import time
import tracemalloc
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from support import BindableFakeMessagesChatModel

from runtime_service.db.repositories import usage as repo
from runtime_service.observability.usage import (
    RuntimeUsageCallback,
    usage_only_config,
    with_runtime_usage,
)
from runtime_service.observability.usage_query import query_run_usage
from runtime_service.runtime.errors import TokenBudgetUnverifiableError
from tests.durable.test_usage_ledger import ledger_dsn  # noqa: F401 - pytest fixture


def identity():
    return dict(
        tenant_id="token-tests",
        project_id=str(uuid4()),
        graph_id="reference_agent",
        thread_id=str(uuid4()),
        run_id=str(uuid4()),
    )


def bind(graph, scope):
    return with_runtime_usage(
        graph,
        {"metadata": {"thread_id": scope["thread_id"], "run_id": scope["run_id"]}},
        graph_id=scope["graph_id"],
        trusted_metadata=scope,
    )


def enable(monkeypatch, maximum=10):
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", str(maximum))


def test_real_budget_dedup_late_usage_recovery_and_database_fault(
    monkeypatch,
    ledger_dsn,  # noqa: F811 - fixture
):
    enable(monkeypatch)
    scope = identity()

    async def run():
        callback = RuntimeUsageCallback(scope)
        root, call = uuid4(), uuid4()
        await callback.on_chain_start({}, {}, run_id=root)
        callback.check_budget()
        await callback.on_chat_model_start({}, [], run_id=call)
        await callback.on_llm_end({}, run_id=call)
        assert callback.token_budget.unverifiable
        await callback.on_llm_end(
            {"input_tokens": 4, "output_tokens": 0, "total_tokens": 4}, run_id=call
        )
        await callback.on_llm_end(
            {"input_tokens": 99, "output_tokens": 0, "total_tokens": 99}, run_id=call
        )
        assert callback.token_budget.used_tokens == 4
        await callback.on_chain_end({}, run_id=root)
        snapshot = repo.read_budget(scope)
        assert int(snapshot["used_tokens"]) == 4 and not snapshot["unverifiable"]
        monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", "1000")
        restored = RuntimeUsageCallback(scope)
        await restored.on_chain_start({}, {}, run_id=uuid4())
        assert restored.token_budget.policy.max_tokens == 10
        assert restored.token_budget.used_tokens == 4
        # A PostgreSQL lock timeout marks the projection unknown even after recovery.
        with psycopg.connect(ledger_dsn) as lock:
            lock.execute(
                "SELECT 1 FROM runtime_usage_runs WHERE run_id=%s FOR UPDATE",
                (scope["run_id"],),
            )
            await restored.on_chat_model_start({}, [], run_id=uuid4())
        with pytest.raises(TokenBudgetUnverifiableError):
            restored.check_budget()
        await restored._finish_collection(True)
        final = await query_run_usage(scope)
        assert final["token_budget"]["stop_code"] == "token_budget_unverifiable"
        assert final["token_budget"]["remaining_tokens"] is None
        assert repo.read_budget(scope)["unverifiable"]
        return final

    result = asyncio.run(run())
    assert result["coverage"]["observed_call_count"] == 1
    monkeypatch.setenv("DATABASE_URI", "postgresql://127.0.0.1:1/unavailable")

    async def failed_read():
        callback = RuntimeUsageCallback(scope)
        await callback.on_chain_start({}, {}, run_id=uuid4())
        with pytest.raises(TokenBudgetUnverifiableError):
            callback.check_budget()

    asyncio.run(failed_read())


def test_old_runtime_reads_extended_ledger_and_preserves_budget_facts(
    monkeypatch,
    ledger_dsn,  # noqa: F811 - fixture
    tmp_path,
):
    enable(monkeypatch)
    scope = identity()
    repo.begin_collection(scope, {"version": 1, "max_tokens": 10, "warn_at_tokens": 8})
    repo.finish_collection(scope, False, "token_budget_exhausted")
    archive = subprocess.check_output(
        ["rtk", "proxy", "git", "archive", "HEAD", "apps/runtime-service/src"],
        cwd=Path(__file__).resolve().parents[4],
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
        bundle.extractall(tmp_path, filter="data")
    source = tmp_path / "apps/runtime-service/src"
    script = """
import asyncio, json, sys
from runtime_service.db.repositories import usage as repo
from runtime_service.observability.usage_query import query_run_usage
identity = json.load(sys.stdin)
repo.begin_collection(identity)
repo.finish_collection(identity, False)
result = asyncio.run(query_run_usage(identity))
assert result['availability'] == 'available', result
assert result['tokens']['total_tokens'] == 0, result
assert 'token_budget' not in result, result
"""
    result = subprocess.run(
        ["rtk", "proxy", sys.executable, "-c", script],
        input=json.dumps(scope),
        env={
            **os.environ,
            "PYTHONPATH": str(source),
            "RUNTIME_TOKEN_BUDGET_ENABLED": "false",
        },
        cwd=tmp_path,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    snapshot = repo.read_budget(scope)
    assert snapshot["policy"]["max_tokens"] == 10
    assert snapshot["stop_code"] == "token_budget_exhausted"


def test_real_model_summary_and_child_report_usage(monkeypatch, ledger_dsn):  # noqa: F811
    env_file = os.getenv("TOKEN_BUDGET_REAL_MODEL_ENV_FILE")
    if not env_file:
        pytest.skip(
            "TOKEN_BUDGET_REAL_MODEL_ENV_FILE enables two bounded real provider calls"
        )
    from dotenv import dotenv_values

    from runtime_service.runtime import (
        AgentDefaults,
        RuntimeContext,
        RuntimePolicy,
        RuntimePrincipal,
        build_model,
        resolve_runtime_config,
    )

    enable(monkeypatch, maximum=4096)
    model_id = "deepseek:DeepSeek-V4-Flash"
    resolved = resolve_runtime_config(
        principal=RuntimePrincipal("test", "test", "test", "developer", ()),
        context=RuntimeContext(max_tokens=128),
        policy=RuntimePolicy("test", (model_id,), (), "test-tools-v2"),
        defaults=AgentDefaults(
            model_id=model_id,
            system_prompt="Return a brief answer.",
            prompt_version="test",
        ),
    )
    model = build_model(resolved, env=dotenv_values(env_file), max_retries=0).bind(
        extra_body={"thinking": {"type": "disabled"}}
    )
    scope = identity()
    child = create_agent(model, system_prompt="Return only OK.")

    async def summarize(state):
        summary = await model.ainvoke(
            "Summarize in under ten words: Run usage belongs to one native Run.",
            config=usage_only_config("summarization"),
        )
        await child.ainvoke({"messages": [("user", "Return only OK.")]})
        return {"answer": summary.text}

    builder = StateGraph(dict)
    builder.add_node("summary_and_child", summarize)
    builder.add_edge(START, "summary_and_child")
    builder.add_edge("summary_and_child", END)
    graph = bind(builder.compile(), scope)
    result = asyncio.run(graph.ainvoke({}))
    report = asyncio.run(query_run_usage(scope))
    assert result["answer"] and report["tokens"]["total_tokens"] > 0
    assert report["coverage"]["observed_call_count"] == 2
    assert report["coverage"]["reported_call_count"] == 2
    assert report["token_budget"]["coverage"] == "complete"
    assert {c["purpose"] for c in report["calls"]["items"]} == {
        "agent",
        "summarization",
    }
    target = os.getenv("TOKEN_BUDGET_REAL_MODEL_EVIDENCE_PATH")
    if target:
        Path(target).write_text(
            json.dumps(
                {
                    "provider": "real_deepseek",
                    "trial_max_tokens": 4096,
                    "max_output_per_call": 128,
                    "physical_calls": 2,
                    "usage": report,
                },
                indent=2,
            )
            + "\n"
        )


def test_budget_performance_matrix(monkeypatch, ledger_dsn):  # noqa: F811
    if os.getenv("TOKEN_BUDGET_PERFORMANCE") != "1":
        pytest.skip("TOKEN_BUDGET_PERFORMANCE=1 enables bounded timing measurements")
    enable(monkeypatch, maximum=1000000)
    message = AIMessage(
        content="ok",
        usage_metadata={"input_tokens": 1, "output_tokens": 0, "total_tokens": 1},
    )
    model = BindableFakeMessagesChatModel(responses=[message])
    sql, budget_reads = 0, 0
    original_connection, original_read = repo._connection, repo.read_budget

    def connection(**kwargs):
        nonlocal sql
        sql += 1
        return original_connection(**kwargs)

    def read(scope):
        nonlocal budget_reads
        budget_reads += 1
        return original_read(scope)

    monkeypatch.setattr(repo, "_connection", connection)
    monkeypatch.setattr(repo, "read_budget", read)
    rows = []
    for calls in (100, 1000):
        for concurrency in (1, 4, 8):
            for enabled in (False, True):
                monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", str(enabled).lower())
                durations = []

                async def execute(
                    index, calls=calls, concurrency=concurrency, durations=durations
                ):
                    count = calls // concurrency + (index < calls % concurrency)

                    async def node(state):
                        for _ in range(count):
                            started = time.perf_counter()
                            await model.ainvoke("probe")
                            durations.append((time.perf_counter() - started) * 1000)
                        return {}

                    builder = StateGraph(dict)
                    builder.add_node("calls", node)
                    builder.add_edge(START, "calls")
                    builder.add_edge("calls", END)
                    await bind(builder.compile(), identity()).ainvoke({})

                async def run(concurrency=concurrency):
                    await asyncio.gather(*(execute(i) for i in range(concurrency)))

                before, reads_before = sql, budget_reads
                tracemalloc.start()
                started = time.perf_counter()
                asyncio.run(run())
                elapsed = time.perf_counter() - started
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                ordered = sorted(durations)
                assert len(ordered) == calls
                assert budget_reads - reads_before == (concurrency if enabled else 0)
                rows.append(
                    dict(
                        enabled=enabled,
                        calls=calls,
                        active_runs=concurrency,
                        p50_ms=round(statistics.median(ordered), 3),
                        p95_ms=round(
                            ordered[min(int(len(ordered) * 0.95), len(ordered) - 1)], 3
                        ),
                        elapsed_seconds=round(elapsed, 3),
                        connection_transactions=sql - before,
                        budget_reads=budget_reads - reads_before,
                        peak_bytes=peak,
                    )
                )
                print(json.dumps(rows[-1]), flush=True)
    target = Path(
        os.getenv(
            "TOKEN_BUDGET_PERFORMANCE_EVIDENCE_PATH", "token-budget-performance.json"
        )
    )
    target.write_text(
        json.dumps({"provider": "fake_model_with_real_pg", "rows": rows}, indent=2)
        + "\n"
    )

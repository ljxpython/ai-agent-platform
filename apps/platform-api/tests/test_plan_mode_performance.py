"""Opt-in local projection measurements; no production SLO is assumed."""

import hashlib
import json
import os
import statistics
import time
import tracemalloc

import pytest

from platform_api.adapters.langgraph.sdk_client import redact_runtime_private_fields


@pytest.mark.skipif(
    os.getenv("PLAN_MODE_PERF_TEST") != "1",
    reason="PLAN_MODE_PERF_TEST=1 runs local measurements",
)
def test_plan_state_and_history_projection_measurements():
    metrics = []
    for size, checkpoints, iterations in (
        (1024, 1, 300),
        (65536, 1, 300),
        (65536, 20, 50),
    ):
        fields = {
            "version": 1,
            "plan_id": "benchmark",
            "revision": 1,
            "title": "Benchmark",
            "markdown": "x" * size,
        }
        canonical = json.dumps(
            fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        raw = {
            **fields,
            "active": True,
            "content_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
            "bound_execution_id": "PRIVATE_CANARY",
            "decision": None,
        }
        state = {"values": {"runtime_plan": raw}}
        source = state if checkpoints == 1 else [state] * checkpoints
        projected = redact_runtime_private_fields(source)
        output = json.dumps(projected)
        assert "PRIVATE_CANARY" not in output
        assert "runtime_plan" not in output
        assert output.count('"agent_plan"') == checkpoints
        samples = []
        tracemalloc.start()
        cpu = time.process_time()
        for _ in range(iterations):
            started = time.perf_counter()
            redact_runtime_private_fields(source)
            samples.append((time.perf_counter() - started) * 1000)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        metrics.append(
            {
                "markdown_bytes": size,
                "checkpoints": checkpoints,
                "iterations": iterations,
                "p50_ms": round(statistics.median(samples), 4),
                "p95_ms": round(sorted(samples)[int(len(samples) * 0.95)], 4),
                "cpu_ms": round((time.process_time() - cpu) * 1000, 3),
                "peak_bytes": peak,
                "projected_json_bytes": len(output.encode()),
            }
        )
    print(json.dumps({"plan_projection_measurements": metrics}))

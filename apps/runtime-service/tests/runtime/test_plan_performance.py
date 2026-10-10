"""Local measurements without an invented production latency threshold."""

import asyncio
import json
import os
import statistics
import time
import tracemalloc
from types import SimpleNamespace

import pytest
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage
from middlewares.test_plan_mode_safety import readonly

from runtime_service.middlewares.plan_mode import PlanModeMiddleware
from runtime_service.runtime.planning import new_plan, plan_content_hash
from runtime_service.tools.plan_mode import PLAN_TOOLS


@pytest.mark.skipif(
    os.getenv("PLAN_MODE_PERF_TEST") != "1",
    reason="PLAN_MODE_PERF_TEST=1 runs local measurements",
)
def test_plan_filter_latency_and_bounded_snapshot():
    async def run():
        metrics = []
        for active, size, count in (
            (False, 0, 10),
            (True, 1024, 10),
            (True, 65536, 100),
        ):
            tools = [
                readonly.model_copy(update={"name": f"read_{i}"}) for i in range(count)
            ]
            middleware = PlanModeMiddleware(tools)
            plan = new_plan("execution")
            if size:
                plan = plan.model_copy(
                    update={"revision": 1, "title": "Benchmark", "markdown": "x" * size}
                )
                plan.content_hash = plan_content_hash(plan)
            state = {"runtime_plan": plan.model_dump()} if active else {}
            request = ModelRequest(
                model=None,
                tools=[*tools, *PLAN_TOOLS],
                messages=[],
                state=state,
                runtime=SimpleNamespace(context={"plan_execution_id": "execution"}),
            )

            async def handler(filtered, count=count):
                assert len(filtered.tools) == count + 3
                return AIMessage(content="done")

            await middleware.awrap_model_call(request, handler)
            samples = []
            tracemalloc.start()
            cpu = time.process_time()
            for _ in range(300):
                started = time.perf_counter()
                await middleware.awrap_model_call(request, handler)
                samples.append((time.perf_counter() - started) * 1000)
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            metrics.append(
                {
                    "active": active,
                    "markdown_bytes": size,
                    "readonly_tools": count,
                    "iterations": len(samples),
                    "p50_ms": round(statistics.median(samples), 4),
                    "p95_ms": round(sorted(samples)[int(len(samples) * 0.95)], 4),
                    "cpu_ms": round((time.process_time() - cpu) * 1000, 3),
                    "peak_bytes": peak,
                    "state_json_bytes": len(json.dumps(state).encode()),
                }
            )
        print(json.dumps({"plan_filter_measurements": metrics}))

    asyncio.run(run())

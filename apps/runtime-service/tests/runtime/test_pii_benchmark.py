"""Record scan cost with fixed synthetic corpora; no unapproved latency SLO."""

import json
import statistics
import time
import tracemalloc

from langchain_core.messages import HumanMessage

from runtime_service.runtime.pii import PiiRedactionConfig, redact_messages, redact_text


def test_bounded_patterns_large_inputs_and_no_mapping_cache():
    policy = PiiRedactionConfig(
        True,
        "synthetic-redaction-secret-32-bytes",
        scope=("tenant", "project", "thread"),
    )
    disabled = PiiRedactionConfig()
    measurements = []
    for size in (4096, 12288, 65536, 1048576):
        fragment = "x" * 480 + " alice@example.test 13800138000 "
        text = (fragment * (size // len(fragment) + 1))[:size]
        for config in (disabled, policy):
            samples = []
            for _ in range(7):
                started = time.perf_counter()
                output = redact_text(text, config)
                samples.append((time.perf_counter() - started) * 1000)
            if config.enabled:
                assert (
                    "alice@example.test" not in output and "13800138000" not in output
                )
            else:
                assert output is text
            tracemalloc.start()
            redact_text(text, config)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            measurements.append(
                {
                    "bytes": size,
                    "enabled": config.enabled,
                    "p50_ms": round(statistics.median(samples), 3),
                    "p95_ms": round(sorted(samples)[-1], 3),
                    "peak_bytes": peak,
                }
            )
    # Long candidates exercise failed boundaries without unbounded nested quantifiers.
    for text in ("a" * 1048576, "9" * 1048576, "a." * 524288):
        assert redact_text(text, policy) == text
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "alice@"},
                {"type": "text", "text": "example.test"},
            ]
        )
        for _ in range(500)
    ]
    started = time.perf_counter()
    safe = redact_messages(messages, policy)
    assert "alice@example.test" not in str(safe)
    measurements.append(
        {
            "messages": 500,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    )
    print("PII_BENCHMARK=" + json.dumps(measurements))

"""Bounded Xiaok replay experiment. Default commands never call a model."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import psycopg
from dotenv import dotenv_values
from langchain_core.messages import AIMessageChunk
from prompt_cache_cases import MODEL_ID, MODEL_NAME, build_manifest, canonical, digest

from runtime_service.observability.usage import (
    estimate_usage_cost,
    normalize_usage,
    safe_pricing,
)
from runtime_service.runtime.modeling import (
    ChatDeepSeek,
    ChatOpenAIWithReasoning,
    _reasoning_text,
)

ROOT = Path(__file__).resolve().parents[3]
REQUEST_TIMEOUT_SECONDS = 120


def write_json(path: Path, value):
    path.write_bytes(canonical(value) + b"\n")


def load_connection(root: Path = ROOT):
    """Read only this registered Worktree's seeded catalog; never inspect a main DB."""
    state = json.loads((root / ".local-stack/environment.json").read_text())
    if Path(state["root"]).resolve() != root.resolve():
        raise ValueError("Worktree identity mismatch")
    values = dotenv_values(root / ".local-stack/platform.env")
    dsn = values["PLATFORM_API_DATABASE_URL"].replace(
        "postgresql+psycopg:", "postgresql:"
    )
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        db, role = connection.execute(
            "SELECT current_database(), current_user"
        ).fetchone()
        if db != state["id"] + "_platform" or role != db:
            raise ValueError("Catalog is not owned by this Worktree")
        row = connection.execute(
            "SELECT model_name, base_url, api_key_ciphertext, pricing_json, provider, protocol "
            "FROM runtime_catalog_models WHERE id=%s AND enabled",
            (MODEL_ID,),
        ).fetchone()
    if not row or row[0] != MODEL_NAME or row[4:] != ("xiaok", "openai-compatible"):
        raise ValueError("Expected Xiaok DeepSeek catalog entry is unavailable")
    url = urlsplit(row[1])
    if (
        url.scheme != "https"
        or url.hostname != "xiaok.lol"
        or url.username
        or url.password
        or url.query
    ):
        raise ValueError("Unexpected Xiaok endpoint")
    sys.path.insert(0, str(root / "apps/platform-api/src"))
    from platform_api.modules.runtime_catalog.application.credentials import (
        decrypt_api_key,
    )

    key_name = "PLATFORM_API_MODEL_CONFIG_MASTER_KEY"
    if key_name not in values:
        raise ValueError("Worktree credential master key is missing")
    key = decrypt_api_key(row[2], master_key=values[key_name])
    price = safe_pricing(row[3])
    if not price or price["input"] is None or price["output"] is None:
        raise ValueError("Configured prices are required for bounded replay")
    return {
        "model": row[0],
        "base_url": row[1].rstrip("/"),
        "api_key": key,
        "pricing": price,
        "environment_id": state["id"],
        "connection_fingerprint": digest(
            {"id": MODEL_ID, "url": row[1], "model": row[0], "protocol": row[5]}
        ),
    }


def validate_manifest(manifest):
    if manifest.get("version") != 1 or manifest.get("material") != "synthetic":
        raise ValueError("Only versioned synthetic manifests are accepted")
    official = manifest.get("route") == "deepseek_official"
    model = "deepseek-flash" if official else MODEL_NAME
    model_id = "official:deepseek-flash" if official else MODEL_ID
    if manifest.get("model_id") != model_id or manifest.get("model") != model:
        raise ValueError("Manifest model mismatch")
    ids = set()
    for row in manifest["records"]:
        if row["id"] in ids or digest(row["payload"]) != row["payload_sha256"]:
            raise ValueError("Duplicate request or changed payload")
        if digest(row["baseline"]) != row["baseline_sha256"]:
            raise ValueError("Baseline hash mismatch")
        ids.add(row["id"])
        payload = row["payload"]
        limit = payload.get("max_completion_tokens", payload.get("max_tokens"))
        if (
            payload.get("model") != model
            or type(limit) is not int
            or not 0 < limit <= 2048
        ):
            raise ValueError("Invalid model or output bound")
        if payload.get("stream") is not True or payload.get("stream_options") != {
            "include_usage": True
        }:
            raise ValueError("Streaming usage must be enabled")
        if len(canonical(payload)) > 500_000:
            raise ValueError("Input byte bound exceeded")
        if official and payload.get("thinking") != {"type": "disabled"}:
            raise ValueError("Official experiment must use frozen non-thinking mode")


def reserve_cost(payload, price):
    """Conservative byte-token proxy at configured rates, not a provider bill cap."""
    input_rate = max(
        Decimal(price[k] or "0")
        for k in (
            "input",
            "cache_read",
            "cache_write",
            "cache_write_5m",
            "cache_write_1h",
        )
    )
    output_limit = payload.get("max_completion_tokens", payload.get("max_tokens"))
    return (
        (len(canonical(payload)) + 4096) * input_rate
        + output_limit * Decimal(price["output"])
    ) / 1_000_000


def normalize_replay_usage(raw):
    """Xiaok's OpenAI totals include cache; ignore foreign protocol aliases."""
    raw_result = normalize_usage(raw or {}, provider="deepseek")
    if not isinstance(raw, dict) or "prompt_tokens" not in raw:
        return raw_result
    # Keep the complete raw response separately. Do not let an Anthropic-shaped
    # zero alias reinterpret an explicitly inclusive OpenAI prompt_tokens total.
    fields = {
        k: raw[k]
        for k in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_tokens_details",
            "completion_tokens_details",
            "prompt_cache_hit_tokens",
        )
        if k in raw
    }
    normalized = normalize_usage(fields, provider="deepseek")
    details = raw.get("prompt_tokens_details")
    detail = details.get("cached_tokens") if isinstance(details, dict) else None
    native = raw.get("prompt_cache_hit_tokens")
    if detail is not None and native is not None and detail != native:
        normalized = {
            "tokens": normalize_usage({})["tokens"],
            "quality": "invalid",
            "source": "conflicting_cache_fields",
        }
    return normalized


def check_answer(text, expected, finish, has_tools):
    import re

    if finish != "stop" or has_tools:
        return False
    if expected.isdigit():
        return re.findall(r"(?<![\d-])\d+(?![\d-])", text) == [expected]
    return expected.casefold() in text.casefold()


async def collect(client, connection, record):
    """Retain SSE data and partial usage even if the stream or request fails."""
    started = time.perf_counter()
    result = {
        k: record[k]
        for k in (
            "id",
            "case",
            "group",
            "repeat",
            "turn",
            "payload_sha256",
            "execution_eligible",
        )
    }
    result.update(
        status="failed",
        events=[],
        raw_usage=None,
        first_reasoning_ms=None,
        first_content_ms=None,
        response_model=None,
        system_fingerprint=None,
        content="",
        finish_reason=None,
        error=None,
        actual_billed_cost=None,
    )
    body, reasoning = [], []
    adapter_class = (
        ChatDeepSeek
        if connection.get("route") == "deepseek_official"
        else ChatOpenAIWithReasoning
    )
    adapter = adapter_class(
        model=connection.get("model", MODEL_NAME),
        api_key="normalization-only",
        max_retries=0,
    )
    full = None
    done, has_tools = False, False

    def consume(data):
        nonlocal full, done, has_tools
        elapsed = (time.perf_counter() - started) * 1000
        if data == "[DONE]":
            done = True
            return
        event = json.loads(data)
        result["events"].append({"elapsed_ms": elapsed, "data": event})
        if event.get("error"):
            raise ValueError("provider_stream_error")
        result["response_model"] = event.get("model") or result["response_model"]
        result["system_fingerprint"] = (
            event.get("system_fingerprint") or result["system_fingerprint"]
        )
        if event.get("usage"):
            result["raw_usage"] = event["usage"]
        for choice in event.get("choices", []):
            delta = choice.get("delta") or {}
            thought = _reasoning_text(delta)
            content = delta.get("content")
            if thought:
                if result["first_reasoning_ms"] is None:
                    result["first_reasoning_ms"] = elapsed
                reasoning.append(thought)
            if isinstance(content, str) and content.strip():
                if result["first_content_ms"] is None:
                    result["first_content_ms"] = elapsed
            if isinstance(content, str):
                body.append(content)
            has_tools = has_tools or bool(delta.get("tool_calls"))
            result["finish_reason"] = (
                choice.get("finish_reason") or result["finish_reason"]
            )
        converted = adapter._convert_chunk_to_generation_chunk(
            event, AIMessageChunk, None
        )
        if converted:
            full = converted.message if full is None else full + converted.message

    async def dispatch():
        async with client.stream(
            "POST",
            connection["base_url"] + "/chat/completions",
            headers={
                "Authorization": "Bearer " + connection["api_key"],
                "Content-Type": "application/json",
            },
            content=canonical(record["payload"]),
        ) as response:
            result["http_status"] = response.status_code
            response.raise_for_status()
            data_lines = []
            async for line in response.aiter_lines():
                if not line:
                    if data_lines:
                        consume("\n".join(data_lines))
                        data_lines = []
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip(" "))
            if data_lines:
                consume("\n".join(data_lines))

    try:
        await asyncio.wait_for(dispatch(), timeout=REQUEST_TIMEOUT_SECONDS)
        if not done or result["finish_reason"] is None:
            raise ValueError("incomplete_stream")
        result["status"] = "completed"
    except Exception as exc:
        # Do not persist arbitrary exception text, URLs or provider echoes of credentials.
        result["error"] = type(exc).__name__
        if isinstance(exc, ValueError):
            result["error"] = (
                str(exc)
                if str(exc) in {"provider_stream_error", "incomplete_stream"}
                else "invalid_stream_data"
            )
    result["completed_ms"] = (time.perf_counter() - started) * 1000
    result["content"] = "".join(body)
    result["reasoning_chars"] = sum(map(len, reasoning))
    normalized = normalize_replay_usage(result["raw_usage"])
    result["raw_usage_normalization"] = normalize_usage(
        result["raw_usage"] or {}, provider="deepseek"
    )
    result["usage"] = normalized
    response = (
        SimpleNamespace(generations=[[SimpleNamespace(message=full)]])
        if full is not None
        else None
    )
    result["adapter_usage"] = normalize_usage(response, provider="deepseek")
    result["cache_normalization_matches"] = all(
        normalized["tokens"][field] == result["adapter_usage"]["tokens"][field]
        for field in ("input_tokens", "output_tokens", "cache_read_tokens")
    )
    result["adapter_cache_comparison"] = (
        "matches" if result["cache_normalization_matches"] else "mismatch_or_missing"
    )
    if (
        connection.get("route") == "deepseek_official"
        and normalized["tokens"]["cache_read_tokens"] is not None
        and result["adapter_usage"]["tokens"]["cache_read_tokens"] is None
        and all(
            normalized["tokens"][field] == result["adapter_usage"]["tokens"][field]
            for field in ("input_tokens", "output_tokens")
        )
    ):
        # Raw native cache usage remains measurable. Do not pretend the installed
        # SDK exposed it, or stop as if two reported cache values disagreed.
        result["cache_normalization_matches"] = None
        result["adapter_cache_comparison"] = "not_exposed_by_sdk; raw_native_cache_used"
    result["usage_protocol"] = (
        "openai-compatible inclusive prompt_tokens; foreign protocol aliases ignored"
    )
    # No failure-zero fallback: missing supplier usage remains unknown.
    result["estimated_cost_usd"], result["cost_unknown_reason"] = estimate_usage_cost(
        normalized, connection["pricing"]
    )
    result["quality_pass"] = check_answer(
        result["content"], record["expected"], result["finish_reason"], has_tools
    )
    if record.get("required_terms"):
        result["quality_pass"] = result["quality_pass"] and all(
            term.casefold() in result["content"].casefold()
            for term in record["required_terms"]
        )
        result["quality_pass"] = result["quality_pass"] and not any(
            term.casefold() in result["content"].casefold()
            for term in record.get("forbidden_terms", [])
        )
    result["quality_method"] = (
        "predeclared_number_or_keyword_and_no_tools; not independent human review"
    )

    def redact(value):
        if isinstance(value, str):
            return value.replace(connection["api_key"], "[REDACTED]")
        if isinstance(value, list):
            return [redact(v) for v in value]
        if isinstance(value, dict):
            return {k: redact(v) for k, v in value.items()}
        return value

    return redact(result)


async def run_manifest(
    manifest, output, connection, max_requests, max_cost, *, client=None
):
    validate_manifest(manifest)
    if manifest.get("route") == "deepseek_official" and (
        connection.get("route") != "deepseek_official"
        or connection.get("base_url") != "https://api.deepseek.com"
        or connection.get("model") != manifest["model"]
    ):
        raise ValueError("Official manifest requires the matching official connection")
    if max_requests <= 0 or not max_cost.is_finite() or max_cost <= 0:
        raise ValueError("Positive finite request and estimated-cost limits required")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "manifest.json", manifest)
    registration = {
        "started_at": datetime.now(UTC).isoformat(),
        "manifest_sha256": digest(manifest),
        "connection_fingerprint": connection["connection_fingerprint"],
        "environment_id": connection["environment_id"],
        "pricing": connection["pricing"],
        "max_requests": max_requests,
        "max_estimated_cost_usd": str(max_cost),
        "cost_limit_basis": "configured price snapshot; byte-token reservation proxy, supplier bill unknown",
        "pricing_reference": connection.get("pricing_reference"),
        "retries": 0,
        "concurrency": 1,
        "timeout_seconds": 120,
        "actual_billed_cost": None,
        "stop_reason": None,
        "attempted": 0,
    }
    write_json(output / "registration.json", registration)
    spent = Decimal(0)
    identity = None
    owned_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(120), follow_redirects=False
    )
    try:
        for row in manifest["records"]:
            reserve = reserve_cost(row["payload"], connection["pricing"])
            if registration["attempted"] >= max_requests or spent + reserve > max_cost:
                registration["stop_reason"] = "request_or_estimated_budget_limit"
                break
            # Persist attempted dispatch before network; an interrupted run is never resumed automatically.
            registration["attempted"] += 1
            registration["inflight_request"] = row["id"]
            write_json(output / "registration.json", registration)
            result = await collect(client, connection, row)
            write_json(output / (row["id"] + ".json"), result)
            registration.pop("inflight_request", None)
            if result["estimated_cost_usd"] is not None:
                spent += Decimal(result["estimated_cost_usd"])
            else:
                spent += reserve
            reason = None
            if result["status"] != "completed":
                reason = "failed_request_no_retry"
            elif result["usage"]["quality"] not in {
                "reported",
                "derived_from_reported",
            }:
                reason = "usage_unavailable_or_invalid"
            elif result["usage"]["tokens"]["cache_read_tokens"] is None:
                reason = "cache_field_unavailable"
            elif result["cache_normalization_matches"] is False:
                reason = "cache_normalization_mismatch"
            elif identity and result["response_model"] != identity:
                reason = "response_model_changed"
            elif not result["quality_pass"]:
                reason = "quality_check_failed"
            identity = identity or result["response_model"]
            if reason:
                registration["stop_reason"] = reason
                break
            write_json(output / "registration.json", registration)
    finally:
        if owned_client:
            await client.aclose()
        registration["estimated_spend_or_reservation_usd"] = str(spent)
        registration["finished_at"] = datetime.now(UTC).isoformat()
        write_json(output / "registration.json", registration)
    return registration


def summarize(rows, planned=None):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["case"], row["group"])].append(row)
    summaries = []
    for (case, group), samples in sorted(groups.items()):
        count = (
            sum(r["case"] == case and r["group"] == group for r in planned)
            if planned is not None
            else len(samples)
        )
        valid = [
            s
            for s in samples
            if s["usage"]["quality"] in {"reported", "derived_from_reported"}
            and s["usage"]["tokens"]["input_tokens"] is not None
            and s["usage"]["tokens"]["cache_read_tokens"] is not None
        ]
        known_input = sum(s["usage"]["tokens"]["input_tokens"] for s in valid)
        cache = sum(s["usage"]["tokens"]["cache_read_tokens"] for s in valid)
        all_inputs = [s["usage"]["tokens"]["input_tokens"] for s in samples]
        inputs = sum(all_inputs) if all(v is not None for v in all_inputs) else None
        all_outputs = [s["usage"]["tokens"]["output_tokens"] for s in samples]
        outputs = sum(all_outputs) if all(v is not None for v in all_outputs) else None
        costs = [s["estimated_cost_usd"] for s in samples]
        ratio = cache / known_input if known_input else None
        data = {
            "case": case,
            "group": group,
            "planned": count,
            "attempted": len(samples),
            "completed": sum(s["status"] == "completed" for s in samples),
            "known_cache_requests": len(valid),
            "input_tokens": inputs,
            "output_tokens": outputs,
            "known_cache_read_tokens": cache,
            "known_input_tokens": known_input,
            "known_sample_cache_ratio": ratio,
            "complete_cache_ratio": ratio
            if len(valid) == len(samples) == count
            else None,
            "cache_input_coverage": known_input / inputs if inputs else None,
            "uncached_input_tokens": inputs - cache
            if inputs is not None and len(valid) == len(samples)
            else None,
            "estimated_cost_usd": str(sum(map(Decimal, costs)))
            if all(c is not None for c in costs)
            else None,
            "actual_billed_cost": None,
            "quality_pass_count": sum(s["quality_pass"] is True for s in samples),
            "quality_evaluated_requests": sum(
                s["quality_pass"] is not None for s in samples
            ),
            "first_request_cache_ratio": next(
                (
                    s["usage"]["tokens"]["cache_read_tokens"]
                    / s["usage"]["tokens"]["input_tokens"]
                    for s in valid
                    if s["turn"] == 0 and s["usage"]["tokens"]["input_tokens"]
                ),
                None,
            ),
        }
        for field in ("first_reasoning_ms", "first_content_ms", "completed_ms"):
            values = [
                s[field]
                for s in samples
                if s["status"] == "completed" and s[field] is not None
            ]
            data[field] = {
                "n": len(values),
                "median": statistics.median(values) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
            }
        summaries.append(data)
    return summaries


def report(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    registration = json.loads((directory / "registration.json").read_text())
    if digest(manifest) != registration["manifest_sha256"]:
        raise ValueError("Run manifest changed")
    rows = []
    for item in manifest["records"]:
        path = directory / (item["id"] + ".json")
        if path.exists():
            row = json.loads(path.read_text())
            if row["payload_sha256"] != item["payload_sha256"]:
                raise ValueError("Result payload mismatch")
            # Recompute from immutable provider usage, including older parser failures.
            row["usage"] = normalize_replay_usage(row["raw_usage"])
            row["estimated_cost_usd"], row["cost_unknown_reason"] = estimate_usage_cost(
                row["usage"], registration["pricing"]
            )
            rows.append(row)
    result = {
        "planned": len(manifest["records"]),
        "attempted": registration["attempted"],
        "recorded": len(rows),
        "unrecorded_dispatches": registration["attempted"] - len(rows),
        "stop_reason": registration["stop_reason"],
        "recomputed_usage_protocol": "OpenAI-compatible; original records are not rewritten",
        "groups": summarize(rows, manifest["records"]),
    }
    write_json(directory / "summary.json", result)
    with (directory / "requests.csv").open("w", newline="") as file:
        fields = [
            "id",
            "status",
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "estimated_cost_usd",
            "first_reasoning_ms",
            "first_content_ms",
            "completed_ms",
            "quality_pass",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{k: row.get(k) for k in fields},
                    **{
                        k: row["usage"]["tokens"].get(k)
                        for k in ("input_tokens", "output_tokens", "cache_read_tokens")
                    },
                }
            )
    return result


def plot_report(directory, result):
    """Export ordinary scientific plots; no missing values are plotted as zero."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    manifest = json.loads((directory / "manifest.json").read_text())
    rows = [
        json.loads(p.read_text())
        for r in manifest["records"]
        if (p := directory / (r["id"] + ".json")).exists()
    ]
    for row in rows:
        row["usage"] = normalize_replay_usage(row["raw_usage"])
    panels = sorted({(r["case"], r["repeat"]) for r in rows})
    columns = min(3, max(1, len(panels)))
    height = max(1, math.ceil(len(panels) / columns))
    fig, axes = plt.subplots(
        height, columns, figsize=(4.2 * columns, 3.3 * height), squeeze=False
    )
    for ax, (case, repeat) in zip(axes.flat, panels, strict=False):
        for group, color in (("A", "#3979a7"), ("B", "#d78125")):
            values = [
                r
                for r in rows
                if (r["case"], r["repeat"], r["group"]) == (case, repeat, group)
                and r["usage"]["tokens"]["cache_read_tokens"] is not None
                and r["usage"]["tokens"]["input_tokens"]
            ]
            if values:
                ax.plot(
                    [r["turn"] + 1 for r in values],
                    [
                        100
                        * r["usage"]["tokens"]["cache_read_tokens"]
                        / r["usage"]["tokens"]["input_tokens"]
                        for r in values
                    ],
                    marker="o",
                    color=color,
                    label=group,
                )
        ax.set(
            title=f"{case}, repetition {repeat + 1}",
            xlabel="Request (first included)",
            ylabel="Cache read / input (%)",
            ylim=(0, 100),
        )
        ax.set_xticks(
            sorted(
                {
                    r["turn"] + 1
                    for r in rows
                    if r["case"] == case and r["repeat"] == repeat
                }
            )
        )
        ax.legend(fontsize=9, loc="upper left")
        ax.grid(alpha=0.2)
    for ax in list(axes.flat)[len(panels) :]:
        ax.set_visible(False)
    fig.tight_layout()
    fig.savefig(directory / "cache-ratio.png", dpi=160)
    plt.close(fig)
    groups = result["groups"]
    fig, ax = plt.subplots(figsize=(9, 4))
    labels = [f"{g['case']}-{g['group']}" for g in groups]
    for index, group in enumerate(groups):
        values = [
            r["completed_ms"] / 1000
            for r in rows
            if r["case"] == group["case"]
            and r["group"] == group["group"]
            and r["status"] == "completed"
        ]
        if values:
            ax.boxplot([values], positions=[index], widths=0.5, showmeans=True)
    ax.set_xticks(range(len(labels)), labels, rotation=25)
    ax.set(
        ylabel="Completed request (seconds)",
        title="Observed samples; network and routing included",
    )
    fig.tight_layout()
    fig.savefig(directory / "latency.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4))
    for index, group in enumerate(groups):
        value = group["estimated_cost_usd"]
        if value is not None:
            ax.bar(index, float(value), color="#3979a7")
        else:
            ax.text(index, 0, "unknown", rotation=90, va="bottom", ha="center")
    ax.set_xticks(range(len(labels)), labels, rotation=25)
    ax.set(
        ylabel="Configured price estimate (USD)",
        title="Attempted requests; supplier bill unknown",
    )
    fig.tight_layout()
    fig.savefig(directory / "configured-cost.png", dpi=160)
    plt.close(fig)


def recompute_bundle(bundle):
    """Recompute a published usage-only dataset; never load a credential or send HTTP."""
    output = []
    for experiment in bundle["experiments"]:
        samples = []
        for original in experiment["requests"]:
            row = dict(original)
            row["usage"] = normalize_replay_usage(row["raw_usage"])
            row["estimated_cost_usd"], _ = estimate_usage_cost(
                row["usage"], experiment["registration"]["pricing"]
            )
            samples.append(row)
        output.append(
            {
                "run": experiment["run"],
                "attempted": experiment["registration"]["attempted"],
                "recorded": len(samples),
                "stop_reason": experiment["registration"]["stop_reason"],
                "groups": summarize(samples, experiment["planned"]),
                "tasks": experiment.get("tasks"),
            }
        )
    return output


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="offline capture; no model request")
    prepare.add_argument("output", type=Path)
    prepare.add_argument("--repeats", type=int, default=1)
    prepare.add_argument(
        "--cases", nargs="+", choices=["C01", "C02", "C03", "C04", "C05"]
    )
    run = sub.add_parser("run", help="paid Xiaok replay after budget registration")
    run.add_argument("manifest", type=Path)
    run.add_argument("output", type=Path)
    run.add_argument("--max-requests", type=int, required=True)
    run.add_argument("--max-estimated-cost-usd", type=Decimal, required=True)
    res = sub.add_parser("report", help="offline recomputation")
    res.add_argument("directory", type=Path)
    res.add_argument("--plots", action="store_true")
    recompute = sub.add_parser(
        "recompute", help="offline recomputation of published usage-only evidence"
    )
    recompute.add_argument("bundle", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.output.exists() or not 0 < args.repeats <= 5:
            raise ValueError(
                "New output file and 1..5 preregistered repetitions required"
            )
        manifest = await build_manifest(
            ROOT / ".local-stack/cache-fixtures", uuid4().hex, args.repeats, args.cases
        )
        manifest["dependencies"] = {
            p: version(p)
            for p in (
                "langchain",
                "langchain-openai",
                "langchain-core",
                "deepagents",
                "openai",
                "httpx",
            )
        }
        files = [
            Path(__file__),
            Path(__file__).with_name("prompt_cache_cases.py"),
            *[
                ROOT / "apps/runtime-service/src/runtime_service" / p
                for p in (
                    "runtime/modeling.py",
                    "services/dearflow_agent/agent.py",
                    "services/dearflow_agent/middleware/memory.py",
                    "services/dearflow_agent/middleware/skills.py",
                    "middlewares/tool_output_pruning.py",
                )
            ],
        ]
        manifest["source_sha256"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        }
        validate_manifest(manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, manifest)
        print(
            json.dumps(
                {
                    "prepared": len(manifest["records"]),
                    "manifest_sha256": digest(manifest),
                    "paid_requests": 0,
                }
            )
        )
    elif args.command == "run":
        manifest = json.loads(args.manifest.read_text())
        result = await run_manifest(
            manifest,
            args.output,
            load_connection(),
            args.max_requests,
            args.max_estimated_cost_usd,
        )
        print(json.dumps(result))
        return 0 if result["stop_reason"] is None else 2
    elif args.command == "recompute":
        print(
            json.dumps(
                recompute_bundle(json.loads(args.bundle.read_text())),
                ensure_ascii=False,
            )
        )
    else:
        result = report(args.directory)
        if args.plots:
            plot_report(args.directory, result)
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

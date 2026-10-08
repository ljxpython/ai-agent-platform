"""Provider usage facts and fail-soft, native-Run-bound collection."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langgraph.config import get_config

from runtime_service.observability.diagnostics import uuid_string

logger = logging.getLogger(__name__)
MAX_TOKEN = 2**53 - 1
TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "cache_creation_5m_tokens",
    "cache_creation_1h_tokens",
    "reasoning_tokens",
)
EXCLUDED_OPERATIONS = ["suggestions", "title", "non_llm_provider_fees"]
_metrics: Counter = Counter()


def usage_enabled() -> bool:
    return os.getenv("RUNTIME_USAGE_ENABLED", "false").lower() in {"1", "true", "yes"}


def empty_tokens(value=None) -> dict:
    return dict.fromkeys(TOKEN_FIELDS, value)


def _usage_payload(response: Any) -> tuple[Mapping, str]:
    if isinstance(response, Mapping):
        return response, "provider_usage"
    for batch in getattr(response, "generations", []) or []:
        for generation in batch:
            message = getattr(generation, "message", None)
            usage = getattr(message, "usage_metadata", None)
            if isinstance(usage, Mapping) and usage:
                return usage, "usage_metadata"
            metadata = getattr(message, "response_metadata", {}) or {}
            if not isinstance(metadata, Mapping):
                continue
            for key in ("token_usage", "usage"):
                if isinstance(metadata.get(key), Mapping) and metadata[key]:
                    return metadata[key], "response_metadata"
    output = getattr(response, "llm_output", {}) or {}
    if isinstance(output, Mapping):
        for key in ("token_usage", "usage"):
            if isinstance(output.get(key), Mapping) and output[key]:
                return output[key], "llm_output"
    return {}, "missing"


def _count(value):
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= MAX_TOKEN:
        raise ValueError("invalid_usage")
    return value


def _pick(data: Mapping, *keys):
    for key in keys:
        if key in data and data[key] is not None:
            return _count(data[key])
    return None


def _details(usage: Mapping, *names) -> Mapping:
    for name in names:
        value = usage.get(name)
        if value is not None:
            if not isinstance(value, Mapping):
                raise ValueError("invalid_usage")
            return value
    return {}


def _token_counts(usage: Mapping, source: str, provider: str) -> dict:
    inputs = _details(usage, "input_token_details", "prompt_tokens_details")
    outputs = _details(usage, "output_token_details", "completion_tokens_details")
    ttl = _details(usage, "cache_creation")
    tokens = empty_tokens()
    tokens.update(
        input_tokens=_pick(usage, "input_tokens", "prompt_tokens"),
        output_tokens=_pick(usage, "output_tokens", "completion_tokens"),
        total_tokens=_pick(usage, "total_tokens"),
        cache_read_tokens=_pick(inputs, "cache_read", "cached_tokens"),
        cache_creation_tokens=_pick(inputs, "cache_creation"),
        cache_creation_5m_tokens=_pick(inputs, "ephemeral_5m_input_tokens"),
        cache_creation_1h_tokens=_pick(inputs, "ephemeral_1h_input_tokens"),
        reasoning_tokens=_pick(outputs, "reasoning", "reasoning_tokens"),
    )
    aliases = {
        "cache_read_tokens": ("cache_read_input_tokens", "prompt_cache_hit_tokens"),
        "cache_creation_tokens": ("cache_creation_input_tokens",),
    }
    for field, names in aliases.items():
        if tokens[field] is None:
            tokens[field] = _pick(usage, *names)
    for field, key in (
        ("cache_creation_5m_tokens", "ephemeral_5m_input_tokens"),
        ("cache_creation_1h_tokens", "ephemeral_1h_input_tokens"),
    ):
        if tokens[field] is None:
            tokens[field] = _pick(ttl, key)
    w5, w1 = tokens["cache_creation_5m_tokens"], tokens["cache_creation_1h_tokens"]
    if w5 is not None and w1 is not None:
        write = tokens["cache_creation_tokens"]
        # Anthropic's official adapter replaces the generic bucket with zero.
        if write is None or source == "usage_metadata" and write == 0:
            tokens["cache_creation_tokens"] = _count(w5 + w1)
        elif write != w5 + w1:
            raise ValueError("invalid_usage")
    if source != "usage_metadata" and "cache_read_input_tokens" in usage:
        values = [
            tokens[k]
            for k in ("input_tokens", "cache_read_tokens", "cache_creation_tokens")
        ]
        if all(v is not None for v in values):
            tokens["input_tokens"] = _count(sum(values))
    # OpenAI/DeepSeek adapters have no cache-write buckets; absence is provably zero.
    if provider in {"openai", "deepseek", "gpt-proxy", "deepseek-proxy"}:
        for field in (
            "cache_creation_tokens",
            "cache_creation_5m_tokens",
            "cache_creation_1h_tokens",
        ):
            if tokens[field] is None:
                tokens[field] = 0
    if tokens["cache_creation_tokens"] == 0:
        tokens["cache_creation_5m_tokens"] = tokens["cache_creation_5m_tokens"] or 0
        tokens["cache_creation_1h_tokens"] = tokens["cache_creation_1h_tokens"] or 0
    return tokens


def normalize_usage(response: Any, *, provider: str = "") -> dict:
    usage, source = _usage_payload(response)
    if not usage:
        return {"tokens": empty_tokens(), "quality": "missing", "source": "missing"}
    try:
        tokens = _token_counts(usage, source, provider)
        inp, out, total = (tokens[k] for k in TOKEN_FIELDS[:3])
        quality = "reported" if total is not None else "derived_from_reported"
        if inp is None or out is None:
            quality = "partial"
        else:
            computed = _count(inp + out)
            if total is not None and total != computed:
                quality = "partial"
            tokens["total_tokens"] = computed
        read, write = tokens["cache_read_tokens"], tokens["cache_creation_tokens"]
        if (
            inp is not None
            and read is not None
            and write is not None
            and read + write > inp
        ):
            raise ValueError("invalid_usage")
        if (
            out is not None
            and tokens["reasoning_tokens"] is not None
            and tokens["reasoning_tokens"] > out
        ):
            raise ValueError("invalid_usage")
        details = {}
        for direction, names in (
            ("input", ("input_token_details", "prompt_tokens_details")),
            ("output", ("output_token_details", "completion_tokens_details")),
        ):
            raw = _details(usage, *names)
            details[direction] = {
                key: _count(value)
                for key, value in raw.items()
                if key
                in {
                    "audio",
                    "audio_tokens",
                    "image",
                    "image_tokens",
                    "text",
                    "text_tokens",
                }
            }
        return {
            "tokens": tokens,
            "quality": quality,
            "source": source,
            "details": details,
        }
    except (ValueError, TypeError, OverflowError):
        return {"tokens": empty_tokens(), "quality": "invalid", "source": source}


def safe_pricing(value: Any) -> dict | None:
    if not isinstance(value, Mapping):
        return None
    if (
        value.get("currency") != "USD"
        or value.get("basis") != "per_million_tokens"
        or value.get("source") != "configured_catalog"
    ):
        return None
    if not uuid_string(value.get("version")):
        return None
    result = {k: value[k] for k in ("currency", "basis", "source", "version")}
    try:
        timestamp = datetime.fromisoformat(str(value.get("updated_at")))
        if timestamp.utcoffset() is None:
            return None
        result["updated_at"] = timestamp.astimezone(UTC).isoformat()
    except ValueError:
        return None
    for key in (
        "input",
        "output",
        "cache_read",
        "cache_write",
        "cache_write_5m",
        "cache_write_1h",
    ):
        rate = value.get(key)
        if rate is not None and (
            not isinstance(rate, str)
            or not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,10})?", rate)
        ):
            return None
        result[key] = rate
    return result


def estimate_usage_cost(usage: dict, pricing: Any) -> tuple[str | None, str | None]:
    price = safe_pricing(pricing)
    if usage["quality"] not in {"reported", "derived_from_reported"}:
        return None, "missing_or_invalid_usage"
    if price is None:
        return None, "missing_pricing"
    if any(
        value
        for details in usage.get("details", {}).values()
        for key, value in details.items()
        if key.startswith(("audio", "image"))
    ):
        return None, "unsupported_pricing"
    tokens = usage["tokens"]
    inp, out, read, write = (
        tokens[k]
        for k in (
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_creation_tokens",
        )
    )
    if any(v is None for v in (inp, out, read, write)):
        return None, "missing_cache_details"
    w5, w1 = tokens["cache_creation_5m_tokens"], tokens["cache_creation_1h_tokens"]
    if w5 is not None or w1 is not None:
        if w5 is None or w1 is None or w5 + w1 != write:
            return None, "incomplete_cache_ttl"
        generic = 0
    else:
        generic, w5, w1 = write, 0, 0
    buckets = {
        "input": inp - read - write,
        "output": out,
        "cache_read": read,
        "cache_write": generic,
        "cache_write_5m": w5,
        "cache_write_1h": w1,
    }
    if any(v < 0 for v in buckets.values()):
        return None, "invalid_usage"
    if any(value and price[key] is None for key, value in buckets.items()):
        return None, "missing_rate"
    try:
        with localcontext() as ctx:
            ctx.prec = 64
            cost = sum(
                Decimal(value) * Decimal(price[key] or "0")
                for key, value in buckets.items()
            ) / Decimal(1_000_000)
            cost = cost.quantize(Decimal("0.000000000001"))
            if cost >= Decimal("10000000000000000"):
                return None, "cost_overflow"
            return format(cost, ".12f"), None
    except (InvalidOperation, ValueError):
        return None, "invalid_pricing"


def _identifier(value: Any) -> str | None:
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_:.-]{1,128}", value)
        else None
    )


class RuntimeUsageCallback(AsyncCallbackHandler):
    def __init__(self, identity: dict):
        self.identity = identity
        self._root = None
        self._calls: dict = {}
        self._usage_providers: dict = {}
        self._degraded = False
        self._active = False

    async def _write(self, function: str, *args) -> None:
        from runtime_service.db.repositories import usage as repository

        try:
            await asyncio.to_thread(getattr(repository, function), self.identity, *args)
            _metrics["usage_write_succeeded"] += 1
        except Exception:
            self._degraded = True
            _metrics["usage_write_failed"] += 1
            logger.warning(
                "runtime_usage_write_failed",
                extra={"code": "usage_persistence_failed", **self.identity},
            )

    async def on_chain_start(
        self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs
    ):
        if not self._active:
            self._root = run_id
            self._active = True
            await self._write("begin_collection")

    async def on_chain_end(self, outputs, *, run_id, **kwargs):
        if run_id == self._root:
            await self._write("finish_collection", self._degraded)
            self._active = False

    async def on_chain_error(self, error, *, run_id, **kwargs):
        if run_id == self._root:
            await self._write("finish_collection", True)
            self._active = False

    async def on_chat_model_start(
        self,
        serialized,
        messages,
        *,
        run_id,
        parent_run_id=None,
        metadata=None,
        tags=None,
        **kwargs,
    ):
        if run_id in self._calls:
            return
        metadata = metadata or {}
        model = metadata.get("runtime_usage_model") or {}
        model = model if isinstance(model, Mapping) else {}
        protocol = model.get("protocol")
        self._usage_providers[run_id] = (
            "deepseek"
            if protocol == "deepseek"
            else "openai"
            if protocol in {"openai", "openai-compatible", "openai_compatible"}
            else _identifier(model.get("provider")) or ""
        )
        namespace = [
            _identifier(p.split(":", 1)[0])
            for p in str(metadata.get("langgraph_checkpoint_ns") or "").split("|")
            if p
        ]
        namespace = [p for p in namespace if p][:8]
        purpose = metadata.get("runtime_usage_purpose", "agent")
        if purpose not in {
            "agent",
            "summarization",
            "memory_extraction",
            "vision",
            "other",
        }:
            purpose = "other"
        if (
            purpose == "agent"
            and "summar" in str(metadata.get("langgraph_node", "")).lower()
        ):
            purpose = "summarization"
        call = {
            "model_call_id": str(run_id),
            "parent_call_id": uuid_string(parent_run_id),
            "model_id": uuid_string(model.get("model_id")),
            "provider": _identifier(model.get("provider")),
            "model_name": _identifier(model.get("model_name")),
            "scope": "auxiliary"
            if purpose in {"vision", "memory_extraction", "summarization"}
            else "subagent"
            if len(namespace) > 1
            else "primary",
            "purpose": purpose,
            "namespace": namespace,
            "pricing_snapshot": safe_pricing(model.get("pricing"))
            if uuid_string(model.get("model_id"))
            else None,
            "started_at": datetime.now(UTC).isoformat(),
            "ended_at": None,
            "outcome": "started",
            "tokens": empty_tokens(),
            "quality": "missing",
            "token_details": {},
            "usage_source": "missing",
            "estimated_cost_usd": None,
            "cost_reason": "incomplete_call",
        }
        self._calls[run_id] = call
        await self._write("upsert_call", call)

    async def _finish_call(self, run_id, response, outcome):
        call = self._calls.get(run_id)
        if call is None:
            self._degraded = True
            return
        usage = normalize_usage(response, provider=self._usage_providers[run_id])
        _metrics["usage_" + usage["quality"]] += 1
        cost, reason = estimate_usage_cost(usage, call["pricing_snapshot"])
        call.update(
            tokens=usage["tokens"],
            quality=usage["quality"],
            usage_source=usage["source"],
            token_details=usage.get("details", {}),
            estimated_cost_usd=cost,
            cost_reason=reason,
            outcome=outcome,
            ended_at=datetime.now(UTC).isoformat(),
        )
        await self._write("upsert_call", call)

    async def on_llm_end(self, response, *, run_id, **kwargs):
        await self._finish_call(run_id, response, "completed")

    async def on_llm_error(self, error, *, run_id, **kwargs):
        outcome = "cancelled" if isinstance(error, asyncio.CancelledError) else "failed"
        await self._finish_call(run_id, kwargs.get("response"), outcome)


def with_runtime_usage(
    graph, config, *, graph_id: str, trusted_metadata: Mapping | None = None
):
    if not usage_enabled():
        return graph.with_config(config)
    metadata = config.get("metadata") or {}
    trusted = trusted_metadata or {}
    identity = {
        key: _identifier(trusted.get(key)) for key in ("tenant_id", "project_id")
    }
    identity.update(
        graph_id=_identifier(graph_id),
        thread_id=uuid_string(metadata.get("thread_id")),
        run_id=uuid_string(metadata.get("run_id")),
    )
    if not all(identity.values()):
        return graph.with_config(config)
    callbacks = list(config.get("callbacks") or [])
    if not any(
        isinstance(c, RuntimeUsageCallback) and c.identity == identity
        for c in callbacks
    ):
        callbacks.append(RuntimeUsageCallback(identity))
    existing = (getattr(graph, "config", None) or {}).get("callbacks") or []
    return graph.with_config(
        {**config, "callbacks": [c for c in callbacks if c not in existing]}
    )


def usage_only_config(purpose: str) -> dict:
    """Preserve trusted usage handlers in hidden calls without adding content exporters."""
    try:
        callbacks = get_config().get("callbacks") or []
    except RuntimeError:
        callbacks = []
    handlers = getattr(callbacks, "handlers", callbacks)
    return {
        "callbacks": [c for c in handlers if isinstance(c, RuntimeUsageCallback)],
        "metadata": {"runtime_usage_purpose": purpose},
    }


__all__ = [
    "RuntimeUsageCallback",
    "normalize_usage",
    "estimate_usage_cost",
    "with_runtime_usage",
    "usage_only_config",
]

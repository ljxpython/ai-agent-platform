"""Platform-gateway-backed Judge LLM with JSON repair, 429 backoff, and budget limits."""

from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from eval_runner.targets.platform_client import PlatformModelConnection


def repair_json_text(raw: str) -> dict[str, Any]:
    """Repair common markdown fences or truncated JSON returned by judge LLMs."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("unparseable_judge_json")


@dataclass
class JudgeBudget:
    max_requests_per_case: int = 12
    requests_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls: list[dict[str, Any]] = field(default_factory=list)

    def reserve(self) -> None:
        if self.requests_used >= self.max_requests_per_case:
            raise RuntimeError("judge_budget_exhausted")
        self.requests_used += 1


def estimate_tokens_cost_usd(
    pricing: dict[str, Any] | None,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Compute USD cost from runtime-catalog per_million_tokens pricing snapshot."""
    if not isinstance(pricing, dict):
        return 0.0
    try:
        in_rate = float(pricing.get("input") or 0.0)
        out_rate = float(pricing.get("output") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return round(((input_tokens * in_rate) + (output_tokens * out_rate)) / 1_000_000.0, 8)


class PlatformJudgeLLM:
    """OpenAI-compatible LLM wrapper backed by platform-api resolved model connection."""

    def __init__(
        self,
        connection: PlatformModelConnection,
        *,
        budget: JudgeBudget | None = None,
        disable_thinking: bool = True,
        timeout: float = 60.0,
    ):
        self.connection = connection
        self.model_name = connection.model
        self.budget = budget or JudgeBudget()
        self.client = OpenAI(
            base_url=connection.base_url,
            api_key=connection.api_key,
            timeout=timeout,
            max_retries=0,
        )
        self.extra_body = (
            {"thinking": {"type": "disabled"}}
            if disable_thinking and "deepseek" in connection.model.lower()
            else {}
        )

    def get_model_name(self) -> str:
        return self.model_name

    def load_model(self) -> OpenAI:
        return self.client

    def generate(self, prompt: str, schema: Any = None) -> str:
        self.budget.reserve()
        full_prompt = prompt
        if schema is not None and hasattr(schema, "model_json_schema"):
            full_prompt += "\nReturn valid JSON matching schema:\n" + json.dumps(
                schema.model_json_schema(), ensure_ascii=False
            )
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": full_prompt}],
                    "temperature": 0,
                }
                if self.extra_body:
                    kwargs["extra_body"] = self.extra_body
                resp = self.client.chat.completions.create(**kwargs)
                usage = getattr(resp, "usage", None)
                if usage is not None:
                    self.budget.input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
                    self.budget.output_tokens += int(
                        getattr(usage, "completion_tokens", 0) or 0
                    )
                text = (resp.choices[0].message.content or "").strip()
                if schema is not None:
                    repaired = repair_json_text(text)
                    return json.dumps(repaired, ensure_ascii=False)
                return text
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < 2:
                    time.sleep((0.5 * (2**attempt)) + random.uniform(0.0, 0.25))
        raise RuntimeError(f"judge_call_failed:{last_exc}") from last_exc

    async def a_generate(self, prompt: str, schema: Any = None) -> str:
        return self.generate(prompt, schema=schema)

"""Small official DeepSeek comparison; prepare is offline, run requires an explicit key source."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from prompt_cache_agent import run_agent
from prompt_cache_cases import (
    canonical,
    capture,
    digest,
    fixtures,
    source_fingerprints,
    text_slots,
)
from prompt_cache_experiment import ROOT, report, run_manifest

MODEL = "deepseek-flash"
MODEL_ID = "official:deepseek-flash"
BASE_URL = "https://api.deepseek.com"
PRICING_REFERENCE = {
    "url": "https://api-docs.deepseek.com/quick_start/pricing",
    "verified_on": "2026-11-23",
    "basis": "fixed peak list-price estimate for both lanes; off-peak is half; actual bill unknown",
    "peak_utc": "Mon-Fri 01:00-04:00 and 06:00-10:00, except Chinese public holidays",
    "served_version_at_verification": "DeepSeek-V4.1-Flash-1017",
}
PRICE = {
    "currency": "USD",
    "basis": "per_million_tokens",
    "source": "configured_catalog",
    "version": "ead2c246-d592-4a1f-85c5-f6da2e8ca4ac",
    "updated_at": "2026-11-23T00:00:00+00:00",
    "input": "0.3",
    "output": "1.2",
    "cache_read": "0.006",
    "cache_write": "0",
    "cache_write_5m": "0",
    "cache_write_1h": "0",
}


def load_official_connection(*, key_env="DEEPSEEK_API_KEY", env_file=None, root=ROOT):
    """Read only the explicitly selected key source; never use catalog or gateway credentials."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
        raise ValueError("Invalid key variable name")
    state = json.loads((root / ".local-stack/environment.json").read_text())
    if Path(state["root"]).resolve() != root.resolve():
        raise ValueError("Worktree identity mismatch")
    values = dotenv_values(env_file) if env_file is not None else os.environ
    key = values.get(key_env)
    if not isinstance(key, str) or not key.strip() or key != key.strip():
        raise ValueError(
            "Official credential is missing from the selected private source"
        )
    return {
        "route": "deepseek_official",
        "model_id": MODEL_ID,
        "model": MODEL,
        "base_url": BASE_URL,
        "api_key": key,
        "pricing": copy.deepcopy(PRICE),
        "pricing_reference": dict(PRICING_REFERENCE),
        "environment_id": state["id"],
        "connection_fingerprint": digest(
            {"url": BASE_URL, "model": MODEL, "protocol": "openai-compatible"}
        ),
    }


async def prepare(root: Path, nonce: str):
    """Eight fixed-history requests; optimized payloads come directly from product middleware."""
    selected = [copy.deepcopy(f) for f in fixtures() if f["case"] == "C02"]
    products, baselines = [], []
    for item in selected:
        item["date"] = "2026-11-23" if item["turn"] < 2 else "2026-11-24"
        item["model"] = MODEL
        item["protocol"] = "deepseek"
        item["messages"][-1].content += " 同时输出本轮 current_date 的 UTC 日期。"
        product = await capture(item, root, layout="product")
        product["thinking"] = {"type": "disabled"}
        products.append(product)
        baseline = await capture(item, root, layout="legacy")
        baseline["thinking"] = {"type": "disabled"}
        baselines.append(baseline)
    records = []
    for group in ("A", "B"):
        lane = digest({"nonce": nonce, "group": group})[:24]
        for item, product, baseline in zip(selected, products, baselines, strict=True):
            payload = copy.deepcopy(baseline if group == "A" else product)
            container, key = text_slots(payload["messages"][0])[0]
            container[key] = (
                f"<cache_experiment_lane>{lane}</cache_experiment_lane>\n"
                + container[key]
            )
            records.append(
                {
                    "id": f"OFFICIAL-combined-{group}-r0-t{item['turn']}",
                    "case": "OFFICIAL-combined",
                    "group": group,
                    "repeat": 0,
                    "turn": item["turn"],
                    "expected": item["date"],
                    "required_terms": [item["expected"]],
                    "forbidden_terms": ["2026-11-23"] if item["turn"] >= 2 else [],
                    "execution_eligible": True,
                    "payload": payload,
                    "payload_sha256": digest(payload),
                    "baseline": baseline,
                    "baseline_sha256": digest(baseline),
                }
            )
    return {
        "version": 1,
        "material": "synthetic",
        "route": "deepseek_official",
        "model": MODEL,
        "model_id": MODEL_ID,
        "nonce": nonce,
        "created_at": datetime.now(UTC).isoformat(),
        "source_sha256": source_fingerprints(),
        "layer": "fixed_history_replay",
        "capture_boundary": "native HTTP capture in both lanes; A restores old factory date and memory wrapping, B uses product middleware",
        "limits": "One AB block, no statistical significance or guaranteed cold cache; no production ACL claim.",
        "records": records,
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("output", type=Path)
    for command in ("replay", "agent"):
        p = sub.add_parser(command)
        p.add_argument("output", type=Path)
        if command == "replay":
            p.add_argument("--manifest", type=Path, required=True)
        p.add_argument("--key-env", default="DEEPSEEK_API_KEY")
        p.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        manifest = await prepare(args.output.parent / "workspaces", uuid4().hex)
        with args.output.open("xb") as handle:
            handle.write(canonical(manifest) + b"\n")
        return {"requests": len(manifest["records"]), "network_calls": 0}
    connection = load_official_connection(key_env=args.key_env, env_file=args.env_file)
    if args.command == "replay":
        manifest = json.loads(args.manifest.read_text())
        if manifest.get("source_sha256") != source_fingerprints():
            raise ValueError("Source changed after preparation; prepare a new version")
        if len(manifest["records"]) != 8:
            raise ValueError(
                "Official batch must contain eight pre-registered requests"
            )
        registration = await run_manifest(
            manifest, args.output, connection, 8, Decimal("1")
        )
        return {"registration": registration, "usage": report(args.output)}
    return await run_agent(
        args.output, connection, factor="combined", product_layout=True
    )


if __name__ == "__main__":
    result = asyncio.run(main())
    print(json.dumps(result, ensure_ascii=False))

"""Convert legacy mlflow-eval-platform v3 cases to native platform CaseUpsert payloads."""

from __future__ import annotations

from typing import Any


def convert_legacy_case_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a legacy v3 JSONL case dict into platform CaseUpsert schema."""
    case_key = str(raw.get("case_key") or raw.get("case_id") or "").strip()
    split = "holdout" if raw.get("split") == "holdout" else "dev"
    turns = [
        {
            "role": t.get("role", "user"),
            "content": t.get("content", ""),
            **({"fixture": t["fixture"]} if t.get("fixture") else {}),
            **({"approval": t["approval"]} if t.get("approval") is not None else {}),
        }
        for t in (raw.get("turns") or [])
        if isinstance(t, dict) and str(t.get("content") or "").strip()
    ]
    exp = dict(raw.get("expectations") or {})
    if raw.get("business_rules") and "business_rules" not in exp:
        exp["business_rules"] = raw["business_rules"]
    caps = list(raw.get("required_capabilities") or [])
    if exp.get("artifacts") and "workspace_files" not in caps:
        caps.append("workspace_files")
    metadata = {
        "fixture": dict(raw.get("fixture") or {}),
        "business_rules": list(raw.get("business_rules") or []),
        "turn_expectations": list(raw.get("turn_expectations") or []),
        "access_policy": str(raw.get("access_policy") or "workspace_write"),
        "provenance": raw.get("provenance") or {},
    }
    return {
        "case_key": case_key,
        "split": split,
        "schema_version": str(raw.get("schema_version") or "3"),
        "required_capabilities": caps,
        "turns": turns,
        "simulation": raw.get("simulation"),
        "expectations": exp,
        "metrics": list(raw.get("metrics") or []),
        "metadata": metadata,
    }

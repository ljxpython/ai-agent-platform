"""Fail-fast validation for the Runtime deployment env contract."""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

BASE_REQUIRED = (
    "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET",
    "PLATFORM_RUNTIME_DELEGATION_ISSUER",
    "PLATFORM_RUNTIME_DELEGATION_AUDIENCE",
    "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER",
    "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE",
    "GRAPHHARBOR_WORKSPACE_ROOT",
)
NUMERIC = (
    "RUNTIME_WORKSPACE_MAX_FILE_BYTES",
    "RUNTIME_WORKSPACE_MAX_FILES",
    "RUNTIME_WORKSPACE_MAX_TOTAL_BYTES",
    "RUNTIME_WORKSPACE_TTL_SECONDS",
    "GRAPHHARBOR_RUN_TIMEOUT_SECONDS",
)
URLS = ("GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER",)


def _settings(path: Path) -> dict[str, str]:
    file_values = {
        key: str(value)
        for key, value in dotenv_values(path).items()
        if value is not None
    }
    return {**file_values, **os.environ}


def _present(settings: dict[str, str], key: str) -> bool:
    return bool(settings.get(key, "").strip())


def validate(path: Path) -> list[str]:
    if not path.is_file():
        return [f"deployment env file is missing: {path}"]

    settings = _settings(path)
    errors: list[str] = []
    required = BASE_REQUIRED
    required += ("PLATFORM_RUNTIME_DELEGATION_SECRET",)
    errors.extend(f"{key} is empty" for key in required if not _present(settings, key))
    for key in NUMERIC:
        if not _present(settings, key):
            errors.append(f"{key} is empty")
            continue
        try:
            value = int(settings[key])
        except ValueError:
            errors.append(f"{key} must be an integer")
            continue
        if value <= 0:
            errors.append(f"{key} must be greater than zero")

    reserve_key = "AGENT_RUN_WRAPUP_RESERVE_SECONDS"
    try:
        reserve = int(settings.get(reserve_key, "").strip() or "120")
        hard_limit = float(settings.get("GRAPHHARBOR_RUN_TIMEOUT_SECONDS", "0"))
        if (
            reserve < 0
            or not math.isfinite(hard_limit)
            or (reserve > 0 and reserve >= hard_limit)
        ):
            errors.append(
                f"{reserve_key} must be zero or less than GRAPHHARBOR_RUN_TIMEOUT_SECONDS"
            )
    except ValueError:
        errors.append(
            f"{reserve_key} must be a non-negative integer with a valid run timeout"
        )

    for key in URLS:
        value = settings.get(key, "").strip()
        if value and urlparse(value).scheme not in {"http", "https"}:
            errors.append(f"{key} must use http or https")

    for key in (
        "PLATFORM_RUNTIME_DELEGATION_SECRET",
        "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET",
    ):
        if _present(settings, key) and len(settings[key].strip()) < 32:
            errors.append(f"{key} must be at least 32 characters")

    workspace_root = settings.get("GRAPHHARBOR_WORKSPACE_ROOT", "").strip()
    if workspace_root and not Path(workspace_root).is_absolute():
        errors.append("GRAPHHARBOR_WORKSPACE_ROOT must be absolute")
    token_key = "RUNTIME_TOKEN_BUDGET_ENABLED"
    enabled = settings.get(token_key, "false").strip().lower()
    if enabled not in {"0", "false", "no", "off", "1", "true", "yes", "on"}:
        errors.append(f"{token_key} must be a boolean")
    if enabled in {"1", "true", "yes", "on"}:
        if settings.get("RUNTIME_USAGE_ENABLED", "false").strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            errors.append("RUNTIME_TOKEN_BUDGET_ENABLED requires RUNTIME_USAGE_ENABLED")
        maximum_key = "RUNTIME_TOKEN_BUDGET_MAX_TOKENS"
        try:
            maximum = int(settings.get(maximum_key, "100000"))
            if not 1 <= maximum <= 2**53 - 1:
                raise ValueError
        except ValueError:
            errors.append(f"{maximum_key} must be a positive safe integer")
        if not _present(settings, "DATABASE_URI") and not _present(
            settings, "RUNTIME_POSTGRES_DB"
        ):
            errors.append(
                "RUNTIME_TOKEN_BUDGET_ENABLED requires a migrated Usage database"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "deploy/.env.runtime-service",
    )
    args = parser.parse_args()
    errors = validate(args.env_file)
    if errors:
        for error in errors:
            print(f"CONFIG_ERROR {error}", file=sys.stderr)
        return 1
    print(f"Runtime deployment config valid: {args.env_file}")
    print("Validated required values without printing secret contents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

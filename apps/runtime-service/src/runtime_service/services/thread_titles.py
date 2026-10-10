"""Scoped one-shot thread title generation without graph or tool side effects."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from runtime_service.runtime import (
    AgentDefaults,
    RuntimeAuthError,
    RuntimeResolutionError,
    VerifiedDelegation,
    build_model,
    fetch_model_connection,
    parse_runtime_context,
    resolve_runtime_config,
    runtime_context_hash,
)
from runtime_service.utils.title_summarizer import (
    clean_generated_title,
    summarize_thread_title,
)

MAX_TITLE_MESSAGES = 8
MAX_TITLE_MESSAGE_CHARS = 4000
MAX_TITLE_TOTAL_CHARS = 12000
DEFAULT_TITLE_TIMEOUT_SECONDS = 8.0


def _validate_messages(messages: object) -> list[dict[str, str]]:
    if not isinstance(messages, list) or not 1 <= len(messages) <= MAX_TITLE_MESSAGES:
        raise ValueError("invalid title messages")
    normalized: list[dict[str, str]] = []
    total = 0
    for item in messages:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"role", "content"}
            or item.get("role") not in {"user", "assistant"}
            or not isinstance(item.get("content"), str)
        ):
            raise ValueError("invalid title message")
        content = item["content"].strip()
        if not content or len(content) > MAX_TITLE_MESSAGE_CHARS:
            raise ValueError("invalid title message")
        total += len(content)
        normalized.append({"role": item["role"], "content": content})
    if total > MAX_TITLE_TOTAL_CHARS:
        raise ValueError("title messages payload too large")
    return normalized


def _timeout_seconds(value: object) -> float:
    if value is None:
        return DEFAULT_TITLE_TIMEOUT_SECONDS
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid title timeout")
    timeout = float(value)
    if not 0 < timeout <= 30:
        raise ValueError("invalid title timeout")
    return timeout


def _attachment_title(
    facts: VerifiedDelegation, thread_id: str, files: list
) -> str | None:
    from runtime_service.runtime.errors import RuntimeWorkspaceError
    from runtime_service.workspace.documents import DocumentError, DocumentWorkspace
    from runtime_service.workspace.file_refs import validate_file_ref
    from runtime_service.workspace.scoped import resolve_thread_workspace

    try:
        root = resolve_thread_workspace(
            facts.principal.tenant_id,
            facts.principal.project_id,
            thread_id,
            facts.scope.assistant_id,
        )
        for item in files:
            ref = validate_file_ref(item)
            _, stored = DocumentWorkspace(root).read(ref["path"])
            if any(
                ref[key] != stored[key] for key in ("sha256", "mime_type", "size_bytes")
            ):
                return None
        return (
            clean_generated_title(files[0]["file_name"])
            if len(files) == 1
            else f"{len(files)}个附件"
        )
    except (DocumentError, RuntimeWorkspaceError, ValueError):
        return None


async def generate_thread_title(
    *,
    facts: VerifiedDelegation,
    thread_id: str,
    payload: Mapping[str, Any],
    model: object | None = None,
) -> dict[str, Any]:
    messages = (
        []
        if payload.get("messages") == []
        else _validate_messages(payload.get("messages"))
    )
    files = payload.get("files", [])
    if not isinstance(files, list) or len(files) > 8:
        raise ValueError("invalid_title_files")
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("invalid thread_id")
    scope = facts.scope
    if (
        scope.operation != "title-generate"
        or scope.thread_id != thread_id
        or scope.assistant_id != payload.get("assistant_id")
        or scope.project_id != facts.principal.project_id
        or scope.tenant_id != facts.principal.tenant_id
    ):
        raise RuntimeAuthError("runtime.auth.invalid_principal", "scope")
    context = parse_runtime_context(payload.get("context"))
    if runtime_context_hash(context) != facts.context_hash:
        raise RuntimeAuthError("runtime.auth.context_hash_mismatch", "context_hash")
    timeout = _timeout_seconds(payload.get("timeout_seconds"))
    try:
        async with asyncio.timeout(timeout):
            if files and not any(item["role"] == "user" for item in messages):
                title = await asyncio.to_thread(
                    _attachment_title, facts, thread_id, files
                )
                return {
                    "title": title,
                    "outcome": "applied" if title else "skipped",
                    "reason": None if title else "materials_missing",
                }
            if not messages:
                return {
                    "title": None,
                    "outcome": "skipped",
                    "reason": "materials_missing",
                }
            if not context.model_id:
                return {
                    "title": None,
                    "outcome": "degraded",
                    "reason": "model_unavailable",
                }
            resolved = resolve_runtime_config(
                principal=facts.principal,
                context=context,
                policy=facts.policy,
                defaults=AgentDefaults(
                    model_id=context.model_id,
                    system_prompt="title-generation-v1",
                    prompt_version="title-v1",
                ),
                available_tool_names=(),
            )
            if model is None:
                configurable = payload.get("config", {}).get("configurable", {})
                connection = await fetch_model_connection(
                    configurable.get("runtime_model_ref"),
                    model_id=resolved.model_id,
                    project_id=facts.principal.project_id,
                )
                if connection is None:
                    return {
                        "title": None,
                        "outcome": "degraded",
                        "reason": "model_unavailable",
                    }
                model = await asyncio.to_thread(
                    build_model, resolved, connection=connection, max_retries=0
                )
                model.disable_streaming = True
            title = await summarize_thread_title(messages, model=model)
            return {
                "title": title if title != "新对话" else None,
                "outcome": "applied" if title != "新对话" else "degraded",
                "reason": None if title != "新对话" else "empty_output",
            }
    except RuntimeAuthError:
        raise
    except RuntimeResolutionError as exc:
        if exc.code != "runtime.model.initialization_failed":
            raise
        return {"title": None, "outcome": "degraded", "reason": "model_unavailable"}
    except TimeoutError:
        return {"title": None, "outcome": "degraded", "reason": "timeout"}
    except Exception:
        return {"title": None, "outcome": "degraded", "reason": "provider_failure"}


__all__ = ["generate_thread_title"]

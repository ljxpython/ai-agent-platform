from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.api.langgraph.runs import _assert_bulk_cancel_scope, _assert_cron_query_scope
from fastapi import HTTPException


def _build_request(project_id: str | None):
    headers = {}
    if project_id is not None:
        headers["x-project-id"] = project_id
    return SimpleNamespace(
        headers=headers,
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(langgraph_scope_guard_enabled=False)
            )
        ),
    )


def test_project_scoped_cron_query_requires_assistant_or_thread_target() -> None:
    request = _build_request("5f419550-a3c7-49c6-9450-09154fd1bf7d")
    try:
        asyncio.run(_assert_cron_query_scope(request, {}))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "assistant_id or thread_id is required for project-scoped cron query"
    else:
        raise AssertionError("project-scoped cron query should require target")


def test_project_scoped_bulk_cancel_requires_thread_id() -> None:
    request = _build_request("5f419550-a3c7-49c6-9450-09154fd1bf7d")
    try:
        asyncio.run(_assert_bulk_cancel_scope(request, {"run_ids": ["run-1"]}))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "thread_id is required for project-scoped bulk cancel"
    else:
        raise AssertionError("project-scoped bulk cancel should require thread_id")


def test_unscoped_bulk_cancel_still_allowed_without_project_header() -> None:
    request = _build_request(None)
    asyncio.run(_assert_bulk_cancel_scope(request, {"run_ids": ["run-1"]}))

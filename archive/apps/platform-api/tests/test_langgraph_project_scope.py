from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.api.langgraph.runs import _raise_langgraph_request_error
from app.services.langgraph_sdk.scope_guard import (
    get_optional_project_id,
    inject_project_metadata,
    inject_project_scope,
)
from fastapi import HTTPException


def _build_request(project_id: str | None):
    headers = {}
    if project_id is not None:
        headers["x-project-id"] = project_id
    return SimpleNamespace(headers=headers)


def test_get_optional_project_id_returns_none_when_header_missing() -> None:
    request = _build_request(None)
    assert get_optional_project_id(request) is None


def test_get_optional_project_id_rejects_invalid_uuid() -> None:
    request = _build_request("not-a-uuid")
    try:
        get_optional_project_id(request)
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("invalid x-project-id should be rejected")


def test_inject_project_metadata_preserves_and_overrides_project_scope() -> None:
    request = _build_request("5f419550-a3c7-49c6-9450-09154fd1bf7d")
    payload = {"metadata": {"foo": "bar", "project_id": "wrong-project"}}

    scoped = inject_project_metadata(request, payload)

    assert scoped["metadata"]["foo"] == "bar"
    assert scoped["metadata"]["project_id"] == "5f419550-a3c7-49c6-9450-09154fd1bf7d"


def test_inject_project_scope_populates_context_and_top_level_metadata_only() -> None:
    request = _build_request("5f419550-a3c7-49c6-9450-09154fd1bf7d")
    payload = {
        "assistant_id": "assistant-1",
        "context": {"foo": "bar"},
        "config": {"metadata": {"trace": "abc"}},
        "metadata": {"origin": "test"},
    }

    scoped = inject_project_scope(request, payload)

    assert scoped["context"]["foo"] == "bar"
    assert scoped["context"]["project_id"] == "5f419550-a3c7-49c6-9450-09154fd1bf7d"
    assert scoped["config"]["metadata"]["trace"] == "abc"
    assert "project_id" not in scoped["config"]["metadata"]
    assert scoped["metadata"]["origin"] == "test"
    assert scoped["metadata"]["project_id"] == "5f419550-a3c7-49c6-9450-09154fd1bf7d"


def test_inject_project_scope_keeps_context_even_when_configurable_exists() -> None:
    request = _build_request("5f419550-a3c7-49c6-9450-09154fd1bf7d")
    payload = {
        "assistant_id": "assistant-1",
        "context": {"foo": "bar"},
        "config": {
            "configurable": {
                "model_id": "deepseek_chat",
                "project_id": "wrong-project",
            },
            "metadata": {"trace": "abc", "project_id": "wrong-project"},
        },
        "metadata": {"origin": "test"},
    }

    scoped = inject_project_scope(request, payload)

    assert scoped["context"]["foo"] == "bar"
    assert scoped["context"]["project_id"] == "5f419550-a3c7-49c6-9450-09154fd1bf7d"
    assert scoped["context"]["model_id"] == "deepseek_chat"
    assert "configurable" not in scoped["config"]
    assert scoped["config"]["metadata"]["trace"] == "abc"
    assert "project_id" not in scoped["config"]["metadata"]
    assert scoped["metadata"]["origin"] == "test"
    assert scoped["metadata"]["project_id"] == "5f419550-a3c7-49c6-9450-09154fd1bf7d"


def test_inject_project_scope_moves_runtime_fields_from_config_into_context() -> None:
    request = _build_request("5f419550-a3c7-49c6-9450-09154fd1bf7d")
    payload = {
        "assistant_id": "assistant-1",
        "config": {
            "recursion_limit": 12,
            "model_id": "config-model",
            "configurable": {
                "thread_id": "thread-1",
                "temperature": 0.7,
                "project_id": "wrong-project",
            },
        },
        "context": {
            "system_prompt": "context prompt",
            "user_id": "user-1",
        },
    }

    scoped = inject_project_scope(request, payload)

    assert scoped["config"]["recursion_limit"] == 12
    assert "model_id" not in scoped["config"]
    assert scoped["config"]["configurable"] == {"thread_id": "thread-1"}
    assert scoped["context"] == {
        "system_prompt": "context prompt",
        "model_id": "config-model",
        "temperature": 0.7,
        "project_id": "5f419550-a3c7-49c6-9450-09154fd1bf7d",
    }


def test_raise_langgraph_request_error_maps_value_error_to_400() -> None:
    try:
        _raise_langgraph_request_error(
            Exception("ValueError: test_case_project_id_required"),
            fallback_detail="langgraph_run_request_failed",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "test_case_project_id_required"
    else:
        raise AssertionError("ValueError should be translated to HTTP 400")

from __future__ import annotations

import pytest
from fastapi import HTTPException

from runtime_service.http.suggestions import (
    SuggestionsRequest,
    _authorize_scope,
)


def _request() -> SuggestionsRequest:
    return SuggestionsRequest(
        assistant_id="agent-1",
        messages=[{"role": "user", "content": "继续解释"}],
    )


def test_suggestions_request_forbids_runtime_injection() -> None:
    with pytest.raises(ValueError):
        SuggestionsRequest(
            assistant_id="agent-1",
            messages=[{"role": "user", "content": "继续"}],
            config={"tools": ["shell"]},
        )


def test_suggestions_scope_is_bound_to_thread_and_assistant() -> None:
    facts = {
        "runtime_principal": {"project_id": "project-1", "tenant_id": "tenant-1"},
        "runtime_scope": {
            "project_id": "project-1",
            "tenant_id": "tenant-1",
            "assistant_id": "agent-1",
            "thread_id": "thread-1",
            "operation": "suggestions-generate",
        },
    }
    _authorize_scope("thread-1", _request(), facts)
    with pytest.raises(HTTPException) as denied:
        _authorize_scope("thread-2", _request(), facts)
    assert denied.value.status_code == 403


def test_suggestions_scope_rejects_native_operation() -> None:
    facts = {
        "runtime_principal": {"project_id": "project-1", "tenant_id": "tenant-1"},
        "runtime_scope": {
            "project_id": "project-1",
            "tenant_id": "tenant-1",
            "assistant_id": "agent-1",
            "thread_id": "thread-1",
            "operation": "read",
        },
    }
    with pytest.raises(HTTPException) as denied:
        _authorize_scope("thread-1", _request(), facts)
    assert denied.value.status_code == 403

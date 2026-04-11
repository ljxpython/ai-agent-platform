from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.api.management.assistants import _normalize_assistant_runtime_contract


def test_normalize_assistant_runtime_contract_moves_runtime_fields_into_context() -> None:
    config, context, metadata = _normalize_assistant_runtime_contract(
        project_id="project-1",
        config={
            "recursion_limit": 12,
            "model_id": "config-model",
            "configurable": {
                "thread_id": "thread-1",
                "enable_tools": True,
                "tools": ["utc_now"],
            },
            "metadata": {
                "trace": "assistant-edit",
                "project_id": "legacy-project",
            },
        },
        context={
            "system_prompt": "context prompt",
        },
        metadata={
            "source": "workspace",
            "projectId": "legacy-project",
        },
    )

    assert config == {
        "recursion_limit": 12,
        "configurable": {"thread_id": "thread-1"},
        "metadata": {"trace": "assistant-edit"},
    }
    assert context == {
        "system_prompt": "context prompt",
        "model_id": "config-model",
        "enable_tools": True,
        "tools": ["utc_now"],
    }
    assert metadata == {"source": "workspace", "project_id": "project-1"}


def test_normalize_assistant_runtime_contract_strips_trusted_context_fields() -> None:
    config, context, metadata = _normalize_assistant_runtime_contract(
        project_id="project-1",
        config={
            "configurable": {
                "project_id": "legacy-project",
                "projectId": "legacy-project-2",
            }
        },
        context={
            "user_id": "user-1",
            "tenant_id": "tenant-1",
            "project_id": "legacy-project",
            "role": "admin",
            "permissions": ["write"],
        },
        metadata={},
    )

    assert config == {}
    assert context == {}
    assert metadata == {"project_id": "project-1"}


def test_normalize_assistant_runtime_contract_prefers_explicit_context_over_legacy_config() -> None:
    config, context, metadata = _normalize_assistant_runtime_contract(
        project_id="project-1",
        config={
            "temperature": 0.9,
            "configurable": {
                "temperature": 0.8,
                "max_tokens": 4096,
            },
        },
        context={
            "temperature": 0.2,
        },
        metadata={},
    )

    assert config == {}
    assert context == {
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    assert metadata == {"project_id": "project-1"}

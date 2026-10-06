from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ForbiddenError, UpstreamServiceError
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)


def _service(
    *, enabled: bool = True, upstream: object | None = None
) -> RuntimeGatewayService:
    service = RuntimeGatewayService(
        session_factory=None,
        upstream=upstream or SimpleNamespace(),
        suggestions_enabled=enabled,
        suggestions_max=3,
        suggestions_timeout_seconds=8.0,
    )
    service._load_thread = AsyncMock(  # type: ignore[method-assign]
        return_value={"thread_id": "thread-1", "metadata": {"graph_id": "agent-1"}}
    )
    service._assert_runtime_target_allowed = Mock()  # type: ignore[method-assign]
    service._inject_project_default_model = Mock(  # type: ignore[method-assign]
        side_effect=lambda *, project_id, payload: payload
    )
    service._validate_run_options = Mock()  # type: ignore[method-assign]
    service._attach_runtime_model_reference = Mock(  # type: ignore[method-assign]
        side_effect=lambda **kwargs: kwargs["payload"]
    )
    return service


def _messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "解释这个架构"}]


def test_suggestions_uses_scoped_operation_and_no_tool_policy() -> None:
    upstream = SimpleNamespace(
        generate_suggestions=AsyncMock(return_value={"suggestions": ["下一步？"]})
    )
    service = _service(upstream=upstream)
    service._thread_upstream = AsyncMock(return_value=upstream)  # type: ignore[method-assign]

    result = asyncio.run(
        service.generate_thread_suggestions(
            actor=ActorContext(user_id="user-1"),
            project_id="project-1",
            thread_id="thread-1",
            messages=_messages(),
            n=1,
        )
    )

    assert result == {"suggestions": ["下一步？"]}
    service._thread_upstream.assert_awaited_once_with(  # type: ignore[attr-defined]
        project_id="project-1",
        thread=service._load_thread.return_value,
        operation="suggestions-generate",
        context_hash=service._thread_upstream.await_args.kwargs["context_hash"],  # type: ignore[attr-defined]
    )
    payload = upstream.generate_suggestions.await_args.args[1]
    assert payload["timeout_seconds"] == 8.0
    assert payload["config"] == {}


def test_disabled_suggestions_still_check_thread_before_returning_empty() -> None:
    upstream = SimpleNamespace(generate_suggestions=AsyncMock())
    service = _service(enabled=False, upstream=upstream)

    assert asyncio.run(
        service.generate_thread_suggestions(
            actor=ActorContext(user_id="user-1"),
            project_id="project-1",
            thread_id="thread-1",
            messages=_messages(),
            n=1,
        )
    ) == {"suggestions": []}
    service._load_thread.assert_awaited_once()  # type: ignore[attr-defined]
    upstream.generate_suggestions.assert_not_awaited()


def test_upstream_server_failure_degrades_but_forbidden_does_not() -> None:
    for error, expected in (
        (
            UpstreamServiceError(
                upstream="runtime", status_code=502, upstream_status_code=503
            ),
            {"suggestions": []},
        ),
        (
            ForbiddenError(code="runtime_model_denied"),
            None,
        ),
    ):
        upstream = SimpleNamespace(generate_suggestions=AsyncMock(side_effect=error))
        service = _service(upstream=upstream)
        service._thread_upstream = AsyncMock(return_value=upstream)  # type: ignore[method-assign]
        call = service.generate_thread_suggestions(
            actor=ActorContext(user_id="user-1"),
            project_id="project-1",
            thread_id="thread-1",
            messages=_messages(),
            n=1,
        )
        if expected is None:
            with pytest.raises(ForbiddenError):
                asyncio.run(call)
        else:
            assert asyncio.run(call) == expected

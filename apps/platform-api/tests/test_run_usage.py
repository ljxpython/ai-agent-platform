import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
)
from platform_api.core.errors.handlers import register_exception_handlers
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.application.usage import (
    RuntimeRunUsage,
    validate_run_query,
    validate_thread_query,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_actor_context,
    get_runtime_gateway_service,
    router,
)

THREAD, RUN = str(uuid4()), str(uuid4())


def summary():
    tokens = dict.fromkeys(
        (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cache_read_tokens",
            "cache_creation_tokens",
            "cache_creation_5m_tokens",
            "cache_creation_1h_tokens",
            "reasoning_tokens",
        )
    )
    return {
        "version": 1,
        "thread_id": THREAD,
        "run_id": RUN,
        "availability": "unavailable",
        "unavailable_reason": "not_recorded",
        "finalized": False,
        "tokens": tokens,
        "known_tokens": tokens,
        "cost": {
            "status": "unknown",
            "estimated_cost_usd": None,
            "known_cost_usd": None,
            "currency": "USD",
            "source": None,
            "unpriced_call_count": 0,
            "pricing_versions": [],
        },
        "coverage": {
            "observed_call_count": 0,
            "reported_call_count": 0,
            "missing_usage_call_count": 0,
            "incomplete_call_count": 0,
            "collection_degraded": False,
            "excluded_operations": ["suggestions", "title", "non_llm_provider_fees"],
        },
        "calls": {"items": [], "next_cursor": None},
        "truncated": False,
    }


def test_gateway_projection_and_run_scope():
    upstream = SimpleNamespace(
        get_thread_run=AsyncMock(
            return_value={"thread_id": THREAD, "run_id": RUN, "status": "success"}
        ),
        get_run_usage=AsyncMock(
            return_value={
                **summary(),
                "prompt": "SECRET",
                "pricing_snapshot": {"api_key": "SECRET"},
            }
        ),
    )
    service = RuntimeGatewayService(session_factory=None, upstream=upstream)
    service._load_thread = AsyncMock(return_value={"thread_id": THREAD})
    service._thread_upstream = AsyncMock(return_value=upstream)
    kwargs = dict(
        actor=ActorContext(user_id="owner"),
        project_id="project",
        thread_id=THREAD,
        run_id=RUN,
        request_id="query",
    )
    result = asyncio.run(service.get_thread_run_usage(**kwargs))
    assert result["run_status"] == "success" and "SECRET" not in json.dumps(result)
    assert service._thread_upstream.await_args.kwargs["operation"] == "usage-read"
    for failure in (ForbiddenError(), NotFoundError()):
        upstream.get_run_usage.reset_mock()
        service._load_thread.side_effect = failure
        with pytest.raises(type(failure)):
            asyncio.run(service.get_thread_run_usage(**kwargs))
        upstream.get_run_usage.assert_not_awaited()
    service._load_thread.side_effect = None
    upstream.get_thread_run.return_value["thread_id"] = str(uuid4())
    with pytest.raises(NotFoundError):
        asyncio.run(service.get_thread_run_usage(**kwargs))
    upstream.get_thread_run.return_value["thread_id"] = THREAD
    upstream.get_run_usage.return_value["thread_id"] = str(uuid4())
    with pytest.raises(PlatformApiError) as exc:
        asyncio.run(service.get_thread_run_usage(**kwargs))
    assert exc.value.status_code == 502


@pytest.mark.parametrize(
    "limit,cursor", [(0, None), (201, None), (True, None), (1, "bad!"), (1, "a" * 513)]
)
def test_bad_pagination(limit, cursor):
    with pytest.raises(BadRequestError):
        validate_run_query(limit, cursor)


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-01-01", "2026-01-02"),
        ("2026-01-01T00:00:00Z", None),
        ("2026-01-01T00:00:00Z", "2026-05-01T00:00:00Z"),
        ("2026-01-01T00:00:00+08:00", "2026-01-02T00:00:00+08:00"),
    ],
)
def test_bad_window(start, end):
    with pytest.raises(BadRequestError):
        validate_thread_query(start, end)


def test_dto_rejects_unsafe_numbers_and_bad_money():
    payload = summary()
    for number in (True, -1, 2**53, 1.5):
        payload["tokens"]["input_tokens"] = number
        with pytest.raises(ValidationError):
            RuntimeRunUsage.model_validate(payload)
    payload["tokens"]["input_tokens"] = None
    for number in (0.1, "1e4", "NaN"):
        payload["cost"]["known_cost_usd"] = number
        with pytest.raises(ValidationError):
            RuntimeRunUsage.model_validate(payload)


def test_dto_rejects_inconsistent_totals_and_completeness():
    payload = summary()
    payload["tokens"] = {
        **payload["tokens"],
        "input_tokens": 10,
        "output_tokens": 2,
        "total_tokens": 99,
    }
    with pytest.raises(ValidationError):
        RuntimeRunUsage.model_validate(payload)
    payload = summary()
    payload["coverage"]["reported_call_count"] = 1
    with pytest.raises(ValidationError):
        RuntimeRunUsage.model_validate(payload)
    payload = summary()
    payload["availability"] = "available"
    payload["unavailable_reason"] = None
    with pytest.raises(ValidationError):
        RuntimeRunUsage.model_validate(payload)


def test_http_uses_no_store_and_frozen_contract():
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)
    service = SimpleNamespace(
        get_thread_run_usage=AsyncMock(
            return_value={**summary(), "run_status": "success", "request_id": "query"}
        )
    )
    app.dependency_overrides[get_actor_context] = lambda: ActorContext(user_id="owner")
    app.dependency_overrides[get_runtime_gateway_service] = lambda: service

    @app.middleware("http")
    async def scope(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id="project"),
            request=SimpleNamespace(request_id="query"),
        )
        return await call_next(request)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/langgraph/threads/{THREAD}/runs/{RUN}/usage"
            )
            assert (
                response.status_code == 200
                and response.headers["cache-control"] == "no-store"
            )
            assert response.json()["unavailable_reason"] == "not_recorded"

    asyncio.run(run())

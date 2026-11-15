import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_evaluation_feedback import setup as _feedback_setup

from platform_api.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)
from platform_api.core.errors import ForbiddenError
from platform_api.modules.evaluation import assistant_bridge as bridge
from platform_api.modules.evaluation import workbench

setup = _feedback_setup


def test_background_advance_only_continues_saved_actor_request(setup, monkeypatch):
    factory, actor, scope = setup
    item_id, job_id = str(uuid4()), str(uuid4())
    item = {
        "id": item_id,
        "assistant_jobs": [
            {"id": job_id, "created_by": actor.user_id, "status": "reserved"}
        ],
    }
    forward = AsyncMock(return_value=item)
    start = AsyncMock(return_value=item)
    reconcile = AsyncMock(return_value=item)
    monkeypatch.setattr(workbench, "forward", forward)
    monkeypatch.setattr(bridge, "start_assistant", start)
    monkeypatch.setattr(bridge, "reconcile_assistant", reconcile)
    monkeypatch.setattr(
        "platform_api.modules.runtime_gateway.presentation.http.get_runtime_gateway_service",
        lambda *a: "gateway",
    )
    context = PlatformRequestContext(
        RequestContext("r", "t", "POST", "/", 0),
        TenantContext(),
        ProjectContext(),
        ActorContext(),
    )
    request = NS(
        app=NS(
            state=NS(
                db_session_factory=factory,
                settings=NS(evaluation_workbench_enabled=True),
            )
        ),
        state=NS(platform_context=context),
    )
    body = bridge.AdvanceRequest(
        project_id=scope[0],
        actor_id=actor.user_id,
        work_item_id=item_id,
        target_id=job_id,
        kind="assistant",
    )
    assert asyncio.run(bridge.advance_saved_request(request, body)) == {
        "status": "checked"
    }
    assert start.await_args.args[1].user_id == actor.user_id
    assert request.state.platform_context.project.project_id == scope[0]
    item["assistant_jobs"][0]["created_by"] = str(uuid4())
    with pytest.raises(ForbiddenError):
        asyncio.run(bridge.advance_saved_request(request, body))
    assert start.await_count == 1


def test_background_explanation_is_not_started_without_real_evidence(
    setup, monkeypatch
):
    factory, actor, scope = setup
    item_id, operation_id, task_id = (str(uuid4()) for _ in range(3))
    item = {
        "operations": [
            {"id": operation_id, "created_by": actor.user_id, "task_id": task_id}
        ],
        "results": [{"task_id": task_id, "status": "cancelled", "evidence": {}}],
    }
    monkeypatch.setattr(workbench, "forward", AsyncMock(return_value=item))
    start = AsyncMock()
    monkeypatch.setattr(bridge, "start_assistant", start)
    request = NS(
        app=NS(
            state=NS(
                db_session_factory=factory,
                settings=NS(evaluation_workbench_enabled=True),
            )
        )
    )
    body = bridge.AdvanceRequest(
        project_id=scope[0],
        actor_id=actor.user_id,
        work_item_id=item_id,
        target_id=operation_id,
        kind="result",
    )
    assert asyncio.run(bridge.advance_saved_request(request, body)) == {
        "status": "no_result"
    }
    start.assert_not_awaited()

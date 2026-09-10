"""Historical behavior probes for the 2026-09-10 architecture review.

Uses temporary SQLite plus mocked upstreams. Assertions demonstrate defects,
not acceptance. Convert them to normal regression tests during implementation.
Pass the platform-api directory as the first argument; no live service needed.
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

root = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(root), str(root / "tests")]
from test_durable_run_coordinator import DurableRunCoordinatorTest
from app.core.errors import PlatformApiError
from app.modules.runtime_gateway.application.service import RuntimeGatewayService
from app.modules.runtime_gateway.infra.sqlalchemy.repository import SqlAlchemyDurableRunsRepository
from app.modules.runtime_gateway.presentation.http import _redact_event_value

async def probe():
    case = DurableRunCoordinatorTest()
    case.setUp()
    try:
        case.service._validate_run_options = AsyncMock()
        args = dict(actor=case.actor, project_id="project-1", thread_id="thread-1", payload=case._command()["params"])
        first = await case.service.create_thread_run(**args)
        case.upstream.create_thread_run.return_value = {"run_id": "run-2"}
        second = await case.service.create_thread_run(**args)
        assert first["run_id"] == second["run_id"] == "run-1"
        assert case.upstream.create_thread_run.await_count == 1
        print("CONFIRMED: standard Runs API reuses the old run for a second identical submission")
    finally:
        case.tearDown()
    case = DurableRunCoordinatorTest()
    case.setUp()
    try:
        case.upstream.create_thread_run.side_effect = PlatformApiError(code="upstream_rejected", status_code=422, message="synthetic rejected request")
        args = dict(actor=case.actor, project_id="project-1", thread_id="thread-1", payload=case._command())
        try:
            await case.service.send_thread_command(**args, idempotency_key="rejected-1")
        except PlatformApiError as error:
            assert error.status_code == 422
        else:
            raise AssertionError("expected rejection")
        with case._session_factory() as session:
            row = SqlAlchemyDurableRunsRepository(session).get_active(project_id="project-1", thread_id="thread-1")
            assert row is not None and row.status == "submitted" and row.run_id is None
        case.dispatcher.dispatch.assert_not_awaited()
        try:
            await case.service.send_thread_command(**args, idempotency_key="new-request-2")
        except PlatformApiError as error:
            assert error.code == "thread_active_run_conflict"
        else:
            raise AssertionError("expected poisoned active slot")
        print("CONFIRMED: upstream 422 leaves an active submitted ledger row and blocks the next request")
    finally:
        case.tearDown()
    case = DurableRunCoordinatorTest()
    case.setUp()
    try:
        case.upstream.get_thread_run.return_value = {"run_id": "run-1", "status": "running", "config": {"configurable": {"runtime_model_ref": "synthetic-capability"}}}
        result = await case.service.get_thread_run(actor=case.actor, project_id="project-1", thread_id="thread-1", run_id="run-1")
        assert result["config"]["configurable"]["runtime_model_ref"] == "synthetic-capability"
        assert _redact_event_value(result)["config"]["configurable"]["runtime_model_ref"] == "synthetic-capability"
        print("CONFIRMED: Run reads and protocol event redaction preserve runtime_model_ref")
    finally:
        case.tearDown()

    service = RuntimeGatewayService(session_factory=None, upstream=SimpleNamespace())
    service._assistant_belongs_project = AsyncMock(return_value=False)
    await service._assert_runtime_target_allowed(
        project_id="project", assistant_id="removed-agent",
        thread={"metadata": {"graph_id": "removed-agent"}},
    )
    print("CONFIRMED: historical thread metadata permits an agent absent from the project")

asyncio.run(probe())

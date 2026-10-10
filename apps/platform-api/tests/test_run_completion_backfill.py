import asyncio
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from platform_api.core.errors import ForbiddenError
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionOriginRecord as Origin,
)
from platform_api.modules.scheduled_tasks.schemas import TaskCreate
from platform_api.modules.scheduled_tasks.service import ScheduledTasksService
from tests import test_run_completion

fixture = test_run_completion.fixture


def module():
    spec = importlib.util.spec_from_file_location(
        "backfill",
        Path(__file__).resolve().parents[1]
        / "scripts/backfill_run_completion_origins.py",
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture
def setup(fixture, monkeypatch):
    value = module()
    monkeypatch.setattr(value, "require_active_project", lambda *args: None)
    task_id = str(uuid4())
    spec = TaskCreate(
        title="existing", prompt="preserve input", agent_key="probe", cron="0 0 * * *"
    )
    row = {
        "thread_id": None,
        "payload": {"assistant_id": "probe", "input": {"x": 1}, "config": {}},
        "metadata": {"task_spec": spec.model_dump(mode="json")},
    }
    upstream = SimpleNamespace(cron_request=AsyncMock())
    gateway = SimpleNamespace(
        _session_factory=fixture.factory,
        _completion_enabled=True,
        _assert_runtime_target_allowed=Mock(),
        _validate_run_options=Mock(),
        _load_thread=AsyncMock(),
    )
    service = ScheduledTasksService(gateway, tenant_id="__default", secret="d" * 32)
    service.list = AsyncMock(return_value={"items": [{"id": task_id}], "total": 1})
    service.get_native = AsyncMock(side_effect=lambda **kwargs: copy.deepcopy(row))
    service._upstream = AsyncMock(return_value=upstream)
    return value, service, upstream, row, fixture


def run(setup, action, path=None):
    value, service, _, _, fixture = setup
    return asyncio.run(
        value.backfill(
            service,
            actor=fixture.actor,
            project_id=fixture.project,
            action=action,
            manifest_path=path,
        )
    )


def test_backfill_preview_apply_response_loss_resume_and_revert(setup, tmp_path):
    _, service, upstream, row, fixture = setup
    assert run(setup, "dry-run")[0]["action"] == "backfill"
    with fixture.factory() as session:
        assert session.scalar(select(func.count()).select_from(Origin)) == 0
    path = tmp_path / "private.json"
    upstream.cron_request.side_effect = TimeoutError("response lost")
    with pytest.raises(TimeoutError):
        run(setup, "apply", path)
    assert path.stat().st_mode & 0o777 == 0o600
    upstream.cron_request.side_effect = None
    assert run(setup, "apply", path)[0]["action"] == "applied"
    assert upstream.cron_request.call_args.kwargs["payload"] == {
        **row["payload"],
        "thread_id": row["thread_id"],
    }
    assert run(setup, "apply", path)[0]["action"] == "applied"
    assert upstream.cron_request.call_count == 2
    with fixture.factory() as session:
        origin = session.scalar(select(Origin))
        assert session.scalar(select(func.count()).select_from(Origin)) == 1
        assert service._upstream.call_args.kwargs["origin_ref"] == origin.origin_ref
    assert run(setup, "revert", path)[0]["action"] == "reverted"
    assert service._upstream.call_args.kwargs["origin_ref"] is None
    with fixture.factory() as session:
        assert session.scalar(select(Origin)).state == "retired"


def test_backfill_rejects_changed_payload_and_skips_revocation(setup, tmp_path):
    _, service, upstream, row, _ = setup
    path = tmp_path / "private.json"
    upstream.cron_request.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        run(setup, "apply", path)
    row["payload"]["input"] = {"x": "changed"}
    with pytest.raises(ValueError, match="payload changed"):
        run(setup, "apply", path)
    service.get_native.side_effect = ForbiddenError(code="revoked", message="revoked")
    assert run(setup, "apply", path)[0]["action"] == "unavailable"

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from test_evaluation_feedback import setup as _feedback_setup

from platform_api.core.db import session_scope
from platform_api.core.errors import ForbiddenError
from platform_api.modules.evaluation import assistant_control as control
from platform_api.modules.evaluation.models import EvaluationExport
from platform_api.modules.evaluation.workbench_grants import check_assistant_thread

setup = _feedback_setup


def grant(factory, actor, project, thread, *, status="ready"):
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord

    export_id = str(uuid4())
    with session_scope(factory) as session:
        agent_id = uuid4()
        session.add(
            AgentRecord(
                id=agent_id,
                project_id=UUID(project),
                name="Synthetic test",
                graph_id="dearflow_agent",
                created_by=UUID(actor.user_id),
                updated_by=UUID(actor.user_id),
            )
        )
        session.add(
            EvaluationExport(
                export_id=export_id,
                event_id=str(uuid4()),
                project_id=project,
                actor_id=actor.user_id,
                digest="a" * 64,
                status=status,
                payload={"source_kind": "work_item", "agent_id": str(agent_id)},
                receipt={"assistant_threads": [thread]},
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    return export_id


def test_changed_membership_stops_registered_assistant(setup):
    from sqlalchemy import select

    from platform_api.modules.projects.models import ProjectMemberRecord

    factory, actor, (project, thread, _) = setup
    grant(factory, actor, project, thread)
    assert not control.control_allowed(factory, project, thread, delete=True)
    with session_scope(factory) as session:
        member = session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.user_id == UUID(actor.user_id)
            )
        )
        member.role = "executor"
    assert control.control_allowed(factory, project, thread, delete=True)


def test_retention_keeps_execution_tombstone_and_waits_for_cleanup(setup):
    from platform_api.modules.evaluation.retention import POLICY, sweep

    factory, actor, (project, thread, _) = setup
    identifier = grant(factory, actor, project, thread, status="revoked")
    with session_scope(factory) as session:
        row = session.get(EvaluationExport, identifier)
        row.payload = {**row.payload, "retention_policy": POLICY}
        row.receipt = {"execution_threads": {thread: "dearflow_agent"}}
    assert sweep(factory, project)["cleaned"] == 0
    with session_scope(factory) as session:
        row = session.get(EvaluationExport, identifier)
        row.receipt = {**row.receipt, "cleaned_threads": [thread]}
    assert sweep(factory, project)["cleaned"] == 1
    with session_scope(factory) as session:
        assert (
            session.get(EvaluationExport, identifier).receipt["execution_threads"][
                thread
            ]
            == "dearflow_agent"
        )
    with pytest.raises(ForbiddenError):
        check_assistant_thread(factory, project, thread)


def test_stop_and_delete_require_registered_scope_and_cause(setup):
    factory, actor, (project, thread, _) = setup
    export_id = grant(factory, actor, project, thread)
    assert check_assistant_thread(factory, project, thread) is True
    assert check_assistant_thread(factory, project, str(uuid4())) is False
    assert not control.control_allowed(factory, project, thread)
    control.request_stop(factory, project, thread, actor.user_id)
    assert control.control_allowed(factory, project, thread)
    assert not control.control_allowed(factory, project, thread, delete=True)
    assert not control.control_allowed(factory, str(uuid4()), thread)
    assert not control.control_allowed(factory, project, str(uuid4()))
    with session_scope(factory) as session:
        row = session.get(EvaluationExport, export_id)
        assert row.receipt["stop_requests"][thread]["requested_by"] == actor.user_id
        row.status = "revoked"
    assert control.control_allowed(factory, project, thread, delete=True)
    with pytest.raises(ForbiddenError):
        check_assistant_thread(factory, project, thread)


@pytest.mark.parametrize("revoked_purpose", ["evaluation_assistance", "regression"])
def test_execution_requires_both_grants_and_closes_every_native_read(
    setup, revoked_purpose
):
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
    from platform_api.modules.evaluation.workbench_grants import (
        GrantBody,
        assistant_thread_ids,
        bind_execution_thread,
        create_grant,
        revoke_grant,
    )

    factory, actor, (project, thread, _) = setup
    agent_id = uuid4()
    with session_scope(factory) as session:
        session.add(
            AgentRecord(
                id=agent_id,
                project_id=UUID(project),
                name="Controlled execution",
                graph_id="dearflow_agent",
                created_by=UUID(actor.user_id),
                updated_by=UUID(actor.user_id),
            )
        )
    item = {
        "id": str(uuid4()),
        "project_id": project,
        "agent_id": str(agent_id),
        "material_hash": "a" * 64,
    }
    grants = {
        purpose: create_grant(
            factory,
            actor,
            project,
            item,
            GrantBody(grant_id=uuid4(), purpose=purpose, synthetic_attestation=True),
            "model",
        )["grant_id"]
        for purpose in ("evaluation_assistance", "regression")
    }
    with pytest.raises(ForbiddenError):
        bind_execution_thread(
            factory,
            project,
            {"regression": grants["regression"]},
            thread,
            str(agent_id),
            "dearflow_agent",
        )
    with pytest.raises(ForbiddenError):
        bind_execution_thread(
            factory, project, grants, thread, str(agent_id), "evaluation_assistant"
        )
    bind_execution_thread(
        factory, project, grants, thread, str(agent_id), "dearflow_agent"
    )
    assert (
        check_assistant_thread(factory, project, thread) is False
    )  # Not the assistant graph.
    assert thread in assistant_thread_ids(factory, project)
    assert not control.control_allowed(factory, project, thread, delete=True)
    revoke_grant(factory, actor, project, grants[revoked_purpose])
    with pytest.raises(ForbiddenError):
        check_assistant_thread(factory, project, thread)
    with pytest.raises(ForbiddenError):
        bind_execution_thread(
            factory, project, grants, str(uuid4()), str(agent_id), "dearflow_agent"
        )
    assert control.control_allowed(factory, project, thread, delete=True)


@pytest.mark.parametrize(
    "stopped,delete_error", [(False, False), (True, True), (True, False)]
)
def test_cleanup_marks_receipt_only_after_real_stop_and_delete(
    setup, monkeypatch, stopped, delete_error
):
    factory, actor, (project, thread, _) = setup
    export_id = grant(factory, actor, project, thread, status="revoked")
    calls = []

    def transport(request):
        calls.append(request.method)
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "execution_stopped": stopped,
                    "phase": "stopped" if stopped else "stopping",
                },
            )
        return httpx.Response(503 if delete_error else 204)

    client_class = httpx.Client
    monkeypatch.setattr(
        control, "create_runtime_delegation_token", lambda **_: "local-test"
    )
    monkeypatch.setattr(
        control.httpx,
        "Client",
        lambda **kw: client_class(**kw, transport=httpx.MockTransport(transport)),
    )
    settings = SimpleNamespace(langgraph_upstream_url="http://runtime.test")
    if delete_error:
        with pytest.raises(httpx.HTTPStatusError):
            control.control(factory, settings, project, thread, delete=True)
    else:
        receipt = control.control(factory, settings, project, thread, delete=True)
        assert bool(receipt.get("deleted")) == stopped
    assert calls == (["POST", "DELETE"] if stopped else ["POST"])
    with session_scope(factory) as session:
        cleaned = session.get(EvaluationExport, export_id).receipt.get(
            "cleaned_threads", []
        )
        assert (thread in cleaned) == (stopped and not delete_error)

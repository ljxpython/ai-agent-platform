"""Historical inspection grants remain readable/revocable after submission retirement."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from platform_api.core.db import session_scope
from platform_api.core.errors import ForbiddenError
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.evaluation.models import EvaluationExport
from platform_api.modules.evaluation.service import (
    authorized_package,
    digest,
    revoke_export,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)


@pytest.fixture
def inspection(setup):
    factory, actor, scope = setup
    agent_id, export_id = uuid4(), str(uuid4())
    payload = {
        "purpose": "quality_inspection",
        "data_class": "synthetic",
        "thread_id": scope[1],
        "run_id": str(uuid4()),
        "agent_id": str(agent_id),
        "input": "Return [REDACTED_1]",
        "output": "[REDACTED_1]",
        "judge_route": "synthetic-judge",
        "budget_policy_version": "inspection-test-v1",
        "source_event": str(uuid4()),
        "content_hash": "legacy-fixture",
    }
    with session_scope(factory) as session:
        session.add(
            AgentRecord(
                id=agent_id,
                project_id=UUID(scope[0]),
                name="Inspection fixture",
                graph_id="dearflow_agent",
                created_by=UUID(actor.user_id),
                updated_by=UUID(actor.user_id),
            )
        )
        session.add(
            EvaluationExport(
                export_id=export_id,
                event_id=payload["source_event"],
                project_id=scope[0],
                actor_id=actor.user_id,
                digest=digest(payload),
                payload=payload,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    return export_id, agent_id


def test_historical_inspection_remains_readable_and_revocable(setup, inspection):
    factory, actor, scope = setup
    export_id, _ = inspection
    package = authorized_package(factory, scope[0], export_id)
    assert package["purpose"] == "quality_inspection"
    assert (
        not {"feedback", "scenario", "expected", "tools", "retrieval"} & package.keys()
    )
    revoke_export(factory, actor, scope[0], export_id)
    revoke_export(factory, actor, scope[0], export_id)
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], export_id)


@pytest.mark.parametrize("reason", ["disabled_agent", "expired", "changed_owner"])
def test_historical_inspection_rechecks_current_scope(setup, inspection, reason):
    factory, _, scope = setup
    export_id, agent_id = inspection
    with session_scope(factory) as session:
        if reason == "disabled_agent":
            session.get(AgentRecord, agent_id).status = "disabled"
        elif reason == "expired":
            session.get(EvaluationExport, export_id).expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)
        else:
            session.get(ThreadAccessRecord, scope[1]).owner_user_id = str(uuid4())
    with pytest.raises(ForbiddenError):
        authorized_package(factory, scope[0], export_id)

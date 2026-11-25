from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from evaluation_fixtures import setup as _feedback_setup

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import ForbiddenError
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.evaluation.delegation import (
    issue_command,
    require_action,
    verify_command,
)
from platform_api.modules.evaluation.models import EvaluationExport
from platform_api.modules.evaluation.service import authorized_package
from platform_api.modules.evaluation.workbench_grants import (
    GrantBody,
    create_grant,
    revoke_grant,
)
from platform_api.modules.projects.models import ProjectMemberRecord

setup = _feedback_setup


@pytest.mark.parametrize("member,enabled", [(True, True), (False, True), (True, False)])
def test_authoring_link_requires_enabled_project_membership(
    monkeypatch, member, enabled
):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from platform_api.modules.evaluation.router import capabilities

    project = str(uuid4())
    settings = SimpleNamespace(
        evaluation_workbench_enabled=enabled,
        evaluation_project_id=project,
        evaluation_assistant_model_route="not-configured",
        evaluation_web_url="http://127.0.0.1:9128/",
        evaluation_feedback_enabled=False,
        evaluation_synthetic_export_enabled=False,
        evaluation_inspection_enabled=False,
    )
    request = SimpleNamespace(
        headers={"x-project-id": project},
        app=SimpleNamespace(
            state=SimpleNamespace(settings=settings, db_session_factory=None)
        ),
    )
    actor = ActorContext(
        user_id=str(uuid4()),
        project_roles={project: ("project_editor",)} if member else {},
    )
    monkeypatch.setattr(
        "platform_api.core.db.session_scope",
        lambda _: nullcontext(SimpleNamespace(get=lambda *_: None)),
    )
    value = capabilities(request, actor)
    assert value["authoring_url"] == (
        "http://127.0.0.1:9128" if member and enabled else None
    )


def test_public_creation_cannot_forge_server_owned_session_materials():
    from platform_api.core.errors import BadRequestError
    from platform_api.modules.evaluation.workbench import reject_client_source_snapshots

    reject_client_source_snapshots({"source_materials": [], "material_submission": {}})
    for data in [
        {"source_materials": [{"thread_id": "forged"}]},
        {"material_submission": {"receipt": "forged"}},
    ]:
        with pytest.raises(BadRequestError):
            reject_client_source_snapshots(data)


@pytest.mark.parametrize(
    "purpose,flag",
    [
        ("evaluation_assistance", "evaluation_workbench_enabled"),
        ("regression", "evaluation_workbench_enabled"),
        ("quality_inspection", "evaluation_inspection_enabled"),
        ("synthetic", "evaluation_synthetic_export_enabled"),
    ],
)
def test_paused_feature_is_unavailable_not_revoked(monkeypatch, purpose, flag):
    from types import SimpleNamespace

    from platform_api.core.errors import ServiceUnavailableError
    from platform_api.modules.evaluation import router
    from platform_api.modules.evaluation.contracts import AuthorizationBatchBody

    settings = SimpleNamespace(
        evaluation_project_id=str(uuid4()),
        evaluation_workbench_enabled=True,
        evaluation_inspection_enabled=True,
        evaluation_synthetic_export_enabled=True,
        evaluation_assistant_model_route="route",
        evaluation_inspection_judge_route="route",
        evaluation_inspection_budget_version="v1",
        evaluation_source_token="test-only",
    )
    package = {
        "purpose": purpose,
        "model_route": "route",
        "judge_route": "route",
        "budget_policy_version": "v1",
    }
    if purpose in {"evaluation_assistance", "regression"}:
        package["source_kind"] = "work_item"
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(settings=settings, db_session_factory=None)
        )
    )
    monkeypatch.setattr(router.service, "authorized_package", lambda *args: package)
    identifier = uuid4()
    body = AuthorizationBatchBody(export_ids=[identifier])
    assert (
        router.source_authorizations(request, body)["authorizations"][str(identifier)]
        is True
    )
    setattr(settings, flag, False)
    with pytest.raises(ServiceUnavailableError):
        router.check_purpose(settings, package)
    with pytest.raises(ServiceUnavailableError):
        router.source_authorizations(request, body)
    setattr(settings, flag, True)
    if purpose != "synthetic":
        package["model_route"] = package["judge_route"] = "changed"
        assert (
            router.source_authorizations(request, body)["authorizations"][
                str(identifier)
            ]
            is False
        )

    def revoked(*args):
        raise ForbiddenError(code="revoked", message="revoked")

    monkeypatch.setattr(router.service, "authorized_package", revoked)
    assert (
        router.source_authorizations(request, body)["authorizations"][str(identifier)]
        is False
    )


def test_all_features_paused_preserves_token_authentication():
    from types import SimpleNamespace

    from platform_api.core.errors import ServiceUnavailableError
    from platform_api.modules.evaluation.router import source_access

    settings = SimpleNamespace(
        evaluation_source_token="test-only",
        evaluation_workbench_enabled=False,
        evaluation_inspection_enabled=False,
        evaluation_synthetic_export_enabled=False,
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings)), headers={}
    )
    with pytest.raises(ForbiddenError):
        source_access(request)
    request.headers["authorization"] = "Bearer test-only"
    with pytest.raises(ServiceUnavailableError):
        source_access(request)


def test_synthetic_boundary_accepts_chinese_punctuation_but_not_private_data():
    from platform_api.core.errors import BadRequestError
    from platform_api.modules.evaluation.privacy import require_synthetic

    require_synthetic("请验证31加24等于55，以及追问再减10；只输出数字。")
    for text in (
        "请发给someone@example.com",
        "password=real-secret",
        "联系13812345678",
    ):
        with pytest.raises(BadRequestError):
            require_synthetic(text)


@pytest.mark.parametrize(
    "role,operation,allowed",
    [
        ("project_admin", "grant", True),
        ("project_editor", "approve", True),
        ("project_executor", "approve", False),
        ("project_executor", "run", True),
        ("project_editor", "assign", False),
        ("project_editor", "grant", False),
    ],
)
def test_role_actions(role, operation, allowed):
    project = str(uuid4())
    actor = ActorContext(user_id=str(uuid4()), project_roles={project: (role,)})
    if allowed:
        require_action(actor, project, operation)
    else:
        with pytest.raises(ForbiddenError):
            require_action(actor, project, operation)


def test_platform_super_admin_can_execute_project_evaluation():
    # 超级管理员拥有绝对权限，可直接进行评测操作
    require_action(
        ActorContext(user_id=str(uuid4()), platform_roles=("platform_super_admin",)),
        str(uuid4()),
        "read",
    )


def test_command_content_audience_and_current_membership(setup):
    factory, actor, scope = setup
    body = {"reason": "synthetic"}
    token = issue_command(
        "test-only-secret", actor, scope[0], "approve", str(uuid4()), str(uuid4()), body
    )
    claims = verify_command("test-only-secret", token, body, factory)
    assert claims["sub"] == actor.user_id
    with pytest.raises(ForbiddenError):
        verify_command("test-only-secret", token, {"reason": "tampered"}, factory)
    with pytest.raises(ForbiddenError):
        verify_command("other-secret", token, body, factory)
    with session_scope(factory) as session:
        from sqlalchemy import select

        member = session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.user_id == UUID(actor.user_id)
            )
        )
        member.role = "executor"
    with pytest.raises(ForbiddenError):
        verify_command("test-only-secret", token, body, factory)


@pytest.mark.parametrize("operation", ["list", "summary"])
def test_project_commands_do_not_require_an_item(setup, operation):
    factory, actor, scope = setup
    token = issue_command(
        "test-only-secret", actor, scope[0], operation, None, str(uuid4()), {}
    )
    claims = verify_command("test-only-secret", token, {}, factory)
    assert claims["item_id"] is None


@pytest.mark.parametrize("data_class", ["synthetic", "business"])
def test_assistance_independent_scope_revocation_and_expiry(setup, data_class):
    factory, actor, scope = setup
    agent_id = uuid4()
    with session_scope(factory) as session:
        session.add(
            AgentRecord(
                id=agent_id,
                project_id=UUID(scope[0]),
                name="Workbench fixture",
                graph_id="dearflow_agent",
                created_by=UUID(actor.user_id),
                updated_by=UUID(actor.user_id),
            )
        )
    item = {
        "id": str(uuid4()),
        "project_id": scope[0],
        "agent_id": str(agent_id),
        "material_hash": "a" * 64,
        "data_class": data_class,
    }
    body = GrantBody(
        grant_id=uuid4(),
        purpose="evaluation_assistance",
        synthetic_attestation=data_class == "synthetic",
        material_consent=True,
    )
    saved = create_grant(factory, actor, scope[0], item, body, "managed-deepseek")
    assert (
        create_grant(factory, actor, scope[0], item, body, "managed-deepseek")[
            "grant_id"
        ]
        == saved["grant_id"]
    )
    package = authorized_package(factory, scope[0], body.grant_id)
    assert package["purpose"] == "evaluation_assistance"
    assert package["data_class"] == data_class
    assert "feedback" not in package and "thread_id" not in package
    revoke_grant(factory, actor, scope[0], body.grant_id)
    with pytest.raises(ForbiddenError) as revoked_exc:
        authorized_package(factory, scope[0], body.grant_id)
    assert revoked_exc.value.code == "evaluation_export_revoked"
    other = body.model_copy(update={"grant_id": uuid4(), "purpose": "regression"})
    create_grant(factory, actor, scope[0], item, other, "managed-deepseek")
    assert (
        authorized_package(factory, scope[0], other.grant_id)["purpose"] == "regression"
    )
    with session_scope(factory) as session:
        session.get(EvaluationExport, str(other.grant_id)).expires_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
    with pytest.raises(ForbiddenError) as expired_exc:
        authorized_package(factory, scope[0], other.grant_id)
    assert expired_exc.value.code == "evaluation_export_expired"

    # 验证永久长效授权 (expires_in_hours=0)
    permanent_body = body.model_copy(
        update={"grant_id": uuid4(), "expires_in_hours": 0}
    )
    perm_res = create_grant(
        factory, actor, scope[0], item, permanent_body, "managed-deepseek"
    )
    perm_expiry = datetime.fromisoformat(perm_res["expires_at"])
    assert perm_expiry > datetime.now(UTC) + timedelta(days=365 * 10)
    perm_pkg = authorized_package(factory, scope[0], permanent_body.grant_id)
    assert perm_pkg["export_id"] == str(permanent_body.grant_id)


def test_batch_authorization_locks_sources_before_all_grants(setup):
    from sqlalchemy import event

    from platform_api.modules.evaluation.service import lock_packages
    from platform_api.modules.evaluation.workbench_grants import check_assistant_thread

    factory, actor, scope = setup
    agent_id = uuid4()
    execution_id = str(uuid4())
    with session_scope(factory) as session:
        session.add(
            AgentRecord(
                id=agent_id,
                project_id=UUID(scope[0]),
                name="Lock ordering",
                graph_id="dearflow_agent",
                created_by=UUID(actor.user_id),
                updated_by=UUID(actor.user_id),
            )
        )
    item = {
        "id": str(uuid4()),
        "project_id": scope[0],
        "agent_id": str(agent_id),
        "material_hash": "a" * 64,
        "source_materials": [{"thread_id": scope[1]}],
    }
    identifiers = [str(uuid4()), str(uuid4())]
    for identifier, purpose in zip(
        identifiers, ("regression", "evaluation_assistance"), strict=True
    ):
        create_grant(
            factory,
            actor,
            scope[0],
            item,
            GrantBody(grant_id=identifier, purpose=purpose, synthetic_attestation=True),
            "managed-deepseek",
        )
        with session_scope(factory) as session:
            session.get(EvaluationExport, identifier).receipt = {
                "assistant_threads": [execution_id]
            }

    locks = []

    def observe(state):
        statement = state.statement
        if getattr(statement, "_for_update_arg", None) is not None:
            locks.append((str(statement), statement.compile().params))

    event.listen(factory, "do_orm_execute", observe)
    try:
        assert check_assistant_thread(factory, scope[0], execution_id)
    finally:
        event.remove(factory, "do_orm_execute", observe)
    assert "FROM thread_access" in locks[0][0]
    assert "ORDER BY thread_access.thread_id" in locks[0][0]
    assert "FROM evaluation_exports" in locks[1][0]
    assert "ORDER BY evaluation_exports.export_id" in locks[1][0]
    assert set(next(iter(locks[1][1].values()))) == set(identifiers)

    with session_scope(factory) as session:
        cached = session.get(EvaluationExport, identifiers[0])
        with session_scope(factory) as concurrent:
            concurrent.get(EvaluationExport, identifiers[0]).status = "revoked"
        assert cached.status == "ready"
        lock_packages(session, identifiers)
        assert cached.status == "revoked"
    with pytest.raises(ForbiddenError):
        check_assistant_thread(factory, scope[0], execution_id)


def test_commands_cannot_cross_connections_even_with_identical_signing_key(setup):
    factory, actor, scope = setup
    body = {"reason": "connection-bound"}
    token = issue_command(
        "test-only-secret",
        actor,
        scope[0],
        "read",
        str(uuid4()),
        str(uuid4()),
        body,
        connection_id="local-dev",
    )
    assert (
        verify_command(
            "test-only-secret", token, body, factory, connection_id="local-dev"
        )["connection_id"]
        == "local-dev"
    )
    with pytest.raises(ForbiddenError):
        verify_command("test-only-secret", token, body, factory, connection_id="server")


def test_conversion_link_keeps_its_source_connection():
    from platform_api.modules.evaluation.materials import authoring_url

    identifier = str(uuid4())
    assert authoring_url("https://evalflow.example", identifier, "server") == (
        f"https://evalflow.example/#/authoring/{identifier}?connection=server"
    )

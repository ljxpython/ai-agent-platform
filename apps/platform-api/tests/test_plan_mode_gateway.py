import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from platform_api.adapters.langgraph.sdk_client import (
    project_execution_error,
    redact_runtime_private_fields,
)
from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import BadRequestError, ConflictError, ForbiddenError
from platform_api.core.runtime_contract import (
    normalize_runtime_payload,
    validate_runtime_option_values,
)
from platform_api.modules.agents.domain.models import ModelResilienceSettings
from platform_api.modules.runtime_gateway.application.planning import (
    validate_plan_resumes,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
    _runtime_context_snapshot,
)


@pytest.fixture
def gateway(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'plans.db'}")
    create_core_tables(engine)
    upstream = SimpleNamespace(
        create_thread_run=AsyncMock(return_value={"run_id": "run-1"}),
        get_thread_state=AsyncMock(return_value={}),
        get_thread_run=AsyncMock(
            return_value={"run_id": "run-1", "status": "interrupted"}
        ),
        get_graph_capabilities=AsyncMock(return_value={"plan_mode": True}),
        update_thread=AsyncMock(),
        update_thread_state=AsyncMock(),
    )
    service = RuntimeGatewayService(
        session_factory=build_session_factory(engine), upstream=upstream
    )
    service._load_thread = AsyncMock(
        return_value={"metadata": {"graph_id": "reference_agent"}}
    )
    service._project_default_model_id = Mock(return_value=None)
    service._assert_runtime_options_allowed = Mock()
    service._assert_runtime_target_allowed = Mock()
    service._model_resilience_snapshot = Mock(
        return_value=ModelResilienceSettings.disabled()
    )
    actor = ActorContext(
        user_id="human", subject="human", project_roles={"project": ("project_admin",)}
    )
    yield service, upstream, actor
    engine.dispose()


def start_command(planning=True):
    return {
        "id": 1,
        "method": "run.start",
        "params": {
            "assistant_id": "reference_agent",
            "context": {"plan_mode": planning},
            "input": {"messages": [{"role": "user", "content": "plan"}]},
        },
    }


def review_state():
    request = {
        "version": 1,
        "type": "agent_plan_review",
        "plan_id": "plan",
        "revision": 1,
        "content_hash": "sha256:" + "a" * 64,
        "title": "Plan",
        "markdown": "Draft",
        "allowed_decisions": ["approve", "request_changes", "abandon"],
    }
    fields = {
        key: request[key]
        for key in ("version", "plan_id", "revision", "title", "markdown")
    }
    request["content_hash"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
    )
    return {
        "metadata": {"run_id": "run-1"},
        "interrupts": [{"id": "review-1", "value": request}],
    }


def response_command(decision="approve"):
    request = review_state()["interrupts"][0]["value"]
    answer = {
        "version": 1,
        "type": "agent_plan_response",
        "decision": decision,
        **{key: request[key] for key in ("plan_id", "revision", "content_hash")},
    }
    if decision == "request_changes":
        answer["feedback"] = "Add validation"
    return {
        "id": 2,
        "method": "input.respond",
        "params": {"resume": {"review-1": answer}},
    }


def test_unknown_ordinary_request_cannot_bypass_a_later_plan(gateway):
    service, upstream, actor = gateway
    upstream.create_thread_run.side_effect = TimeoutError()

    async def run():
        args = {
            "actor": actor,
            "project_id": "project",
            "thread_id": "thread",
            "payload": start_command(False),
            "idempotency_key": "old-unknown",
        }
        with pytest.raises(TimeoutError):
            await service.send_thread_command(**args)
        upstream.create_thread_run.side_effect = None
        upstream.get_thread_state.return_value = {
            "values": {
                "runtime_plan": {
                    "active": True,
                    "bound_execution_id": "another-execution",
                }
            }
        }
        with pytest.raises(ConflictError) as error:
            await service.send_thread_command(**args)
        assert error.value.code == "plan_execution_conflict"
        assert upstream.create_thread_run.await_count == 1

    asyncio.run(run())


def test_context_is_strict_and_private_fields_rejected():
    for value in (None, 0, 1, "true", [], {}):
        with pytest.raises(ValueError):
            validate_runtime_option_values({"plan_mode": value})
    with pytest.raises(ValueError):
        normalize_runtime_payload(
            payload={
                "context": {"plan_mode": True},
                "config": {"configurable": {"platform_runtime": {"plan_mode": False}}},
            },
            project_id="project",
        )
    for key in (
        "runtime_plan",
        "agent_plan",
        "plan_execution_id",
        "plan_bootstrap_required",
    ):
        with pytest.raises(ValueError):
            normalize_runtime_payload(
                payload={"input": {key: True}}, project_id="project"
            )


def test_plan_reply_matches_exact_snapshot_and_human():
    actor = ActorContext(user_id="human")
    for decision in ("approve", "request_changes", "abandon"):
        resumes = response_command(decision)["params"]["resume"]
        validate_plan_resumes(review_state(), resumes, actor)
        with pytest.raises(ForbiddenError):
            validate_plan_resumes(
                review_state(),
                resumes,
                ActorContext(subject="service", principal_type="service_account"),
            )
    bad = response_command()["params"]["resume"]
    bad["review-1"]["revision"] = 2
    with pytest.raises(ConflictError):
        validate_plan_resumes(review_state(), bad, actor)
    bad["review-1"]["revision"] = 1
    bad["review-1"]["active"] = False
    with pytest.raises(BadRequestError):
        validate_plan_resumes(review_state(), bad, actor)


def test_start_and_resume_keep_signed_identity_and_durable_idempotency(gateway):
    service, upstream, actor = gateway

    async def run():
        args = {"actor": actor, "project_id": "project", "thread_id": "thread"}
        await service.send_thread_command(
            **args, payload=start_command(), idempotency_key="start-1"
        )
        original = upstream.create_thread_run.call_args.args[1]
        execution = original["context"]["plan_execution_id"]
        assert original["context"]["plan_mode"] is True
        upstream.get_thread_state.return_value = review_state()
        upstream.create_thread_run.return_value = {"run_id": "run-2"}
        await service.send_thread_command(**args, payload=response_command())
        resumed = upstream.create_thread_run.call_args.args[1]
        assert resumed["context"]["plan_execution_id"] == execution
        assert resumed["context"] == original["context"]
        assert "approved" not in json.dumps(resumed["context"])
        await service.send_thread_command(**args, payload=response_command())
        assert upstream.create_thread_run.await_count == 2
        with pytest.raises(ConflictError):
            await service.send_thread_command(
                **args, payload=response_command("abandon")
            )
        malformed = response_command()
        malformed["params"]["resume"]["review-1"] = {"type": "agent_plan_response"}
        with pytest.raises(ConflictError):
            await service.send_thread_command(**args, payload=malformed)
        with pytest.raises(ConflictError):
            await service.send_thread_command(
                **args, payload=start_command(False), idempotency_key="start-2"
            )

    asyncio.run(run())


def test_plan_execution_error_projection_is_exact_and_safe():
    value = {
        "type": "RuntimeResolutionError",
        "message": "runtime.plan.tool_denied",
        "stack": "PRIVATE_CANARY",
    }
    result = project_execution_error(value)
    assert result["code"] == "runtime.plan.tool_denied"
    assert "PRIVATE_CANARY" not in json.dumps(result)
    value["message"] += ": PRIVATE_CANARY"
    assert project_execution_error(value)["code"] == "runtime_execution_failed"


def test_projection_keeps_user_content_and_hides_internal_identity():
    raw = {
        "version": 1,
        "active": True,
        "plan_id": "plan",
        "revision": 1,
        "title": "Plan",
        "markdown": "Draft",
        "content_hash": "sha256:" + "a" * 64,
        "bound_execution_id": "PRIVATE",
        "approved_by": None,
        "approved_at": None,
        "decision": None,
    }
    raw["content_hash"] = review_state()["interrupts"][0]["value"]["content_hash"]
    result = redact_runtime_private_fields(
        {
            "values": {"runtime_plan": raw},
            "context": {"plan_execution_id": "PRIVATE"},
            "messages": [{"content": {"runtime_plan": "ordinary user content"}}],
        }
    )
    assert result["values"]["agent_plan"]["status"] == "planning"
    assert result["messages"][0]["content"]["runtime_plan"] == "ordinary user content"
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize(
    "protocol,typed", [(False, False), (False, True), (True, True)]
)
@pytest.mark.parametrize("method", ["values", "updates", "checkpoints"])
def test_fragmented_plan_events_keep_public_snapshot_and_native_envelope(
    protocol, typed, method
):
    from platform_api.modules.runtime_gateway.presentation.http import (
        _redact_protocol_event_stream,
    )

    fields = review_state()["interrupts"][0]["value"]
    raw = {
        **{
            key: value
            for key, value in fields.items()
            if key not in {"type", "allowed_decisions"}
        },
        "active": True,
        "decision": None,
        "bound_execution_id": "PRIVATE_CANARY",
    }
    user = {"content": {"runtime_plan": "USER_TEXT"}}
    values = {"runtime_plan": raw, "messages": [user]}
    data = (
        {"tools": values}
        if method == "updates"
        else {"values": values}
        if method == "checkpoints"
        else values
    )
    payload = (
        {
            "method": method,
            "seq": 7,
            "params": {"namespace": ["agent:workflow"], "data": data},
        }
        if typed
        else data
    )
    frame = (
        f"event: {method}|child\nid: cursor-7\ndata: {json.dumps(payload)}\n\n".encode()
    )

    async def chunks():
        for part in (frame[:19], frame[19:71], frame[71:]):
            yield part

    async def run():
        result = b"".join(
            [
                part
                async for part in _redact_protocol_event_stream(
                    chunks(), protocol=protocol
                )
            ]
        )
        assert b'"agent_plan"' in result and b"PRIVATE_CANARY" not in result
        assert b"USER_TEXT" in result and b"id: cursor-7" in result
        if typed:
            decoded = json.loads(result.decode().split("data: ")[1])
            assert decoded["seq"] == 7
            assert decoded["params"]["namespace"] == ["agent:workflow"]

    asyncio.run(run())


def test_context_hash_includes_plan_fields():
    empty, _ = _runtime_context_snapshot({"params": {}})
    requested, _ = _runtime_context_snapshot(
        {"params": {"context": {"plan_mode": True}}}
    )
    bound, snapshot = _runtime_context_snapshot(
        {"params": {"context": {"plan_mode": True, "plan_execution_id": "id"}}}
    )
    assert len({empty, requested, bound}) == 3
    assert snapshot["plan_execution_id"] == "id"


def test_plan_start_rejects_unsupported_graph_and_capability(gateway):
    service, upstream, actor = gateway

    async def run():
        unsupported = start_command()
        unsupported["params"]["assistant_id"] = "unregistered_agent"
        with pytest.raises(BadRequestError) as unsupported_error:
            await service.send_thread_command(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload=unsupported,
                idempotency_key="unsupported-graph",
            )
        assert unsupported_error.value.code == "plan_mode_unsupported"
        assert upstream.create_thread_run.await_count == 0

        upstream.get_graph_capabilities.return_value = {"plan_mode": False}
        with pytest.raises(BadRequestError) as capability_error:
            await service.send_thread_command(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload=start_command(),
                idempotency_key="unsupported-capability",
            )
        assert capability_error.value.code == "plan_mode_unsupported"
        assert upstream.create_thread_run.await_count == 0

    asyncio.run(run())


def test_active_plan_blocks_state_and_metadata_client_mutation(gateway):
    service, upstream, actor = gateway

    async def run():
        upstream.get_thread_state.return_value = review_state()
        with pytest.raises(ConflictError) as pending_error:
            await service.update_thread_state(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload={"values": {"ordinary": "value"}},
            )
        assert pending_error.value.code == "plan_review_pending"
        upstream.update_thread_state = AsyncMock()
        with pytest.raises(BadRequestError, match="Runtime private state"):
            await service.update_thread_state(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload={"values": {"runtime_plan": {"active": False}}},
            )
        with pytest.raises(BadRequestError, match="Runtime private state"):
            await service.update_thread(
                actor=actor,
                project_id="project",
                thread_id="thread",
                metadata_updates={"plan_bootstrap_required": False},
            )
        upstream.update_thread_state.assert_not_awaited()

    asyncio.run(run())


@pytest.mark.parametrize("bootstrap", [False, True])
def test_planning_blocks_state_edits_before_review(gateway, bootstrap):
    service, upstream, actor = gateway
    if bootstrap:
        service._load_thread.return_value["metadata"]["plan_bootstrap_required"] = True
    else:
        upstream.get_thread_state.return_value = {
            "values": {"runtime_plan": {"active": True}}
        }

    async def run():
        with pytest.raises(ConflictError) as error:
            await service.update_thread_state(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload={
                    "values": {"messages": []},
                    "as_node": "tools",
                    "checkpoint_id": "old",
                },
            )
        assert error.value.code == "plan_state_update_denied"
        upstream.update_thread_state.assert_not_awaited()

    asyncio.run(run())


@pytest.mark.parametrize("source", ["active", "bootstrap", "history"])
def test_planning_cannot_be_bypassed_by_changing_graph(gateway, source):
    service, upstream, actor = gateway
    if source == "bootstrap":
        service._load_thread.return_value["metadata"]["plan_bootstrap_required"] = True
    elif source == "active":
        upstream.get_thread_state.return_value = {
            "values": {"runtime_plan": {"active": True}}
        }
    else:
        upstream.get_thread_state.side_effect = [
            {},
            {"values": {"runtime_plan": {"active": False}}},
        ]
    command = start_command(False)
    command["params"]["assistant_id"] = "unregistered_agent"
    if source == "history":
        command["params"]["checkpoint_id"] = "old"

    async def run():
        with pytest.raises(BadRequestError) as error:
            await service.send_thread_command(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload=command,
                idempotency_key="change-graph",
            )
        assert error.value.code == "plan_mode_unsupported"
        upstream.create_thread_run.assert_not_awaited()
        upstream.update_thread.assert_not_awaited()

    asyncio.run(run())


@pytest.mark.parametrize("private_plan", [{"active": False}, [], 0, "corrupted"])
def test_invalid_persisted_plan_does_not_allow_graph_or_state_bypass(
    gateway, private_plan
):
    service, upstream, actor = gateway
    upstream.get_thread_state.return_value = {"values": {"runtime_plan": private_plan}}
    command = start_command(False)
    command["params"]["assistant_id"] = "unregistered_agent"

    async def run():
        with pytest.raises(BadRequestError) as error:
            await service.send_thread_command(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload=command,
                idempotency_key="invalid-state",
            )
        assert error.value.code == "plan_mode_unsupported"
        with pytest.raises(ConflictError) as error:
            await service.update_thread_state(
                actor=actor,
                project_id="project",
                thread_id="thread",
                payload={"values": {"messages": []}},
            )
        assert error.value.code == "plan_state_update_denied"
        upstream.create_thread_run.assert_not_awaited()
        upstream.update_thread_state.assert_not_awaited()

    asyncio.run(run())


def test_bootstrap_is_preserved_on_unknown_and_cleared_after_persisted_plan(gateway):
    service, upstream, actor = gateway
    service._load_thread.return_value["metadata"]["plan_bootstrap_required"] = True
    upstream.create_thread_run.side_effect = TimeoutError()

    async def run():
        args = {"actor": actor, "project_id": "project", "thread_id": "thread"}
        with pytest.raises(TimeoutError):
            await service.send_thread_command(
                **args, payload=start_command(False), idempotency_key="unknown"
            )
        upstream.update_thread.assert_not_awaited()
        assert upstream.create_thread_run.call_args.args[1]["context"]["plan_mode"]
        upstream.create_thread_run.side_effect = None
        await service.send_thread_command(
            **args, payload=start_command(False), idempotency_key="unknown"
        )
        upstream.update_thread.assert_not_awaited()
        snapshot = review_state()["interrupts"][0]["value"]
        upstream.get_thread_state.return_value = {
            "values": {"runtime_plan": {**snapshot, "active": True}}
        }
        await service.send_thread_command(
            **args, payload=start_command(False), idempotency_key="persisted"
        )
        upstream.update_thread.assert_awaited_once_with(
            "thread", {"metadata": {"plan_bootstrap_required": False}}
        )
        assert upstream.create_thread_run.call_args.args[1]["context"]["plan_mode"]

    asyncio.run(run())


def test_scheduled_run_cannot_inherit_unapproved_plan(gateway):
    service, upstream, actor = gateway
    upstream.get_thread_state.return_value = {
        "values": {"runtime_plan": {"active": True}}
    }

    async def run():
        with pytest.raises(BadRequestError) as error:
            await service.launch_runtime_run(
                actor=actor,
                project_id="project",
                thread_id="thread",
                command=start_command(False),
                upstream_payload=start_command(False)["params"],
                idempotency_key="cron",
                scheduled_config={},
            )
        assert error.value.code == "plan_mode_scheduled_forbidden"
        upstream.create_thread_run.assert_not_awaited()

    asyncio.run(run())


@pytest.mark.parametrize("requested", [False, True])
def test_configurable_plan_option_is_canonicalized_before_server_enforcement(
    gateway, requested
):
    service, upstream, actor = gateway
    command = start_command(False)
    command["params"].pop("context")
    command["params"]["config"] = {
        "configurable": {"platform_runtime": {"plan_mode": requested}}
    }
    if not requested:
        upstream.get_thread_state.return_value = {
            "values": {"runtime_plan": {"active": True}}
        }

    async def run():
        await service.send_thread_command(
            actor=actor,
            project_id="project",
            thread_id="thread",
            payload=command,
            idempotency_key="configurable",
        )
        sent = upstream.create_thread_run.call_args.args[1]
        assert sent["context"]["plan_mode"] is True
        assert "plan_mode" not in sent["config"].get("configurable", {}).get(
            "platform_runtime", {}
        )

    asyncio.run(run())

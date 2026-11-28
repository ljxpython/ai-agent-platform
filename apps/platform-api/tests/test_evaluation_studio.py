"""Tests for native evaluation studio control-plane API, readiness, and multi-graph targets."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from platform_api.core.context.models import ActorContext
from platform_api.core.db.base import Base
from platform_api.core.db.init_db import import_core_models
from platform_api.core.errors import register_exception_handlers
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.evaluation import studio_router, targets
from platform_api.modules.evaluation.models import EvalRunCase
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_runtime_gateway_service,
)


def _make_app():
    import_core_models()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    project_id = str(uuid4())
    target_project_uuid = uuid4()
    target_project_id = str(target_project_uuid)
    user_uuid = uuid4()
    user_id = str(user_uuid)
    agent_id = uuid4()
    model_id = uuid4()
    judge_model_id = uuid4()

    with factory() as session:
        session.add(
            AgentRecord(
                id=agent_id,
                project_id=target_project_uuid,
                name="Ref Agent",
                graph_id="reference_agent",
                status="active",
                context={},
                created_by=user_uuid,
                updated_by=user_uuid,
            )
        )
        session.add(
            RuntimeCatalogModelRecord(
                id=model_id,
                display_name="DeepSeek V4 Flash",
                provider="deepseek",
                base_url="https://api.example.com/v1",
                protocol="openai-compatible",
                model_name="deepseek-chat",
                api_key_ciphertext="enc",
                enabled=True,
                scope_type="platform",
            )
        )
        session.add(
            RuntimeCatalogModelRecord(
                id=judge_model_id,
                display_name="Judge DeepSeek V4",
                provider="deepseek",
                base_url="https://api.example.com/v1",
                protocol="openai-compatible",
                model_name="deepseek-chat",
                api_key_ciphertext="enc",
                enabled=True,
                scope_type="platform",
            )
        )
        session.commit()

    app = FastAPI()
    register_exception_handlers(app)

    @app.middleware("http")
    async def _attach_state(request, call_next):
        request.state.platform_context = NS(
            request_id="test-req",
            trace_id="test-trace",
            request=NS(request_id="test-req", trace_id="test-trace"),
            tenant=NS(tenant_id="__default"),
            project=NS(
                project_id=request.headers.get("x-project-id") or target_project_id
            ),
        )
        return await call_next(request)

    app.state.db_session_factory = factory
    app.state.settings = NS(
        evaluation_project_id="",
        runtime_delegation_secret="test-secret-123",
        model_config_master_key="",
    )
    actor = ActorContext(
        user_id=user_id,
        project_roles={
            project_id: ("project_admin",),
            target_project_id: ("project_admin",),
        },
    )
    app.dependency_overrides[get_actor_context] = lambda: actor

    fake_gateway = NS(
        _authorize=lambda **kwargs: None,
        _require_session_factory=lambda: factory,
        _assert_runtime_target_allowed=lambda **kwargs: None,
        _runtime_id="default",
        evaluation_capabilities=AsyncMock(
            return_value={
                "schema": "evaluation-runtime/v1",
                "available": True,
                "manifest": {"package_sha256": "pkg-sha"},
                "tools": [],
                "graph_features": {
                    "workspace_files": False,
                    "clarification": False,
                    "plan_mode": True,
                },
            }
        ),
    )
    app.dependency_overrides[get_runtime_gateway_service] = lambda: fake_gateway
    app.include_router(studio_router.router)
    return (
        app,
        factory,
        project_id,
        target_project_id,
        str(agent_id),
        str(model_id),
        str(judge_model_id),
    )


def test_studio_lifecycle_readiness_non_sandbox_warning_and_internal_bridges(
    monkeypatch,
):
    (
        app,
        factory,
        project_id,
        target_project_id,
        agent_id,
        model_id,
        judge_model_id,
    ) = _make_app()
    monkeypatch.setattr(
        targets,
        "configured_target",
        lambda gateway, actor, pid, spec: (
            {
                "id": str(spec.agent_id),
                "project_id": pid,
                "name": "Ref Agent",
                "graph_id": "reference_agent",
                "status": "active",
                "context": {},
            },
            {"model": {"model_id": str(spec.model_id)}},
        ),
    )
    client = TestClient(app)
    headers = {"x-project-id": project_id}

    # 1. Create suite + upsert case requiring workspace_files + publish
    suite_res = client.post(
        "/api/evaluation/studio/suites",
        headers=headers,
        json={
            "name": "核心多图评测集",
            "suite_type": "regression",
            "default_graph_id": "reference_agent",
        },
    )
    assert suite_res.status_code == 201, suite_res.text
    suite_id = suite_res.json()["id"]

    case_res = client.put(
        f"/api/evaluation/studio/suites/{suite_id}/cases",
        headers=headers,
        json={
            "case_key": "case_file_check",
            "split": "dev",
            "turns": [{"role": "user", "content": "check file"}],
            "expectations": {"artifacts": [{"path": "/workspace/work/out.txt"}]},
            "metrics": [{"name": "artifact_correct"}],
        },
    )
    assert case_res.status_code == 200
    assert "workspace_files" in case_res.json()["required_capabilities"]

    pub_res = client.post(
        f"/api/evaluation/studio/suites/{suite_id}/publish",
        headers=headers,
        json={"note": "v1"},
    )
    assert pub_res.status_code == 201
    version_id = pub_res.json()["id"]

    # 2. Readiness detects non-sandbox warning and graph incompatibility
    ready_res = client.post(
        "/api/evaluation/studio/readiness",
        headers=headers,
        json={
            "suite_id": suite_id,
            "target_project_id": target_project_id,
            "agent_id": agent_id,
            "model_id": model_id,
            "judge_model_id": judge_model_id,
        },
    )
    assert ready_res.status_code == 200
    ready_data = ready_res.json()
    assert ready_data["is_sandbox"] is False
    assert ready_data["sandbox_warning"] is not None
    assert ready_data["ready"] is False
    assert ready_data["incompatible_cases"][0]["case_key"] == "case_file_check"

    # 3. Non-sandbox without confirm is rejected; with confirm + skip_incompatible succeeds
    bad_run = client.post(
        "/api/evaluation/studio/runs",
        headers=headers,
        json={
            "suite_id": suite_id,
            "version_id": version_id,
            "target_project_id": target_project_id,
            "agent_id": agent_id,
            "model_id": model_id,
            "judge_model_id": judge_model_id,
            "concurrency": 3,
        },
    )
    assert bad_run.status_code == 400

    # Concurrency > 5 rejected by Pydantic
    over_conc = client.post(
        "/api/evaluation/studio/runs",
        headers=headers,
        json={
            "suite_id": suite_id,
            "version_id": version_id,
            "target_project_id": target_project_id,
            "agent_id": agent_id,
            "model_id": model_id,
            "concurrency": 6,
            "confirm_non_sandbox": True,
            "skip_incompatible": True,
        },
    )
    assert over_conc.status_code == 422

    ok_run = client.post(
        "/api/evaluation/studio/runs",
        headers=headers,
        json={
            "suite_id": suite_id,
            "version_id": version_id,
            "target_project_id": target_project_id,
            "agent_id": agent_id,
            "model_id": model_id,
            "judge_model_id": judge_model_id,
            "concurrency": 4,
            "confirm_non_sandbox": True,
            "skip_incompatible": True,
        },
    )
    assert ok_run.status_code == 201
    run_id = ok_run.json()["id"]

    # 4. Run control (pause -> resume) & L3 human review
    paused = client.post(
        f"/api/evaluation/studio/runs/{run_id}/control",
        headers=headers,
        json={"action": "pause"},
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post(
        f"/api/evaluation/studio/runs/{run_id}/control",
        headers=headers,
        json={"action": "resume"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "queued"

    with factory() as session:
        rc = session.query(EvalRunCase).filter_by(run_id=run_id).first()
        rc_id = rc.id
    review = client.post(
        f"/api/evaluation/studio/run-cases/{rc_id}/review",
        headers=headers,
        json={"human_verdict": "pass", "reason": "人工复核通过"},
    )
    assert review.status_code == 201

    # 5. Internal HMAC diagnosis-evidence slice
    body_bytes = json.dumps(
        {"project_id": project_id, "run_id": run_id, "ref": "overview", "offset": 0}
    ).encode()
    stamp = str(int(time.time()))
    sig = hmac.new(
        b"test-secret-123",
        b"\n".join([b"diagnosis-evidence", stamp.encode(), body_bytes]),
        hashlib.sha256,
    ).hexdigest()
    diag_res = client.post(
        "/api/evaluation/internal/diagnosis-evidence",
        content=body_bytes,
        headers={
            "content-type": "application/json",
            "x-eval-time": stamp,
            "x-eval-signature": sig,
        },
    )
    assert diag_res.status_code == 200
    assert diag_res.json()["reference"] == "overview"

    # 6. Import cases & verify sample_cases preview in list_suites & soft archive
    imp_res = client.post(
        f"/api/evaluation/studio/suites/{suite_id}/cases/import",
        headers=headers,
        json={
            "items": [
                {
                    "case_key": "imported_001",
                    "split": "holdout",
                    "turns": [{"role": "user", "content": "请总结本次变更"}],
                    "expectations": {"expected_answer": "变更摘要"},
                    "metrics": ["completion"],
                }
            ]
        },
    )
    assert imp_res.status_code == 200
    assert imp_res.json()["imported"] == 1

    listed = client.get("/api/evaluation/studio/suites", headers=headers)
    assert listed.status_code == 200
    suite_entry = next(s for s in listed.json()["items"] if s["id"] == suite_id)
    assert len(suite_entry["sample_cases"]) >= 1
    assert suite_entry["runs_count"] >= 1

    # 7. Enriched compare_runs includes question, ground truth, and both sides' payload
    with factory() as session:
        rc = session.query(EvalRunCase).filter_by(run_id=run_id).first()
        rc.status = "completed"
        rc.rule_passed = True
        rc.overall_score = 0.85
        rc.ttft_ms = 420
        rc.duration_ms = 1200
        rc.token_usage_json = {"total_tokens": 120}
        rc.results_json = {
            "final_answer": "模型输出文本",
            "metrics": [
                {
                    "name": "artifact_correct",
                    "layer": "L1",
                    "passed": True,
                    "score": 0.85,
                }
            ],
            "timing_breakdown": {"ttft_ms": 420, "generation_ms": 780},
        }
        session.commit()
    cmp_res = client.get(
        f"/api/evaluation/studio/runs/compare?baseline_id={run_id}&candidate_id={run_id}",
        headers=headers,
    )
    assert cmp_res.status_code == 200
    cmp_item = cmp_res.json()["unchanged"][0]
    assert cmp_item["question"] == "check file"
    assert cmp_item["baseline"]["final_answer"] == "模型输出文本"
    assert cmp_item["candidate"]["token_usage"]["total_tokens"] == 120

    del_res = client.delete(
        f"/api/evaluation/studio/suites/{suite_id}", headers=headers
    )
    assert del_res.status_code == 200
    assert del_res.json()["archived"] is True

    # 8. Internal HMAC Task 6.1 bridges: thread-setup, thread-evidence, cross-project-probe
    async def _body_bytes():
        yield b"csv,val\n1,10\n"

    mock_gw = NS(
        create_thread=AsyncMock(return_value={"thread_id": "th-eval-1"}),
        upload_thread_file=AsyncMock(
            return_value={"path": "/workspace/uploads/in.csv"}
        ),
        get_thread_state=AsyncMock(
            side_effect=lambda **kw: (
                (_ for _ in ()).throw(
                    studio_router.ForbiddenError(code="denied", message="forbidden")
                )
                if kw.get("project_id") != target_project_id
                else {
                    "values": {"messages": [{"role": "assistant", "content": "done"}]}
                }
            )
        ),
        list_thread_runs=AsyncMock(
            return_value=[{"run_id": "r-sub-1", "status": "success"}]
        ),
        thread_workspace=AsyncMock(
            side_effect=lambda **kw: (
                NS(body=_body_bytes())
                if kw.get("resource") == "workspace/content"
                else {"items": [{"path": "/workspace/work/out.csv", "is_dir": False}]}
            )
        ),
        get_thread_run_diagnostics=AsyncMock(
            return_value={
                "observations": [{"event": "runtime.loop.transition", "signals": 0}]
            }
        ),
        get_thread_execution_evidence=AsyncMock(
            return_value={"run_id": "r-sub-1", "verified": True}
        ),
        send_thread_command=AsyncMock(
            return_value={
                "type": "success",
                "result": {"run_id": "r-resume-1", "thread_id": "th-eval-1"},
            }
        ),
        join_thread_run_stream=AsyncMock(
            return_value=iter(
                [
                    b'event: values\ndata: {"messages":[{"role":"assistant","content":"resumed ok"}]}\n\n'
                ]
            )
        ),
        evaluation_capabilities=AsyncMock(
            return_value={
                "schema": "evaluation-runtime/v1",
                "available": True,
                "manifest": {"package_sha256": "pkg-sha"},
                "tools": ["read_file", "write_file"],
                "graph_features": {"workspace_files": True},
            }
        ),
    )
    monkeypatch.setattr(
        studio_router, "build_runtime_gateway_service", lambda req, act, pid: mock_gw
    )
    monkeypatch.setattr(
        studio_router,
        "load_user_actor",
        lambda **kw: ActorContext(
            user_id=str(kw.get("user_id") or "u1"),
            project_roles={target_project_id: ("project_admin",)},
        ),
    )

    def _signed_post(purpose: str, data: dict):
        raw_b = json.dumps(data).encode()
        st = str(int(time.time()))
        sg = hmac.new(
            b"test-secret-123",
            b"\n".join([purpose.encode(), st.encode(), raw_b]),
            hashlib.sha256,
        ).hexdigest()
        return client.post(
            f"/api/evaluation/internal/{purpose}",
            content=raw_b,
            headers={
                "content-type": "application/json",
                "x-eval-time": st,
                "x-eval-signature": sg,
            },
        )

    setup_res = _signed_post(
        "thread-setup", {"run_id": run_id, "fixtures": {"in.csv": "a,b\n1,2\n"}}
    )
    assert setup_res.status_code == 200
    assert setup_res.json()["thread_id"] == "th-eval-1"
    assert setup_res.json()["fixture_paths"]["in.csv"] == "/workspace/uploads/in.csv"

    ev_res = _signed_post(
        "thread-evidence",
        {"run_id": run_id, "thread_id": "th-eval-1", "run_ids": ["r-sub-1"]},
    )
    assert ev_res.status_code == 200
    assert "/workspace/work/out.csv" in ev_res.json()["artifacts"]
    assert (
        ev_res.json()["diagnostics"][0]["observations"][0]["event"]
        == "runtime.loop.transition"
    )

    probe_res = _signed_post(
        "cross-project-probe", {"run_id": run_id, "thread_id": "th-eval-1"}
    )
    assert probe_res.status_code == 200
    assert probe_res.json()["denied"] is True

    async def _empty_stream(*_args, **_kwargs):
        yield b'event: values\ndata: {"messages":[{"role":"assistant","content":"resumed ok"}]}\n\n'

    mock_gw.join_thread_run_stream = AsyncMock(side_effect=_empty_stream)
    resume_res = _signed_post(
        "execute-turn",
        {
            "run_id": run_id,
            "thread_id": "th-eval-1",
            "command": {"resume": {"int-1": {"decisions": [{"type": "approve"}]}}},
        },
    )
    assert resume_res.status_code == 200
    assert mock_gw.send_thread_command.await_count == 1
    assert mock_gw.join_thread_run_stream.await_count == 1

    # Copilot authoring bridges: suites, capabilities, strong validation, graded save, control run ownership
    cop_suite_res = client.post(
        "/api/evaluation/studio/suites",
        headers=headers,
        json={
            "name": "Copilot 出题测试集",
            "suite_type": "curated",
            "default_graph_id": "dearflow_agent",
        },
    )
    assert cop_suite_res.status_code == 201
    cop_suite_id = cop_suite_res.json()["id"]

    suites_res = _signed_post("copilot-suites", {"project_id": project_id})
    assert suites_res.status_code == 200
    assert any(s["id"] == cop_suite_id for s in suites_res.json()["items"])

    caps_res = _signed_post("copilot-capabilities", {"project_id": project_id})
    assert caps_res.status_code == 200
    assert "read_file" in caps_res.json()["graphs"]["dearflow_agent"]["tools"]

    bad_case_res = _signed_post(
        "copilot-save-cases",
        {
            "project_id": project_id,
            "suite_id": cop_suite_id,
            "mode": "create_only",
            "items": [
                {
                    "case_key": "COP-BAD-01",
                    "turns": [{"role": "user", "content": "计算 1+1"}],
                    "expectations": {
                        "tool_constraints": {"required": ["magic_unknown_tool"]}
                    },
                    "metrics": ["completion", "Faithfulness"],
                }
            ],
        },
    )
    assert bad_case_res.status_code == 400
    assert (
        "unknown_tools_for_dearflow_agent:magic_unknown_tool"
        in bad_case_res.json()["error"]["message"]
    )
    assert (
        "non_rag_case_with_rag_metrics:Faithfulness"
        in bad_case_res.json()["error"]["message"]
    )

    create_res = _signed_post(
        "copilot-save-cases",
        {
            "project_id": project_id,
            "suite_id": cop_suite_id,
            "mode": "create_only",
            "items": [
                {
                    "case_key": "COP-NEW-01",
                    "schema_version": 3,
                    "split": "dev",
                    "tags": ["smoke"],
                    "description": "copilot normalize check",
                    "fixture": {"sales.csv": "id,amt\n1,100\n"},
                    "expected_artifacts": [
                        {
                            "path": "/workspace/work/summary.txt",
                            "kind": "contains",
                            "expected": "100",
                        }
                    ],
                    "tool_constraints": {
                        "required": ["read_file"],
                        "protected_files": ["/workspace/work/policy_lock.txt"],
                    },
                    "turns": [
                        {
                            "role": "user",
                            "content": "读取 {{sales.csv}} 并输出 summary.txt",
                        }
                    ],
                    "simulation": {
                        "goal": "读取文件并输出摘要",
                        "user_mode": "ambiguous_changer",
                        "max_turns": 6,
                    },
                    "metrics": [
                        "completion",
                        "protected_unchanged",
                        "artifact_correct",
                        "ConversationalGEval",
                    ],
                }
            ],
        },
    )
    assert create_res.status_code == 200
    assert create_res.json()["created"] == ["COP-NEW-01"]
    saved_item = create_res.json()["items"][0]
    assert saved_item["schema_version"] == "3"
    assert saved_item["metadata"]["tags"] == ["smoke"]
    assert (
        saved_item["expectations"]["artifacts"][0]["path"]
        == "/workspace/work/summary.txt"
    )
    assert saved_item["expectations"]["tool_constraints"]["required"] == ["read_file"]
    assert "policy_lock.txt" in saved_item["turns"][0]["fixture"]

    overwrite_blocked = _signed_post(
        "copilot-save-cases",
        {
            "project_id": project_id,
            "suite_id": cop_suite_id,
            "mode": "create_only",
            "items": [
                {
                    "case_key": "COP-NEW-01",
                    "turns": [{"role": "user", "content": "updated"}],
                    "metrics": ["completion"],
                }
            ],
        },
    )
    assert overwrite_blocked.status_code == 409

    upsert_ok = _signed_post(
        "copilot-save-cases",
        {
            "project_id": project_id,
            "suite_id": cop_suite_id,
            "mode": "upsert",
            "items": [
                {
                    "case_key": "COP-NEW-01",
                    "turns": [{"role": "user", "content": "updated content"}],
                    "metrics": ["completion", "StepEfficiency"],
                }
            ],
        },
    )
    assert upsert_ok.status_code == 200
    assert upsert_ok.json()["updated"] == ["COP-NEW-01"]

    status_res = _signed_post(
        "copilot-run-status", {"project_id": project_id, "run_id": run_id}
    )
    assert status_res.status_code == 200
    assert status_res.json()["run"]["id"] == run_id

    cancel_ext_denied = _signed_post(
        "copilot-control-run",
        {
            "project_id": project_id,
            "run_id": run_id,
            "action": "cancel",
            "copilot_thread_id": "th-copilot-9",
            "require_own": True,
        },
    )
    assert cancel_ext_denied.status_code == 409

    cancel_ok = _signed_post(
        "copilot-control-run",
        {
            "project_id": project_id,
            "run_id": run_id,
            "action": "cancel",
            "require_own": False,
        },
    )
    assert cancel_ok.status_code == 200
    assert cancel_ok.json()["status"] == "cancelled"

    trial_res = _signed_post(
        "copilot-trial-run",
        {
            "project_id": project_id,
            "actor_id": "u1",
            "suite_id": cop_suite_id,
            "case_keys": ["COP-NEW-01"],
            "target_project_id": target_project_id,
            "agent_id": agent_id,
            "model_id": model_id,
            "judge_model_id": judge_model_id,
            "copilot_thread_id": "th-copilot-trial",
        },
    )
    assert trial_res.status_code == 200, trial_res.text
    assert trial_res.json()["mode"] == "regression"
    trial_run_id = trial_res.json()["id"]
    own_cancel = _signed_post(
        "copilot-control-run",
        {
            "project_id": project_id,
            "run_id": trial_run_id,
            "action": "cancel",
            "copilot_thread_id": "th-copilot-trial",
            "require_own": True,
        },
    )
    assert own_cancel.status_code == 200
    assert own_cancel.json()["status"] == "cancelled"

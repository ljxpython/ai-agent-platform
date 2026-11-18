import asyncio
from types import SimpleNamespace
from uuid import uuid4

from platform_api.modules.evaluation.materials import snapshot


def test_snapshot_reconstructs_original_messages_without_final_workspace():
    first = {"id": "u1", "type": "human", "content": "31加24，只回答数字"}
    answer = {"id": "a1", "type": "ai", "content": "55"}
    second = {"id": "u2", "type": "human", "content": "把24改成14"}
    final = {"id": "a2", "type": "ai", "content": "45"}

    class Gateway:
        async def get_thread(self, **kwargs):
            return {"metadata": {"agent_id": str(uuid4()), "title": "合成两轮"}}

        async def get_thread_state(self, **kwargs):
            return {
                "checkpoint": {"checkpoint_id": "last"},
                "values": {"messages": [second, final]},
            }

        async def get_thread_history(self, **kwargs):
            assert kwargs["payload"]["before"] == {"checkpoint_id": "last"}
            return [
                {"values": {"messages": [second, final]}},
                {"values": {"messages": [first, answer, second]}},
                {"values": {"messages": [first]}},
            ]

        async def list_thread_runs(self, **kwargs):
            return [
                {"run_id": "r1", "status": "success"},
                {"run_id": "r2", "status": "success"},
            ]

    value = asyncio.run(
        snapshot(Gateway(), SimpleNamespace(), str(uuid4()), str(uuid4()))
    )
    assert [m["id"] for m in value["messages"]] == ["u1", "a1", "u2", "a2"]
    assert value["history_complete"] and value["runs_complete"]
    assert value["environment"]["initial_files"] == {}
    assert value["environment"]["status"] == "initial_state_unavailable"
    assert value["missing"] == []


def test_empty_history_is_explicitly_incomplete():
    class Gateway:
        async def get_thread(self, **kwargs):
            return {"metadata": {"agent_id": str(uuid4())}}

        async def get_thread_state(self, **kwargs):
            return {"values": {"messages": [{"content": "压缩摘要"}]}}

        async def get_thread_history(self, **kwargs):
            return []

        async def list_thread_runs(self, **kwargs):
            return []

    value = asyncio.run(snapshot(Gateway(), None, str(uuid4()), str(uuid4())))
    assert not value["history_complete"]
    assert value["missing"]


def test_later_snapshot_cannot_be_misrepresented_as_session_initial_state():
    class Gateway:
        async def get_thread(self, **kwargs):
            return {"metadata": {"agent_id": str(uuid4())}}

        async def get_thread_state(self, **kwargs):
            return {
                "checkpoint": {"checkpoint_id": "frozen"},
                "values": {"messages": []},
            }

        async def get_thread_history(self, **kwargs):
            return []

        async def list_thread_runs(self, **kwargs):
            return [
                {"run_id": "first", "created_at": "2026-01-01T00:00:00+00:00"},
                {"run_id": "second", "created_at": "2026-01-02T00:00:00+00:00"},
            ]

        async def get_thread_execution_evidence(self, **kwargs):
            if kwargs["run_id"] == "first":
                raise ValueError("missing")
            return {
                "manifest": {
                    "environment": {"initial_files": {"later.txt": "not original"}}
                }
            }

    value = asyncio.run(snapshot(Gateway(), None, str(uuid4()), str(uuid4())))
    assert value["environment"]["status"] == "initial_state_unavailable"
    assert value["environment"]["initial_files"] == {}
    assert len(value["environment"]["run_snapshots"]) == 1


def test_session_filter_uses_authorized_page_and_exposes_pagination(monkeypatch):
    from platform_api.modules.evaluation import materials as module
    from platform_api.modules.evaluation.materials import SessionQuery

    agent, project = str(uuid4()), str(uuid4())
    seen = []

    class Gateway:
        async def search_threads(self, **kwargs):
            seen.append(kwargs)
            return [
                {
                    "thread_id": str(i),
                    "created_at": "2026-11-15T02:00:00Z",
                    "status": "idle",
                    "metadata": {"title": "合成"},
                }
                for i in range(100)
            ]

    monkeypatch.setattr(module, "require_action", lambda *args: None)
    monkeypatch.setattr(module, "_require_project_id", lambda _: project)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(db_session_factory=None))
    )
    result = asyncio.run(
        module.list_material_sessions(
            request,
            SessionQuery(agent_id=agent),
            SimpleNamespace(user_id="actor"),
            Gateway(),
        )
    )
    assert len(result["items"]) == 100
    assert all("feedback" not in row for row in result["items"])
    assert result["next_offset"] == 100 and result["scanned"] == 100
    assert seen[0]["project_id"] == project and seen[0]["payload"]["metadata"] == {
        "agent_id": agent
    }


def test_filter_rejects_inverted_or_unzoned_dates():
    import pytest

    from platform_api.modules.evaluation.materials import SessionQuery

    with pytest.raises(ValueError):
        SessionQuery(
            agent_id=uuid4(), since="2026-11-16T00:00:00Z", until="2026-11-15T00:00:00Z"
        )
    with pytest.raises(ValueError):
        SessionQuery(agent_id=uuid4(), since="2026-11-15T00:00:00")


def test_snapshot_separates_later_uploads_and_changed_files_from_initial_state():
    class Gateway:
        async def get_thread(self, **kwargs):
            return {"metadata": {"agent_id": "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"}}

        async def get_thread_state(self, **kwargs):
            return {
                "checkpoint": {"checkpoint_id": "fixed"},
                "values": {"messages": []},
            }

        async def get_thread_history(self, **kwargs):
            return []

        async def list_thread_runs(self, **kwargs):
            return [
                {"run_id": "second", "created_at": "2026-01-02T00:00:00+00:00"},
                {"run_id": "first", "created_at": "2026-01-01T00:00:00+00:00"},
            ]

        async def get_thread_execution_evidence(self, **kwargs):
            files = (
                {"sales.csv": "original"}
                if kwargs["run_id"] == "first"
                else {"sales.csv": "changed", "refunds.csv": "new"}
            )
            return {
                "manifest": {
                    "environment": {"status": "captured", "initial_files": files},
                    "artifacts": {"report.md": "generated, not initial"},
                }
            }

    value = asyncio.run(
        snapshot(
            Gateway(),
            None,
            "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb",
            "cccccccc-cccc-4ccc-cccc-cccccccccccc",
        )
    )
    assert value["environment"]["initial_files"] == {"sales.csv": "original"}
    assert value["environment"]["later_uploads"] == [
        {
            "before_run_id": "second",
            "files": {"refunds.csv": "new"},
            "changed_paths": ["sales.csv"],
        }
    ]
    assert "report.md" not in value["environment"]["initial_files"]


def test_snapshot_freezes_messages_and_reports_concurrent_source_change():
    class Gateway:
        reads = 0

        async def get_thread(self, **kwargs):
            return {"metadata": {"agent_id": str(uuid4())}}

        async def get_thread_state(self, **kwargs):
            self.reads += 1
            return {
                "checkpoint": {
                    "checkpoint_id": "before" if self.reads == 1 else "after"
                },
                "values": {
                    "messages": [
                        {
                            "id": "u",
                            "type": "human",
                            "content": "old" if self.reads == 1 else "new",
                        }
                    ]
                },
            }

        async def get_thread_history(self, **kwargs):
            assert kwargs["payload"]["before"] == {"checkpoint_id": "before"}
            return [{"values": {"messages": []}}]

        async def list_thread_runs(self, **kwargs):
            return []

    value = asyncio.run(snapshot(Gateway(), None, str(uuid4()), str(uuid4())))
    assert value["messages"][0]["content"] == "old"
    assert value["changed_during_capture"]
    assert "采集期间会话发生变化" in value["missing"][0]


def test_material_submission_reuses_receipt_without_reading_source_again(monkeypatch):
    import pytest

    from platform_api.core.errors import ConflictError
    from platform_api.modules.evaluation import materials as module

    project, thread, actor = (
        str(uuid4()),
        uuid4(),
        SimpleNamespace(user_id=str(uuid4())),
    )
    body = module.MaterialRequest(
        request_id=uuid4(),
        thread_ids=[thread],
        title="合成",
        synthetic_attestation=True,
    )
    receipt = {"status": "delivered", "materials": [], "failures": []}
    previous = {
        "id": str(uuid4()),
        "material_submission": {
            "scope": {
                "title": "合成",
                "thread_ids": [str(thread)],
                "data_class": "synthetic",
                "auto_generate": False,
            },
            "receipt": receipt,
        },
    }

    async def forward(*args):
        assert args[3] == "read"
        return previous

    async def fail(*args):
        pytest.fail("idempotent replay must not collect changed source")

    monkeypatch.setattr(module, "forward", forward)
    monkeypatch.setattr(module, "snapshot", fail)
    monkeypatch.setattr(module, "require_action", lambda *args: None)
    monkeypatch.setattr(module, "_require_project_id", lambda _: project)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    evaluation_connection_id="default",
                    evaluation_web_url="http://127.0.0.1:9138",
                )
            )
        )
    )
    value = asyncio.run(module.send_materials(request, body, actor, None))
    assert value["reused"] and value["item_id"] == previous["id"]
    with pytest.raises(ConflictError):
        asyncio.run(
            module.send_materials(
                request, body.model_copy(update={"title": "changed"}), actor, None
            )
        )


def test_material_batch_keeps_denied_source_out_of_forwarded_payload(monkeypatch):
    from platform_api.modules.evaluation import materials as module

    project, agent, allowed, denied = [str(uuid4()) for _ in range(4)]
    actor = SimpleNamespace(user_id=str(uuid4()))
    writes = []

    async def forward(*args):
        if args[3] == "read":
            return {}
        writes.append(args[-1])
        return {"id": args[4]}

    async def collect(gateway, actor, project_id, identifier, data_class):
        if identifier == denied:
            raise ValueError("无权访问此会话")
        return {
            "thread_id": allowed,
            "agent_id": agent,
            "title": "合成",
            "content_hash": "a" * 64,
            "missing": [],
            "environment": {},
            "messages": [{"content": "allowed"}],
        }

    monkeypatch.setattr(module, "forward", forward)
    monkeypatch.setattr(module, "snapshot", collect)
    monkeypatch.setattr(module, "require_action", lambda *args: None)
    monkeypatch.setattr(module, "_require_project_id", lambda _: project)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    evaluation_connection_id="default", evaluation_web_url=""
                )
            )
        )
    )
    body = module.MaterialRequest(
        request_id=uuid4(),
        thread_ids=[allowed, denied, allowed],
        title="合成",
        synthetic_attestation=True,
    )
    value = asyncio.run(module.send_materials(request, body, actor, None))
    assert value["status"] == "partial" and value["failures"][0]["thread_id"] == denied
    assert len(writes[0]["source_materials"]) == 1
    assert writes[0]["source_materials"][0]["thread_id"] == allowed


def test_business_material_redacts_consistently_and_preserves_source():
    from platform_api.modules.evaluation.privacy import prepare_business_material

    source = {
        "messages": [{"content": "客户buyer@example.com，退款300元，销售1800元"}],
        "environment": {
            "initial_files": {"contacts.csv": "buyer@example.com,13812345678"}
        },
    }
    clean, report = prepare_business_material(source)
    assert report["redacted_occurrences"] == 3
    assert "buyer@example.com" not in str(clean) and "13812345678" not in str(clean)
    marker = clean["messages"][0]["content"].split("客户", 1)[1].split("，", 1)[0]
    assert marker in clean["environment"]["initial_files"]["contacts.csv"]
    assert "300元" in str(clean) and "1800元" in str(clean)
    assert "buyer@example.com" in source["messages"][0]["content"]
    assert (
        prepare_business_material("口径：Ａ＋Ｂ＝３００，保留原文。斜线／与空格　")[0]
        == "口径：Ａ＋Ｂ＝３００，保留原文。斜线／与空格　"
    )


def test_business_material_rejects_secrets_and_requires_consent():
    import pytest

    from platform_api.core.errors import BadRequestError
    from platform_api.modules.evaluation.materials import MaterialRequest
    from platform_api.modules.evaluation.privacy import (
        prepare_business_material,
        require_safe_material,
    )

    for value in [
        {"nested": {"password": "test-credential"}},
        '{"api_key": "test-credential"}',
        "Bearer test-credential",
    ]:
        with pytest.raises(BadRequestError):
            prepare_business_material(value)
    with pytest.raises(BadRequestError):
        require_safe_material('{"api_key": "test-credential"}')
    with pytest.raises(ValueError):
        MaterialRequest(
            request_id=uuid4(),
            thread_ids=[uuid4()],
            title="业务会话",
            data_class="business",
        )
    value, report = prepare_business_material("手机号１３８１２３４５６７８")
    assert report["redacted_occurrences"] == 1 and "13812345678" not in value

    # Ensure normal programming code assignments or type annotations do not trigger false positives
    for safe_code in [
        "token = _operation.set(operation)",
        "token = None",
        "token: str",
        "token = self._token",
    ]:
        safe_val, _ = prepare_business_material(safe_code)
        assert safe_val == safe_code


def test_conversion_resumes_lost_generation_receipt_without_recollecting(monkeypatch):
    from platform_api.core.errors import ServiceUnavailableError
    from platform_api.modules.evaluation import materials as module
    from platform_api.modules.evaluation import workbench_grants

    project, agent, thread = [str(uuid4()) for _ in range(3)]
    actor = SimpleNamespace(user_id=str(uuid4()))
    state, collected, jobs, grants = {}, [], set(), set()
    fail_once = [True]

    async def collect(*args):
        collected.append(args[-2:])
        return {
            "thread_id": thread,
            "agent_id": agent,
            "title": "业务",
            "content_hash": "a" * 64,
            "missing": [],
            "environment": {},
            "messages": [{"content": "销售1800元"}],
        }

    async def forward(request, who, pid, operation, item_id, request_id, data):
        if operation == "read":
            return state
        if operation == "create":
            state.update(
                {
                    **data,
                    "id": item_id,
                    "project_id": pid,
                    "material_hash": "a" * 64,
                    "grants": {},
                    "assistant_jobs": [],
                }
            )
        elif operation == "grant":
            grants.add(str(request_id))
            state["grants"]["evaluation_assistance"] = data["grant_id"]
        elif operation == "generate":
            if str(request_id) not in jobs:
                jobs.add(str(request_id))
                state["assistant_jobs"].append(
                    {"id": str(request_id), "status": "reserved"}
                )
            if fail_once:
                fail_once.clear()
                raise ServiceUnavailableError("模拟生成已入队但回执丢失")
        return state

    monkeypatch.setattr(module, "forward", forward)
    monkeypatch.setattr(module, "snapshot", collect)
    monkeypatch.setattr(module, "require_action", lambda *args: None)
    monkeypatch.setattr(module, "_require_project_id", lambda _: project)
    monkeypatch.setattr(
        workbench_grants,
        "create_grant",
        lambda factory, actor, pid, item, body, route: {"grant_id": str(body.grant_id)},
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                db_session_factory=None,
                settings=SimpleNamespace(
                    evaluation_web_url="http://127.0.0.1:9138",
                    evaluation_assistant_model_route="managed",
                    evaluation_connection_id="default",
                ),
            )
        )
    )
    body = module.MaterialRequest(
        request_id=uuid4(),
        thread_ids=[thread],
        title="业务会话",
        data_class="business",
        material_consent=True,
        auto_generate=True,
    )
    first = asyncio.run(module.send_materials(request, body, actor, None))
    assert first["generation_status"] == "needs_retry" and first["item_id"]
    second = asyncio.run(module.send_materials(request, body, actor, None))
    assert second["reused"] and second["generation_status"] == "reserved"
    assert len(collected) == len(jobs) == len(grants) == 1
    assert state["data_class"] == "business" and not state["synthetic_attestation"]
    assert "regression" not in state["grants"]


def test_auto_conversion_checks_grant_permission_before_source_access(monkeypatch):
    import pytest

    from platform_api.core.errors import ForbiddenError
    from platform_api.modules.evaluation import materials as module

    def require(actor, project, action):
        if action == "grant":
            raise ForbiddenError("需要资料负责人")

    async def collect(*args):
        pytest.fail("must reject before source collection")

    monkeypatch.setattr(module, "require_action", require)
    monkeypatch.setattr(module, "_require_project_id", lambda _: str(uuid4()))
    monkeypatch.setattr(module, "snapshot", collect)
    body = module.MaterialRequest(
        request_id=uuid4(),
        thread_ids=[uuid4()],
        title="业务",
        data_class="business",
        material_consent=True,
        auto_generate=True,
    )
    with pytest.raises(ForbiddenError):
        asyncio.run(module.send_materials(None, body, None, None))


def test_async_mode_returns_202_accepted_and_dispatches_background_task(monkeypatch):
    from fastapi import BackgroundTasks, Response

    from platform_api.modules.evaluation import materials as module

    project = str(uuid4())
    actor = SimpleNamespace(user_id=str(uuid4()))
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(
                    evaluation_connection_id="default",
                    evaluation_web_url="http://127.0.0.1:9128",
                ),
                db_session_factory=None,
            )
        )
    )

    async def forward(*args):
        if args[3] == "read":
            return {}
        return {"id": args[4]}

    monkeypatch.setattr(module, "forward", forward)
    monkeypatch.setattr(module, "require_action", lambda *args: None)
    monkeypatch.setattr(module, "_require_project_id", lambda _: project)

    background_tasks = BackgroundTasks()
    response = Response()
    body = module.MaterialRequest(
        request_id=uuid4(),
        thread_ids=[uuid4()],
        title="异步业务评测集",
        synthetic_attestation=True,
        async_mode=True,
    )

    result = asyncio.run(
        module.send_materials(
            request,
            body,
            actor,
            None,
            background_tasks=background_tasks,
            response=response,
        )
    )

    assert response.status_code == 202
    assert result["status"] == "accepted"
    assert "task_id" in result
    assert result["title"] == "异步业务评测集"
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func == module.process_materials_background


def test_background_task_processes_and_notifies(monkeypatch):
    from platform_api.modules.evaluation import materials as module

    project, agent = str(uuid4()), str(uuid4())
    actor = SimpleNamespace(user_id=str(uuid4()))
    notifications = []

    async def forward(*args):
        if args[3] == "read":
            return {}
        return {"id": args[4], "assistant_jobs": []}

    async def finish(*args):
        return {"status": "delivered", "materials": []}

    async def collect(*args):
        return {
            "thread_id": str(uuid4()),
            "agent_id": agent,
            "title": "会话A",
            "content_hash": "b" * 64,
            "missing": [],
            "environment": {},
            "messages": [],
        }

    def mock_notify(
        factory,
        user_id,
        project_id,
        title,
        item_id,
        url,
        error_message=None,
        *,
        connection_id="default",
    ):
        notifications.append(
            {
                "user_id": user_id,
                "project_id": project_id,
                "title": title,
                "item_id": item_id,
                "error": error_message,
            }
        )

    monkeypatch.setattr(module, "forward", forward)
    monkeypatch.setattr(module, "finish_conversion", finish)
    monkeypatch.setattr(module, "snapshot", collect)
    monkeypatch.setattr(module, "notify_conversion_result", mock_notify)

    app_state = SimpleNamespace(
        settings=SimpleNamespace(
            evaluation_connection_id="default",
            evaluation_web_url="http://127.0.0.1:9128",
        ),
        db_session_factory=None,
    )
    body = module.MaterialRequest(
        request_id=uuid4(),
        thread_ids=[uuid4()],
        title="异步成功测试",
        synthetic_attestation=True,
    )

    asyncio.run(
        module.process_materials_background(
            app_state=app_state,
            actor=actor,
            project_id=project,
            gateway=None,
            body=body,
            item_id="item-123",
            submission={},
            title="异步成功测试",
        )
    )

    assert len(notifications) == 1
    assert notifications[0]["item_id"] == "item-123"
    assert notifications[0]["error"] is None


def test_conversion_notification_only_confirms_delivery(setup):
    from sqlalchemy import select

    from platform_api.core.db import session_scope
    from platform_api.modules.evaluation.materials import notify_conversion_result
    from platform_api.modules.notifications.models import NotificationRecord

    factory, actor, scope = setup
    item_id = str(uuid4())
    notify_conversion_result(
        factory, actor.user_id, scope[0], "算术", item_id, "https://evalflow.example"
    )
    with session_scope(factory) as session:
        notification = session.scalar(select(NotificationRecord))
        assert notification.title == "评测集【算术】资料已送达"
        assert "查看 AI 处理状态" in notification.content
        assert "草稿已就绪" not in notification.content
        assert (
            notification.action_url == f"https://evalflow.example/#/authoring/{item_id}"
        )

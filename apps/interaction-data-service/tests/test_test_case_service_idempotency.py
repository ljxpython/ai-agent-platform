from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.api.test_case_service.test_cases import create_one_test_case, list_all_test_cases  # noqa: E402
from app.db.init_db import create_core_tables  # noqa: E402
from app.schemas.test_case_service import CreateTestCaseRequest  # noqa: E402


def _build_fake_request(session_factory: sessionmaker) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    db_session_factory=session_factory,
                    document_asset_root="",
                )
            )
        ),
    )


def _build_test_context(tmp_path: Path) -> Any:
    db_path = tmp_path / "interaction-data-idempotency.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    create_core_tables(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return _build_fake_request(session_factory)


def test_create_test_case_reuses_existing_row_when_idempotency_key_matches(
    tmp_path: Path,
) -> None:
    request = _build_test_context(tmp_path)
    project_id = str(uuid.uuid4())
    batch_id = "test-case-service:idempotency"
    idempotency_key = "tc:login-success"

    first = asyncio.run(
        create_one_test_case(
            request,
            CreateTestCaseRequest(
                project_id=project_id,
                batch_id=batch_id,
                idempotency_key=idempotency_key,
                case_id="TC-LOGIN-001",
                title="登录成功",
                description="验证合法账号密码可以成功登录",
                status="active",
                module_name="认证中心",
                priority="P0",
                source_document_ids=["doc-1"],
                content_json={"title": "登录成功", "version": 1},
            ),
        )
    )
    second = asyncio.run(
        create_one_test_case(
            request,
            CreateTestCaseRequest(
                project_id=project_id,
                batch_id=batch_id,
                idempotency_key=idempotency_key,
                case_id="TC-LOGIN-001",
                title="登录成功-覆盖",
                description="第二次保存应覆盖旧内容",
                status="draft",
                module_name="账号中心",
                priority="P1",
                source_document_ids=["doc-2"],
                content_json={"title": "登录成功-覆盖", "version": 2},
            ),
        )
    )

    assert first["id"] == second["id"]
    assert second["title"] == "登录成功-覆盖"
    assert second["status"] == "draft"
    assert second["module_name"] == "账号中心"
    assert second["source_document_ids"] == ["doc-2"]
    assert second["content_json"] == {"title": "登录成功-覆盖", "version": 2}
    assert second["idempotency_key"] == idempotency_key

    listing = asyncio.run(
        list_all_test_cases(
            request,
            project_id=project_id,
            status=None,
            batch_id=batch_id,
            query="登录成功",
            limit=20,
            offset=0,
        )
    )
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == first["id"]

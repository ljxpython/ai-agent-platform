from __future__ import annotations

import asyncio
import sys
import uuid
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers, UploadFile

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.api.test_case_service.aggregates import get_batch_detail, get_overview, list_batches  # noqa: E402
from app.api.test_case_service.documents import (  # noqa: E402
    create_document,
    create_document_asset,
    download_document_asset,
    get_document_relations,
    list_documents,
    preview_document_asset,
)
from app.api.test_case_service.test_cases import create_one_test_case, list_all_test_cases  # noqa: E402
from app.db.init_db import create_core_tables  # noqa: E402
from app.db.models import TestCaseDocument as InteractionTestCaseDocumentModel  # noqa: E402
from app.schemas.test_case_service import (  # noqa: E402
    CreateTestCaseDocumentRequest,
    CreateTestCaseRequest,
)
from sqlalchemy import select  # noqa: E402


def _build_fake_request(session_factory: sessionmaker, *, document_asset_root: Path) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    db_session_factory=session_factory,
                    document_asset_root=str(document_asset_root),
                )
            )
        ),
    )


def _build_test_context(tmp_path: Path) -> tuple[Any, sessionmaker]:
    db_path = tmp_path / "interaction-data.db"
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
    asset_root = tmp_path / "document-assets"
    asset_root.mkdir(parents=True, exist_ok=True)
    return _build_fake_request(session_factory, document_asset_root=asset_root), session_factory


def test_test_case_service_overview_batches_and_filters(tmp_path: Path) -> None:
    request, _ = _build_test_context(tmp_path)
    project_id = str(uuid.uuid4())
    other_project_id = str(uuid.uuid4())

    batch_login = "test-case-service:login"
    batch_reset = "test-case-service:reset"

    asyncio.run(
        create_document(
            request,
            CreateTestCaseDocumentRequest(
                project_id=project_id,
                batch_id=batch_login,
                idempotency_key="doc-login-v1",
                filename="登录接口文档.pdf",
                content_type="application/pdf",
                source_kind="upload",
                parse_status="parsed",
                summary_for_model="提取出登录成功和失败规则",
                parsed_text="登录接口要求用户名密码必填。",
                structured_data={"key_points": ["login"]},
                provenance={"phase": "phase2"},
            ),
        )
    )
    asyncio.run(
        create_document(
            request,
            CreateTestCaseDocumentRequest(
                project_id=project_id,
                batch_id=batch_reset,
                idempotency_key="doc-reset-v1",
                filename="重置密码接口文档.pdf",
                content_type="application/pdf",
                source_kind="upload",
                parse_status="failed",
                summary_for_model="PDF 解析失败",
                parsed_text="重置密码流程提取失败。",
                structured_data={"key_points": ["reset-password"]},
                provenance={"phase": "phase2"},
                error={"message": "parser_failed"},
            ),
        )
    )
    asyncio.run(
        create_document(
            request,
            CreateTestCaseDocumentRequest(
                project_id=other_project_id,
                batch_id="test-case-service:other",
                idempotency_key="doc-other-v1",
                filename="其他项目文档.pdf",
                content_type="application/pdf",
            ),
        )
    )

    duplicate_login = asyncio.run(
        create_document(
            request,
            CreateTestCaseDocumentRequest(
                project_id=project_id,
                batch_id=batch_login,
                idempotency_key="doc-login-v1",
                filename="登录接口文档.pdf",
                content_type="application/pdf",
                source_kind="upload",
                parse_status="parsed",
                summary_for_model="提取出登录成功和失败规则-重试",
                parsed_text="登录接口要求用户名密码必填，重试不应新增记录。",
                structured_data={"key_points": ["login", "retry"]},
                provenance={"phase": "phase2", "fingerprint": "doc-login-v1"},
            ),
        )
    )
    assert duplicate_login["idempotency_key"] == "doc-login-v1"

    asyncio.run(
        create_one_test_case(
            request,
            CreateTestCaseRequest(
                project_id=project_id,
                batch_id=batch_login,
                case_id="TC-LOGIN-001",
                title="登录成功",
                description="验证合法账号密码可以成功登录",
                status="active",
                module_name="认证中心",
                priority="P0",
                source_document_ids=[],
                content_json={"title": "登录成功"},
            ),
        )
    )
    asyncio.run(
        create_one_test_case(
            request,
            CreateTestCaseRequest(
                project_id=project_id,
                batch_id=batch_login,
                case_id="TC-LOGIN-002",
                title="登录失败",
                description="验证错误密码时提示失败",
                status="draft",
                module_name="认证中心",
                priority="P1",
                source_document_ids=[],
                content_json={"title": "登录失败"},
            ),
        )
    )

    overview = asyncio.run(get_overview(request, project_id=project_id))
    assert overview["project_id"] == project_id
    assert overview["documents_total"] == 2
    assert overview["parsed_documents_total"] == 1
    assert overview["failed_documents_total"] == 1
    assert overview["test_cases_total"] == 2
    assert overview["latest_batch_id"] in {batch_login, batch_reset}
    assert overview["latest_activity_at"]

    batches = asyncio.run(list_batches(request, project_id=project_id, limit=20, offset=0))
    assert batches["total"] == 2
    by_batch = {item["batch_id"]: item for item in batches["items"]}
    assert by_batch[batch_login]["documents_count"] == 1
    assert by_batch[batch_login]["test_cases_count"] == 2
    assert by_batch[batch_login]["parse_status_summary"] == {"parsed": 1}
    assert by_batch[batch_reset]["documents_count"] == 1
    assert by_batch[batch_reset]["test_cases_count"] == 0
    assert by_batch[batch_reset]["parse_status_summary"] == {"failed": 1}

    filtered_documents = asyncio.run(
        list_documents(
            request,
            project_id=project_id,
            batch_id=None,
            parse_status="failed",
            query="重置密码",
            limit=20,
            offset=0,
        )
    )
    assert filtered_documents["total"] == 1
    assert filtered_documents["items"][0]["batch_id"] == batch_reset
    assert filtered_documents["items"][0]["idempotency_key"] == "doc-reset-v1"

    filtered_cases = asyncio.run(
        list_all_test_cases(
            request,
            project_id=project_id,
            status="draft",
            batch_id=batch_login,
            query="失败",
            limit=20,
            offset=0,
        )
    )
    assert filtered_cases["total"] == 1
    assert filtered_cases["items"][0]["case_id"] == "TC-LOGIN-002"

    login_documents = asyncio.run(
        list_documents(
            request,
            project_id=project_id,
            batch_id=batch_login,
            parse_status=None,
            query="登录接口",
            limit=20,
            offset=0,
        )
    )
    assert login_documents["total"] == 1
    assert login_documents["items"][0]["id"] == duplicate_login["id"]
    assert login_documents["items"][0]["structured_data"] == {"key_points": ["login", "retry"]}

    batch_detail = asyncio.run(
        get_batch_detail(
            request,
            batch_id=batch_login,
            project_id=project_id,
            document_limit=20,
            document_offset=0,
            case_limit=20,
            case_offset=0,
        )
    )
    assert batch_detail["batch"]["batch_id"] == batch_login
    assert batch_detail["batch"]["documents_count"] == 1
    assert batch_detail["batch"]["test_cases_count"] == 2
    assert batch_detail["batch"]["parse_status_summary"] == {"parsed": 1}
    assert batch_detail["documents"]["total"] == 1
    assert batch_detail["documents"]["items"][0]["id"] == duplicate_login["id"]
    assert batch_detail["test_cases"]["total"] == 2
    assert {item["case_id"] for item in batch_detail["test_cases"]["items"]} == {
        "TC-LOGIN-001",
        "TC-LOGIN-002",
    }


def test_test_case_service_document_relations_and_assets(tmp_path: Path) -> None:
    request, _ = _build_test_context(tmp_path)
    project_id = str(uuid.uuid4())
    batch_id = "test-case-service:assets"
    upload = UploadFile(
        file=BytesIO(b"%PDF-1.4\n%fake\n1 0 obj\n<<>>\nendobj\n"),
        filename="接口文档.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    asset = asyncio.run(
        create_document_asset(
            request,
            project_id=project_id,
            batch_id=batch_id,
            idempotency_key="asset-login-v1",
            filename="接口文档.pdf",
            content_type="application/pdf",
            file=upload,
        )
    )
    assert asset["storage_path"].endswith(".pdf")
    asset_path = Path(request.app.state.document_asset_root) / asset["storage_path"]
    assert asset_path.exists()
    assert asset_path.read_bytes().startswith(b"%PDF-1.4")

    document = asyncio.run(
        create_document(
            request,
            CreateTestCaseDocumentRequest(
                project_id=project_id,
                batch_id=batch_id,
                idempotency_key="doc-login-v1",
                filename="接口文档.pdf",
                content_type="application/pdf",
                storage_path=asset["storage_path"],
                source_kind="upload",
                parse_status="parsed",
                summary_for_model="提取出登录接口关键规则",
                parsed_text="登录接口要求用户名密码必填。",
                structured_data={"key_points": ["login"]},
                provenance={
                    "runtime": {
                        "thread_id": "thread-123",
                        "run_id": "run-456",
                        "agent_key": "test_case_service",
                    },
                    "asset": {"storage_path": asset["storage_path"]},
                },
            ),
        )
    )
    asyncio.run(
        create_one_test_case(
            request,
            CreateTestCaseRequest(
                project_id=project_id,
                batch_id=batch_id,
                case_id="TC-LOGIN-001",
                title="登录成功",
                description="验证合法账号密码可以成功登录",
                status="active",
                module_name="认证中心",
                priority="P0",
                source_document_ids=[document["id"]],
                content_json={"title": "登录成功"},
            ),
        )
    )

    relations = asyncio.run(get_document_relations(request, document["id"]))
    assert relations["document"]["id"] == document["id"]
    assert relations["runtime_meta"] == {
        "thread_id": "thread-123",
        "run_id": "run-456",
        "agent_key": "test_case_service",
    }
    assert relations["related_cases_count"] == 1
    assert relations["related_cases"][0]["case_id"] == "TC-LOGIN-001"

    preview_response = asyncio.run(preview_document_asset(request, document["id"]))
    download_response = asyncio.run(download_document_asset(request, document["id"]))
    assert Path(preview_response.path) == asset_path
    assert Path(download_response.path) == asset_path
    assert preview_response.headers["content-disposition"].startswith('inline; filename="document.pdf";')
    assert "filename*=UTF-8''" in preview_response.headers["content-disposition"]
    assert download_response.headers["content-disposition"].startswith(
        'attachment; filename="document.pdf";'
    )
    assert "filename*=UTF-8''" in download_response.headers["content-disposition"]


def test_test_case_service_document_asset_endpoints_accept_legacy_provenance_storage_path(
    tmp_path: Path,
) -> None:
    request, _ = _build_test_context(tmp_path)
    project_id = str(uuid.uuid4())
    batch_id = "test-case-service:legacy-assets"
    upload = UploadFile(
        file=BytesIO(b"%PDF-1.4\n%legacy\n1 0 obj\n<<>>\nendobj\n"),
        filename="旧版接口文档.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    asset = asyncio.run(
        create_document_asset(
            request,
            project_id=project_id,
            batch_id=batch_id,
            idempotency_key="asset-legacy-v1",
            filename="旧版接口文档.pdf",
            content_type="application/pdf",
            file=upload,
        )
    )
    asset_path = Path(request.app.state.document_asset_root) / asset["storage_path"]

    document = asyncio.run(
        create_document(
            request,
            CreateTestCaseDocumentRequest(
                project_id=project_id,
                batch_id=batch_id,
                idempotency_key="doc-legacy-v1",
                filename="旧版接口文档.pdf",
                content_type="application/pdf",
                storage_path=None,
                source_kind="upload",
                parse_status="parsed",
                summary_for_model="历史数据只在 provenance.asset 中保留 storage_path。",
                parsed_text="历史 testcase 文档记录。",
                structured_data={"key_points": ["legacy-storage-path"]},
                provenance={
                    "asset": {"storage_path": asset["storage_path"]},
                },
            ),
        )
    )

    preview_response = asyncio.run(preview_document_asset(request, document["id"]))
    download_response = asyncio.run(download_document_asset(request, document["id"]))

    assert Path(preview_response.path) == asset_path
    assert Path(download_response.path) == asset_path


def test_test_case_service_serializes_legacy_asset_metadata_into_document_fields(
    tmp_path: Path,
) -> None:
    request, session_factory = _build_test_context(tmp_path)
    project_id = str(uuid.uuid4())
    batch_id = "test-case-service:legacy-metadata"
    upload = UploadFile(
        file=BytesIO(b"%PDF-1.4\n%legacy-metadata\n1 0 obj\n<<>>\nendobj\n"),
        filename="历史文档.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    asset = asyncio.run(
        create_document_asset(
            request,
            project_id=project_id,
            batch_id=batch_id,
            idempotency_key="asset-legacy-metadata-v1",
            filename="历史文档.pdf",
            content_type="application/pdf",
            file=upload,
        )
    )

    document = asyncio.run(
        create_document(
            request,
            CreateTestCaseDocumentRequest(
                project_id=project_id,
                batch_id=batch_id,
                idempotency_key="doc-legacy-metadata-v1",
                filename="历史文档.pdf",
                content_type="application/pdf",
                storage_path=asset["storage_path"],
                source_kind="upload",
                parse_status="parsed",
                summary_for_model="旧记录字段回填测试。",
                parsed_text="旧 testcase 文档详情。",
                structured_data={"key_points": ["legacy-metadata"]},
                provenance={
                    "asset": {
                        "storage_path": asset["storage_path"],
                        "content_type": "application/pdf",
                    },
                },
            ),
        )
    )

    with session_factory() as session:
        row = session.scalar(
            select(InteractionTestCaseDocumentModel).where(
                InteractionTestCaseDocumentModel.id == uuid.UUID(document["id"])
            )
        )
        assert row is not None
        row.storage_path = None
        row.content_type = ""
        session.commit()

    listed = asyncio.run(
        list_documents(
            request,
            project_id=project_id,
            batch_id=batch_id,
            parse_status=None,
            query=None,
            limit=20,
            offset=0,
        )
    )
    relations = asyncio.run(get_document_relations(request, document["id"]))

    assert listed["items"][0]["storage_path"] == asset["storage_path"]
    assert listed["items"][0]["content_type"] == "application/pdf"
    assert relations["document"]["storage_path"] == asset["storage_path"]
    assert relations["document"]["content_type"] == "application/pdf"

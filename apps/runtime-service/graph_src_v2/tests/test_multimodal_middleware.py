from __future__ import annotations

import asyncio
import base64
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from graph_src_v2.middlewares.multimodal import (  # noqa: E402
    MULTIMODAL_ATTACHMENTS_KEY,
    MULTIMODAL_SUMMARY_KEY,
    AttachmentArtifact,
    MultimodalMiddleware,
    _extract_pdf_text,
    _parse_model_response,
    _resolve_parser_transport,
    build_attachment_artifact,
    build_multimodal_system_message,
    normalize_messages,
)


def test_build_attachment_artifact_for_frontend_image_block() -> None:
    artifact = build_attachment_artifact(
        {
            "type": "image",
            "mimeType": "image/png",
            "data": "abc123",
            "metadata": {"name": "screen.png"},
        },
        1,
    )
    assert artifact is not None
    assert artifact["kind"] == "image"
    assert artifact["mime_type"] == "image/png"
    assert artifact["status"] == "unprocessed"
    assert artifact["name"] == "screen.png"


def test_build_attachment_artifact_for_docx_block() -> None:
    artifact = build_attachment_artifact(
        {
            "type": "file",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "data": "abc123",
            "metadata": {"filename": "report.docx"},
        },
        2,
    )
    assert artifact is not None
    assert artifact["kind"] == "docx"
    assert artifact["status"] == "unprocessed"


def test_normalize_messages_converts_frontend_blocks_to_langchain_shape() -> None:
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "请看附件"},
                {
                    "type": "image",
                    "mimeType": "image/png",
                    "data": "abc123",
                    "metadata": {"name": "screen.png"},
                },
                {
                    "type": "file",
                    "mimeType": "application/pdf",
                    "data": "pdfbase64",
                    "metadata": {"filename": "report.pdf"},
                },
            ]
        )
    ]

    normalized = normalize_messages(messages)
    content = cast(list[dict[str, Any]], normalized[0].content)
    assert isinstance(content, list)
    assert content[1]["base64"] == "abc123"
    assert content[1]["mime_type"] == "image/png"
    assert content[2]["base64"] == "pdfbase64"
    assert content[2]["mime_type"] == "application/pdf"


def test_multimodal_middleware_wrap_model_call_augments_request() -> None:
    def fake_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = "PDF 已解析：这是测试摘要。"
        next_artifact["parsed_text"] = "测试 PDF 文本"
        next_artifact["structured_data"] = {"key_points": ["测试摘要"]}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=fake_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "帮我看下这个 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        system_prompt = updated_request.system_prompt or ""
        assert "Base prompt" in system_prompt
        assert "## Multimodal Attachments" in system_prompt
        state = cast(dict[str, Any], updated_request.state)
        assert MULTIMODAL_ATTACHMENTS_KEY in state
        assert MULTIMODAL_SUMMARY_KEY in state
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["status"] == "parsed"
        assert "PDF 已解析" in state[MULTIMODAL_SUMMARY_KEY]
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert isinstance(content, list)
        assert content[1]["type"] == "text"
        assert "PDF 已解析" in content[1]["text"]
        assert "测试 PDF 文本" in content[1]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_before_model_records_state() -> None:
    middleware = MultimodalMiddleware()
    state = {
        "messages": [
            HumanMessage(
                content=[
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "abc",
                        "metadata": {"name": "screen.png"},
                    },
                ]
            )
        ]
    }
    updates = middleware.before_model(cast(Any, state), runtime=None)
    assert updates is not None
    assert MULTIMODAL_ATTACHMENTS_KEY in updates
    assert updates[MULTIMODAL_ATTACHMENTS_KEY][0]["kind"] == "image"
    assert MULTIMODAL_SUMMARY_KEY in updates


def test_multimodal_middleware_awrap_model_call_augments_request() -> None:
    async def fake_async_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "parsed"
        next_artifact["summary_for_model"] = "DOC 已解析：这是测试摘要。"
        next_artifact["parsed_text"] = "测试 DOC 文本"
        next_artifact["structured_data"] = {"key_points": ["测试 DOC"]}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(async_parser=fake_async_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {
                        "type": "file",
                        "mimeType": "application/msword",
                        "data": "docbase64",
                        "metadata": {"filename": "brief.doc"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    async def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["kind"] == "doc"
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["status"] == "unprocessed"
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[0]["type"] == "text"
        assert "kind=doc" in content[0]["text"]
        return ModelResponse(result=[AIMessage(content="ok")])

    response = asyncio.run(middleware.awrap_model_call(request, handler))
    assert response.result[0].text == "ok"


def test_multimodal_middleware_preserves_model_with_attachments() -> None:
    class DummyModel:
        def __init__(self) -> None:
            self.bound_kwargs: dict[str, Any] | None = None

        def bind(self, **kwargs: Any) -> "DummyModel":
            bound = DummyModel()
            bound.bound_kwargs = kwargs
            return bound

    base_model = DummyModel()
    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, base_model),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请分析这个 PDF"},
                    {
                        "type": "file",
                        "mimeType": "application/pdf",
                        "data": "pdfbase64",
                        "metadata": {"filename": "report.pdf"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
        )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is base_model
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "text"
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_preserves_model_without_attachments() -> None:
    class DummyModel:
        def __init__(self) -> None:
            self.bound_kwargs: dict[str, Any] | None = None

        def bind(self, **kwargs: Any) -> "DummyModel":
            bound = DummyModel()
            bound.bound_kwargs = kwargs
            return bound

    base_model = DummyModel()
    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, base_model),
        messages=[HumanMessage(content="纯文本请求")],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        assert updated_request.model is base_model
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_parser_failure_is_fail_soft() -> None:
    def failing_parser(
        artifact: AttachmentArtifact, block: Mapping[str, Any]
    ) -> AttachmentArtifact:
        del block
        next_artifact = dict(artifact)
        next_artifact["status"] = "failed"
        next_artifact["summary_for_model"] = "附件解析失败：测试失败"
        next_artifact["error"] = {"message": "测试失败"}
        return cast(AttachmentArtifact, next_artifact)

    middleware = MultimodalMiddleware(parser=failing_parser)
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "imgbase64",
                        "metadata": {"name": "screen.png"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        state = cast(dict[str, Any], updated_request.state)
        assert state[MULTIMODAL_ATTACHMENTS_KEY][0]["status"] == "failed"
        assert "附件解析失败" in state[MULTIMODAL_SUMMARY_KEY]
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[0]["type"] == "image"
        assert content[0]["base64"] == "imgbase64"
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_multimodal_middleware_keeps_image_blocks_for_model() -> None:
    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[
            HumanMessage(
                content=[
                    {"type": "text", "text": "请看图片"},
                    {
                        "type": "image",
                        "mimeType": "image/png",
                        "data": "imgbase64",
                        "metadata": {"name": "screen.png"},
                    },
                ]
            )
        ],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(Any, {}),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        content = cast(list[dict[str, Any]], updated_request.messages[0].content)
        assert content[1]["type"] == "image"
        assert content[1]["base64"] == "imgbase64"
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_extract_pdf_text_from_base64_payload() -> None:
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 72 100 Td (Hello PDF) Tj ET\nendstream endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000113 00000 n \n0000000240 00000 n \n0000000334 00000 n \n"
        b"trailer<</Root 1 0 R/Size 6>>\nstartxref\n404\n%%EOF"
    )
    block = {
        "type": "file",
        "mimeType": "application/pdf",
        "data": base64.b64encode(pdf_bytes).decode("utf-8"),
        "metadata": {"filename": "hello.pdf"},
    }

    text, metadata = _extract_pdf_text(block)
    assert text is not None
    assert "Hello PDF" in text
    assert metadata is not None
    assert metadata["page_count"] == 1
    assert metadata["extraction"] == "pymupdf4llm_markdown"


def test_multimodal_summary_not_reinjected_on_follow_up_text_turn() -> None:
    middleware = MultimodalMiddleware()
    request = ModelRequest(
        model=cast(BaseChatModel, object()),
        messages=[HumanMessage(content="这是一条纯文本追问")],
        system_message=SystemMessage(content="Base prompt"),
        state=cast(
            Any,
            {
                MULTIMODAL_ATTACHMENTS_KEY: [{"attachment_id": "att_1"}],
                MULTIMODAL_SUMMARY_KEY: "旧摘要",
            },
        ),
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        system_prompt = updated_request.system_prompt or ""
        state = cast(dict[str, Any], updated_request.state)
        assert "## Multimodal Attachments" not in system_prompt
        assert MULTIMODAL_ATTACHMENTS_KEY not in state
        assert MULTIMODAL_SUMMARY_KEY not in state
        return ModelResponse(result=[AIMessage(content="ok")])

    response = middleware.wrap_model_call(request, handler)
    assert response.result[0].text == "ok"


def test_build_multimodal_system_message_removes_stale_section() -> None:
    existing = SystemMessage(
        content=(
            "BASE_PROMPT\n\n## Multimodal Attachments\n"
            "检测到以下多模态附件：\n- 旧摘要"
        )
    )
    next_message = build_multimodal_system_message(existing, None)
    assert next_message is not None
    assert next_message.content == "BASE_PROMPT"


def test_parse_model_response_never_uses_raw_json_as_summary() -> None:
    raw = 'Here is the result: {"summary_for_model":"一张动漫头像","parsed_text":null,"structured_data":{"key_points":["头像"]},"confidence":0.98}'
    parsed = _parse_model_response(raw)
    assert parsed["summary_for_model"] == "一张动漫头像"
    assert parsed["structured_data"] == {"key_points": ["头像"]}


def test_resolve_parser_transport_uses_openai_clients() -> None:

    class FakeModel:
        model_name = "qwen3-vl-plus"
        root_client = object()
        root_async_client = object()

    with patch(
        "graph_src_v2.middlewares.multimodal.resolve_model_by_id",
        return_value=FakeModel(),
    ):
        model_name, root_client, root_async_client = _resolve_parser_transport(
            "iflow_qwen3-vl-plus"
        )
    assert model_name == "qwen3-vl-plus"
    assert root_client is FakeModel.root_client
    assert root_async_client is FakeModel.root_async_client

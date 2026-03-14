from __future__ import annotations

import base64
import importlib
import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Literal, cast

from graph_src_v2.runtime.modeling import resolve_model_by_id
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import HumanMessage, SystemMessage
from typing_extensions import NotRequired, TypedDict

AttachmentKind = Literal["image", "pdf", "doc", "docx", "xlsx", "file", "other"]
AttachmentStatus = Literal["unprocessed", "parsed", "unsupported", "failed"]

MULTIMODAL_ATTACHMENTS_KEY = "multimodal_attachments"
MULTIMODAL_SUMMARY_KEY = "multimodal_summary"
DEFAULT_MULTIMODAL_MODEL_ID = "iflow_qwen3-vl-plus"
_MULTIMODAL_PROMPT_HEADER = "## Multimodal Attachments\n"

_DOC_MIME_TYPES = {
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}


class AttachmentArtifact(TypedDict):
    attachment_id: str
    kind: AttachmentKind
    mime_type: str | None
    status: AttachmentStatus
    source_type: str
    name: str | None
    summary_for_model: str
    parsed_text: str | None
    structured_data: dict[str, Any] | None
    provenance: dict[str, Any]
    confidence: float | None
    error: dict[str, Any] | None


ParserResult = TypedDict(
    "ParserResult",
    {
        "summary_for_model": str,
        "parsed_text": str | None,
        "structured_data": dict[str, Any] | None,
        "confidence": float | None,
    },
)


AttachmentParser = Callable[[AttachmentArtifact, Mapping[str, Any]], AttachmentArtifact]
AsyncAttachmentParser = Callable[
    [AttachmentArtifact, Mapping[str, Any]], Awaitable[AttachmentArtifact]
]


class MultimodalAgentState(AgentState):
    multimodal_attachments: NotRequired[list[AttachmentArtifact]]
    multimodal_summary: NotRequired[str]


def _get_message_content(message: Any) -> Any:
    if hasattr(message, "content"):
        return getattr(message, "content")
    if isinstance(message, Mapping):
        return message.get("content")
    return None


def _get_message_type(message: Any) -> str | None:
    if hasattr(message, "type"):
        value = getattr(message, "type")
        return value if isinstance(value, str) else None
    if isinstance(message, Mapping):
        value = message.get("type")
        return value if isinstance(value, str) else None
    return None


def _resolve_mime_type(block: Mapping[str, Any]) -> str | None:
    raw = block.get("mime_type") or block.get("mimeType")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _resolve_attachment_name(block: Mapping[str, Any]) -> str | None:
    metadata = block.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("filename", "name", "title"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("filename", "name"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_attachment_kind(block_type: str, mime_type: str | None) -> AttachmentKind:
    if block_type == "image":
        return "image"
    if mime_type == "application/pdf":
        return "pdf"
    if mime_type in _DOC_MIME_TYPES:
        return cast(AttachmentKind, _DOC_MIME_TYPES[mime_type])
    if block_type == "file":
        return "file"
    return "other"


def _resolve_attachment_status(kind: AttachmentKind) -> AttachmentStatus:
    if kind == "other":
        return "unsupported"
    return "unprocessed"


def _normalize_content_block(item: Any) -> Any:
    if not isinstance(item, Mapping):
        return item

    block = dict(item)
    block_type = block.get("type")
    if block_type not in {"image", "file"}:
        return block

    normalized = dict(block)
    if "base64" not in normalized and isinstance(normalized.get("data"), str):
        normalized["base64"] = normalized["data"]
    mime_type = _resolve_mime_type(block)
    if mime_type and "mime_type" not in normalized:
        normalized["mime_type"] = mime_type
    return normalized


def normalize_message_content(content: Any) -> Any:
    if not isinstance(content, list):
        return content
    return [_normalize_content_block(item) for item in content]


def normalize_messages(messages: Sequence[Any]) -> list[Any]:
    normalized_messages: list[Any] = []
    for message in messages:
        content = _get_message_content(message)
        normalized_content = normalize_message_content(content)
        if normalized_content is content or normalized_content == content:
            normalized_messages.append(message)
            continue
        if hasattr(message, "model_copy"):
            normalized_messages.append(
                message.model_copy(update={"content": normalized_content})
            )
            continue
        if isinstance(message, Mapping):
            next_message = dict(message)
            next_message["content"] = normalized_content
            normalized_messages.append(next_message)
            continue
        normalized_messages.append(message)
    return normalized_messages


def _artifact_model_text(artifact: AttachmentArtifact) -> str:
    lines: list[str] = []
    name = artifact.get("name") or artifact.get("attachment_id") or "附件"
    kind = artifact.get("kind") or "file"
    lines.append(f"[附件: {name}; kind={kind}; status={artifact.get('status', 'unknown')}]")

    summary = artifact.get("summary_for_model")
    if isinstance(summary, str) and summary.strip():
        lines.append(f"摘要: {summary.strip()}")

    parsed_text = artifact.get("parsed_text")
    if isinstance(parsed_text, str) and parsed_text.strip():
        lines.append(f"解析文本摘录:\n{parsed_text.strip()[:4000]}")

    structured_data = artifact.get("structured_data")
    if isinstance(structured_data, Mapping) and structured_data:
        lines.append(
            "结构化要点: " + json.dumps(dict(structured_data), ensure_ascii=False)
        )

    return "\n".join(lines)


def _rewrite_latest_human_message_for_model(
    messages: Sequence[Any],
    artifacts: Sequence[AttachmentArtifact],
) -> list[Any]:
    if not artifacts:
        return list(messages)

    latest_index = -1
    for idx in range(len(messages) - 1, -1, -1):
        message = messages[idx]
        if _get_message_type(message) not in {"human", "user"}:
            continue
        content = _get_message_content(message)
        if not isinstance(content, list):
            continue
        if any(
            isinstance(item, Mapping) and item.get("type") in {"image", "file"}
            for item in content
        ):
            latest_index = idx
            break

    if latest_index < 0:
        return list(messages)

    message = messages[latest_index]
    content = _get_message_content(message)
    if not isinstance(content, list):
        return list(messages)

    artifact_iter = iter(artifacts)
    rewritten_content: list[Any] = []
    for item in content:
        if not isinstance(item, Mapping) or item.get("type") not in {"image", "file"}:
            rewritten_content.append(item)
            continue

        artifact = next(artifact_iter, None)
        if artifact is None:
            rewritten_content.append(item)
            continue

        if artifact.get("kind") == "image":
            rewritten_content.append(item)
            continue

        rewritten_content.append(
            {
                "type": "text",
                "text": _artifact_model_text(artifact),
            }
        )

    rewritten_messages = list(messages)
    if hasattr(message, "model_copy"):
        rewritten_messages[latest_index] = message.model_copy(
            update={"content": rewritten_content}
        )
    elif isinstance(message, Mapping):
        next_message = dict(message)
        next_message["content"] = rewritten_content
        rewritten_messages[latest_index] = next_message
    else:
        rewritten_messages[latest_index] = message
    return rewritten_messages


def _build_attachment_summary(
    kind: AttachmentKind,
    mime_type: str | None,
    name: str | None,
    status: AttachmentStatus,
) -> str:
    label = {
        "image": "图片",
        "pdf": "PDF",
        "doc": "DOC",
        "docx": "DOCX",
        "xlsx": "XLSX",
        "file": "文件",
        "other": "未知文件",
    }[kind]
    name_part = f"“{name}”" if name else "未命名附件"
    mime_part = f"（{mime_type}）" if mime_type else ""
    if status == "unsupported":
        return f"{label}附件 {name_part}{mime_part} 已识别，但当前不在 Phase 1 支持范围内。"
    return f"{label}附件 {name_part}{mime_part} 已识别；当前仅完成协议归一化与状态登记，尚未进行语义解析。"


def build_attachment_artifact(
    block: Mapping[str, Any], index: int
) -> AttachmentArtifact | None:
    block_type = block.get("type")
    if not isinstance(block_type, str) or block_type not in {"image", "file"}:
        return None

    mime_type = _resolve_mime_type(block)
    kind = _resolve_attachment_kind(block_type, mime_type)
    status = _resolve_attachment_status(kind)
    name = _resolve_attachment_name(block)
    return {
        "attachment_id": f"att_{index}",
        "kind": kind,
        "mime_type": mime_type,
        "status": status,
        "source_type": block_type,
        "name": name,
        "summary_for_model": _build_attachment_summary(kind, mime_type, name, status),
        "parsed_text": None,
        "structured_data": None,
        "provenance": {"phase": "phase1", "source": "message_block"},
        "confidence": None,
        "error": None,
    }


def collect_attachment_artifacts(messages: Sequence[Any]) -> list[AttachmentArtifact]:
    artifacts: list[AttachmentArtifact] = []
    next_index = 1
    for message in messages:
        content = _get_message_content(message)
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, Mapping):
                continue
            artifact = build_attachment_artifact(item, next_index)
            if artifact is None:
                continue
            artifacts.append(artifact)
            next_index += 1
    return artifacts


def get_latest_human_message_with_attachments(messages: Sequence[Any]) -> Any | None:
    for message in reversed(messages):
        if _get_message_type(message) not in {"human", "user"}:
            continue
        content = _get_message_content(message)
        if not isinstance(content, list):
            continue
        if any(
            isinstance(item, Mapping) and item.get("type") in {"image", "file"}
            for item in content
        ):
            return message
    return None


def collect_current_turn_attachment_artifacts(
    messages: Sequence[Any],
) -> list[AttachmentArtifact]:
    latest_message = get_latest_human_message_with_attachments(messages)
    if latest_message is None:
        return []
    return collect_attachment_artifacts([latest_message])


def build_multimodal_summary(artifacts: Sequence[AttachmentArtifact]) -> str | None:
    if not artifacts:
        return None
    lines = ["检测到以下多模态附件："]
    for artifact in artifacts:
        summary = artifact["summary_for_model"]
        if artifact["status"] == "failed":
            lines.append(f"- 附件解析失败：{summary}")
        elif artifact["status"] == "unsupported":
            lines.append(f"- 附件暂不支持：{summary}")
        else:
            lines.append(f"- {summary}")
    lines.append(
        "请以原始附件块为事实来源；解析结果属于增强信息，可能存在误差，需要和原始附件一起判断。"
    )
    return "\n".join(lines)


def build_multimodal_system_message(
    existing: SystemMessage | None, summary: str | None
) -> SystemMessage | None:
    header = f"\n\n{_MULTIMODAL_PROMPT_HEADER}"
    existing_content = ""
    if existing is not None and isinstance(existing.content, str):
        existing_content = existing.content
    if _MULTIMODAL_PROMPT_HEADER in existing_content:
        existing_content = existing_content.split(
            f"\n\n{_MULTIMODAL_PROMPT_HEADER}", 1
        )[0].rstrip()
        if not existing_content:
            existing_content = existing_content.strip()
    if not summary:
        return SystemMessage(content=existing_content) if existing_content else None
    content = (
        f"{existing_content}{header}{summary}"
        if existing_content
        else f"{_MULTIMODAL_PROMPT_HEADER}{summary}"
    )
    return SystemMessage(content=content)


def _extract_text_from_message(message: Any) -> str:
    text = getattr(message, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                maybe = item.get("text")
                if isinstance(maybe, str) and maybe.strip():
                    parts.append(maybe.strip())
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        return "\n".join(parts).strip()
    return str(message).strip()


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        body = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
        if body.endswith("```"):
            body = body[:-3]
        return body.strip()
    return stripped


def _extract_json_candidate(text: str) -> str:
    stripped = _strip_code_fence(text)
    match = re.search(r"\{[\s\S]*\}", stripped)
    if match:
        return match.group(0).strip()
    return stripped


def _coerce_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number


def _parse_model_response(raw_text: str) -> ParserResult:
    cleaned = _extract_json_candidate(raw_text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        fallback_text = _strip_code_fence(raw_text)
        return {
            "summary_for_model": "模型已完成附件解析，但返回内容未能结构化解析。",
            "parsed_text": fallback_text[:4000] or None,
            "structured_data": None,
            "confidence": None,
        }

    if not isinstance(payload, Mapping):
        fallback_text = _strip_code_fence(raw_text)
        return {
            "summary_for_model": "模型已完成附件解析，但返回结构不符合预期。",
            "parsed_text": fallback_text[:4000] or None,
            "structured_data": None,
            "confidence": None,
        }

    summary = payload.get("summary_for_model")
    parsed_text = payload.get("parsed_text")
    structured_data = payload.get("structured_data")
    return {
        "summary_for_model": (
            str(summary).strip()
            if summary is not None
            else "模型已完成解析，但未返回摘要。"
        ),
        "parsed_text": (
            str(parsed_text).strip()
            if isinstance(parsed_text, str) and parsed_text.strip()
            else None
        ),
        "structured_data": (
            dict(structured_data) if isinstance(structured_data, Mapping) else None
        ),
        "confidence": _coerce_confidence(payload.get("confidence")),
    }


def _build_parser_prompt(artifact: AttachmentArtifact) -> str:
    kind = artifact["kind"]
    name = artifact.get("name") or "未命名附件"
    mime_type = artifact.get("mime_type") or "unknown"
    if kind == "image":
        task = "请分析这张图片，提取可见文字，并给出对后续对话最有价值的简要摘要。"
    elif kind == "pdf":
        task = "请阅读这个 PDF，基于已抽取出的文档文本与结构信息给出简要摘要。"
    else:
        task = "请分析这个文件，并给出对后续对话最有价值的简要摘要。"
    return (
        f"你正在为 LangGraph 多模态中间件做附件预处理。附件名：{name}；类型：{kind}；MIME：{mime_type}。"
        f"{task} 请只返回 JSON，不要返回 Markdown，不要加解释。JSON schema: "
        '{"summary_for_model":"string","parsed_text":"string|null","structured_data":{"key_points":["..."]}|null,"confidence":0.0}'
    )


def _build_parser_message(
    artifact: AttachmentArtifact, block: Mapping[str, Any]
) -> HumanMessage:
    normalized_block = _normalize_content_block(block)
    content = [
        {"type": "text", "text": _build_parser_prompt(artifact)},
        normalized_block,
    ]
    return HumanMessage(content=content)


def _extract_pdf_text(
    block: Mapping[str, Any]
) -> tuple[str | None, dict[str, Any] | None]:
    payload = block.get("base64") or block.get("data")
    if not isinstance(payload, str) or not payload.strip():
        return None, {"page_count": 0, "extraction": "missing_base64"}

    try:
        raw_bytes = base64.b64decode(payload)
    except Exception:
        return None, {"page_count": 0, "extraction": "invalid_base64"}

    try:
        pymupdf = importlib.import_module("pymupdf")
        pymupdf4llm = importlib.import_module("pymupdf4llm")
    except ModuleNotFoundError:
        return None, {"page_count": 0, "extraction": "missing_pymupdf4llm_dependency"}

    try:
        doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
    except Exception:
        return None, {"page_count": 0, "extraction": "document_open_error"}

    try:
        chunks = cast(
            list[dict[str, Any]],
            pymupdf4llm.to_markdown(
                doc,
                page_chunks=True,
                ignore_images=True,
                ignore_graphics=False,
                force_text=True,
            ),
        )
    except Exception:
        return None, {"page_count": doc.page_count, "extraction": "pymupdf4llm_error"}
    finally:
        doc.close()

    parts: list[str] = []
    total_tables = 0
    total_images = 0
    toc_items: list[Any] = []
    document_metadata: Mapping[str, Any] | None = None
    for chunk in chunks:
        if document_metadata is None and isinstance(chunk.get("metadata"), Mapping):
            document_metadata = cast(Mapping[str, Any], chunk["metadata"])
        page_text = chunk.get("text")
        if isinstance(page_text, str) and page_text.strip():
            parts.append(page_text.strip())
        tables = chunk.get("tables")
        if isinstance(tables, list):
            total_tables += len(tables)
        images = chunk.get("images")
        if isinstance(images, list):
            total_images += len(images)
        chunk_toc_items = chunk.get("toc_items")
        if isinstance(chunk_toc_items, list) and chunk_toc_items:
            toc_items.extend(chunk_toc_items)

    text = "\n\n".join(parts).strip()
    page_count = len(chunks)
    metadata = {
        "page_count": page_count,
        "extraction": "pymupdf4llm_markdown" if text else "pymupdf4llm_empty_text",
        "tables_count": total_tables,
        "images_count": total_images,
        "toc_items": toc_items,
    }
    if document_metadata is not None:
        title = document_metadata.get("title")
        if isinstance(title, str) and title.strip():
            metadata["title"] = title.strip()
        author = document_metadata.get("author")
        if isinstance(author, str) and author.strip():
            metadata["author"] = author.strip()
    return (text or None), metadata


def _build_pdf_text_summary_prompt(
    artifact: AttachmentArtifact, extracted_text: str
) -> str:
    name = artifact.get("name") or "未命名 PDF"
    preview = extracted_text[:12000]
    return (
        f"你正在为 LangGraph 多模态中间件总结 PDF 文档。文件名：{name}。"
        "下面是从 PDF 中抽取出的文本，请生成 JSON，不要返回 Markdown，不要加解释。"
        'JSON schema: {"summary_for_model":"string","parsed_text":"string|null","structured_data":{"key_points":["..."]}|null,"confidence":0.0}\n\n'
        f"PDF_TEXT:\n{preview}"
    )


def _build_pdf_text_message(
    artifact: AttachmentArtifact, extracted_text: str
) -> HumanMessage:
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": _build_pdf_text_summary_prompt(artifact, extracted_text),
            }
        ]
    )


def _phase2_provenance(existing: Any, *, model_id: str) -> dict[str, Any]:
    provenance: dict[str, Any] = {}
    if isinstance(existing, Mapping):
        for key, value in existing.items():
            provenance[str(key)] = value
    provenance["phase"] = "phase2"
    provenance["processor"] = model_id
    return provenance


def _resolve_parser_transport(model_id: str) -> tuple[str, Any, Any]:
    model = resolve_model_by_id(model_id)
    model_name = getattr(model, "model_name", None)
    root_client = getattr(model, "root_client", None)
    root_async_client = getattr(model, "root_async_client", None)
    if (
        not isinstance(model_name, str)
        or root_client is None
        or root_async_client is None
    ):
        raise ValueError(
            f"Model '{model_id}' is not a ChatOpenAI-compatible parser transport."
        )
    return model_name, root_client, root_async_client


def _extract_openai_response_text(response: Any) -> str:
    try:
        choices = getattr(response, "choices")
        first = choices[0]
        message = first.message
        content = getattr(message, "content", None)
    except Exception:
        return str(response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts)
    return str(content)


def _build_image_parser_payload(
    artifact: AttachmentArtifact, block: Mapping[str, Any]
) -> list[dict[str, Any]]:
    mime_type = artifact.get("mime_type") or _resolve_mime_type(block) or "image/png"
    payload = block.get("base64") or block.get("data")
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError("Missing base64 image payload.")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _build_parser_prompt(artifact)},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{payload}"},
                },
            ],
        }
    ]


def _build_pdf_summary_payload(
    artifact: AttachmentArtifact, extracted_text: str
) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _build_pdf_text_summary_prompt(artifact, extracted_text),
                },
            ],
        }
    ]


def _apply_parser_result(
    artifact: AttachmentArtifact, parsed: ParserResult, *, model_id: str
) -> AttachmentArtifact:
    next_artifact = dict(artifact)
    next_artifact.update(
        summary_for_model=parsed["summary_for_model"],
        parsed_text=parsed["parsed_text"],
        structured_data=parsed["structured_data"],
        confidence=parsed["confidence"],
        status="parsed",
    )
    next_artifact["provenance"] = _phase2_provenance(
        next_artifact.get("provenance"), model_id=model_id
    )
    next_artifact["error"] = None
    return cast(AttachmentArtifact, next_artifact)


def _build_failed_artifact(
    artifact: AttachmentArtifact, error_message: str, *, model_id: str
) -> AttachmentArtifact:
    next_artifact = dict(artifact)
    next_artifact["status"] = "failed"
    next_artifact["summary_for_model"] = error_message
    next_artifact["provenance"] = _phase2_provenance(
        next_artifact.get("provenance"), model_id=model_id
    )
    next_artifact["error"] = {"message": error_message}
    return cast(AttachmentArtifact, next_artifact)


def _parse_attachment_with_model(
    artifact: AttachmentArtifact, block: Mapping[str, Any], *, model_id: str
) -> AttachmentArtifact:
    if artifact["kind"] not in {"image", "pdf"}:
        return artifact
    model_name, root_client, _ = _resolve_parser_transport(model_id)
    if artifact["kind"] == "pdf":
        extracted_text, pdf_meta = _extract_pdf_text(block)
        if not extracted_text:
            message = "PDF 文本抽取失败或为空，当前解析链路无法继续。"
            failed = _build_failed_artifact(artifact, message, model_id=model_id)
            if pdf_meta is not None:
                failed["structured_data"] = pdf_meta
            return failed
        try:
            response = root_client.chat.completions.create(
                model=model_name,
                messages=_build_pdf_summary_payload(artifact, extracted_text),
                stream=False,
            )
        except Exception as exc:
            failed = _build_failed_artifact(
                artifact, f"PDF 摘要生成失败：{exc}", model_id=model_id
            )
            failed["parsed_text"] = extracted_text[:12000]
            if pdf_meta is not None:
                failed["structured_data"] = pdf_meta
            return failed
        parsed = _parse_model_response(_extract_openai_response_text(response))
        structured_data = dict(parsed.get("structured_data") or {})
        if pdf_meta is not None:
            structured_data.update(pdf_meta)
        parsed["structured_data"] = structured_data or None
        if parsed["parsed_text"] is None:
            parsed["parsed_text"] = extracted_text[:12000]
        return _apply_parser_result(artifact, parsed, model_id=model_id)
    try:
        response = root_client.chat.completions.create(
            model=model_name,
            messages=_build_image_parser_payload(artifact, block),
            stream=False,
        )
    except Exception as exc:
        return _build_failed_artifact(
            artifact, f"附件解析失败：{exc}", model_id=model_id
        )
    parsed = _parse_model_response(_extract_openai_response_text(response))
    return _apply_parser_result(artifact, parsed, model_id=model_id)


async def _aparse_attachment_with_model(
    artifact: AttachmentArtifact, block: Mapping[str, Any], *, model_id: str
) -> AttachmentArtifact:
    if artifact["kind"] not in {"image", "pdf"}:
        return artifact
    model_name, _, root_async_client = _resolve_parser_transport(model_id)
    if artifact["kind"] == "pdf":
        extracted_text, pdf_meta = _extract_pdf_text(block)
        if not extracted_text:
            message = "PDF 文本抽取失败或为空，当前解析链路无法继续。"
            failed = _build_failed_artifact(artifact, message, model_id=model_id)
            if pdf_meta is not None:
                failed["structured_data"] = pdf_meta
            return failed
        try:
            response = await root_async_client.chat.completions.create(
                model=model_name,
                messages=_build_pdf_summary_payload(artifact, extracted_text),
                stream=False,
            )
        except Exception as exc:
            failed = _build_failed_artifact(
                artifact, f"PDF 摘要生成失败：{exc}", model_id=model_id
            )
            failed["parsed_text"] = extracted_text[:12000]
            if pdf_meta is not None:
                failed["structured_data"] = pdf_meta
            return failed
        parsed = _parse_model_response(_extract_openai_response_text(response))
        structured_data = dict(parsed.get("structured_data") or {})
        if pdf_meta is not None:
            structured_data.update(pdf_meta)
        parsed["structured_data"] = structured_data or None
        if parsed["parsed_text"] is None:
            parsed["parsed_text"] = extracted_text[:12000]
        return _apply_parser_result(artifact, parsed, model_id=model_id)
    try:
        response = await root_async_client.chat.completions.create(
            model=model_name,
            messages=_build_image_parser_payload(artifact, block),
            stream=False,
        )
    except Exception as exc:
        return _build_failed_artifact(
            artifact, f"附件解析失败：{exc}", model_id=model_id
        )
    parsed = _parse_model_response(_extract_openai_response_text(response))
    return _apply_parser_result(artifact, parsed, model_id=model_id)


class MultimodalMiddleware(AgentMiddleware[AgentState[Any], Any]):
    state_schema = MultimodalAgentState

    def __init__(
        self,
        *,
        parser_model_id: str = DEFAULT_MULTIMODAL_MODEL_ID,
        parser: AttachmentParser | None = None,
        async_parser: AsyncAttachmentParser | None = None,
    ) -> None:
        self._parser_model_id = parser_model_id
        self._parser = parser
        self._async_parser = async_parser

    @staticmethod
    def _build_state(
        messages: Sequence[Any], current_state: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        state = dict(current_state or {})
        artifacts = collect_current_turn_attachment_artifacts(messages)
        summary = build_multimodal_summary(artifacts)
        if artifacts:
            state[MULTIMODAL_ATTACHMENTS_KEY] = artifacts
        else:
            state.pop(MULTIMODAL_ATTACHMENTS_KEY, None)
        if summary:
            state[MULTIMODAL_SUMMARY_KEY] = summary
        else:
            state.pop(MULTIMODAL_SUMMARY_KEY, None)
        return state

    def _parse_artifacts(
        self, messages: Sequence[Any], current_state: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        state = self._build_state(messages, current_state)
        artifacts = cast(
            list[AttachmentArtifact], state.get(MULTIMODAL_ATTACHMENTS_KEY) or []
        )
        if not artifacts:
            return state
        parsed_artifacts: list[AttachmentArtifact] = []
        latest_message = get_latest_human_message_with_attachments(messages)
        if latest_message is None:
            return state
        content = _get_message_content(latest_message)
        next_index = 0
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, Mapping):
                    continue
                artifact = build_attachment_artifact(item, next_index + 1)
                if artifact is None:
                    continue
                base_artifact = artifacts[next_index]
                if base_artifact["kind"] not in {"image", "pdf"}:
                    parsed = base_artifact
                elif self._parser is not None:
                    try:
                        parsed = self._parser(base_artifact, item)
                    except Exception as exc:
                        parsed = _build_failed_artifact(
                            base_artifact,
                            f"附件解析失败：{exc}",
                            model_id=self._parser_model_id,
                        )
                else:
                    parsed = _parse_attachment_with_model(
                        base_artifact, item, model_id=self._parser_model_id
                    )
                parsed_artifacts.append(parsed)
                next_index += 1
        state[MULTIMODAL_ATTACHMENTS_KEY] = parsed_artifacts
        summary = build_multimodal_summary(parsed_artifacts)
        if summary:
            state[MULTIMODAL_SUMMARY_KEY] = summary
        else:
            state.pop(MULTIMODAL_SUMMARY_KEY, None)
        return state

    async def _aparse_artifacts(
        self, messages: Sequence[Any], current_state: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        state = self._build_state(messages, current_state)
        artifacts = cast(
            list[AttachmentArtifact], state.get(MULTIMODAL_ATTACHMENTS_KEY) or []
        )
        if not artifacts:
            return state
        parsed_artifacts: list[AttachmentArtifact] = []
        latest_message = get_latest_human_message_with_attachments(messages)
        if latest_message is None:
            return state
        content = _get_message_content(latest_message)
        next_index = 0
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, Mapping):
                    continue
                artifact = build_attachment_artifact(item, next_index + 1)
                if artifact is None:
                    continue
                base_artifact = artifacts[next_index]
                if base_artifact["kind"] not in {"image", "pdf"}:
                    parsed = base_artifact
                elif self._async_parser is not None:
                    try:
                        parsed = await self._async_parser(base_artifact, item)
                    except Exception as exc:
                        parsed = _build_failed_artifact(
                            base_artifact,
                            f"附件解析失败：{exc}",
                            model_id=self._parser_model_id,
                        )
                elif self._parser is not None:
                    try:
                        parsed = self._parser(base_artifact, item)
                    except Exception as exc:
                        parsed = _build_failed_artifact(
                            base_artifact,
                            f"附件解析失败：{exc}",
                            model_id=self._parser_model_id,
                        )
                else:
                    parsed = await _aparse_attachment_with_model(
                        base_artifact, item, model_id=self._parser_model_id
                    )
                parsed_artifacts.append(parsed)
                next_index += 1
        state[MULTIMODAL_ATTACHMENTS_KEY] = parsed_artifacts
        summary = build_multimodal_summary(parsed_artifacts)
        if summary:
            state[MULTIMODAL_SUMMARY_KEY] = summary
        else:
            state.pop(MULTIMODAL_SUMMARY_KEY, None)
        return state

    def before_model(
        self, state: AgentState[Any], runtime: Any
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages", [])
        next_state = self._build_state(messages, state)
        updates: dict[str, Any] = {}
        for key in (MULTIMODAL_ATTACHMENTS_KEY, MULTIMODAL_SUMMARY_KEY):
            if state.get(key) != next_state.get(key):
                updates[key] = next_state.get(key)
        return updates or None

    def _augment_request(
        self,
        request: ModelRequest,
        next_state: Mapping[str, Any] | None = None,
    ) -> ModelRequest:
        normalized_messages = normalize_messages(request.messages)
        resolved_state = dict(
            next_state
            or MultimodalMiddleware._build_state(normalized_messages, request.state)
        )
        rewritten_messages = _rewrite_latest_human_message_for_model(
            normalized_messages,
            cast(
                list[AttachmentArtifact],
                resolved_state.get(MULTIMODAL_ATTACHMENTS_KEY) or [],
            ),
        )
        summary = cast(str | None, resolved_state.get(MULTIMODAL_SUMMARY_KEY))
        system_message = build_multimodal_system_message(
            request.system_message, summary
        )
        return request.override(
            messages=rewritten_messages,
            state=cast(AgentState[Any], resolved_state),
            system_message=system_message,
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        normalized_messages = normalize_messages(request.messages)
        next_state = self._parse_artifacts(normalized_messages, request.state)
        return handler(self._augment_request(request=request, next_state=next_state))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        normalized_messages = normalize_messages(request.messages)
        next_state = await self._aparse_artifacts(normalized_messages, request.state)
        return await handler(
            self._augment_request(request=request, next_state=next_state)
        )


__all__ = [
    "AttachmentArtifact",
    "AttachmentKind",
    "AttachmentStatus",
    "MULTIMODAL_ATTACHMENTS_KEY",
    "MULTIMODAL_SUMMARY_KEY",
    "DEFAULT_MULTIMODAL_MODEL_ID",
    "MultimodalAgentState",
    "MultimodalMiddleware",
    "ParserResult",
    "build_attachment_artifact",
    "build_multimodal_summary",
    "build_multimodal_system_message",
    "collect_attachment_artifacts",
    "normalize_message_content",
    "normalize_messages",
    "_resolve_parser_transport",
]

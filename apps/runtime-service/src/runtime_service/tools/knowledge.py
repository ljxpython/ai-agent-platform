"""Project knowledge results are projected before Adapter/model/checkpoint conversion."""

import json
from typing import Literal

from langchain_core.messages import ToolMessage
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel, ConfigDict, Field, model_validator

from runtime_service.runtime.mcp_config import knowledge_sources_version

KNOWLEDGE_TOOL = "mcp_query_project_knowledge"


class _Source(BaseModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    document_id: str = Field(pattern=r"^kd_[a-f0-9]{32}$")
    chunk_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    title: str = Field(pattern=r"^\[\d{1,2}\] [^/\\\r\n]{1,160}$")
    kind: Literal["knowledge"]
    preview: str = Field(min_length=1)
    truncated: bool = Field(strict=True)


class _Result(BaseModel):
    status: Literal["ok", "no_hit"]
    sources: list[_Source] = Field(max_length=100)


class _Locator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: Literal["page", "slide", "unknown"]
    start: int | None = Field(strict=True, ge=1)
    end: int | None = Field(strict=True, ge=1)
    block_type: Literal["text", "image", "table", "equation"] | None

    @model_validator(mode="after")
    def valid_range(self):
        if self.unit == "unknown":
            if self.start is not None or self.end is not None:
                raise ValueError("unknown_locator_range")
        elif self.start is None or self.end is None or self.start > self.end:
            raise ValueError("invalid_locator_range")
        return self


class _SourceV2(_Source):
    locator: _Locator


class _ResultV2(BaseModel):
    status: Literal["ok", "no_hit"]
    sources_version: Literal[2]
    sources: list[_SourceV2] = Field(max_length=100)


def _safe_error() -> CallToolResult:
    return CallToolResult(
        isError=True,
        content=[
            TextContent(type="text", text='{"code":"knowledge_retrieval_failed"}')
        ],
    )


def _bound_sources(safe: dict, *, max_chars: int | None = None) -> str:
    sources = safe["sources"]
    encoded = json.dumps(safe, ensure_ascii=False)
    while len(encoded.encode()) > 12 * 1024 or (
        max_chars is not None and len(encoded) > max_chars
    ):
        largest = max(sources, key=lambda s: len(s["preview"]))
        if len(largest["preview"]) > 1:
            largest["preview"] = largest["preview"][
                : max(1, len(largest["preview"]) // 2)
            ]
            largest["truncated"] = True
        elif len(sources) > 1:
            sources.pop()
        else:
            raise ValueError("knowledge_output_budget_too_small")
        encoded = json.dumps(safe, ensure_ascii=False)
    return encoded


def project_knowledge_result(result: CallToolResult) -> CallToolResult:
    if not isinstance(result, CallToolResult) or result.isError:
        return _safe_error()
    try:
        if len(result.content) != 1 or not isinstance(result.content[0], TextContent):
            raise ValueError()
        text = result.content[0].text
        if len(text.encode()) > 2 * 1024 * 1024:
            raise ValueError()
        payload = json.loads(text)
        if result.structuredContent is not None and result.structuredContent != payload:
            raise ValueError()
        if not isinstance(payload, dict):
            raise ValueError()
        version = payload.get("sources_version", 1)
        if type(version) is not int or version not in {1, 2}:
            raise ValueError()
        parsed = (_ResultV2 if version == 2 else _Result).model_validate(payload)
        if (parsed.status == "ok") != bool(parsed.sources):
            raise ValueError()
        sources = [s.model_dump() for s in parsed.sources[:8]]
        if len({s["source_id"] for s in sources}) != len(sources):
            raise ValueError()
        for source in sources:
            source["truncated"] |= len(source["preview"]) > 800
            source["preview"] = source["preview"][:800]
        safe = {"status": parsed.status, "sources": sources}
        if version == 2:
            safe["sources_version"] = 2
        encoded = _bound_sources(safe)
        return CallToolResult(
            content=[TextContent(type="text", text=encoded)], structuredContent=safe
        )
    except (ValueError, TypeError):
        return _safe_error()


def fit_knowledge_message(message: ToolMessage, max_chars: int) -> ToolMessage:
    """F04 reduces complete fields, keeping model content and history artifact identical."""
    try:
        artifact = message.artifact["structured_content"]
        safe = project_knowledge_result(
            CallToolResult(
                content=[
                    TextContent(
                        type="text", text=json.dumps(artifact, ensure_ascii=False)
                    )
                ],
                structuredContent=artifact,
            )
        )
        if safe.isError:
            raise ValueError("invalid_knowledge_result")
        encoded = _bound_sources(safe.structuredContent, max_chars=max_chars)
        return message.model_copy(
            update={
                "content": encoded,
                "artifact": {"structured_content": safe.structuredContent},
            }
        )
    except (KeyError, TypeError, ValueError):
        return message.model_copy(
            update={
                "content": '{"code":"knowledge_retrieval_failed"}',
                "artifact": None,
                "status": "error",
            }
        )


async def knowledge_result_interceptor(request, handler):
    if request.name != KNOWLEDGE_TOOL:
        return await handler(request)
    args = {k: v for k, v in request.args.items() if k != "sources_version"}
    version = knowledge_sources_version()
    if version == 2:
        args["sources_version"] = 2
    safe = project_knowledge_result(await handler(request.override(args=args)))
    if not safe.isError and safe.structuredContent.get("sources_version", 1) != version:
        return _safe_error()
    return safe

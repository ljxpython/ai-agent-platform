"""Internal HTTP endpoint for thread title summarization."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from runtime_service.utils.title_summarizer import summarize_thread_title

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/threads/{thread_id}/title", tags=["title-summary"])


class MessagePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str = "user"
    content: str


class SummarizeTitleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    messages: list[MessagePayload] = Field(default_factory=list)


class SummarizeTitleResponse(BaseModel):
    thread_id: str
    title: str


@router.post("/summarize", response_model=SummarizeTitleResponse)
async def summarize_thread_title_endpoint(
    thread_id: str,
    payload: SummarizeTitleRequest,
    authorization: str | None = Header(default=None),
) -> SummarizeTitleResponse:
    """基于提供的首轮对话内容，调用轻量 Agent 提炼不超过 10 字的精炼标题。"""
    if not thread_id or not thread_id.strip():
        raise HTTPException(status_code=400, detail="Invalid thread_id")

    dict_messages = [msg.model_dump() for msg in payload.messages]

    try:
        title = await summarize_thread_title(dict_messages)
        return SummarizeTitleResponse(thread_id=thread_id, title=title)
    except Exception as exc:
        logger.error(
            "title_summary: unexpected error summarizing title for thread %s: %s",
            thread_id,
            exc,
        )
        return SummarizeTitleResponse(thread_id=thread_id, title="新对话")

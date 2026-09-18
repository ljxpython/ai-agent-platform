"""Unit tests for title_summarizer utility."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.language_models import FakeListChatModel

from runtime_service.utils.title_summarizer import (
    clean_generated_title,
    _fallback_extract_title,
    summarize_thread_title,
    build_title_summarizer_agent,
)


def test_clean_generated_title_standard():
    assert clean_generated_title("用户登录架构") == "用户登录架构"


def test_clean_generated_title_with_quotes_and_brackets():
    assert clean_generated_title("《购物车设计》") == "购物车设计"
    assert clean_generated_title("\"秒杀微服务\"") == "秒杀微服务"
    assert clean_generated_title("【系统设计方案】") == "系统设计方案"
    assert clean_generated_title("“数据同步”") == "数据同步"


def test_clean_generated_title_with_prefix():
    assert clean_generated_title("标题：微信登录") == "微信登录"
    assert clean_generated_title("主题: 权限系统") == "权限系统"
    assert clean_generated_title("会话标题:报表导出") == "报表导出"


def test_clean_generated_title_with_punctuation():
    assert clean_generated_title("接口设计完成！") == "接口设计完成"
    assert clean_generated_title("架构方案。") == "架构方案"
    assert clean_generated_title("代码审查，") == "代码审查"


def test_clean_generated_title_max_length_truncation():
    long_title = "一个非常非常非常长的电商平台接口架构改造计划"
    cleaned = clean_generated_title(long_title)
    assert len(cleaned) <= 10
    assert cleaned == "一个非常非常非常长的"


def test_clean_generated_title_empty():
    assert clean_generated_title("") == "新对话"
    assert clean_generated_title("   ") == "新对话"
    assert clean_generated_title("《》") == "新对话"


def test_fallback_extract_title_from_template_prefix():
    messages = [
        {"role": "user", "content": "设计功能方案：电商购物车微服务"},
        {"role": "assistant", "content": "收到，马上设计"},
    ]
    assert _fallback_extract_title(messages) == "电商购物车微服务"


def test_fallback_extract_title_without_colon():
    messages = [
        {"role": "user", "content": "帮我写个排序算法"},
    ]
    assert _fallback_extract_title(messages) == "帮我写个排序算法"


@pytest.mark.anyio
async def test_summarize_thread_title_success():
    fake_model = FakeListChatModel(responses=["《商城登录改造》"])
    agent = build_title_summarizer_agent(model=fake_model)

    messages = [
        {"role": "user", "content": "帮我设计一下商城的用户登录与注册逻辑"},
        {"role": "assistant", "content": "好的，首先我们需要设计 JWT 鉴权..."},
    ]

    title = await summarize_thread_title(messages, agent=agent)
    assert title == "商城登录改造"


@pytest.mark.anyio
async def test_summarize_thread_title_fallback_on_error():
    class BrokenModel(FakeListChatModel):
        async def _agenerate(self, *args, **kwargs):
            raise ConnectionError("Upstream model connection timeout")

    broken_model = BrokenModel(responses=[])
    agent = build_title_summarizer_agent(model=broken_model)

    messages = [
        {"role": "user", "content": "设计功能方案：秒杀库存扣减架构"},
    ]

    # 不应抛出异常，而应优雅降级
    title = await summarize_thread_title(messages, agent=agent)
    assert title == "秒杀库存扣减架构"

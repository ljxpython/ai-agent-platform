"""Title summarizer utility using LangChain standard create_agent paradigm."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_deepseek import ChatDeepSeek

logger = logging.getLogger(__name__)

TITLE_SYSTEM_PROMPT = """你是一个极简会话标题提炼专家。
你的唯一任务是根据用户与AI的首轮对话，提炼出一个高辨识度、高度概括会话主旨的中文标题。

【硬性约束】：
1. 长度绝对不能超过 10 个汉字或字符；
2. 严禁出现任何标点符号（无逗号、句号、冒号、感叹号）；
3. 严禁包含任何书名号《》、双引号""、单引号、括号；
4. 严禁包含废话前缀，如“关于...”、“讨论...”、“...的方案”、“标题：”；
5. 只输出标题纯文本本身，绝不解释。"""


def clean_generated_title(raw_title: str) -> str:
    """强制清洗并截断大模型输出，保证绝对不超过 10 个字符且无多余标点。"""
    if not raw_title:
        return "新对话"
    cleaned = raw_title.strip()
    # 过滤可能携带的“标题：”、“会话标题：”、“主题：”等前缀
    cleaned = re.sub(r"^(标题|会话标题|主题|对话主题)[:：\s]*", "", cleaned)
    # 过滤包裹的首尾标点、书名号、引号、括号
    cleaned = re.sub(r"^[\s\"'《“「(（\[【]+|[\s\"'》”」)）\]】]+$", "", cleaned)
    # 过滤末尾标点
    cleaned = re.sub(r"[。！？!?,，:：；;]+$", "", cleaned)
    # 二次首尾清洗
    cleaned = cleaned.strip()
    if not cleaned:
        return "新对话"
    # 强行截断至 10 个字符
    return cleaned[:10].strip()


def build_title_summarizer_agent(model: BaseChatModel | None = None) -> Any:
    """根据 runtime-service/.env 构建符合 LangChain 范式的轻量 Agent。"""
    if model is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            # 同时也尝试加载上层或本包目录下的 .env
            env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
            if os.path.exists(env_path):
                load_dotenv(env_path)
        except Exception:
            pass

        api_key = os.environ.get("DEEPSEEK_PROXY_API_KEY", "")
        base_url = os.environ.get("DEEPSEEK_PROXY_URL", "http://120.48.180.39:20002/v1")
        model_name = os.environ.get("DEEPSEEK_PROXY_DEFAULT_MODEL", "DeepSeek-V4-Flash")

        model = ChatDeepSeek(
            model=model_name,
            api_key=api_key or "EMPTY",
            base_url=base_url,
            temperature=0.6,
            max_tokens=512,
        )

    return create_agent(
        model=model,
        tools=[],
        system_prompt=TITLE_SYSTEM_PROMPT,
        name="title_summarizer_agent",
    )


def _format_messages_for_agent(
    messages: Sequence[dict[str, Any] | BaseMessage],
) -> list[BaseMessage]:
    """格式化输入对话为明确的提炼指令材料，兼顾会话起初目标与最新讨论进展。"""
    dialogue_lines: list[str] = []
    # 如果会话较长，同时抓取前 2 条（确定初衷）和最近 6 条（反映最新讨论进展）
    if len(messages) > 8:
        selected_messages = list(messages[:2]) + list(messages[-6:])
    else:
        selected_messages = list(messages)
    for msg in selected_messages:
        role = "用户"
        content = ""
        if isinstance(msg, BaseMessage):
            content = str(msg.content).strip()
            if isinstance(msg, HumanMessage):
                role = "用户"
            elif isinstance(msg, AIMessage):
                role = "助手"
            else:
                role = getattr(msg, "type", "系统")
        elif isinstance(msg, dict):
            raw_role = str(msg.get("role", "user")).lower()
            role = "用户" if raw_role in ("user", "human") else "助手" if raw_role in ("assistant", "ai") else "系统"
            content = str(msg.get("content", "")).strip()

        if content:
            cleaned_content = content.replace("\r", " ").replace("\n", " ").strip()
            dialogue_lines.append(f"{role}: {cleaned_content[:200]}")

    if not dialogue_lines:
        return []

    materials = "\n".join(dialogue_lines)
    prompt = f"""【待提炼标题的对话内容如下】：
---
{materials}
---
请严格遵守系统提示，为上述对话提炼一个10字以内的极简中文标题。只输出标题纯文本本身，严禁任何标点，严禁废话："""
    return [HumanMessage(content=prompt)]


def _fallback_extract_title(messages: Sequence[dict[str, Any] | BaseMessage]) -> str:
    """当 LLM 不可用或超时时的保底规则提取。"""
    for msg in messages:
        content = ""
        if isinstance(msg, BaseMessage) and isinstance(msg, HumanMessage):
            content = str(msg.content).strip()
        elif isinstance(msg, dict) and msg.get("role") in ("user", "human"):
            content = str(msg.get("content", "")).strip()
        if content:
            # 清除前后换行
            first_line = content.splitlines()[0].strip()
            # 过滤冒号前缀
            if "：" in first_line:
                parts = first_line.split("：", 1)
                first_line = parts[1].strip() or parts[0].strip()
            elif ":" in first_line:
                parts = first_line.split(":", 1)
                first_line = parts[1].strip() or parts[0].strip()
            return clean_generated_title(first_line)
    return "新对话"


async def summarize_thread_title(
    messages: Sequence[dict[str, Any] | BaseMessage],
    *,
    model: BaseChatModel | None = None,
    agent: Any = None,
) -> str:
    """对外统一异步调用入口，提炼不超过 10 个字符的高精炼会话标题。"""
    if not messages:
        return "新对话"

    formatted_msgs = _format_messages_for_agent(messages)
    if not formatted_msgs:
        return "新对话"

    try:
        title_agent = agent or build_title_summarizer_agent(model=model)
        response = await title_agent.ainvoke({"messages": formatted_msgs})
        msg_list = response.get("messages") or []
        if msg_list:
            last_msg = msg_list[-1]
            raw_title = getattr(last_msg, "content", "")
            if (not raw_title or not str(raw_title).strip()) and hasattr(last_msg, "additional_kwargs"):
                raw_title = last_msg.additional_kwargs.get("reasoning_content", "")
            cleaned = clean_generated_title(str(raw_title))
            if cleaned and cleaned != "新对话":
                return cleaned
        return _fallback_extract_title(messages)
    except Exception as exc:
        logger.warning(
            "title_summarizer: failed to summarize title via agent: %s, falling back to rule extraction",
            exc,
        )
        return _fallback_extract_title(messages)

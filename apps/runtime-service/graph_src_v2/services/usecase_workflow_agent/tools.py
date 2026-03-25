# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

"""usecase_workflow_agent 的工具集合（Tools）。

这个文件是 `usecase_workflow_agent` 的“业务动作层”，主要做三件事：

1) 子智能体调用封装：
   - `run_requirement_analysis_subagent`：基于当前 thread state（尤其是多模态中间件注入的摘要/要点）做需求分析。
   - `run_usecase_review_subagent`：基于当前 thread state（以及最近一次需求分析结果）做用例评审。

2) 工作流快照（snapshot）落盘到对话 state：
   - `record_requirement_analysis`：把“需求分析 JSON”标准化后包装成 `build_workflow_snapshot(...)`。
   - `record_usecase_review`：把“候选用例 + 评审报告”标准化后包装成快照。
   说明：快照的作用是让主 Agent 不必在长对话里靠自然语言回忆状态，而是始终有结构化中间结果可追踪。

3) 最终持久化（带人工确认）：
   - `run_usecase_persist_subagent`：进入最终落库阶段，并在子智能体内部触发 HITL 审批。
   - `persist_approved_usecases`：持久化子智能体内部使用的执行工具，把最终用例 + 附件解析产物写入 `interaction-data-service`。

设计要点：
- 工具参数尽量短：上下文（PDF 摘要/关键信息/最近用户意图/历史工具结果）从 `runtime.state` 中推导，避免把大段文本塞进 tool args。
- 工具返回尽量结构化：返回 JSON 字符串（快照），便于上游 middleware/平台解析与展示。
"""

import json
import os
import copy
import re
from collections.abc import Mapping
from typing import Any

import requests
from graph_src_v2.runtime.options import read_configurable
from graph_src_v2.services.usecase_workflow_agent.schemas import (
    DEFAULT_WORKFLOW_TYPE,
    RequirementAnalysisPayload,
    UsecaseDraftPayload,
    UsecaseReviewPayload,
    UsecaseWorkflowServiceConfig,
    UsecaseWorkflowState,
    build_workflow_snapshot,
)
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool


def build_usecase_workflow_service_config(
    config: Any | None,
) -> UsecaseWorkflowServiceConfig:
    """从 RunnableConfig / 环境变量中读取 interaction-data-service 的配置。

    读取优先级：
    - `configurable`（来自 LangGraph/LangChain 的运行时 config）
    - 环境变量（`INTERACTION_DATA_SERVICE_URL/TOKEN/TIMEOUT_SECONDS`）

    该函数只做“配置归一化”，不做连通性校验。
    """

    configurable = read_configurable(config)
    workflow_type = str(
        configurable.get("usecase_workflow_type", DEFAULT_WORKFLOW_TYPE)
    ).strip() or DEFAULT_WORKFLOW_TYPE
    service_url = str(
        configurable.get("interaction_data_service_url")
        or os.getenv("INTERACTION_DATA_SERVICE_URL")
        or ""
    ).strip() or None
    service_token = str(
        configurable.get("interaction_data_service_token")
        or os.getenv("INTERACTION_DATA_SERVICE_TOKEN")
        or ""
    ).strip() or None
    timeout_raw = (
        configurable.get("interaction_data_service_timeout_seconds")
        or os.getenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS")
        or 10
    )
    try:
        timeout_seconds = int(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = 10
    if timeout_seconds <= 0:
        timeout_seconds = 10
    return UsecaseWorkflowServiceConfig(
        workflow_type=workflow_type,
        interaction_data_service_url=service_url,
        interaction_data_service_token=service_token,
        interaction_data_service_timeout_seconds=timeout_seconds,
    )


def _prepare_subagent_model(model: Any) -> Any:
    prepared_model = model
    if not (hasattr(model, "responses") and hasattr(model, "i")):
        try:
            prepared_model = copy.copy(model)
        except Exception:
            prepared_model = model
    if hasattr(prepared_model, "disable_streaming"):
        setattr(prepared_model, "disable_streaming", True)
    return prepared_model


def _invoke_subagent_with_retry(subagent: Any, payload: dict[str, Any]) -> Any:
    last_exc: Exception | None = None
    for _ in range(2):
        try:
            return subagent.invoke(payload)
        except Exception as exc:
            if not _is_retryable_model_response_error(exc):
                raise
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("subagent_invoke_failed")


def _build_requirement_analysis_subagent(model: Any) -> Any:
    """创建“需求分析子智能体”。

    约束：
    - tools=[]：子智能体不暴露额外工具，避免越权/跑偏
    - system_prompt：强制只输出 JSON（见 `prompts.py`）
    """

    from graph_src_v2.services.usecase_workflow_agent.prompts import (
        REQUIREMENT_ANALYSIS_SUBAGENT_PROMPT,
    )

    return create_agent(
        model=_prepare_subagent_model(model),
        tools=[],
        system_prompt=REQUIREMENT_ANALYSIS_SUBAGENT_PROMPT,
        name="requirement_analysis_subagent",
    )


def _build_usecase_review_subagent(model: Any) -> Any:
    """创建“用例评审子智能体”。

    同样不暴露 tools，只负责把候选用例按规范进行审查并输出 JSON 评审报告。
    """

    from graph_src_v2.services.usecase_workflow_agent.prompts import (
        USECASE_REVIEW_SUBAGENT_PROMPT,
    )

    return create_agent(
        model=_prepare_subagent_model(model),
        tools=[],
        system_prompt=USECASE_REVIEW_SUBAGENT_PROMPT,
        name="usecase_review_subagent",
    )


def _build_usecase_generation_subagent(model: Any) -> Any:
    from graph_src_v2.services.usecase_workflow_agent.prompts import (
        USECASE_GENERATION_SUBAGENT_PROMPT,
    )

    return create_agent(
        model=_prepare_subagent_model(model),
        tools=[],
        system_prompt=USECASE_GENERATION_SUBAGENT_PROMPT,
        name="usecase_generation_subagent",
    )


def _build_usecase_persist_subagent(model: Any, persist_tool: Any) -> Any:
    from graph_src_v2.services.usecase_workflow_agent.prompts import (
        USECASE_PERSIST_SUBAGENT_PROMPT,
    )

    return create_agent(
        model=_prepare_subagent_model(model),
        tools=[persist_tool],
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "persist_approved_usecases": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                        "description": (
                            "Persisting reviewed use cases requires explicit execution approval."
                        ),
                    }
                },
                description_prefix="Use case persistence pending confirmation",
            )
        ],
        system_prompt=USECASE_PERSIST_SUBAGENT_PROMPT,
        name="usecase_persist_subagent",
    )


def _extract_last_text(result: Any) -> str:
    """从子智能体 invoke 的返回中提取“最后一条消息的文本内容”。

    背景：不同运行时/版本下，invoke 的返回可能是：
    - dict（含 `messages`）
    - 对象（有 `.messages` 属性）
    - message.content 可能是 str 或多模态 list[block]
    """

    messages = (
        result.get("messages") if isinstance(result, dict) else getattr(result, "messages", None)
    )
    if not isinstance(messages, list) or not messages:
        return ""
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
                elif isinstance(item, str) and item.strip():
                    parts.append(item.strip())
            if parts:
                return "\n".join(parts).strip()
        elif content is not None:
            text = str(content).strip()
            if text:
                return text
    return ""


def _load_json_object_from_text(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text:
        return None

    candidates = [text]
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        fenced_body = fenced_match.group(1).strip()
        if fenced_body:
            candidates.insert(0, fenced_body)
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        object_body = text[first_brace : last_brace + 1].strip()
        if object_body and object_body not in candidates:
            candidates.insert(0, object_body)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _extract_recent_human_context(messages: list[Any] | None) -> str:
    """从对话历史中提取“最近一次用户意图”的纯文本。

    规则：
    - 从后往前找最近的 `HumanMessage`
    - 如果 content 是 list[block]，优先抽取其中 text block，且过滤掉形如 `[附件: ...]` 的占位
    """

    if not isinstance(messages, list):
        return ""
    parts: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, HumanMessage):
            continue
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            parts.append(content.strip())
            break
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip() and not text.strip().startswith("[附件:"):
                        text_parts.append(text.strip())
            if text_parts:
                parts.append("\n".join(text_parts))
                break
    return "\n".join(parts).strip()


def _get_runtime_state(runtime: ToolRuntime[Any, Any]) -> dict[str, Any]:
    """统一从 ToolRuntime 中获取 state（兼容不同 runtime 实现）。"""

    state = runtime.state if hasattr(runtime, "state") else {}
    return state if isinstance(state, dict) else {}


def _extract_attachment_key_points(state: dict[str, Any]) -> list[str]:
    """从多模态中间件解析出来的附件 structured_data 中提取关键要点。

    依赖字段：
    - state["multimodal_attachments"]: list[AttachmentArtifact]
    - attachment["structured_data"]["key_points"]: list

    这里做了“保守提取”：每个附件最多取前 6 条 key_points，避免上下文过长。
    """

    attachments = state.get("multimodal_attachments")
    if not isinstance(attachments, list):
        return []
    key_points: list[str] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        structured_data = attachment.get("structured_data")
        if not isinstance(structured_data, dict):
            continue
        raw_points = structured_data.get("key_points")
        if not isinstance(raw_points, list):
            continue
        for item in raw_points[:6]:
            text = str(item).strip()
            if text:
                key_points.append(text)
    return key_points


def _extract_recent_ai_text(messages: list[Any] | None) -> str:
    """抽取最近一条 AI 输出的纯文本（排除 HumanMessage）。

    用途：在 review 阶段把“当前候选用例（可能由主 Agent 生成）”作为评审上下文。
    """

    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            continue
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def _is_retryable_model_response_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "null value for 'choices'" in message
        or "no generations found in stream" in message
    )


def _extract_latest_tool_payload(state: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    """从 state.messages 里反向查找最近一次指定 tool 的输出，并解析为 dict。

    注意：LangChain 的 tool message content 往往是字符串，这里要求 content 是 JSON 字符串。
    如果 content 不是合法 JSON / 不是 object，则忽略继续往前找。
    """

    messages = state.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if getattr(message, "type", None) != "tool":
            continue
        if getattr(message, "name", None) != tool_name:
            continue
        payload = _load_json_object_from_text(getattr(message, "content", None))
        if isinstance(payload, dict):
            return payload
    return None


def _extract_latest_review_snapshot(state: dict[str, Any]) -> dict[str, Any] | None:
    messages = state.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if getattr(message, "type", None) != "tool":
            continue
        tool_name = getattr(message, "name", None)
        if tool_name not in {"record_usecase_review", "run_usecase_persist_subagent"}:
            continue
        payload = _load_json_object_from_text(getattr(message, "content", None))
        if not isinstance(payload, dict):
            continue
        if payload.get("stage") == "reviewed_candidate_usecases":
            return payload
    return None


def _extract_latest_generation_snapshot(state: dict[str, Any]) -> dict[str, Any] | None:
    messages = state.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if getattr(message, "type", None) != "tool":
            continue
        if getattr(message, "name", None) != "record_generated_usecases":
            continue
        payload = _load_json_object_from_text(getattr(message, "content", None))
        if isinstance(payload, dict) and payload.get("stage") == "generated_candidate_usecases":
            return payload
    return None

def _derive_requirement_context(runtime: ToolRuntime[Any, Any]) -> str:
    """构造“需求分析子智能体”的输入上下文。

    来源：
    - `multimodal_summary`：多模态中间件从附件/PDF 提炼的高层摘要
    - `ATTACHMENT_KEY_POINTS`：从附件 structured_data 中抽取的关键要点
    - `USER_GOAL`：最近一次用户的文字诉求

    输出是一个短文本块（带 section header），交给子智能体按 JSON schema 输出分析结果。
    """

    state = _get_runtime_state(runtime)
    summary = state.get("multimodal_summary")
    recent_human = _extract_recent_human_context(state.get("messages"))
    key_points = _extract_attachment_key_points(state)
    sections: list[str] = []
    if isinstance(summary, str) and summary.strip():
        sections.append(f"[MULTIMODAL_SUMMARY]\n{summary.strip()}")
    if key_points:
        sections.append("[ATTACHMENT_KEY_POINTS]\n" + "\n".join(f"- {item}" for item in key_points))
    if recent_human:
        sections.append(f"[USER_GOAL]\n{recent_human}")
    return "\n\n".join(sections).strip()


def _derive_generation_context(runtime: ToolRuntime[Any, Any]) -> str:
    state = _get_runtime_state(runtime)
    recent_human = _extract_recent_human_context(state.get("messages"))
    latest_analysis = _extract_latest_tool_payload(state, "run_requirement_analysis_subagent")
    latest_generation_snapshot = _extract_latest_generation_snapshot(state)
    latest_review_snapshot = _extract_latest_review_snapshot(state)
    latest_generation_payload = (
        latest_generation_snapshot.get("payload")
        if isinstance(latest_generation_snapshot, dict)
        else None
    )
    latest_review_payload = (
        latest_review_snapshot.get("payload")
        if isinstance(latest_review_snapshot, dict)
        else None
    )
    sections: list[str] = []
    if recent_human:
        sections.append(f"[USER_REQUEST]\n{recent_human}")
    if isinstance(latest_analysis, dict):
        sections.append(
            "[REQUIREMENT_ANALYSIS]\n" + json.dumps(latest_analysis, ensure_ascii=False)
        )
    if isinstance(latest_generation_payload, dict):
        candidate_usecases = latest_generation_payload.get("candidate_usecases")
        if isinstance(candidate_usecases, dict):
            sections.append(
                "[PREVIOUS_GENERATED_CANDIDATE_USECASES]\n"
                + json.dumps(candidate_usecases, ensure_ascii=False)
            )
    if isinstance(latest_review_payload, dict):
        review_report = latest_review_payload.get("review_report")
        if isinstance(review_report, dict):
            sections.append(
                "[LATEST_REVIEW_REPORT]\n" + json.dumps(review_report, ensure_ascii=False)
            )
        revision_feedback = _coerce_optional_text(
            latest_review_payload.get("human_revision_feedback")
        )
        if revision_feedback:
            sections.append(f"[HUMAN_REVISION_FEEDBACK]\n{revision_feedback}")
    return "\n\n".join(sections).strip()


def _derive_review_context(runtime: ToolRuntime[Any, Any]) -> str:
    """构造“用例评审子智能体”的输入上下文。

    review 上下文由三块拼出来：
    - `USER_REQUEST`：用户最近的诉求（例如“请按需求生成用例并评审/修改”）
    - `CURRENT_CANDIDATE_USECASES`：主 Agent 最近一轮输出的候选用例文本
    - `REQUIREMENT_ANALYSIS`：最近一次需求分析工具输出（JSON），用于对照覆盖
    """

    state = _get_runtime_state(runtime)
    recent_human = _extract_recent_human_context(state.get("messages"))
    recent_ai = _extract_recent_ai_text(state.get("messages"))
    latest_analysis = _extract_latest_tool_payload(state, "run_requirement_analysis_subagent")
    latest_generation_snapshot = _extract_latest_generation_snapshot(state)
    latest_review_snapshot = _extract_latest_review_snapshot(state)
    latest_generation_payload: dict[str, Any] = {}
    if isinstance(latest_generation_snapshot, dict):
        snapshot_payload = latest_generation_snapshot.get("payload")
        if isinstance(snapshot_payload, dict):
            latest_generation_payload = snapshot_payload
    latest_review_payload: dict[str, Any] = {}
    if isinstance(latest_review_snapshot, dict):
        snapshot_payload = latest_review_snapshot.get("payload")
        if isinstance(snapshot_payload, dict):
            latest_review_payload = snapshot_payload
    generated_candidates = latest_generation_payload.get("candidate_usecases")
    recorded_candidates = latest_review_payload.get("candidate_usecases")
    review_report = latest_review_payload.get("review_report")
    revision_feedback = _coerce_optional_text(
        latest_review_payload.get("human_revision_feedback")
    )
    sections: list[str] = []
    if recent_human:
        sections.append(f"[USER_REQUEST]\n{recent_human}")
    if revision_feedback:
        sections.append(f"[HUMAN_REVISION_FEEDBACK]\n{revision_feedback}")
    if isinstance(generated_candidates, dict):
        sections.append(
            "[LATEST_GENERATED_CANDIDATE_USECASES]\n"
            + json.dumps(generated_candidates, ensure_ascii=False)
        )
    if recent_ai and not isinstance(generated_candidates, dict):
        sections.append(f"[CURRENT_CANDIDATE_USECASES]\n{recent_ai}")
    if isinstance(recorded_candidates, dict):
        sections.append(
            "[LATEST_RECORDED_CANDIDATE_USECASES]\n"
            + json.dumps(recorded_candidates, ensure_ascii=False)
        )
    if isinstance(review_report, dict):
        sections.append(
            "[LATEST_REVIEW_REPORT]\n" + json.dumps(review_report, ensure_ascii=False)
        )
    if isinstance(latest_analysis, dict):
        sections.append("[REQUIREMENT_ANALYSIS]\n" + json.dumps(latest_analysis, ensure_ascii=False))
    return "\n\n".join(sections).strip()


def _derive_persist_context(runtime: ToolRuntime[Any, Any]) -> str:
    state = _get_runtime_state(runtime)
    recent_human = _extract_recent_human_context(state.get("messages"))
    latest_review_snapshot = _extract_latest_review_snapshot(state)
    latest_review_payload = (
        latest_review_snapshot.get("payload")
        if isinstance(latest_review_snapshot, dict)
        else None
    )
    latest_review_report = (
        latest_review_payload.get("review_report")
        if isinstance(latest_review_payload, dict)
        else None
    )
    revised_usecases = (
        latest_review_payload.get("revised_usecases")
        if isinstance(latest_review_payload, dict)
        else None
    )
    candidate_usecases = (
        latest_review_payload.get("candidate_usecases")
        if isinstance(latest_review_payload, dict)
        else None
    )
    final_usecases = (
        revised_usecases
        if isinstance(revised_usecases, dict) and isinstance(revised_usecases.get("usecases"), list)
        else candidate_usecases
    )
    attachments = state.get("multimodal_attachments")
    attachment_count = len(attachments) if isinstance(attachments, list) else 0
    multimodal_summary = _coerce_optional_text(state.get("multimodal_summary"))

    if not recent_human and not isinstance(final_usecases, dict) and not isinstance(latest_review_report, dict):
        return ""

    sections: list[str] = []
    if recent_human:
        sections.append(f"[USER_CONFIRMATION]\n{recent_human}")
    if isinstance(final_usecases, dict):
        sections.append(
            "[LATEST_REVIEWED_USECASES]\n" + json.dumps(final_usecases, ensure_ascii=False)
        )
    if isinstance(latest_review_report, dict):
        sections.append(
            "[LATEST_REVIEW_REPORT]\n" + json.dumps(latest_review_report, ensure_ascii=False)
        )
    sections.append(
        "[ATTACHMENT_PERSISTENCE_CONTEXT]\n"
        + json.dumps(
            {
                "attachment_count": attachment_count,
                "has_multimodal_summary": bool(multimodal_summary),
                "multimodal_summary": multimodal_summary,
            },
            ensure_ascii=False,
        )
    )
    return "\n\n".join(sections).strip()


def build_requirement_analysis_subagent_tool(model: Any) -> Any:
    """把需求分析子智能体封装成一个 `@tool`。

    关键点：
    - tool 的唯一入参是 runtime（不接收长文本参数）
    - 上下文由 `_derive_requirement_context(runtime)` 从 state 推导
    - 子智能体返回的 JSON 被当成纯文本返回（供主 Agent/下游工具解析）
    """

    subagent = _build_requirement_analysis_subagent(model)

    @tool(
        "run_requirement_analysis_subagent",
        description="Run the requirement-analysis specialist using the current thread state, multimodal summary, and attachment key points. Do not pass document text manually.",
    )
    def run_requirement_analysis_subagent(
        runtime: ToolRuntime[None, UsecaseWorkflowState],
    ) -> str:
        requirement_context = _derive_requirement_context(runtime)
        if not requirement_context:
            raise ValueError("requirement_context is required")
        result = _invoke_subagent_with_retry(
            subagent,
            {"messages": [HumanMessage(content=requirement_context)]},
        )
        return _extract_last_text(result)

    return run_requirement_analysis_subagent


def build_usecase_generation_subagent_tool(model: Any) -> Any:
    subagent = _build_usecase_generation_subagent(model)

    @tool(
        "run_usecase_generation_subagent",
        description="Run the usecase-generation specialist using the current thread state, latest requirement analysis, and revision feedback. Do not pass long candidate-usecase text manually.",
    )
    def run_usecase_generation_subagent(
        runtime: ToolRuntime[None, UsecaseWorkflowState],
    ) -> str:
        generation_context = _derive_generation_context(runtime)
        if not generation_context:
            raise ValueError("generation_context is required")
        result = _invoke_subagent_with_retry(
            subagent,
            {"messages": [HumanMessage(content=generation_context)]},
        )
        return _extract_last_text(result)

    return run_usecase_generation_subagent


def build_usecase_review_subagent_tool(model: Any) -> Any:
    """把用例评审子智能体封装成一个 `@tool`。

    与需求分析工具同理：上下文从 state 推导，避免参数膨胀。
    """

    subagent = _build_usecase_review_subagent(model)

    @tool(
        "run_usecase_review_subagent",
        description="Run the usecase-review specialist using the current thread state, latest requirement analysis, and latest candidate use cases. Do not pass long review text manually.",
    )
    def run_usecase_review_subagent(
        runtime: ToolRuntime[None, UsecaseWorkflowState],
    ) -> str:
        review_context = _derive_review_context(runtime)
        if not review_context:
            raise ValueError("review_context is required")
        result = _invoke_subagent_with_retry(
            subagent,
            {"messages": [HumanMessage(content=review_context)]},
        )
        return _extract_last_text(result)

    return run_usecase_review_subagent


def build_usecase_persist_subagent_tool(model: Any) -> Any:
    @tool(
        "run_usecase_persist_subagent",
        description="Prepare the final persistence plan from the latest reviewed use cases, explicit user confirmation, and attachment state. Do not pass long persistence payloads manually.",
    )
    def run_usecase_persist_subagent(
        runtime: ToolRuntime[None, UsecaseWorkflowState],
    ) -> str:
        state = _get_runtime_state(runtime)
        persist_context = _derive_persist_context(runtime)
        if not persist_context:
            raise ValueError("persist_context is required")
        subagent = _build_usecase_persist_subagent(
            model,
            _build_persist_execution_tool(state),
        )
        try:
            result = _invoke_subagent_with_retry(
                subagent,
                {"messages": [HumanMessage(content=persist_context)]},
            )
            return _extract_last_text(result)
        except Exception as exc:
            if not _is_retryable_model_response_error(exc):
                raise
            latest_snapshot = _extract_latest_review_snapshot(state) or {}
            payload_data = latest_snapshot.get("payload")
            fallback_payload = payload_data if isinstance(payload_data, dict) else {}
            return json.dumps(
                _build_persist_plan_from_review_payload(fallback_payload, approval_note=""),
                ensure_ascii=False,
            )

    return run_usecase_persist_subagent


def _coerce_optional_text(value: Any) -> str | None:
    """把任意值尽量转成可选字符串：None/空白 -> None。"""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_optional_float(value: Any) -> float | None:
    """把任意值尽量转成可选 float；失败则返回 None。"""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_mapping(value: Any) -> dict[str, Any] | None:
    """把 Mapping 规范化成 `dict[str, Any]`，否则返回 None。"""

    if not isinstance(value, Mapping):
        return None
    return {str(key): item for key, item in value.items()}


def _normalize_error_payload(value: Any) -> dict[str, Any] | None:
    """把 error 字段统一成 dict 形态，便于服务端存储。"""

    payload = _coerce_mapping(value)
    if payload is not None:
        return payload
    text = _coerce_optional_text(value)
    return {"message": text} if text else None


def _normalize_requirement_analysis(payload: dict[str, Any]) -> RequirementAnalysisPayload:
    """标准化需求分析 JSON。

    由于 LLM 输出可能缺字段/字段类型飘，这里把若干关键字段强制归一成 list。
    """

    normalized = RequirementAnalysisPayload(payload)
    for key in [
        "requirements",
        "business_rules",
        "preconditions",
        "edge_cases",
        "exception_scenarios",
        "open_questions",
    ]:
        value = normalized.get(key)
        if not isinstance(value, list):
            normalized[key] = []
    return normalized


def _normalize_usecase_draft(payload: dict[str, Any]) -> UsecaseDraftPayload:
    """标准化候选用例草稿：确保 `usecases` 为 list。"""

    normalized = UsecaseDraftPayload(payload)
    if not isinstance(normalized.get("usecases"), list):
        normalized["usecases"] = []
    return normalized


def _normalize_usecase_review(payload: dict[str, Any]) -> UsecaseReviewPayload:
    """标准化用例评审报告：确保若干字段为 list。"""

    normalized = UsecaseReviewPayload(payload)
    for key in ["deficiencies", "strengths", "revision_suggestions"]:
        value = normalized.get(key)
        if not isinstance(value, list):
            normalized[key] = []
    return normalized


def _build_persist_plan_from_review_payload(
    payload_data: dict[str, Any], approval_note: str
) -> dict[str, Any]:
    revised_usecases = payload_data.get("revised_usecases")
    revised_payload = revised_usecases if isinstance(revised_usecases, dict) else {}
    candidate_usecases = payload_data.get("candidate_usecases")
    candidate_payload = candidate_usecases if isinstance(candidate_usecases, dict) else {}
    usecase_payload = _normalize_usecase_draft(
        {
            "workflow_id": payload_data.get("workflow_id"),
            "project_id": payload_data.get("project_id"),
            "usecases": (
                revised_payload.get("usecases") or candidate_payload.get("usecases") or []
            ),
        }
    )
    return {
        "summary": "Prepared fallback persistence plan from the latest reviewed use cases.",
        "workflow_id": usecase_payload.get("workflow_id"),
        "project_id": usecase_payload.get("project_id"),
        "approval_note": approval_note,
        "document_persistence_requested": True,
        "final_usecases": usecase_payload.get("usecases") or [],
    }


def _normalize_persist_plan(
    payload: dict[str, Any],
    *,
    fallback_payload: dict[str, Any],
    approval_note: str,
) -> dict[str, Any]:
    fallback_plan = _build_persist_plan_from_review_payload(fallback_payload, approval_note)
    final_usecases = payload.get("final_usecases")
    if not isinstance(final_usecases, list):
        final_usecases = fallback_plan["final_usecases"]

    document_persistence_requested = payload.get("document_persistence_requested")
    if not isinstance(document_persistence_requested, bool):
        document_persistence_requested = bool(fallback_plan["document_persistence_requested"])

    return {
        "summary": _coerce_optional_text(payload.get("summary")) or fallback_plan["summary"],
        "workflow_id": _coerce_optional_text(payload.get("workflow_id")) or fallback_plan["workflow_id"],
        "project_id": _coerce_optional_text(payload.get("project_id")) or fallback_plan["project_id"],
        "approval_note": _coerce_optional_text(payload.get("approval_note")) or approval_note,
        "document_persistence_requested": document_persistence_requested,
        "final_usecases": final_usecases,
    }


def _build_runtime_persistence_config() -> UsecaseWorkflowServiceConfig:
    """构造持久化所需的 service_config。

    当前实现使用一个“空 configurable”，意味着：
    - 运行时不从 thread config 读取持久化地址/鉴权
    - 主要依赖环境变量（`INTERACTION_DATA_SERVICE_URL/TOKEN/...`）

    如果你希望在不同 assistant / 不同租户下动态指定服务地址，通常会把 runtime.config 透传进来。
    """

    return build_usecase_workflow_service_config({"configurable": {}})


def _persist_approved_usecases_from_state(
    state: dict[str, Any],
    *,
    approval_note: str = "",
    revision_feedback: str = "",
) -> str:
    latest_snapshot = _extract_latest_review_snapshot(state)
    if latest_snapshot is None:
        raise ValueError("latest reviewed usecase snapshot is missing")
    snapshot_payload = latest_snapshot.get("payload")
    payload_data = snapshot_payload if isinstance(snapshot_payload, dict) else {}
    normalized_feedback = _coerce_optional_text(revision_feedback)
    if normalized_feedback:
        payload = _normalize_usecase_draft(
            {
                "workflow_id": payload_data.get("workflow_id"),
                "project_id": payload_data.get("project_id"),
                "usecases": (
                    (payload_data.get("revised_usecases") or {}).get("usecases")
                    if isinstance(payload_data.get("revised_usecases"), dict)
                    else None
                )
                or (
                    (payload_data.get("candidate_usecases") or {}).get("usecases")
                    if isinstance(payload_data.get("candidate_usecases"), dict)
                    else None
                )
                or [],
            }
        )
        review_report_payload = payload_data.get("review_report")
        review_report = _normalize_usecase_review(
            review_report_payload if isinstance(review_report_payload, dict) else {}
        )
        deficiency_count = payload_data.get("deficiency_count")
        deficiency_total = (
            deficiency_count
            if isinstance(deficiency_count, int)
            else len(review_report.get("deficiencies") or [])
        )
        return json.dumps(
            build_workflow_snapshot(
                workflow_type=DEFAULT_WORKFLOW_TYPE,
                stage="reviewed_candidate_usecases",
                summary="Human reviewer requested revisions before persistence.",
                persistable=False,
                next_action="revise_and_review_again",
                payload={
                    "workflow_id": payload_data.get("workflow_id"),
                    "project_id": payload_data.get("project_id"),
                    "candidate_usecase_count": len(payload["usecases"]),
                    "deficiency_count": max(1, deficiency_total),
                    "candidate_usecases": payload,
                    "review_report": review_report,
                    "revised_usecases": payload_data.get("revised_usecases"),
                    "approval_note": approval_note,
                    "human_revision_feedback": normalized_feedback,
                },
            ),
            ensure_ascii=False,
        )
    latest_persist_plan = _extract_latest_tool_payload(state, "run_usecase_persist_subagent")
    persist_plan = _normalize_persist_plan(
        latest_persist_plan if isinstance(latest_persist_plan, dict) else {},
        fallback_payload=payload_data,
        approval_note=approval_note,
    )
    payload = _normalize_usecase_draft(
        {
            "workflow_id": persist_plan.get("workflow_id"),
            "project_id": persist_plan.get("project_id"),
            "usecases": persist_plan.get("final_usecases") or [],
        }
    )
    project_id = payload.get("project_id") if isinstance(payload.get("project_id"), str) else None
    usecase_count = len(payload["usecases"])
    service_config = _build_runtime_persistence_config()
    # 当前工作流不会先在 interaction-data-service 创建 usecase_workflows 主记录，
    # 所以真实落库时不能把内存里的 workflow_id 直接传给外部服务。
    persisted_workflow_id = None
    if persist_plan["document_persistence_requested"]:
        document_persistence_result = _persist_requirement_documents_to_interaction_service(
            state=state,
            project_id=project_id,
            workflow_id=persisted_workflow_id,
            service_config=service_config,
        )
    else:
        document_persistence_result = {
            "document_delivery_status": "skipped_by_plan",
            "persisted_document_items": [],
        }
    persistence_result = _persist_usecases_to_interaction_service(
        payload=payload,
        workflow_id=persisted_workflow_id,
        approval_note=str(persist_plan.get("approval_note") or ""),
        service_config=service_config,
    )
    persistence_result.update(document_persistence_result)
    return json.dumps(
        build_workflow_snapshot(
            workflow_type=DEFAULT_WORKFLOW_TYPE,
            stage="persisted",
            summary="Approved use cases have been persisted.",
            persistable=True,
            next_action="workflow_completed",
            payload={
                "approval_note": persist_plan.get("approval_note") or "",
                "persist_plan": persist_plan,
                "persistence_result": persistence_result,
                "final_usecase_count": usecase_count,
                "final_usecases": payload,
                "human_revision_feedback": normalized_feedback,
            },
        ),
        ensure_ascii=False,
    )


def _build_persist_execution_tool(state: dict[str, Any]) -> Any:
    @tool(
        "persist_approved_usecases",
        description=(
            "Persist the final approved use cases only after the user explicitly confirms the "
            "current version is ready. If human revision feedback is supplied during edit, "
            "return to review instead of persisting."
        ),
    )
    def persist_approved_usecases_for_subagent(
        approval_note: str = "",
        revision_feedback: str = "",
    ) -> str:
        return _persist_approved_usecases_from_state(
            state,
            approval_note=approval_note,
            revision_feedback=revision_feedback,
        )

    return persist_approved_usecases_for_subagent


def _build_service_headers(service_config: UsecaseWorkflowServiceConfig) -> dict[str, str]:
    """构造调用 interaction-data-service 的请求头。"""

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if service_config.interaction_data_service_token:
        headers["Authorization"] = (
            f"Bearer {service_config.interaction_data_service_token}"
        )
    return headers


def _build_service_base_url(service_config: UsecaseWorkflowServiceConfig) -> str | None:
    """对 base_url 做 strip/normalize，空值返回 None。"""

    base_url = service_config.interaction_data_service_url
    return base_url.rstrip("/") if isinstance(base_url, str) and base_url.strip() else None


def _post_service_json(
    *,
    service_config: UsecaseWorkflowServiceConfig,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """POST JSON 到 interaction-data-service。

    - 统一处理 base_url 缺失
    - `raise_for_status()` 让错误直接冒泡（由上游决定是否重试/兜底）
    """

    base_url = _build_service_base_url(service_config)
    if not base_url:
        raise RuntimeError("interaction_data_service_not_configured")
    response = requests.post(
        f"{base_url}{path}",
        headers=_build_service_headers(service_config),
        json=payload,
        timeout=service_config.interaction_data_service_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _build_requirement_document_payloads(
    *,
    state: dict[str, Any],
    project_id: str | None,
    workflow_id: str | None,
) -> list[dict[str, Any]]:
    """把多模态中间件解析出来的附件 artifacts 转成“文档持久化”payload。

    输入依赖：
    - state["multimodal_attachments"]：每个附件包含 parsed_text/structured_data/provenance 等

    输出：每个附件对应一个 payload，供 interaction-data-service 记录“需求文档解析产物”。
    """

    if not isinstance(project_id, str) or not project_id.strip():
        return []
    attachments = state.get("multimodal_attachments")
    if not isinstance(attachments, list):
        return []

    multimodal_summary = _coerce_optional_text(state.get("multimodal_summary")) or ""
    payloads: list[dict[str, Any]] = []
    for attachment in attachments:
        if not isinstance(attachment, Mapping):
            continue
        filename = (
            _coerce_optional_text(attachment.get("name"))
            or _coerce_optional_text(attachment.get("attachment_id"))
            or "attachment"
        )
        content_type = _coerce_optional_text(attachment.get("mime_type")) or "application/octet-stream"
        source_kind = (
            _coerce_optional_text(attachment.get("kind"))
            or _coerce_optional_text(attachment.get("source_type"))
            or "upload"
        )
        parse_status = _coerce_optional_text(attachment.get("status")) or "unprocessed"
        payloads.append(
            {
                "project_id": project_id,
                "workflow_id": workflow_id,
                "filename": filename,
                "content_type": content_type,
                "storage_path": None,
                "source_kind": source_kind,
                "parse_status": parse_status,
                "summary_for_model": (
                    _coerce_optional_text(attachment.get("summary_for_model"))
                    or multimodal_summary
                    or f"Parsed {source_kind} attachment."
                ),
                "parsed_text": _coerce_optional_text(attachment.get("parsed_text")),
                "structured_data": _coerce_mapping(attachment.get("structured_data")),
                "provenance": _coerce_mapping(attachment.get("provenance")) or {},
                "confidence": _coerce_optional_float(attachment.get("confidence")),
                "error": _normalize_error_payload(attachment.get("error")),
            }
        )
    return payloads


def _persist_requirement_documents_to_interaction_service(
    *,
    state: dict[str, Any],
    project_id: str | None,
    workflow_id: str | None,
    service_config: UsecaseWorkflowServiceConfig,
) -> dict[str, Any]:
    """把附件解析产物（需求文档）写入 interaction-data-service。

    这是一个“best-effort”能力：
    - 未配置服务/缺少 project_id/没有附件时不会报错，而是返回一个状态码（便于快照记录）
    - 真正发起 HTTP 时，错误会抛出（`requests.raise_for_status()`）
    """

    base_url = service_config.interaction_data_service_url
    if not base_url:
        return {
            "document_delivery_status": "not_configured",
            "persisted_document_items": [],
        }

    if not isinstance(project_id, str) or not project_id.strip():
        return {
            "document_delivery_status": "missing_project_id",
            "persisted_document_items": [],
        }

    document_payloads = _build_requirement_document_payloads(
        state=state,
        project_id=project_id,
        workflow_id=workflow_id,
    )
    if not document_payloads:
        return {
            "document_delivery_status": "no_attachments",
            "persisted_document_items": [],
        }

    persisted_document_items = [
        _post_service_json(
            service_config=service_config,
            path="/api/usecase-generation/workflows/documents",
            payload=document_payload,
        )
        for document_payload in document_payloads
    ]
    return {
        "document_delivery_status": "persisted",
        "persisted_document_items": persisted_document_items,
    }


def _persist_usecases_to_interaction_service(
    *,
    payload: UsecaseDraftPayload,
    workflow_id: str | None,
    approval_note: str,
    service_config: UsecaseWorkflowServiceConfig,
) -> dict[str, Any]:
    """把用例列表逐条写入 interaction-data-service。"""

    base_url = service_config.interaction_data_service_url
    if not base_url:
        return {
            "delivery_status": "not_configured",
            "persisted_items": [],
            "approval_note": approval_note,
        }

    usecases = payload.get("usecases")
    if not isinstance(usecases, list):
        return {
            "delivery_status": "missing_usecases",
            "persisted_items": [],
            "approval_note": approval_note,
        }

    project_id = payload.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        return {
            "delivery_status": "missing_project_id",
            "persisted_items": [],
            "approval_note": approval_note,
        }

    persisted_items: list[dict[str, Any]] = []
    for item in usecases:
        if not isinstance(item, dict):
            continue
        persisted_items.append(
            _post_service_json(
                service_config=service_config,
                path="/api/usecase-generation/use-cases",
                payload={
                    "project_id": project_id,
                    "workflow_id": workflow_id,
                    "title": str(item.get("title") or "Untitled use case"),
                    "description": str(item.get("description") or ""),
                    "status": str(item.get("status") or "active"),
                    "content_json": item,
                },
            )
        )

    return {
        "delivery_status": "persisted",
        "persisted_items": persisted_items,
        "approval_note": approval_note,
    }


@tool(
    "record_requirement_analysis",
    description="Record one structured requirement-analysis snapshot for the current workflow before draft use cases are finalized.",
)
def record_requirement_analysis(
    runtime: ToolRuntime[None, UsecaseWorkflowState],
) -> str:
    """把最近一次 `run_requirement_analysis_subagent` 的结果记录成快照（JSON 字符串）。

    为什么不直接让子智能体输出快照？
    - 子智能体的职责是“做分析”，而快照 schema 属于“工作流协议”，放在主工具层更稳定
    - 同时这里可以对 LLM 输出做归一化（缺字段/类型不对时兜底）
    """

    state = _get_runtime_state(runtime)
    latest = _extract_latest_tool_payload(state, "run_requirement_analysis_subagent")
    if latest is None:
        raise ValueError("latest requirement analysis result is missing")
    payload = _normalize_requirement_analysis(latest)
    requirement_count = len(payload["requirements"])
    snapshot = build_workflow_snapshot(
        workflow_type=DEFAULT_WORKFLOW_TYPE,
        stage="requirement_analysis",
        summary=str(payload.get("summary") or "Requirement analysis captured."),
        persistable=False,
        next_action="run_usecase_generation_subagent",
        payload={
            "workflow_id": payload.get("workflow_id"),
            "project_id": payload.get("project_id"),
            "requirement_count": requirement_count,
            "analysis": payload,
        },
    )
    return json.dumps(snapshot, ensure_ascii=False)


@tool(
    "record_generated_usecases",
    description="Record one generated candidate-usecase snapshot before the review stage starts.",
)
def record_generated_usecases(
    runtime: ToolRuntime[None, UsecaseWorkflowState],
) -> str:
    state = _get_runtime_state(runtime)
    latest = _extract_latest_tool_payload(state, "run_usecase_generation_subagent")
    if latest is None:
        raise ValueError("latest generated usecase result is missing")
    payload = _normalize_usecase_draft(
        {
            "workflow_id": latest.get("workflow_id") or state.get("workflow_id"),
            "project_id": latest.get("project_id")
            or state.get("project_id")
            or state.get("latest_snapshot", {}).get("payload", {}).get("project_id"),
            "usecases": latest.get("usecases") or latest.get("candidate_usecases") or [],
        }
    )
    snapshot = build_workflow_snapshot(
        workflow_type=DEFAULT_WORKFLOW_TYPE,
        stage="generated_candidate_usecases",
        summary=str(latest.get("summary") or "Candidate use cases generated and ready for review."),
        persistable=False,
        next_action="run_usecase_review_subagent",
        payload={
            "workflow_id": payload.get("workflow_id"),
            "project_id": payload.get("project_id"),
            "candidate_usecase_count": len(payload["usecases"]),
            "candidate_usecases": payload,
        },
    )
    return json.dumps(snapshot, ensure_ascii=False)


@tool(
    "record_usecase_review",
    description="Record candidate use cases together with the review report and revision suggestions before asking the user for confirmation.",
)
def record_usecase_review(
    runtime: ToolRuntime[None, UsecaseWorkflowState],
) -> str:
    """把最近一次 `run_usecase_review_subagent` 的结果记录成快照。

    该快照既保存候选用例，也保存评审报告（deficiencies/strengths/suggestions）。
    并根据 deficiency_count 推断：
    - `persistable=True`：可进入最终确认（等待用户决定是否落库）
    - `persistable=False`：先返回 review 结果并等待用户给出修订意见
    """

    state = _get_runtime_state(runtime)
    latest = _extract_latest_tool_payload(state, "run_usecase_review_subagent")
    if latest is None:
        raise ValueError("latest usecase review result is missing")
    latest_generation_snapshot = _extract_latest_generation_snapshot(state)
    latest_generation_payload = (
        latest_generation_snapshot.get("payload")
        if isinstance(latest_generation_snapshot, dict)
        else None
    )
    generated_candidates = (
        latest_generation_payload.get("candidate_usecases")
        if isinstance(latest_generation_payload, dict)
        else None
    )
    candidates = _normalize_usecase_draft(
        {
            "workflow_id": state.get("workflow_id"),
            "project_id": state.get("project_id") or state.get("latest_snapshot", {}).get("payload", {}).get("project_id"),
            "usecases": latest.get("candidate_usecases")
            or (generated_candidates.get("usecases") if isinstance(generated_candidates, dict) else [])
            or [],
        }
    )
    review = _normalize_usecase_review(latest)
    revised = None
    usecase_count = len(candidates["usecases"])
    deficiency_count = len(review["deficiencies"])
    workflow_id = (
        candidates.get("workflow_id")
        if isinstance(candidates.get("workflow_id"), str)
        else (
            revised.get("workflow_id")
            if isinstance(revised, dict) and isinstance(revised.get("workflow_id"), str)
            else None
        )
    )
    snapshot = build_workflow_snapshot(
        workflow_type=DEFAULT_WORKFLOW_TYPE,
        stage="reviewed_candidate_usecases",
        summary=str(review.get("summary") or "Candidate use cases reviewed and ready for user inspection."),
        persistable=deficiency_count == 0,
        next_action=(
            "await_user_confirmation"
            if deficiency_count == 0
            else "await_user_revision"
        ),
        payload={
            "workflow_id": workflow_id,
            "project_id": candidates.get("project_id"),
            "candidate_usecase_count": usecase_count,
            "deficiency_count": deficiency_count,
            "candidate_usecases": candidates,
            "review_report": review,
            "revised_usecases": revised,
        },
    )
    return json.dumps(snapshot, ensure_ascii=False)


def build_usecase_workflow_tools(model: Any | None = None) -> list[Any]:
    """组装对外暴露的工具列表。

    - model != None：同时提供四个“子智能体调用工具” + 三个“工作流快照工具”
    - model == None：只提供本地工作流工具（便于某些离线/测试场景）
    """

    tools: list[Any] = []
    if model is not None:
        tools.extend(
            [
                build_requirement_analysis_subagent_tool(model),
                build_usecase_generation_subagent_tool(model),
                build_usecase_review_subagent_tool(model),
                build_usecase_persist_subagent_tool(model),
            ]
        )
    tools.extend(
        [
            record_requirement_analysis,
            record_generated_usecases,
            record_usecase_review,
        ]
    )
    return tools


__all__ = [
    "UsecaseWorkflowServiceConfig",
    "build_usecase_workflow_service_config",
    "build_usecase_workflow_tools",
    "build_requirement_analysis_subagent_tool",
    "build_usecase_generation_subagent_tool",
    "build_usecase_persist_subagent_tool",
    "build_usecase_review_subagent_tool",
    "record_requirement_analysis",
    "record_generated_usecases",
    "record_usecase_review",
]

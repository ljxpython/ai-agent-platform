"""Structured detail and classification for runtime/model exceptions.

Inspired by open-swe's error categorization and actionable follow-up model,
adapted for the platform-api runtime gateway boundary.
"""

# 结构化原因机器码的人话映射 (借鉴 open-swe)
REASON_TEXT: dict[str, str] = {
    "provider_overloaded": "大模型上游服务商负载过高，暂未恢复响应",
    "provider_rate_limited": "触发大模型服务商调用频率限制 (Rate Limit)",
    "provider_unavailable": "大模型服务商持续返回服务不可用或内部错误 (5xx)",
    "provider_timeout": "大模型调用超时或网络握手超时",
    "context_too_long": "对话上下文长度超出大模型窗口上限",
    "model_unavailable": "当前工作区未配置或不支持所选模型",
    "sandbox_unreachable": "沙箱运行环境失联或已被销毁",
    "step_limit": "单次任务执行达到最大步数限制 (GraphRecursionError)",
    "runtime.execution_failed": "智能体执行中断或发生不可恢复异常",
    "runtime.loop.detected": "检测到工具调用或模型输出进入死循环",
}

# 结构化恢复操作指引 (Actionable Follow-up)
REASON_FOLLOW_UP: dict[str, str] = {
    "context_too_long": "建议点击左侧新建会话，开启新对话以重置上下文长度。",
    "provider_rate_limited": "模型调用配额超限，请等待 1~2 分钟后再试，或在输入框切换其他可用模型。",
    "provider_overloaded": "服务商服务器繁忙，请稍等片刻后发送新消息继续。",
    "provider_unavailable": "上游接口故障，请核对模型接入配置或稍后重试。",
    "provider_timeout": "响应超时，请重试发送消息或减小单次提示词复杂度。",
    "model_unavailable": "请前往设置检查模型凭据是否有效，或选择其他可用模型。",
    "sandbox_unreachable": "建议刷新页面并重新发起运行以自动重建沙箱。",
    "step_limit": "任务复杂度过高，建议将大任务拆分为小步骤分别指派给智能体。",
    "runtime.loop.detected": "已触发安全保护终止循环，请调整 Prompt 明确停止条件后重试。",
    "runtime.execution_failed": "可点击【查看排障详情】或【复制排障信息】交由运维/开发定位。",
}

# 异常类名映射
_ERROR_TYPE_CODES: dict[str, str] = {
    "RateLimitError": "provider_rate_limited",
    "OverloadedError": "provider_overloaded",
    "APIConnectionError": "provider_unavailable",
    "APIError": "provider_unavailable",
    "APIStatusError": "provider_unavailable",
    "InternalServerError": "provider_unavailable",
    "APITimeoutError": "provider_timeout",
    "ModelCallTimeoutError": "provider_timeout",
    "GraphRecursionError": "step_limit",
    "RecursionError": "step_limit",
    "SandboxConnectionError": "sandbox_unreachable",
    "SandboxUnreachableError": "sandbox_unreachable",
}


def classify_run_error(
    error_code: str | None = None,
    raw_message: str | None = None,
    exc: BaseException | None = None,
) -> dict[str, str]:
    """Classify an error into standardized reason_code, reason_text, and follow_up."""
    matched_code = (error_code or "").strip()

    # 1. 尝试从 Exception 类名和属性推导
    if exc is not None:
        exc_type = type(exc).__name__
        if exc_type in _ERROR_TYPE_CODES:
            matched_code = _ERROR_TYPE_CODES[exc_type]
        status = getattr(exc, "status_code", None)
        if status == 429:
            matched_code = "provider_rate_limited"
        elif status == 529:
            matched_code = "provider_overloaded"
        elif isinstance(status, int) and status >= 500:
            matched_code = "provider_unavailable"

    # 2. 如果仍是泛化错误或空，则基于 haystack 文本匹配
    if not matched_code or matched_code in (
        "runtime.execution_failed",
        "runtime_execution_failed",
        "N/A",
    ):
        haystack = f"{matched_code} {raw_message or ''} {str(exc or '')}".lower()
        if "rate_limit" in haystack or "429" in haystack:
            matched_code = "provider_rate_limited"
        elif "overloaded" in haystack or "529" in haystack:
            matched_code = "provider_overloaded"
        elif (
            "context_length_exceeded" in haystack
            or "prompt is too long" in haystack
            or "context_too_long" in haystack
        ):
            matched_code = "context_too_long"
        elif "model_not_found" in haystack or "model_unavailable" in haystack:
            matched_code = "model_unavailable"
        elif "timeout" in haystack or "timed out" in haystack:
            matched_code = "provider_timeout"
        elif (
            "recursion" in haystack
            or "step_limit" in haystack
            or "graphrecursionerror" in haystack
        ):
            matched_code = "step_limit"
        elif "sandbox" in haystack and (
            "unreachable" in haystack or "lost" in haystack or "failed" in haystack
        ):
            matched_code = "sandbox_unreachable"
        elif "loop" in haystack:
            matched_code = "runtime.loop.detected"
        elif not matched_code:
            matched_code = "runtime.execution_failed"

    reason_text = REASON_TEXT.get(matched_code) or (
        f"执行异常: {raw_message}" if raw_message else "智能体执行未完成，请重试。"
    )
    follow_up = REASON_FOLLOW_UP.get(
        matched_code, REASON_FOLLOW_UP["runtime.execution_failed"]
    )

    return {
        "reason_code": matched_code,
        "reason_text": reason_text,
        "follow_up": follow_up,
    }

import type {
  ModelErrorCode,
  ReasonCode,
  NotificationCode,
  SafeCompletion,
} from "./types";

export interface FailurePresentation {
  title: string;
  detail: string;
  suggestedAction: string;
  actionType: "retry" | "switch_model" | "new_thread" | "inspect" | "none";
}

/**
 * 细粒度模型错误码文案映射
 */
const MODEL_ERROR_MAP: Record<
  ModelErrorCode,
  {
    label: string;
    action: string;
    actionType: FailurePresentation["actionType"];
  }
> = {
  provider_rate_limited: {
    label: "模型服务暂时限流",
    action: "稍后重试",
    actionType: "retry",
  },
  provider_overloaded: {
    label: "模型服务繁忙",
    action: "稍后重试 / 切换模型",
    actionType: "switch_model",
  },
  provider_timeout: {
    label: "模型调用响应超时",
    action: "重新运行 / 切换模型",
    actionType: "switch_model",
  },
  context_too_long: {
    label: "会话上下文超出模型容量限制",
    action: "建议开启新会话或整理上下文",
    actionType: "new_thread",
  },
  provider_auth_failed: {
    label: "模型服务认证失败",
    action: "联系管理员检查模型配置",
    actionType: "none",
  },
  provider_access_denied: {
    label: "模型服务访问被拒绝",
    action: "联系管理员核对权限",
    actionType: "none",
  },
  model_unavailable: {
    label: "模型暂不可用",
    action: "切换模型或稍后重试",
    actionType: "switch_model",
  },
  provider_unavailable: {
    label: "模型服务连接暂时中断",
    action: "检查网络或稍后重试",
    actionType: "retry",
  },
  model_call_failed: {
    label: "模型调用异常",
    action: "重新运行",
    actionType: "retry",
  },
};

/**
 * Reason 业务与运行时原因文案映射
 */
const REASON_CODE_MAP: Record<
  ReasonCode,
  {
    label: string;
    action: string;
    actionType: FailurePresentation["actionType"];
  }
> = {
  runtime_run_timeout: {
    label: "本次运行已超过系统最大时限",
    action: "重新运行",
    actionType: "retry",
  },
  runtime_execution_failed: {
    label: "Agent 未能完成本次执行",
    action: "查看诊断详情",
    actionType: "inspect",
  },
  runtime_graph_step_limit_reached: {
    label: "运行步数达到系统上限",
    action: "调整提示词或增加步数限制",
    actionType: "none",
  },
  runtime_model_call_limit_reached: {
    label: "模型调用次数达到单次运行上限",
    action: "调整提示词或联系管理员",
    actionType: "none",
  },
  runtime_tool_call_limit_reached: {
    label: "工具调用次数达到单次运行上限",
    action: "调整提示词或拆分任务",
    actionType: "none",
  },
  "runtime.model.retry_exhausted": {
    label: "模型服务重试次数耗尽",
    action: "稍后重新运行",
    actionType: "retry",
  },
  "runtime.model.retry_budget_exceeded": {
    label: "模型恢复预算耗尽",
    action: "稍后重新运行",
    actionType: "retry",
  },
  "runtime.model.stream_interrupted": {
    label: "模型输出流中断，内容可能不完整",
    action: "查看轨迹并重试",
    actionType: "inspect",
  },
  "runtime.model.provider_rejected": {
    label: "模型服务拒绝当前请求输入",
    action: "检查提示词内容",
    actionType: "none",
  },
  "runtime.model.fallback_incompatible": {
    label: "备用模型不兼容当前执行要求",
    action: "联系管理员调整模型策略",
    actionType: "none",
  },
  "runtime.workspace.unavailable": {
    label: "工作区环境不可用",
    action: "联系管理员检查工作区",
    actionType: "none",
  },
  "runtime.workspace.execution_unavailable": {
    label: "工作区执行服务未就绪",
    action: "稍后重试",
    actionType: "retry",
  },
  "runtime.workspace.backend_invalid": {
    label: "工作区后端配置无效",
    action: "联系管理员",
    actionType: "none",
  },
  "runtime.workspace.image_invalid": {
    label: "工作区镜像配置无效",
    action: "联系管理员",
    actionType: "none",
  },
  "runtime.workspace.execution_outcome_unknown": {
    label: "工具执行结果无法确认",
    action: "查看诊断详情（谨慎重试有副作用的操作）",
    actionType: "inspect",
  },
};

/**
 * 兜底 notification_code 文案映射
 */
const NOTIFICATION_CODE_MAP: Record<
  NotificationCode,
  {
    label: string;
    action: string;
    actionType: FailurePresentation["actionType"];
  }
> = {
  run_timed_out: {
    label: "任务执行超时",
    action: "重新运行",
    actionType: "retry",
  },
  run_failed: {
    label: "Agent 运行失败",
    action: "查看诊断",
    actionType: "inspect",
  },
  run_failed_step_limit: {
    label: "运行步数超限失败",
    action: "调整参数后重试",
    actionType: "none",
  },
  run_failed_workspace: {
    label: "工作区执行失败",
    action: "查看诊断",
    actionType: "inspect",
  },
  run_failed_provider_rate_limited: {
    label: "模型服务暂时限流",
    action: "稍后重试",
    actionType: "retry",
  },
  run_failed_provider_overloaded: {
    label: "模型服务繁忙",
    action: "稍后重试 / 切换模型",
    actionType: "switch_model",
  },
  run_failed_provider_timeout: {
    label: "模型调用超时",
    action: "重新运行 / 切换模型",
    actionType: "switch_model",
  },
  run_failed_provider_unavailable: {
    label: "模型服务不可用",
    action: "稍后重试",
    actionType: "retry",
  },
  run_failed_provider_auth_failed: {
    label: "模型认证失败",
    action: "联系管理员",
    actionType: "none",
  },
  run_failed_provider_access_denied: {
    label: "模型访问被拒绝",
    action: "联系管理员",
    actionType: "none",
  },
  run_failed_context_too_long: {
    label: "会话上下文超出容量限制",
    action: "开启新会话",
    actionType: "new_thread",
  },
  run_failed_model_unavailable: {
    label: "模型服务暂不可用",
    action: "切换模型",
    actionType: "switch_model",
  },
  run_failed_model_call_failed: {
    label: "模型调用失败",
    action: "重新运行",
    actionType: "retry",
  },
};

/**
 * 细粒度优先策略：解析运行失败的最终呈现
 * 顺序：model_error_code -> reason_code -> notification_code -> status 兜底
 */
export function resolveFailurePresentation(
  completion: Pick<
    SafeCompletion,
    | "status"
    | "reason"
    | "reason_code"
    | "model_error_code"
    | "notification_code"
  >,
): FailurePresentation {
  // 1. 优先尝试 model_error_code
  if (
    completion.model_error_code &&
    MODEL_ERROR_MAP[completion.model_error_code]
  ) {
    const item = MODEL_ERROR_MAP[completion.model_error_code];
    return {
      title: item.label,
      detail: item.label,
      suggestedAction: item.action,
      actionType: item.actionType,
    };
  }

  // 2. 其次尝试 reason_code
  if (completion.reason_code && REASON_CODE_MAP[completion.reason_code]) {
    const item = REASON_CODE_MAP[completion.reason_code];
    return {
      title: item.label,
      detail: item.label,
      suggestedAction: item.action,
      actionType: item.actionType,
    };
  }

  // 3. 再次尝试 notification_code
  if (
    completion.notification_code &&
    NOTIFICATION_CODE_MAP[completion.notification_code]
  ) {
    const item = NOTIFICATION_CODE_MAP[completion.notification_code];
    return {
      title: item.label,
      detail: item.label,
      suggestedAction: item.action,
      actionType: item.actionType,
    };
  }

  // 4. status / reason 兜底
  if (completion.status === "timeout" || completion.reason === "timeout") {
    return {
      title: "任务执行超时",
      detail: "本次运行已超过最大允许时限",
      suggestedAction: "重新运行",
      actionType: "retry",
    };
  }

  return {
    title: "运行未能成功完成",
    detail: "Agent 执行中断或发生未分类错误",
    suggestedAction: "查看诊断详情",
    actionType: "inspect",
  };
}

/**
 * 格式化通知时间戳为易读相对/绝对时间
 */
export function formatNotificationTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return isoString;
    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

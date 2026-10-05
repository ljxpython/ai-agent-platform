/**
 * 定时任务专有错误码人话字典与状态标签
 */

export interface ErrorMappingInfo {
  label: string;
  type: "error" | "warning" | "default";
  description: string;
}

export const ERROR_CODE_MAP: Record<string, ErrorMappingInfo> = {
  scheduled_task_approval_required: {
    label: "需审批中止",
    type: "error",
    description:
      "定时任务处于无人值守状态，智能体触发了人工审批（HITL）工具，系统已自动安全中止执行。",
  },
  scheduled_task_execution_failed: {
    label: "执行异常",
    type: "error",
    description: "智能体图执行过程中抛出未捕获错误，任务已终止。",
  },
  scheduled_task_principal_revoked: {
    label: "凭据失效",
    type: "warning",
    description: "任务创建者账号已失效或凭据被吊销，任务无法继续代行。",
  },
  scheduled_task_project_revoked: {
    label: "项目权限失效",
    type: "warning",
    description: "创建者已被移出当前项目，执行前授权被拒绝。",
  },
  scheduled_task_project_inactive: {
    label: "项目已停用",
    type: "warning",
    description: "当前项目已被归档或处于非活跃状态。",
  },
  scheduled_task_thread_deleted: {
    label: "会话已删除",
    type: "warning",
    description: "所复用的会话 Thread 已被清理删除。",
  },
  scheduled_task_authorization_unavailable: {
    label: "鉴权超时",
    type: "warning",
    description: "平台权限认证服务暂时不可达，出于安全防护未派发执行。",
  },
  thread_action_denied: {
    label: "会话权限不足",
    type: "error",
    description: "当前主体对绑定的 Thread 缺少评论/写入权限。",
  },
  thread_not_found: {
    label: "会话不存在",
    type: "error",
    description: "指定的 Thread ID 未找到。",
  },
  project_not_found: {
    label: "项目不存在",
    type: "error",
    description: "关联的项目不存在。",
  },
};

export function resolveTaskErrorInfo(
  errorCode: string | null | undefined,
): ErrorMappingInfo {
  if (!errorCode) {
    return {
      label: "执行失败",
      type: "error",
      description: "任务执行未成功，未返回具体错误码。",
    };
  }
  return (
    ERROR_CODE_MAP[errorCode] || {
      label: errorCode,
      type: "error",
      description: `发生未知错误 (${errorCode})`,
    }
  );
}

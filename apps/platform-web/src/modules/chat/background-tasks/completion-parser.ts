/**
 * 后台长任务完成通知解析与识别
 * 用于拦截平台服务端派发的 completion run 触发消息，将其转换为居中系统通知微胶囊
 */

export interface BackgroundTaskCompletionInfo {
  taskId: string;
  shortTaskId: string;
  status:
    | "succeeded"
    | "failed"
    | "timed_out"
    | "cancelled"
    | "unknown"
    | string;
  exitCode: number | null;
  rawPrompt: string;
}

export const BACKGROUND_TASK_PROMPT_REGEX =
  /^Workspace background task\s+([a-f0-9-]+)\s+finished:\s+status=([a-z_]+),\s+exit_code=(-?\d+|None|null)/i;

/**
 * 判断指定消息对象或文本是否为服务端派发的后台长任务完成通知
 */
export function isBackgroundTaskCompletionMessage(message: unknown): boolean {
  if (!message || typeof message !== "object") {
    if (typeof message === "string") {
      return BACKGROUND_TASK_PROMPT_REGEX.test(message.trim());
    }
    return false;
  }

  const raw = message as Record<string, unknown>;
  const id = String(raw.id ?? "");
  if (id.startsWith("background:")) {
    return true;
  }

  // 检查 contentBlocks 或 content
  const content = raw.content ?? raw.text;
  if (typeof content === "string") {
    return BACKGROUND_TASK_PROMPT_REGEX.test(content.trim());
  }

  if (Array.isArray(content)) {
    for (const item of content) {
      if (
        typeof item === "string" &&
        BACKGROUND_TASK_PROMPT_REGEX.test(item.trim())
      ) {
        return true;
      }
      if (item && typeof item === "object") {
        const itemObj = item as Record<string, unknown>;
        if (
          typeof itemObj.text === "string" &&
          BACKGROUND_TASK_PROMPT_REGEX.test(itemObj.text.trim())
        ) {
          return true;
        }
      }
    }
  }

  // 检查 raw 中的 blocks
  if (Array.isArray(raw.blocks)) {
    for (const b of raw.blocks) {
      if (b && typeof b === "object") {
        const bObj = b as Record<string, unknown>;
        if (
          typeof bObj.text === "string" &&
          BACKGROUND_TASK_PROMPT_REGEX.test(bObj.text.trim())
        ) {
          return true;
        }
      }
    }
  }

  return false;
}

/**
 * 从消息文本中解析后台长任务完成通知结构
 */
export function parseBackgroundTaskCompletionNotification(
  text: string,
): BackgroundTaskCompletionInfo | null {
  if (!text || typeof text !== "string") return null;
  const match = BACKGROUND_TASK_PROMPT_REGEX.exec(text.trim());
  if (!match) return null;

  const taskId = match[1] ?? "";
  const status = match[2]?.toLowerCase() ?? "unknown";
  const rawExitCode = match[3];
  let exitCode: number | null = null;
  if (rawExitCode && !["none", "null"].includes(rawExitCode.toLowerCase())) {
    const parsed = parseInt(rawExitCode, 10);
    if (!Number.isNaN(parsed)) {
      exitCode = parsed;
    }
  }

  return {
    taskId,
    shortTaskId: taskId.slice(0, 8),
    status,
    exitCode,
    rawPrompt: text.trim(),
  };
}

export type CompletionIconName =
  | "check"
  | "alert"
  | "activity"
  | "x"
  | "sparkle";

export interface TaskCompletionStatusMeta {
  label: string;
  icon: CompletionIconName;
  colorClass: string;
  badgeClass: string;
}

/**
 * 获取任务完成状态的可视化语义配置
 */
export function getTaskCompletionStatusMeta(
  status: string,
): TaskCompletionStatusMeta {
  switch (status.toLowerCase()) {
    case "succeeded":
      return {
        label: "任务执行成功",
        icon: "check",
        colorClass:
          "text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-300 dark:bg-emerald-950/40 dark:border-emerald-800/60",
        badgeClass: "text-emerald-700 dark:text-emerald-400",
      };
    case "failed":
      return {
        label: "任务执行失败",
        icon: "alert",
        colorClass:
          "text-rose-700 bg-rose-50 border-rose-200 dark:text-rose-300 dark:bg-rose-950/40 dark:border-rose-800/60",
        badgeClass: "text-rose-700 dark:text-rose-400",
      };
    case "timed_out":
    case "timeout":
      return {
        label: "任务超时终止",
        icon: "activity",
        colorClass:
          "text-amber-700 bg-amber-50 border-amber-200 dark:text-amber-300 dark:bg-amber-950/40 dark:border-amber-800/60",
        badgeClass: "text-amber-700 dark:text-amber-400",
      };
    case "cancelled":
    case "cancel_requested":
      return {
        label: "任务已取消",
        icon: "x",
        colorClass:
          "text-gray-700 bg-gray-50 border-gray-200 dark:text-gray-300 dark:bg-dark-900 dark:border-dark-700",
        badgeClass: "text-gray-600 dark:text-gray-400",
      };
    default:
      return {
        label: "任务已完成",
        icon: "sparkle",
        colorClass:
          "text-blue-700 bg-blue-50 border-blue-200 dark:text-blue-300 dark:bg-blue-950/40 dark:border-blue-800/60",
        badgeClass: "text-blue-700 dark:text-blue-400",
      };
  }
}

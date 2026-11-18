import type { NotificationItem, NotificationLevel } from "../types";

/**
 * 剔除标题中由于后端/外部系统附加的冗余级别标签，例如 [CRITICAL]、[WARNING] 等
 */
export function cleanNotificationTitle(title: string): string {
  if (!title) return "";
  return title
    .replace(/^\[(CRITICAL|ERROR|WARNING|INFO|已恢复|FATAL)\]\s*/i, "")
    .trim();
}

/**
 * 智能解析通知动作 URL，彻底杜绝无上下文的空会话跳转
 */
export function resolveNotificationActionUrl(
  item: NotificationItem,
): string | null {
  const rawUrl = item.action_url ? item.action_url.trim() : "";

  const meta = item.extra_metadata || {};
  const details = (meta.details as Record<string, unknown>) || {};
  const threadId =
    meta.thread_id || meta.threadId || details.thread_id || details.threadId;

  const traceId =
    meta.trace_id ||
    meta.traceId ||
    meta.fingerprint ||
    details.trace_id ||
    details.traceId;

  // 1. 如果没有提供 action_url
  if (!rawUrl) {
    if (item.level === "critical" || item.level === "error") {
      return traceId
        ? `/workspace/trace-diagnostics?traceId=${encodeURIComponent(String(traceId))}`
        : "/workspace/trace-diagnostics";
    }
    if (item.category === "eval" || item.title.includes("评测集")) {
      return "/workspace/projects";
    }
    return null;
  }

  // 2. 检查是否为通用空白 chat 路径（如 /workspace/chat, /workspace/chat/, http://.../workspace/chat）
  const isGenericChat =
    rawUrl.endsWith("/workspace/chat") ||
    rawUrl.endsWith("/workspace/chat/") ||
    rawUrl.endsWith("/chat") ||
    rawUrl.endsWith("/chat/") ||
    rawUrl.includes("/workspace/chat?") ||
    rawUrl.endsWith("/#/chat");

  if (isGenericChat) {
    if (threadId) {
      return `/workspace/chat/${String(threadId)}`;
    }
    // 无 thread 上下文时，严重或错误告警必须跳转到链路诊断中心排障
    if (item.level === "critical" || item.level === "error") {
      return traceId
        ? `/workspace/trace-diagnostics?traceId=${encodeURIComponent(String(traceId))}`
        : "/workspace/trace-diagnostics";
    }
    if (item.category === "eval" || item.title.includes("评测集")) {
      return "/workspace/projects";
    }
    return "/workspace/trace-diagnostics";
  }

  // 3. 处理带协议的绝对 URL：若为本域，转换为 SPA 内部相对路径
  if (rawUrl.startsWith("http://") || rawUrl.startsWith("https://")) {
    try {
      const parsed = new URL(rawUrl);
      if (parsed.origin === window.location.origin) {
        // 如果是本域的 chat 但同样无 threadId
        const path = parsed.pathname.replace(/\/$/, "");
        if (path === "/workspace/chat" || path === "/chat") {
          if (threadId) return `/workspace/chat/${String(threadId)}`;
          return traceId
            ? `/workspace/trace-diagnostics?traceId=${encodeURIComponent(String(traceId))}`
            : "/workspace/trace-diagnostics";
        }
        return parsed.pathname + parsed.search + parsed.hash;
      }
    } catch {
      // 忽略解析错误，直接走 fallback
    }
  }

  return rawUrl;
}

/**
 * 依据通知类型、状态与级别返回最贴切的行动指引文案与颜色
 */
export function getNotificationActionInfo(item: NotificationItem): {
  label: string;
  colorClass: string;
} {
  const isCompletedTask =
    item.category === "eval" ||
    item.title.includes("已生成完毕") ||
    item.title.includes("生成完毕") ||
    item.title.includes("已完成") ||
    item.title.includes("已就绪") ||
    item.level === "info";

  if (isCompletedTask) {
    return {
      label: item.title.includes("评测集") ? "前往评测集查看" : "立即前往查看",
      colorClass:
        "text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300",
    };
  }

  if (item.level === "critical" || item.level === "error") {
    return {
      label: "立即前往排障排错",
      colorClass:
        "text-rose-600 hover:text-rose-700 dark:text-rose-400 dark:hover:text-rose-300",
    };
  }

  if (item.level === "warning") {
    return {
      label: item.title.includes("未完成") ? "查看原因与重试" : "查看详情",
      colorClass:
        "text-amber-600 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-300",
    };
  }

  return {
    label: "查看详情",
    colorClass:
      "text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300",
  };
}

/**
 * 获取通知级别的 Badge 渲染样式与名称
 */
export function getNotificationLevelBadge(level: NotificationLevel): {
  label: string;
  class: string;
} {
  switch (level) {
    case "critical":
      return {
        label: "严重",
        class:
          "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20 shrink-0 whitespace-nowrap",
      };
    case "error":
      return {
        label: "错误",
        class:
          "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20 shrink-0 whitespace-nowrap",
      };
    case "warning":
      return {
        label: "警告",
        class:
          "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 shrink-0 whitespace-nowrap",
      };
    default:
      return {
        label: "信息",
        class:
          "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 shrink-0 whitespace-nowrap",
      };
  }
}

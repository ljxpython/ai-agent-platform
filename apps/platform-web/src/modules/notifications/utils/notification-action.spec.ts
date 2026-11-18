import { describe, expect, it } from "vitest";
import type { NotificationItem } from "../types";
import {
  cleanNotificationTitle,
  getNotificationActionInfo,
  getNotificationLevelBadge,
  resolveNotificationActionUrl,
} from "./notification-action";

describe("notification-action utilities", () => {
  it.each(["http://localhost:9128", "http://127.0.0.1:9128"])(
    "保留评测服务的跨端口地址：%s",
    (origin) => {
      const actionUrl = origin + "/#/authoring/copilot-candidate";
      const item: NotificationItem = {
        id: "copilot",
        title: "评测候选待审阅",
        content: "",
        level: "info",
        category: "eval",
        status: "unread",
        action_url: actionUrl,
        extra_metadata: {},
        created_at: new Date().toISOString(),
      };
      expect(resolveNotificationActionUrl(item)).toBe(actionUrl);
      item.action_url =
        window.location.origin + "/workspace/evaluation?tab=results";
      expect(resolveNotificationActionUrl(item)).toBe(
        "/workspace/evaluation?tab=results",
      );
    },
  );

  it("cleanNotificationTitle: 剔除 [CRITICAL]、[WARNING] 等前后缀", () => {
    expect(
      cleanNotificationTitle(
        "[CRITICAL] Agent 执行死循环拦截告警：连续 5 次重复调用",
      ),
    ).toBe("Agent 执行死循环拦截告警：连续 5 次重复调用");
    expect(cleanNotificationTitle("[WARNING] 评测集转换未完成")).toBe(
      "评测集转换未完成",
    );
    expect(cleanNotificationTitle("正常标题没有任何前缀")).toBe(
      "正常标题没有任何前缀",
    );
  });

  it("resolveNotificationActionUrl: 空 action_url 的致命告警智能导向链路诊断", () => {
    const item: NotificationItem = {
      id: "1",
      title: "严重故障",
      content: "内容",
      level: "critical",
      category: "system",
      status: "unread",
      action_url: null,
      extra_metadata: { trace_id: "tr-123456" },
      created_at: new Date().toISOString(),
    };
    expect(resolveNotificationActionUrl(item)).toBe(
      "/workspace/trace-diagnostics?traceId=tr-123456",
    );
  });

  it("resolveNotificationActionUrl: 通用空 chat 在无 threadId 时坚决重定向至链路诊断中心", () => {
    const item: NotificationItem = {
      id: "2",
      title: "死循环拦截",
      content: "内容",
      level: "critical",
      category: "system",
      status: "unread",
      action_url: "http://localhost:3000/workspace/chat",
      extra_metadata: { fingerprint: "fp-abc" },
      created_at: new Date().toISOString(),
    };
    expect(resolveNotificationActionUrl(item)).toBe(
      "/workspace/trace-diagnostics?traceId=fp-abc",
    );
  });

  it("resolveNotificationActionUrl: 通用 chat 含有 threadId 时正确拼接会话路径", () => {
    const item: NotificationItem = {
      id: "3",
      title: "单会话报错",
      content: "内容",
      level: "error",
      category: "system",
      status: "unread",
      action_url: "/workspace/chat",
      extra_metadata: { thread_id: "th-778899" },
      created_at: new Date().toISOString(),
    };
    expect(resolveNotificationActionUrl(item)).toBe(
      "/workspace/chat/th-778899",
    );
  });

  it("getNotificationActionInfo: 正确识别评测任务完成与排障动作文案", () => {
    const evalDoneItem: NotificationItem = {
      id: "4",
      title: "评测集【全链路验证】已生成完毕",
      content: "内容",
      level: "info",
      category: "eval",
      status: "unread",
      action_url: "/eval",
      extra_metadata: {},
      created_at: new Date().toISOString(),
    };
    expect(getNotificationActionInfo(evalDoneItem).label).toBe(
      "前往评测集查看",
    );

    const criticalItem: NotificationItem = {
      id: "5",
      title: "死循环拦截",
      content: "内容",
      level: "critical",
      category: "system",
      status: "unread",
      action_url: null,
      extra_metadata: {},
      created_at: new Date().toISOString(),
    };
    expect(getNotificationActionInfo(criticalItem).label).toBe(
      "立即前往排障排错",
    );
  });

  it("getNotificationLevelBadge: 包含防折行样式约束", () => {
    const badge = getNotificationLevelBadge("critical");
    expect(badge.label).toBe("严重");
    expect(badge.class).toContain("shrink-0");
    expect(badge.class).toContain("whitespace-nowrap");
  });
});

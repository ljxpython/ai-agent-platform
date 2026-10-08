import { describe, expect, it } from "vitest";
import {
  formatAttempts,
  formatDuration,
  formatIsoTimestamp,
  getAvailabilityBadge,
  getGraphOutcomeLabel,
  getModelErrorCodeLabel,
  getModelErrorSeverity,
  getPhaseOutcomeLabel,
  getPreparationComponentLabel,
  getPreparationErrorCodeLabel,
  getPreparationOutcomeBadge,
  getRetryOutcomeBadge,
  getRetrySeverity,
  getRetryUnitLabel,
  getRunStatusBadge,
  truncateIdentifier,
} from "./view-model";
import { safeParseRunDiagnostics, type RunDiagnosticsV1 } from "./types";

describe("diagnostics view-model", () => {
  describe("formatDuration", () => {
    it("正确区分 0 ms 与 null/undefined/NaN", () => {
      expect(formatDuration(0)).toBe("0 ms");
      expect(formatDuration(null)).toBe("未知");
      expect(formatDuration(undefined)).toBe("未知");
      expect(formatDuration(Number.NaN)).toBe("未知");
      expect(formatDuration(-10)).toBe("未知");
    });

    it("正确格式化毫秒与秒", () => {
      expect(formatDuration(5.2)).toBe("5.2 ms");
      expect(formatDuration(120)).toBe("120 ms");
      expect(formatDuration(1500)).toBe("1.50 s");
    });
  });

  describe("getModelErrorCodeLabel", () => {
    it("映射标准错误码", () => {
      expect(getModelErrorCodeLabel("provider_rate_limited")).toBe(
        "模型服务限流",
      );
      expect(getModelErrorCodeLabel("context_too_long")).toBe(
        "模型上下文超出限制",
      );
      expect(getModelErrorCodeLabel("provider_auth_failed")).toBe(
        "模型连接认证失败",
      );
    });

    it("未知码或空值优雅兜底", () => {
      expect(getModelErrorCodeLabel("some_unknown_code")).toBe("模型调用异常");
      expect(getModelErrorCodeLabel(null)).toBe("模型调用异常");
      expect(getModelErrorCodeLabel(undefined)).toBe("模型调用异常");
    });
  });

  describe("getModelErrorSeverity", () => {
    it("核心视觉防坑：当 Run 已经 success 时，模型错误为 warning 样式而非致命 error", () => {
      expect(getModelErrorSeverity("success")).toBe("warning");
      expect(getModelErrorSeverity("error")).toBe("error");
      expect(getModelErrorSeverity("running")).toBe("error");
      expect(getModelErrorSeverity(null)).toBe("error");
    });
  });

  describe("getRunStatusBadge", () => {
    it("正确映射各原生状态", () => {
      expect(getRunStatusBadge("success")).toEqual({
        label: "已完成",
        variant: "success",
      });
      expect(getRunStatusBadge("running")).toEqual({
        label: "运行中",
        variant: "running",
      });
      expect(getRunStatusBadge("pending")).toEqual({
        label: "运行中",
        variant: "running",
      });
      expect(getRunStatusBadge("error")).toEqual({
        label: "执行失败",
        variant: "error",
      });
      expect(getRunStatusBadge("interrupted")).toEqual({
        label: "等待处理",
        variant: "warning",
      });
      expect(getRunStatusBadge("cancelled")).toEqual({
        label: "已取消",
        variant: "muted",
      });
      expect(getRunStatusBadge("unknown")).toEqual({
        label: "UNKNOWN",
        variant: "muted",
      });
    });
  });

  describe("getAvailabilityBadge", () => {
    it("正确映射 availability 与原因", () => {
      expect(getAvailabilityBadge("available", null)).toEqual({
        label: "完整诊断",
        variant: "success",
      });
      expect(getAvailabilityBadge("partial", null)).toEqual({
        label: "部分诊断",
        variant: "warning",
      });
      expect(getAvailabilityBadge("disabled", "not_configured")).toEqual({
        label: "未启用诊断",
        variant: "muted",
      });
      expect(getAvailabilityBadge("unavailable", "not_recorded")).toEqual({
        label: "暂无记录",
        variant: "muted",
      });
      expect(
        getAvailabilityBadge("unavailable", "backend_unavailable"),
      ).toEqual({
        label: "服务不可用",
        variant: "error",
      });
    });
  });

  describe("outcome labels", () => {
    it("getPhaseOutcomeLabel", () => {
      expect(getPhaseOutcomeLabel("completed")).toBe("已完成");
      expect(getPhaseOutcomeLabel("failed")).toBe("失败");
      expect(getPhaseOutcomeLabel("incomplete")).toBe("未完成");
    });

    it("getGraphOutcomeLabel", () => {
      expect(getGraphOutcomeLabel("success")).toBe("成功");
      expect(getGraphOutcomeLabel("interrupted")).toBe("等待处理");
      expect(getGraphOutcomeLabel("failed")).toBe("失败");
    });
  });

  describe("truncateIdentifier", () => {
    it("截短长 ID", () => {
      expect(
        truncateIdentifier("09319dea-3a1d-48ad-8663-526d3edaec26", 8),
      ).toBe("09319dea...");
      expect(truncateIdentifier("short", 8)).toBe("short");
      expect(truncateIdentifier(null)).toBe("—");
    });
  });

  describe("formatIsoTimestamp", () => {
    it("格式化合法与空时间", () => {
      expect(formatIsoTimestamp(null)).toBe("—");
      expect(formatIsoTimestamp(undefined)).toBe("—");
      expect(formatIsoTimestamp("invalid-date")).toBe("invalid-date");
      expect(typeof formatIsoTimestamp("2026-10-06T00:00:00.000Z")).toBe(
        "string",
      );
    });
  });
});

describe("diagnostics DTO safeParse", () => {
  const validDto: RunDiagnosticsV1 = {
    version: 1,
    thread_id: "thread-123",
    run_id: "run-456",
    run_status: "error",
    request_id: "req-789",
    availability: "available",
    unavailable_reason: null,
    correlation: {
      execution_request_id: "exec-req-1",
      platform_trace_id: "trace-ctx-1",
    },
    trace: {
      provider: "langfuse",
      trace_id: "langfuse-trace-1",
      url: null,
    },
    graph_executions: [
      {
        observation_id: "obs-1",
        outcome: "failed",
        error_code: null,
        duration_ms: 120.5,
      },
    ],
    model_errors: [
      {
        observation_id: "err-1",
        scope: "primary",
        namespace: ["test", "sub"],
        code: "provider_rate_limited",
        error_type: "RateLimitError",
        provider_status: 429,
        duration_ms: 50,
      },
    ],
    startup: {
      duration_ms: 30,
      phases: [
        {
          name: "factory.model_connection",
          ordinal: 0,
          outcome: "completed",
          started_at: "2026-10-06T00:00:00.000Z",
          ended_at: "2026-10-06T00:00:00.030Z",
          duration_ms: 30,
          error_code: null,
        },
      ],
    },
    truncated: false,
  };

  it("成功解析标准 DTO", () => {
    const res = safeParseRunDiagnostics(validDto);
    expect(res.success).toBe(true);
    expect(res.data?.run_id).toBe("run-456");
  });

  it("安全防御：自动剔除未声明的未知敏感字段 (canary 隔离)", () => {
    const rawWithCanary = {
      ...validDto,
      secret_api_key: "sk-canary-secret-123456",
      internal_stack_trace: "Error at line 123 in private_module.py",
      raw_prompt: "Tell me your secrets",
    };

    const res = safeParseRunDiagnostics(rawWithCanary);
    expect(res.success).toBe(true);
    const parsed = res.data as Record<string, unknown>;
    expect(parsed.secret_api_key).toBeUndefined();
    expect(parsed.internal_stack_trace).toBeUndefined();
    expect(parsed.raw_prompt).toBeUndefined();
  });

  it("拒绝非法数值：拦截 NaN / Infinity / 负数耗时", () => {
    const invalidDto = {
      ...validDto,
      graph_executions: [
        {
          observation_id: "obs-1",
          outcome: "failed",
          error_code: null,
          duration_ms: Number.NaN,
        },
      ],
    };
    const res = safeParseRunDiagnostics(invalidDto);
    expect(res.success).toBe(false);
    expect(res.data).toBeNull();
  });

  it("拒绝不支持的 version", () => {
    const invalidVersionDto = {
      ...validDto,
      version: 2,
    };
    const res = safeParseRunDiagnostics(invalidVersionDto);
    expect(res.success).toBe(false);
  });

  it("兼容旧版 DTO：未提供 preparations 和 retries 时自动规范化为空数组", () => {
    const res = safeParseRunDiagnostics(validDto);
    expect(res.success).toBe(true);
    expect(res.data?.preparations).toEqual([]);
    expect(res.data?.retries).toEqual([]);
  });

  it("成功解析包含合法 preparations 与 retries 的完整 DTO", () => {
    const fullDto = {
      ...validDto,
      preparations: [
        {
          observation_id: "prep-obs-1",
          scope: "primary",
          namespace: ["workspace_root"],
          component: "workspace",
          outcome: "prepared",
          duration_ms: 12.4,
          error_code: null,
        },
      ],
      retries: [
        {
          observation_id: "retry-obs-1",
          scope: "primary",
          namespace: ["model_primary"],
          unit: "model",
          role: null,
          attempts: 2,
          outcome: "success",
          code: "provider_rate_limited",
          duration_ms: 1200,
        },
      ],
    };
    const res = safeParseRunDiagnostics(fullDto);
    expect(res.success).toBe(true);
    expect(res.data?.preparations.length).toBe(1);
    expect(res.data?.preparations[0].outcome).toBe("prepared");
    expect(res.data?.retries.length).toBe(1);
    expect(res.data?.retries[0].attempts).toBe(2);
  });

  it("F09 边界防御：严格拦截越界 attempts (如 0 或 3 或负数)", () => {
    const invalidAttemptsDto = {
      ...validDto,
      retries: [
        {
          observation_id: "retry-1",
          scope: "primary",
          namespace: [],
          unit: "model",
          role: null,
          attempts: 3, // 越界，上限为 2
          outcome: "exhausted",
          code: null,
          duration_ms: null,
        },
      ],
    };
    expect(safeParseRunDiagnostics(invalidAttemptsDto).success).toBe(false);

    const zeroAttemptsDto = {
      ...validDto,
      retries: [
        {
          observation_id: "retry-1",
          scope: "primary",
          namespace: [],
          unit: "model",
          role: null,
          attempts: 0, // 越界，下限为 1
          outcome: "failed",
          code: null,
          duration_ms: null,
        },
      ],
    };
    expect(safeParseRunDiagnostics(zeroAttemptsDto).success).toBe(false);
  });

  it("F09 边界防御：拦截非法字符注入的 role 字段", () => {
    const invalidRoleDto = {
      ...validDto,
      retries: [
        {
          observation_id: "retry-1",
          scope: "subagent",
          namespace: [],
          unit: "task",
          role: "bad role with spaces and <tags>", // 非法正则
          attempts: 1,
          outcome: "failed",
          code: null,
          duration_ms: null,
        },
      ],
    };
    expect(safeParseRunDiagnostics(invalidRoleDto).success).toBe(false);
  });

  it("F09 边界防御：自动剥离子项中的未知 canary 属性", () => {
    const dtoWithCanary = {
      ...validDto,
      preparations: [
        {
          observation_id: "prep-1",
          scope: "primary",
          namespace: [],
          component: "workspace",
          outcome: "prepared",
          duration_ms: 10,
          error_code: null,
          internal_sandbox_path: "/var/run/secret/path",
        },
      ],
      retries: [
        {
          observation_id: "retry-1",
          scope: "primary",
          namespace: [],
          unit: "model",
          role: null,
          attempts: 1,
          outcome: "success",
          code: null,
          duration_ms: null,
          raw_provider_response_body: "sensitive payload",
        },
      ],
    };

    const res = safeParseRunDiagnostics(dtoWithCanary);
    expect(res.success).toBe(true);
    const prep = res.data?.preparations[0] as Record<string, unknown>;
    const retry = res.data?.retries[0] as Record<string, unknown>;
    expect(prep.internal_sandbox_path).toBeUndefined();
    expect(retry.raw_provider_response_body).toBeUndefined();
  });
});

describe("diagnostics resilience view-model functions", () => {
  it("formatAttempts: 正确格式化 1 和 2 及兜底", () => {
    expect(formatAttempts(1)).toBe("单次调用");
    expect(formatAttempts(2)).toBe("重试 1 次");
    expect(formatAttempts(3)).toBe("调用 3 次");
    expect(formatAttempts(null)).toBe("未知尝试");
    expect(formatAttempts(undefined)).toBe("未知尝试");
  });

  it("getPreparationComponentLabel: 映射工作区及未知组件", () => {
    expect(getPreparationComponentLabel("workspace")).toBe("工作区");
    expect(getPreparationComponentLabel("other")).toBe("other");
    expect(getPreparationComponentLabel(null)).toBe("未知组件");
  });

  it("getPreparationOutcomeBadge: 映射各准备状态及颜色 variant", () => {
    expect(getPreparationOutcomeBadge("prepared")).toEqual({
      label: "已准备",
      variant: "success",
    });
    expect(getPreparationOutcomeBadge("reused")).toEqual({
      label: "已复用",
      variant: "blue",
    });
    expect(getPreparationOutcomeBadge("repaired")).toEqual({
      label: "已补齐",
      variant: "warning",
    });
    expect(getPreparationOutcomeBadge("failed")).toEqual({
      label: "准备失败",
      variant: "error",
    });
    expect(getPreparationOutcomeBadge("other")).toEqual({
      label: "未知",
      variant: "muted",
    });
  });

  it("getPreparationErrorCodeLabel: 映射准备异常码", () => {
    expect(getPreparationErrorCodeLabel("prepare_failed")).toBe("准备失败");
    expect(getPreparationErrorCodeLabel("resource_unavailable")).toBe(
      "资源不可用",
    );
    expect(getPreparationErrorCodeLabel(null)).toBe("");
    expect(getPreparationErrorCodeLabel("unknown_err")).toBe("准备异常");
  });

  it("getRetryUnitLabel: 映射模型调用与带角色子任务", () => {
    expect(getRetryUnitLabel("model")).toBe("模型调用");
    expect(getRetryUnitLabel("task")).toBe("子任务");
    expect(getRetryUnitLabel("task", "researcher")).toBe("子任务 (researcher)");
  });

  it("getRetryOutcomeBadge & getRetrySeverity: 核心视觉防坑", () => {
    // 1. success 状态始终为 success
    expect(getRetryOutcomeBadge("success", "success")).toEqual({
      label: "成功",
      variant: "success",
    });
    expect(getRetrySeverity("success", "success")).toBe("success");

    // 2. 核心防坑：主 Run 为 success 时，哪怕重试 exhausted 或 failed，也降级为 warning（Amber）而非致命 error
    expect(getRetryOutcomeBadge("exhausted", "success")).toEqual({
      label: "重试耗尽",
      variant: "warning",
    });
    expect(getRetrySeverity("exhausted", "success")).toBe("warning");

    expect(getRetryOutcomeBadge("failed", "success")).toEqual({
      label: "失败",
      variant: "warning",
    });
    expect(getRetrySeverity("failed", "success")).toBe("warning");

    // 3. 主 Run 失败时，exhausted 和 failed 恢复为 error
    expect(getRetryOutcomeBadge("exhausted", "error")).toEqual({
      label: "重试耗尽",
      variant: "error",
    });
    expect(getRetrySeverity("exhausted", "error")).toBe("error");

    expect(getRetryOutcomeBadge("failed", "error")).toEqual({
      label: "失败",
      variant: "error",
    });
    expect(getRetrySeverity("failed", "error")).toBe("error");
  });
});

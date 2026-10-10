import { describe, it, expect } from "vitest";
import { resolveFailurePresentation } from "./presentation";

describe("Failure Presentation 细粒度降级策略", () => {
  it("优先使用 model_error_code 呈现最细粒度文案与切换模型操作", () => {
    const res = resolveFailurePresentation({
      status: "error",
      reason: "business_error",
      reason_code: "runtime.model.retry_exhausted",
      model_error_code: "provider_overloaded",
      notification_code: "run_failed_provider_overloaded",
    });

    expect(res.title).toBe("模型服务繁忙");
    expect(res.actionType).toBe("switch_model");
  });

  it("当无 model_error_code 时降级使用 reason_code", () => {
    const res = resolveFailurePresentation({
      status: "error",
      reason: "business_error",
      reason_code: "runtime.model.stream_interrupted",
      model_error_code: null,
      notification_code: "run_failed_model_call_failed",
    });

    expect(res.title).toBe("模型输出流中断，内容可能不完整");
    expect(res.actionType).toBe("inspect");
  });

  it("当仅有 notification_code 时正确降级", () => {
    const res = resolveFailurePresentation({
      status: "error",
      reason: "business_error",
      reason_code: null,
      model_error_code: null,
      notification_code: "run_failed_step_limit",
    });

    expect(res.title).toBe("运行步数超限失败");
  });

  it("当仅有 status 为 timeout 时兜底展示超时文案", () => {
    const res = resolveFailurePresentation({
      status: "timeout",
      reason: "timeout",
      reason_code: null,
      model_error_code: null,
      notification_code: null,
    });

    expect(res.title).toBe("任务执行超时");
    expect(res.actionType).toBe("retry");
  });
});

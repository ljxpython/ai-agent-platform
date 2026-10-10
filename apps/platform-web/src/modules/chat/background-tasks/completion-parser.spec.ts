import { describe, expect, it } from "vitest";
import {
  isBackgroundTaskCompletionMessage,
  parseBackgroundTaskCompletionNotification,
  getTaskCompletionStatusMeta,
} from "./completion-parser";

describe("completion-parser", () => {
  const samplePrompt =
    "Workspace background task 34eb5183-5182-4aa8-ab48-e8cb9b7ba409 finished: status=succeeded, exit_code=0. This is task result data. Read background_task for bounded details when needed. Do not start another background task in this completion Run.";

  it("detects completion prompt string correctly", () => {
    expect(isBackgroundTaskCompletionMessage(samplePrompt)).toBe(true);
    expect(isBackgroundTaskCompletionMessage("普通用户提问：你好")).toBe(false);
  });

  it("detects message with background: id prefix", () => {
    expect(
      isBackgroundTaskCompletionMessage({
        id: "background:evt-123",
        content: "some text",
      }),
    ).toBe(true);
  });

  it("detects message with completion prompt in contentBlocks", () => {
    expect(
      isBackgroundTaskCompletionMessage({
        id: "msg-456",
        blocks: [{ text: samplePrompt }],
      }),
    ).toBe(true);
  });

  it("parses valid completion notification correctly", () => {
    const parsed = parseBackgroundTaskCompletionNotification(samplePrompt);
    expect(parsed).not.toBeNull();
    expect(parsed?.taskId).toBe("34eb5183-5182-4aa8-ab48-e8cb9b7ba409");
    expect(parsed?.shortTaskId).toBe("34eb5183");
    expect(parsed?.status).toBe("succeeded");
    expect(parsed?.exitCode).toBe(0);
  });

  it("handles null and None exit_codes gracefully", () => {
    const promptNone =
      "Workspace background task 11111111-2222-3333-4444-555555555555 finished: status=timed_out, exit_code=None.";
    const parsed = parseBackgroundTaskCompletionNotification(promptNone);
    expect(parsed).not.toBeNull();
    expect(parsed?.status).toBe("timed_out");
    expect(parsed?.exitCode).toBeNull();
  });

  it("returns correct visual metadata for different statuses", () => {
    expect(getTaskCompletionStatusMeta("succeeded").icon).toBe("check");
    expect(getTaskCompletionStatusMeta("failed").icon).toBe("alert");
    expect(getTaskCompletionStatusMeta("timed_out").icon).toBe("activity");
    expect(getTaskCompletionStatusMeta("cancelled").icon).toBe("x");
  });
});

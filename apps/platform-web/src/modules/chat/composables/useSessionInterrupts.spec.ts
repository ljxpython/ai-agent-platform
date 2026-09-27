import { computed, effectScope, ref, shallowRef } from "vue";
import type { Run } from "@langchain/langgraph-sdk";
import { expect, it, vi } from "vitest";
import type { createSessionService } from "@/services/threads/session.service";
import type { createRunActions } from "../run-actions";
import { useSessionInterrupts } from "./useSessionInterrupts";

it("does not submit an approval after its interrupt ID changes during verification", async () => {
  const value = {
    action_requests: [{ name: "edit_file", args: { path: "/fixture.txt" } }],
    review_configs: [
      { action_name: "edit_file", allowed_decisions: ["approve", "reject"] },
    ],
  };
  const respondAll = vi.fn();
  const begin = vi.fn();
  const fail = vi.fn();
  const scope = effectScope();
  try {
    const session = scope.run(() =>
      useSessionInterrupts({
        threadId: ref("thread-1"),
        hydrated: ref(true),
        verified: ref(true),
        checking: ref(false),
        error: ref(""),
        run: shallowRef({ run_id: "run-1", status: "interrupted" } as Run),
        canApprove: computed(() => true),
        pendingAction: computed(() => false),
        isDisposed: () => false,
        stream: { interrupts: ref([{ id: "old-id", value }]), respondAll },
        service: {
          state: vi
            .fn()
            .mockResolvedValue({ interrupts: [{ id: "new-id", value }] }),
        } as unknown as ReturnType<typeof createSessionService>,
        actions: { begin, rejectUnsent: vi.fn() } as unknown as ReturnType<
          typeof createRunActions
        >,
        verify: vi.fn(),
        fail,
      }),
    )!;
    await session.approve({ "old-id": [{ type: "approve" }] });
    expect(begin).not.toHaveBeenCalled();
    expect(respondAll).not.toHaveBeenCalled();
    expect(fail).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining("审批请求已变化"),
      }),
    );
    // 验证自愈机制：旧的 old-id 已被自动剔除，不再作为待审批项
    expect(session.resolvedReviewIds.value.has("old-id")).toBe(true);
  } finally {
    scope.stop();
  }
});

it("filters out stale replayed interrupts and retains only authoritative active interrupts", async () => {
  const valueOld = {
    action_requests: [{ name: "old_cmd", args: { cmd: "old" } }],
    review_configs: [
      { action_name: "old_cmd", allowed_decisions: ["approve", "reject"] },
    ],
  };
  const valueNew = {
    action_requests: [{ name: "new_cmd", args: { cmd: "new" } }],
    review_configs: [
      { action_name: "new_cmd", allowed_decisions: ["approve", "reject"] },
    ],
  };
  const respondAll = vi.fn();
  const begin = vi.fn();
  const scope = effectScope();
  try {
    const session = scope.run(() =>
      useSessionInterrupts({
        threadId: ref("thread-1"),
        hydrated: ref(true),
        verified: ref(true),
        checking: ref(false),
        error: ref(""),
        run: shallowRef({ run_id: "run-2", status: "interrupted" } as Run),
        canApprove: computed(() => true),
        pendingAction: computed(() => false),
        isDisposed: () => false,
        stream: {
          interrupts: ref([
            { id: "zombie-id", value: valueOld },
            { id: "active-id", value: valueNew },
          ]),
          respondAll,
        },
        service: {
          state: vi.fn().mockResolvedValue({
            interrupts: [{ id: "active-id", value: valueNew }],
          }),
        } as unknown as ReturnType<typeof createSessionService>,
        actions: { begin, rejectUnsent: vi.fn() } as unknown as ReturnType<
          typeof createRunActions
        >,
        verify: vi.fn(),
        fail: vi.fn(),
      }),
    )!;

    // 手动触发一次权威对齐
    await session.syncAuthoritativeReviews();
    expect(session.reviews.value.map((r) => r.id)).toEqual(["active-id"]);

    // 针对 active-id 提交审批，应顺利通过
    await session.approve({ "active-id": [{ type: "approve" }] });
    expect(begin).toHaveBeenCalledWith(
      "thread-1",
      "resume",
      expect.objectContaining({ "active-id": expect.anything() }),
    );
    expect(respondAll).toHaveBeenCalled();
  } finally {
    scope.stop();
  }
});

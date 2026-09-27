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
  } finally {
    scope.stop();
  }
});

import {
  computed,
  ref,
  watch,
  type ComputedRef,
  type Ref,
  type ShallowRef,
} from "vue";
import type { Run } from "@langchain/langgraph-sdk";
import {
  buildReviewResponses,
  parseReviews,
  type ReviewDraft,
} from "../approvals";
import {
  buildClarificationResponse,
  filterActiveClarifications,
  parseClarifications,
} from "../human-input";
import type { createSessionService } from "@/services/threads/session.service";
import type { createRunActions } from "../run-actions";

export function useSessionInterrupts(deps: {
  threadId: Ref<string | null>;
  hydrated: Ref<boolean>;
  verified: Ref<boolean>;
  checking: Ref<boolean>;
  error: Ref<string>;
  run: ShallowRef<Run | null>;
  canApprove: ComputedRef<boolean>;
  pendingAction: ComputedRef<boolean>;
  isDisposed: () => boolean;
  streamInFlight?: Ref<boolean>;
  stream: {
    interrupts: Ref<
      | readonly { id?: string; value?: unknown; ns?: readonly string[] }[]
      | undefined
    >;
    values?: Ref<unknown>;
    messages?: Ref<readonly unknown[] | undefined>;
    respondAll: (responses: Record<string, unknown>) => Promise<unknown>;
  };
  service: ReturnType<typeof createSessionService>;
  actions: ReturnType<typeof createRunActions>;
  verify: (force?: boolean) => Promise<boolean>;
  fail: (cause: unknown) => void;
}) {
  const resolvedClarificationIds = ref<Set<string>>(new Set());
  const resolvedReviewIds = ref<Set<string>>(new Set());

  watch(
    () => deps.threadId.value,
    () => {
      resolvedClarificationIds.value.clear();
      resolvedReviewIds.value.clear();
    },
  );

  const isInterruptAllowed = computed(() => {
    if (deps.threadId.value && (!deps.hydrated.value || !deps.verified.value)) {
      return false;
    }
    if (deps.run.value != null && deps.run.value.status !== "interrupted") {
      return false;
    }
    return true;
  });

  async function syncAuthoritativeReviews() {
    if (!deps.threadId.value || deps.isDisposed()) return;
    try {
      const state = await deps.service.state(deps.threadId.value);
      if (deps.isDisposed()) return;
      const current = parseReviews(state.interrupts ?? []);
      const activeIds = new Set(current.map((item) => item.id));
      const all = parseReviews(rawInterrupts.value);
      for (const r of all) {
        if (!activeIds.has(r.id)) {
          resolvedReviewIds.value.add(r.id);
        }
      }
    } catch {
      // Best-effort authoritative sync, ignore fetch errors
    }
  }

  watch(
    () => deps.stream.interrupts.value?.length ?? 0,
    (len, prevLen) => {
      if (
        len > 0 &&
        len !== prevLen &&
        deps.run.value?.status !== "interrupted" &&
        !deps.checking.value &&
        deps.threadId.value
      ) {
        void deps.verify(false);
      }
      if (len > 0 && deps.threadId.value) {
        void syncAuthoritativeReviews();
      }
    },
  );

  const rawInterrupts = computed(() => deps.stream.interrupts.value ?? []);
  const reviews = computed(() => {
    if (!isInterruptAllowed.value) return [];
    return parseReviews(rawInterrupts.value).filter(
      (review) => !resolvedReviewIds.value.has(review.id),
    );
  });
  const rawClarifications = computed(() =>
    parseClarifications(rawInterrupts.value),
  );
  const clarifications = computed(() => {
    if (!isInterruptAllowed.value) return [];
    const rawMessages = Array.isArray(
      (deps.stream.values?.value as { messages?: unknown })?.messages,
    )
      ? ((deps.stream.values?.value as { messages?: unknown })
          .messages as readonly unknown[])
      : (deps.stream.messages?.value ?? []);
    if (
      deps.threadId.value &&
      (!deps.hydrated.value || (deps.checking.value && !deps.run.value)) &&
      rawMessages.length === 0
    ) {
      return [];
    }
    return filterActiveClarifications(
      rawClarifications.value,
      rawMessages,
      resolvedClarificationIds.value,
    );
  });

  const hasPendingInterrupts = computed(
    () => reviews.value.length > 0 || clarifications.value.length > 0,
  );

  async function approve(drafts: Record<string, ReviewDraft[]>) {
    if (
      !deps.canApprove.value ||
      deps.checking.value ||
      deps.pendingAction.value ||
      !deps.threadId.value
    )
      return;
    const before = reviews.value;
    deps.checking.value = true;
    deps.error.value = "";
    try {
      const state = await deps.service.state(deps.threadId.value);
      if (deps.isDisposed() || !deps.canApprove.value) return;
      const current = parseReviews(state.interrupts ?? []);
      const activeIds = new Set(current.map((item) => item.id));

      for (const r of before) {
        if (!activeIds.has(r.id)) {
          resolvedReviewIds.value.add(r.id);
        }
      }

      if (
        current.length !== before.length ||
        before.some(
          (review) =>
            !current.some(
              (item) =>
                item.id === review.id &&
                item.fingerprint === review.fingerprint,
            ),
        )
      ) {
        throw new Error("审批请求已变化，请恢复连接后重新确认");
      }
      const responses = buildReviewResponses(current, drafts);
      deps.actions.begin(deps.threadId.value, "resume", responses);
      if (deps.streamInFlight) deps.streamInFlight.value = true;
      deps.run.value = null;
      await deps.stream.respondAll(responses);
      for (const r of current) {
        resolvedReviewIds.value.add(r.id);
      }
      await deps.verify(true);
    } catch (cause) {
      deps.actions.rejectUnsent();
      deps.fail(cause);
    } finally {
      if (deps.streamInFlight) deps.streamInFlight.value = false;
      if (!deps.isDisposed()) deps.checking.value = false;
    }
  }

  async function answerClarification(
    interruptId: string,
    values: Record<string, unknown>,
  ) {
    if (
      !deps.canApprove.value ||
      deps.checking.value ||
      deps.pendingAction.value ||
      !deps.threadId.value
    )
      return;
    const targetClarification = clarifications.value.find(
      (c) => c.id === interruptId,
    );
    if (!targetClarification) return;
    resolvedClarificationIds.value.add(interruptId);
    deps.checking.value = true;
    deps.error.value = "";
    try {
      const response = buildClarificationResponse(
        targetClarification.id,
        values,
        targetClarification.request.schema_version,
        targetClarification.raw,
      );
      deps.actions.begin(deps.threadId.value, "resume", response);
      if (deps.streamInFlight) deps.streamInFlight.value = true;
      deps.run.value = null;
      await deps.stream.respondAll(response);
      await deps.verify(true);
    } catch (cause) {
      resolvedClarificationIds.value.delete(interruptId);
      deps.actions.rejectUnsent();
      deps.fail(cause);
    } finally {
      if (deps.streamInFlight) deps.streamInFlight.value = false;
      if (!deps.isDisposed()) deps.checking.value = false;
    }
  }

  return {
    resolvedClarificationIds,
    resolvedReviewIds,
    reviews,
    clarifications,
    hasPendingInterrupts,
    approve,
    answerClarification,
    resumeClarification: answerClarification,
    syncAuthoritativeReviews,
  };
}

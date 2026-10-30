import { onActivated, onDeactivated, watch } from "vue";
import type { createSessionService } from "@/services/threads/session.service";

export function useThreadActivity(
  projectId: () => string | undefined,
  threadId: () => string | undefined,
  service: () => ReturnType<typeof createSessionService>,
) {
  let active = true;
  const report = () => {
    const thread = threadId();
    if (active && projectId() && thread) {
      void service()
        .activity(thread)
        .catch(() => {
          console.warn("Unable to record session activity");
        });
    }
  };
  watch([projectId, threadId], report, { immediate: true, flush: "post" });
  onActivated(() => {
    const returning = !active;
    active = true;
    if (returning) report();
  });
  onDeactivated(() => {
    active = false;
  });
}

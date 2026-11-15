import { onBeforeUnmount, ref, watch, type Ref } from "vue";
import {
  commandWorkItem,
  readWorkItem,
  type Command,
  type WorkItem,
} from "@/services/evaluation/workbench";
import { extractPlatformHttpError } from "@/utils/http-error";

export function useWorkItem(project: Ref<string>, id: Ref<string>) {
  const item = ref<WorkItem | null>(null);
  const busy = ref(false);
  const loading = ref(false);
  const error = ref("");
  const pending = ref<{ action: string; command: Command } | null>(null);
  let epoch = 0;
  let mutation = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  async function refresh(silent = false) {
    const current = epoch;
    const before = mutation;
    if (!id.value || !project.value || busy.value) return;
    if (!silent) loading.value = true;
    try {
      const value = await readWorkItem(project.value, id.value);
      if (current === epoch && before === mutation) {
        item.value = value;
        error.value = "";
        const request = pending.value;
        if (
          request &&
          value.history?.some(
            (entry) =>
              entry.request_id === request.command.request_id &&
              entry.action === request.action,
          )
        )
          pending.value = null;
      }
    } catch (cause) {
      if (current === epoch && before === mutation) {
        const detail = extractPlatformHttpError(cause);
        error.value = detail.message;
        if (
          detail.status === 401 ||
          detail.status === 403 ||
          detail.status === 404
        )
          item.value = null;
      }
    } finally {
      if (current === epoch) loading.value = false;
    }
  }
  async function act(
    action: string,
    data: Record<string, unknown>,
    retry = false,
  ) {
    if (busy.value || (pending.value && !retry)) return;
    const current = epoch;
    mutation++;
    pending.value ||= {
      action,
      command: {
        request_id: crypto.randomUUID(),
        data: JSON.parse(JSON.stringify(data)),
      },
    };
    const request = pending.value;
    busy.value = true;
    error.value = "";
    try {
      const value = await commandWorkItem(
        project.value,
        id.value,
        request.action,
        request.command,
      );
      if (current !== epoch) return;
      pending.value = null;
      if (action === "revoke") {
        const refreshed = await readWorkItem(project.value, id.value);
        if (current === epoch) item.value = refreshed;
      } else item.value = value;
    } catch (cause) {
      if (current !== epoch) return;
      const detail = extractPlatformHttpError(cause);
      error.value = detail.message;
      if (detail.status && detail.status >= 400 && detail.status < 500)
        pending.value = null;
      if (detail.status === 401 || detail.status === 403) item.value = null;
    } finally {
      if (current === epoch) busy.value = false;
    }
  }
  watch(
    [project, id],
    () => {
      epoch++;
      clearTimeout(timer);
      item.value = null;
      pending.value = null;
      error.value = "";
      busy.value = false;
      const current = epoch;
      async function poll() {
        await refresh(item.value !== null);
        if (current === epoch) timer = setTimeout(poll, 4000);
      }
      void poll();
    },
    { immediate: true },
  );
  onBeforeUnmount(() => {
    epoch++;
    clearTimeout(timer);
  });
  return { item, busy, loading, error, pending, refresh, act };
}

import { computed, ref, watch, type Ref } from "vue";
import { platformHttpClient } from "@/services/http/client";
import { resolvePlatformHttpErrorMessage } from "@/utils/http-error";

export function useEvaluationCapabilities(projectId: Ref<string>) {
  const available = ref(false);
  const authoringUrl = ref("");
  const error = ref("");
  const loading = ref(false);
  watch(
    projectId,
    async (id, _previous, onCleanup) => {
      let cancelled = false;
      onCleanup(() => {
        cancelled = true;
      });
      available.value = false;
      authoringUrl.value = "";
      error.value = "";
      loading.value = Boolean(id);
      if (!id) return;
      try {
        const { data } = await platformHttpClient.get<{
          workbench: boolean;
          authoring_url?: string | null;
        }>("/api/evaluation/capabilities", { headers: { "X-Project-Id": id } });
        if (cancelled) return;
        available.value = data.workbench === true;
        authoringUrl.value = data.authoring_url || "";
      } catch (cause) {
        if (!cancelled)
          error.value = resolvePlatformHttpErrorMessage(
            cause,
            "暂时无法确认评测集转换是否可用。",
            "评测集转换",
          );
      } finally {
        if (!cancelled) loading.value = false;
      }
    },
    { immediate: true },
  );
  const unavailableReason = computed(() =>
    loading.value
      ? "正在确认评测集转换是否可用…"
      : error.value || (available.value ? "" : "当前项目未启用评测集转换。"),
  );
  return { available, authoringUrl, unavailableReason };
}

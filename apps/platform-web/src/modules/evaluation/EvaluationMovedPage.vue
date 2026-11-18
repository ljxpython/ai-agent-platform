<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import EmptyState from "@/components/platform/EmptyState.vue";
import { useEvaluationCapabilities } from "./useEvaluationCapabilities";

const route = useRoute();
const projectId = computed(() => String(route.params.projectId || ""));
const { available, authoringUrl, unavailableReason } =
  useEvaluationCapabilities(projectId);
const destination = computed(() => {
  if (!available.value || !authoringUrl.value) return "";
  try {
    const url = new URL(authoringUrl.value);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password
    )
      return "";
    const itemId = String(route.params.itemId || "");
    if (itemId && !/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(itemId))
      return "";
    url.hash = itemId ? `/authoring/${itemId}` : "/authoring";
    return url.href;
  } catch {
    return "";
  }
});
</script>

<template>
  <section class="pw-page-shell">
    <EmptyState
      icon="activity"
      title="评测操作已移至 EvalFlow"
      description="请在 EvalFlow 中出题、修改、发布、运行和查看结果。Agent 平台保留会话转为评测集入口。历史条目是否可读，以 EvalFlow 的权限与资料状态为准。"
    />
    <a v-if="destination" :href="destination" class="pw-btn pw-btn-primary">
      {{
        route.params.itemId ? "在 EvalFlow 查看原条目" : "打开 EvalFlow 评测集"
      }}
    </a>
    <p v-else role="status">
      {{
        unavailableReason ||
        "未配置有效的 EvalFlow 地址，或条目编号无效。请联系管理员。"
      }}
    </p>
  </section>
</template>

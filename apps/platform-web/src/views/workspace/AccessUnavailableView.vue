<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import EmptyState from "@/components/platform/EmptyState.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import { useWorkspaceStore } from "@/stores/workspace";
const route = useRoute();
const router = useRouter();
const workspace = useWorkspaceStore();
const retrying = ref(false);
async function retry() {
  const target = route.query.returnTo;
  if (
    typeof target !== "string" ||
    !target.startsWith("/workspace/") ||
    retrying.value
  )
    return;
  retrying.value = true;
  try {
    if (workspace.currentProjectId)
      await workspace.refreshCurrentProjectAccess();
    await router.replace(target);
  } catch {
    /* Store 提供具体错误，并保留重试入口。 */
  } finally {
    retrying.value = false;
  }
}
</script>

<template>
  <section class="pw-page-shell">
    <EmptyState
      icon="project"
      :title="
        route.name === 'workspace-not-found'
          ? '页面不存在'
          : route.query.reason === 'unavailable'
            ? '暂时无法确认访问权限'
            : '无法访问此页面'
      "
      :description="
        route.query.reason === 'unavailable'
          ? '连接暂时不可用，请稍后重试。你的登录会话会保留。'
          : workspace.error || '该资源不存在，或当前账号没有访问权限。'
      "
    />
    <div class="flex gap-3">
      <BaseButton
        variant="secondary"
        @click="router.push('/workspace/projects')"
      >
        返回项目列表 </BaseButton
      ><BaseButton
        v-if="route.query.returnTo"
        :disabled="retrying"
        @click="retry"
      >
        重试
      </BaseButton>
    </div>
  </section>
</template>

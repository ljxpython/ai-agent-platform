<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import EmptyState from '@/components/platform/EmptyState.vue'
import BaseButton from '@/components/base/BaseButton.vue'
import { useWorkspaceStore } from '@/stores/workspace'
const route = useRoute()
const router = useRouter()
const workspace = useWorkspaceStore()
function retry() {
  const target = route.query.returnTo
  if (typeof target === 'string' && target.startsWith('/workspace/')) void router.replace(target)
}
</script>

<template>
  <section class="pw-page-shell">
    <EmptyState
      icon="project"
      :title="route.name === 'workspace-not-found' ? '页面不存在' : '无法访问此页面'"
      :description="workspace.error || '该资源不存在，或当前账号没有访问权限。'"
    />
    <div class="flex gap-3">
      <BaseButton
        variant="secondary"
        @click="router.push('/workspace/projects')"
      >
        返回项目列表
      </BaseButton><BaseButton
        v-if="route.query.returnTo"
        @click="retry"
      >
        重试
      </BaseButton>
    </div>
  </section>
</template>

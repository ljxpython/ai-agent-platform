<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { listRuntimeModels, listRuntimeTools } from '@/services/runtime/runtime.service'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()

const loading = ref(false)
const error = ref('')
const modelCount = ref(0)
const toolCount = ref(0)
const modelSyncTime = ref<string | null>(null)
const toolSyncTime = ref<string | null>(null)

const stats = computed(() => [
  {
    label: '模型目录',
    value: modelCount.value,
    hint: modelSyncTime.value ? `最近同步：${modelSyncTime.value}` : '等待首次同步',
    icon: 'runtime',
    tone: 'primary'
  },
  {
    label: '工具目录',
    value: toolCount.value,
    hint: toolSyncTime.value ? `最近同步：${toolSyncTime.value}` : '等待首次同步',
    icon: 'activity',
    tone: 'success'
  },
  {
    label: '目录状态',
    value: error.value ? '需要排查' : '已接通',
    hint: error.value ? '至少有一个目录请求失败' : 'Runtime 基础目录已经纳入新工作台',
    icon: 'shield',
    tone: error.value ? 'warning' : 'danger'
  }
])

async function loadRuntimeOverview() {
  const projectId = workspaceStore.runtimeScopedProjectId
  loading.value = true
  error.value = ''

  const results = await Promise.allSettled([
    listRuntimeModels(projectId),
    listRuntimeTools(projectId)
  ])
  const [modelsResult, toolsResult] = results
  const failedSections: string[] = []

  if (modelsResult.status === 'fulfilled') {
    modelCount.value = Array.isArray(modelsResult.value.models) ? modelsResult.value.models.length : 0
    modelSyncTime.value = modelsResult.value.last_synced_at
  } else {
    modelCount.value = 0
    modelSyncTime.value = null
    failedSections.push('模型目录')
  }

  if (toolsResult.status === 'fulfilled') {
    toolCount.value = Array.isArray(toolsResult.value.tools) ? toolsResult.value.tools.length : 0
    toolSyncTime.value = toolsResult.value.last_synced_at
  } else {
    toolCount.value = 0
    toolSyncTime.value = null
    failedSections.push('工具目录')
  }

  if (failedSections.length) {
    error.value = `Runtime 概览加载失败：${failedSections.join('、')}`
  }

  loading.value = false
}

onMounted(() => {
  void loadRuntimeOverview()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Runtime"
      title="Runtime"
      description="Runtime 先承接模型目录和工具目录两块最关键的可见性能力，避免助手配置和联调继续回旧页面翻数据。"
    >
      <template #actions>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/runtime/models"
        >
          <BaseIcon
            name="runtime"
            size="sm"
          />
          模型目录
        </router-link>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/runtime/tools"
        >
          <BaseIcon
            name="activity"
            size="sm"
          />
          工具目录
        </router-link>
        <router-link
          class="pw-btn pw-btn-secondary"
          to="/workspace/runtime/policies"
        >
          <BaseIcon
            name="shield"
            size="sm"
          />
          策略覆盖
        </router-link>
        <router-link
          class="pw-btn pw-btn-ghost"
          to="/workspace/operations"
        >
          <BaseIcon
            name="activity"
            size="sm"
          />
          Operations
        </router-link>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="Runtime 概览存在缺口"
      :description="error"
      variant="warning"
    />

    <div class="grid gap-4 xl:grid-cols-3">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <div class="grid gap-6 xl:grid-cols-2">
      <SurfaceCard class="space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <BaseIcon
            name="runtime"
            size="sm"
            class="text-primary-500"
          />
          模型目录
        </div>
        <p class="text-sm leading-7 text-gray-500 dark:text-dark-300">
          先把 runtime 暴露出来的模型、默认项和同步状态接进新工作台。后续 assistant 新建和配置页会直接消费这里的数据。
        </p>
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="pw-card-glass p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
              当前目录
            </div>
            <div class="mt-2 text-2xl font-semibold text-gray-950 dark:text-white">
              {{ loading ? '--' : modelCount }}
            </div>
          </div>
          <div class="pw-card-glass p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
              目录入口
            </div>
            <div class="mt-3">
              <router-link
                class="pw-btn pw-btn-ghost"
                to="/workspace/runtime/models"
              >
                打开模型目录
              </router-link>
            </div>
          </div>
        </div>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <BaseIcon
            name="activity"
            size="sm"
            class="text-primary-500"
          />
          工具目录
        </div>
        <p class="text-sm leading-7 text-gray-500 dark:text-dark-300">
          工具来源、描述和同步状态也先统一收回来，后面助手挂工具时不用继续在旧工作区里来回找 source 和 key。
        </p>
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="pw-card-glass p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
              当前目录
            </div>
            <div class="mt-2 text-2xl font-semibold text-gray-950 dark:text-white">
              {{ loading ? '--' : toolCount }}
            </div>
          </div>
          <div class="pw-card-glass p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-dark-400">
              目录入口
            </div>
            <div class="mt-3">
              <router-link
                class="pw-btn pw-btn-ghost"
                to="/workspace/runtime/tools"
              >
                打开工具目录
              </router-link>
            </div>
          </div>
        </div>
      </SurfaceCard>

      <SurfaceCard class="space-y-4 xl:col-span-2">
        <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
          <BaseIcon
            name="shield"
            size="sm"
            class="text-primary-500"
          />
          运行策略治理
        </div>
        <p class="text-sm leading-7 text-gray-500 dark:text-dark-300">
          phase-3 会把项目级模型、工具、图策略覆盖收进统一治理页，同时所有刷新任务都能回流到 operations
          中心追踪，不再靠口头同步。
        </p>
        <div class="flex flex-wrap gap-3">
          <router-link
            class="pw-btn pw-btn-secondary"
            to="/workspace/runtime/policies"
          >
            打开运行策略
          </router-link>
          <router-link
            class="pw-btn pw-btn-ghost"
            to="/workspace/operations"
          >
            查看刷新任务
          </router-link>
        </div>
      </SurfaceCard>
    </div>
  </section>
</template>

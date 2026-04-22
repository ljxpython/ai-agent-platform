<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import KnowledgeWorkspaceNav from '@/modules/knowledge/components/KnowledgeWorkspaceNav.vue'
import { useKnowledgeProjectRoute } from '@/modules/knowledge/composables/useKnowledgeProjectRoute'
import { getProjectKnowledgeSpace, refreshProjectKnowledgeSpace } from '@/services/knowledge/knowledge.service'
import type { ProjectKnowledgeSpace } from '@/types/management'
import { formatDateTime } from '@/utils/format'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

const { projectId, project } = useKnowledgeProjectRoute()
const authorization = useAuthorization()

const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const space = ref<ProjectKnowledgeSpace | null>(null)
const canRead = computed(() => authorization.can('project.knowledge.read', projectId.value))
const canAdmin = computed(() => authorization.can('project.knowledge.admin', projectId.value))

type HealthFactRow = {
  label: string
  value: string
  monospace?: boolean
}

type HealthSection = {
  key: string
  label: string
  raw: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function humanizeKey(key: string) {
  return key
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim()
}

function isSimpleHealthValue(value: unknown) {
  return (
    value === null ||
    ['string', 'number', 'boolean'].includes(typeof value) ||
    (Array.isArray(value) && value.every((item) => item === null || ['string', 'number', 'boolean'].includes(typeof item)))
  )
}

function formatHealthValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '--'
  }

  if (Array.isArray(value)) {
    return value.length ? value.map((item) => formatHealthValue(item)).join(', ') : '--'
  }

  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }

  if (typeof value === 'number' || typeof value === 'string') {
    return String(value)
  }

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function readHealthValue(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key]
    if (value !== undefined && value !== null && value !== '') {
      return value
    }
  }

  return undefined
}

const workspaceBindingRows = computed(() => {
  if (!space.value) {
    return []
  }

  return [
    {
      label: 'project_id',
      value: projectId.value || '--',
      valueClass: 'font-mono text-xs'
    },
    {
      label: 'workspace_key',
      value: space.value.workspace_key,
      valueClass: 'font-mono text-xs'
    },
    {
      label: '治理链路',
      value: 'platform-web → platform-api → LightRAG',
      valueClass: 'text-right break-words'
    },
    {
      label: '运行地址',
      value: space.value.service_base_url,
      valueClass: 'text-right break-all'
    }
  ]
})
const healthPayload = computed<Record<string, unknown> | null>(() => {
  return isRecord(space.value?.health) ? space.value.health : null
})
const healthStatusLabel = computed(() => {
  const payload = healthPayload.value
  if (!payload) {
    return 'unknown'
  }

  const status = readHealthValue(payload, ['status', 'state', 'health', 'result'])
  if (typeof status === 'string') {
    return status
  }

  const healthy = readHealthValue(payload, ['healthy', 'ok'])
  if (typeof healthy === 'boolean') {
    return healthy ? 'healthy' : 'degraded'
  }

  return 'available'
})
const healthTone = computed<'neutral' | 'success' | 'warning' | 'danger'>(() => {
  const normalized = healthStatusLabel.value.toLowerCase()
  if (['ok', 'healthy', 'ready', 'alive', 'up', 'success', 'available'].includes(normalized)) {
    return 'success'
  }
  if (['warn', 'warning', 'pending', 'degraded', 'partial'].includes(normalized)) {
    return 'warning'
  }
  if (normalized === 'unknown') {
    return 'neutral'
  }
  return 'danger'
})
const healthSummaryCards = computed(() => {
  return [
    {
      label: '总体状态',
      value: healthStatusLabel.value,
      monospace: false,
    },
    {
      label: 'Provider',
      value: space.value?.provider || '--',
      monospace: false,
    },
    {
      label: '最近刷新',
      value: formatDateTime(space.value?.updated_at),
      monospace: false,
    },
  ]
})
const healthFactRows = computed<HealthFactRow[]>(() => {
  const payload = healthPayload.value
  if (!payload) {
    return []
  }

  const preferredKeys = [
    'status',
    'state',
    'healthy',
    'ok',
    'workspace',
    'workspace_key',
    'provider',
    'service',
    'request_id',
    'trace_id',
    'checked_at',
    'updated_at',
    'latency_ms',
    'elapsed_ms',
  ]
  const rows: HealthFactRow[] = []
  const seen = new Set<string>()

  for (const key of preferredKeys) {
    if (!(key in payload)) {
      continue
    }

    const value = payload[key]
    if (!isSimpleHealthValue(value)) {
      continue
    }

    rows.push({
      label: humanizeKey(key),
      value: formatHealthValue(value),
      monospace: key.includes('id') || key.includes('url') || key.includes('workspace'),
    })
    seen.add(key)
  }

  for (const [key, value] of Object.entries(payload)) {
    if (seen.has(key) || !isSimpleHealthValue(value)) {
      continue
    }

    rows.push({
      label: humanizeKey(key),
      value: formatHealthValue(value),
      monospace: key.includes('id') || key.includes('url') || key.includes('workspace'),
    })
  }

  return rows
})
const healthSections = computed<HealthSection[]>(() => {
  const payload = healthPayload.value
  if (!payload) {
    return []
  }

  return Object.entries(payload)
    .filter(([, value]) => !isSimpleHealthValue(value))
    .map(([key, value]) => ({
      key,
      label: humanizeKey(key),
      raw: JSON.stringify(value, null, 2),
    }))
})
const healthRawPayload = computed(() => {
  if (!healthPayload.value) {
    return ''
  }

  return JSON.stringify(healthPayload.value, null, 2)
})

async function loadSpace() {
  if (!projectId.value || !canRead.value) {
    space.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    space.value = await getProjectKnowledgeSpace(projectId.value)
  } catch (loadError) {
    space.value = null
    error.value = resolvePlatformHttpErrorMessage(loadError, '知识空间设置加载失败', '知识空间设置')
  } finally {
    loading.value = false
  }
}

async function refreshSpace() {
  if (!projectId.value || !canAdmin.value) {
    return
  }
  refreshing.value = true
  error.value = ''
  try {
    space.value = await refreshProjectKnowledgeSpace(projectId.value)
  } catch (refreshError) {
    error.value = resolvePlatformHttpErrorMessage(refreshError, '知识空间刷新失败', '知识空间设置')
  } finally {
    refreshing.value = false
  }
}

watch(
  () => projectId.value,
  () => {
    void loadSpace()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell h-full min-h-0 overflow-y-auto">
    <PageHeader
      eyebrow="Knowledge"
      :title="project ? `${project.name} · 知识设置` : '知识设置'"
      description="这里展示项目默认知识空间、workspace 映射和当前 LightRAG 服务状态。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="refreshing || !canAdmin"
          @click="refreshSpace"
        >
          {{ refreshing ? '刷新中…' : '刷新状态' }}
        </BaseButton>
      </template>
    </PageHeader>

    <KnowledgeWorkspaceNav
      v-if="projectId"
      :project-id="projectId"
    />

    <StateBanner
      v-if="projectId && !canRead"
      class="mt-4"
      title="当前角色没有知识设置读取权限"
      description="请联系项目管理员授予 project.knowledge.read 权限后，再查看当前项目的知识空间设置。"
      variant="info"
    />
    <StateBanner
      v-else-if="error"
      class="mt-4"
      title="知识设置异常"
      :description="error"
      variant="danger"
    />
    <StateBanner
      v-else-if="space && !canAdmin"
      class="mt-4"
      title="当前为只读设置视图"
      description="只有项目管理员可以主动刷新或修改知识空间设置，其他角色可在这里查看当前绑定与服务状态。"
      variant="info"
    />

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <SurfaceCard>
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
          默认知识空间
        </div>
        <template v-if="space">
          <dl class="mt-4 space-y-3 text-sm text-gray-700 dark:text-dark-200">
            <div class="flex items-start justify-between gap-4">
              <dt class="text-gray-400 dark:text-dark-500">
                显示名称
              </dt>
              <dd class="font-medium text-gray-900 dark:text-white">
                {{ space.display_name }}
              </dd>
            </div>
            <div class="flex items-start justify-between gap-4">
              <dt class="text-gray-400 dark:text-dark-500">
                Provider
              </dt>
              <dd>{{ space.provider }}</dd>
            </div>
            <div class="flex items-start justify-between gap-4">
              <dt class="text-gray-400 dark:text-dark-500">
                workspace_key
              </dt>
              <dd class="font-mono text-xs">
                {{ space.workspace_key }}
              </dd>
            </div>
            <div class="flex items-start justify-between gap-4">
              <dt class="text-gray-400 dark:text-dark-500">
                状态
              </dt>
              <dd>{{ space.status }}</dd>
            </div>
            <div class="flex items-start justify-between gap-4">
              <dt class="text-gray-400 dark:text-dark-500">
                服务地址
              </dt>
              <dd class="text-right break-all">
                {{ space.service_base_url }}
              </dd>
            </div>
            <div class="flex items-start justify-between gap-4">
              <dt class="text-gray-400 dark:text-dark-500">
                更新时间
              </dt>
              <dd>{{ formatDateTime(space.updated_at) }}</dd>
            </div>
          </dl>
        </template>
        <p
          v-else
          class="mt-4 text-sm text-gray-500 dark:text-dark-300"
        >
          {{ loading ? '正在加载项目知识空间…' : '当前还没有可展示的知识空间信息。' }}
        </p>
      </SurfaceCard>

      <SurfaceCard>
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
          workspace 映射摘要
        </div>
        <template v-if="space">
          <dl class="mt-4 space-y-3 text-sm text-gray-700 dark:text-dark-200">
            <div
              v-for="row in workspaceBindingRows"
              :key="row.label"
              class="flex items-start justify-between gap-4"
            >
              <dt class="text-gray-400 dark:text-dark-500">
                {{ row.label }}
              </dt>
              <dd :class="row.valueClass">
                {{ row.value }}
              </dd>
            </div>
          </dl>
          <p class="mt-4 text-sm leading-6 text-gray-500 dark:text-dark-300">
            前端页面只使用 <code>project_id</code> 作为上下文；真正的 <code>workspace_key</code>
            由控制面 facade 在服务端解析并注入 <code>LIGHTRAG-WORKSPACE</code>，避免 UI 直接耦合下游数据面细节。
          </p>
        </template>
        <p
          v-else
          class="mt-4 text-sm text-gray-500 dark:text-dark-300"
        >
          {{ loading ? '正在加载 workspace 映射摘要…' : '当前还没有可展示的 workspace 绑定信息。' }}
        </p>
      </SurfaceCard>

      <SurfaceCard class="xl:col-span-2">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              服务健康
            </div>
            <div class="mt-2 text-sm text-gray-500 dark:text-dark-300">
              这里按平台工作台的展示方式拆出状态摘要、关键字段和原始 payload，避免健康信息只能横向滚动查看。
            </div>
          </div>
          <StatusPill :tone="healthTone">
            {{ healthStatusLabel }}
          </StatusPill>
        </div>
        <template v-if="healthPayload">
          <div class="mt-4 grid gap-3 md:grid-cols-3">
            <div
              v-for="card in healthSummaryCards"
              :key="card.label"
              class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-3 dark:border-dark-800 dark:bg-dark-900/70"
            >
              <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                {{ card.label }}
              </div>
              <div
                class="mt-2 text-sm font-semibold text-gray-900 dark:text-white"
                :class="card.monospace ? 'font-mono break-all' : ''"
              >
                {{ card.value }}
              </div>
            </div>
          </div>

          <div
            v-if="healthFactRows.length"
            class="mt-4 grid gap-4 lg:grid-cols-2"
          >
            <div
              v-for="row in healthFactRows"
              :key="row.label"
              class="rounded-2xl border border-gray-100 bg-white/80 px-4 py-3 dark:border-dark-800 dark:bg-dark-950/60"
            >
              <div class="text-xs uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                {{ row.label }}
              </div>
              <div
                class="mt-2 text-sm text-gray-900 dark:text-white"
                :class="row.monospace ? 'font-mono break-all' : 'break-words'"
              >
                {{ row.value }}
              </div>
            </div>
          </div>

          <div
            v-if="healthSections.length"
            class="mt-4 grid gap-4 xl:grid-cols-2"
          >
            <div
              v-for="section in healthSections"
              :key="section.key"
              class="rounded-2xl border border-gray-100 bg-white/80 px-4 py-4 dark:border-dark-800 dark:bg-dark-950/60"
            >
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                {{ section.label }}
              </div>
              <pre class="pw-code-block mt-3 max-h-[240px]">{{ section.raw }}</pre>
            </div>
          </div>

          <div class="mt-4 rounded-2xl border border-gray-100 bg-white/80 px-4 py-4 dark:border-dark-800 dark:bg-dark-950/60">
            <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              Raw Payload
            </div>
            <pre class="pw-code-block mt-3 max-h-[360px]">{{ healthRawPayload }}</pre>
          </div>
        </template>
        <p
          v-else
          class="mt-4 text-sm text-gray-500 dark:text-dark-300"
        >
          当前还没有拉到健康状态，请点击右上角“刷新状态”。
        </p>
      </SurfaceCard>

      <SurfaceCard class="xl:col-span-2">
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
          运行说明 / 风险说明
        </div>
        <div class="mt-4 space-y-4 text-sm leading-6 text-gray-600 dark:text-dark-300">
          <div>
            <div class="font-medium text-gray-900 dark:text-white">
              运行说明
            </div>
            <ul class="mt-2 list-disc space-y-2 pl-5">
              <li>文档上传后，建议先在 Documents 页触发扫描，再到 Retrieval / Graph 页验证知识是否已入库。</li>
              <li>长耗时动作统一进入 operation；如需观察进度，请前往平台 Operations 页面查看执行状态。</li>
              <li>当前 human-facing 路径固定为 <code>platform-web → platform-api → LightRAG</code>。</li>
            </ul>
          </div>
          <div>
            <div class="font-medium text-gray-900 dark:text-white">
              风险说明
            </div>
            <ul class="mt-2 list-disc space-y-2 pl-5">
              <li>清空知识文档属于高风险操作，仅项目管理员可执行；普通写权限仅覆盖上传、扫描与单文档删除。</li>
              <li>跨项目隔离依赖 <code>project_id → workspace_key</code> 的治理映射与 LightRAG workspace 数据隔离，请勿在前端直接复用下游 workspace 标识。</li>
              <li>future runtime-side reuse 仍应走 LightRAG MCP，而不是绕过 control-plane 直接把这里的工作台接口当作统一程序化 API。</li>
            </ul>
          </div>
        </div>
      </SurfaceCard>
    </div>
  </section>
</template>

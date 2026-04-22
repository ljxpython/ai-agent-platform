<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDrawer from '@/components/base/BaseDrawer.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import GuidePanel from '@/components/platform/GuidePanel.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import MiniTrendChart from '@/components/platform/MiniTrendChart.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import {
  getSystemHealth,
  getSystemLiveProbe,
  getSystemMetrics,
  getSystemReadyProbe,
  type SystemProbeStatus
} from '@/services/system/system-governance.service'
import { useUiStore } from '@/stores/ui'
import type { PlatformConfigSnapshot } from '@/types/management'
import { formatDateTime, shortId } from '@/utils/format'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

type MetricsHistoryPoint = {
  at: number
  requestTotal: number
  requestFailed: number
  queueDepth: number
  healthyWorkers: number
}

type RiskFlag = {
  title: string
  description: string
  tone: 'warning' | 'danger' | 'success' | 'info'
}

const uiStore = useUiStore()
const loading = ref(false)
const error = ref('')
const live = ref<SystemProbeStatus | null>(null)
const ready = ref<SystemProbeStatus | null>(null)
const health = ref<SystemProbeStatus | null>(null)
const metrics = ref<PlatformConfigSnapshot['observability'] | null>(null)
const autoRefresh = ref(true)
const lastReadyStatus = ref<string | null>(null)
const metricsHistory = ref<MetricsHistoryPoint[]>([])
const workerDrawerOpen = ref(false)
const selectedWorkerId = ref('')
let refreshTimer: number | null = null

const stats = computed(() => {
  const failureRate = metrics.value?.requests.failure_rate ?? 0
  return [
    {
      label: 'Live',
      value: live.value?.status || 'unknown',
      hint: '进程是否存活',
      icon: 'activity',
      tone: live.value?.status === 'alive' ? 'success' : 'warning'
    },
    {
      label: 'Ready',
      value: ready.value?.status || 'unknown',
      hint: '数据库与 worker 是否就绪',
      icon: 'check',
      tone: ready.value?.status === 'ready' ? 'success' : 'warning'
    },
    {
      label: 'Health',
      value: health.value?.status || 'unknown',
      hint: '服务整体健康状态',
      icon: 'shield',
      tone: health.value?.status === 'ok' ? 'success' : 'danger'
    },
    {
      label: 'Fail Rate',
      value: `${(failureRate * 100).toFixed(2)}%`,
      hint: '当前请求失败率',
      icon: 'alert',
      tone: failureRate >= 0.05 ? 'danger' : failureRate > 0 ? 'warning' : 'primary'
    }
  ]
})

const riskFlags = computed<RiskFlag[]>(() => {
  const flags: RiskFlag[] = []

  if (ready.value && ready.value.status !== 'ready') {
    flags.push({
      title: 'Ready 未就绪',
      description: `当前 ready = ${ready.value.status}，优先检查数据库连接和 worker 心跳。`,
      tone: 'danger'
    })
  }

  if (health.value && health.value.status !== 'ok') {
    flags.push({
      title: 'Health 降级',
      description: `当前 health = ${health.value.status}，建议立即查看平台日志与最近失败请求。`,
      tone: 'danger'
    })
  }

  if ((metrics.value?.workers.stale_count ?? 0) > 0) {
    flags.push({
      title: '存在 stale worker',
      description: `${metrics.value?.workers.stale_count ?? 0} 个 worker 已掉队，需要确认进程、网络或队列状态。`,
      tone: 'warning'
    })
  }

  if ((metrics.value?.requests.failure_rate ?? 0) >= 0.05) {
    flags.push({
      title: '失败率偏高',
      description: `最近失败率 ${(((metrics.value?.requests.failure_rate ?? 0) * 100)).toFixed(2)}%，已经超过值班页告警阈值。`,
      tone: 'warning'
    })
  }

  if ((metrics.value?.operations.queue_depth ?? 0) >= 10) {
    flags.push({
      title: '队列积压',
      description: `当前 queue depth = ${metrics.value?.operations.queue_depth ?? 0}，需要确认 worker 消费速度。`,
      tone: 'warning'
    })
  }

  if (flags.length === 0 && metrics.value) {
    flags.push({
      title: '当前没有明显风险',
      description: 'live / ready / health / workers 口径都正常，可以继续观测趋势。',
      tone: 'success'
    })
  }

  return flags
})

const trendCards = computed(() => {
  const history = metricsHistory.value
  return [
    {
      label: 'Requests',
      value: metrics.value?.requests.total ?? 0,
      hint: '累计请求量',
      series: history.map((item) => item.requestTotal),
      stroke: '#2563eb',
      fill: 'rgba(37, 99, 235, 0.12)'
    },
    {
      label: 'Failed',
      value: metrics.value?.requests.failed ?? 0,
      hint: '累计失败请求',
      series: history.map((item) => item.requestFailed),
      stroke: '#dc2626',
      fill: 'rgba(220, 38, 38, 0.12)'
    },
    {
      label: 'Queue Depth',
      value: metrics.value?.operations.queue_depth ?? 0,
      hint: '当前操作队列堆积',
      series: history.map((item) => item.queueDepth),
      stroke: '#d97706',
      fill: 'rgba(217, 119, 6, 0.12)'
    },
    {
      label: 'Healthy Workers',
      value: metrics.value?.workers.healthy_count ?? 0,
      hint: '健康 worker 数量',
      series: history.map((item) => item.healthyWorkers),
      stroke: '#059669',
      fill: 'rgba(5, 150, 105, 0.12)'
    }
  ]
})

const workerItems = computed(() => metrics.value?.workers.items || [])

const selectedWorker = computed(() => {
  return workerItems.value.find((item) => item.worker_id === selectedWorkerId.value) ?? null
})

function formatPercent(value: number | undefined) {
  return `${((value ?? 0) * 100).toFixed(2)}%`
}

function formatMetadata(value: Record<string, unknown> | undefined) {
  if (!value || Object.keys(value).length === 0) {
    return '{}'
  }
  return JSON.stringify(value, null, 2)
}

function appendMetricsHistory(nextMetrics: PlatformConfigSnapshot['observability']) {
  const nextPoint: MetricsHistoryPoint = {
    at: Date.now(),
    requestTotal: nextMetrics.requests.total,
    requestFailed: nextMetrics.requests.failed,
    queueDepth: nextMetrics.operations.queue_depth,
    healthyWorkers: nextMetrics.workers.healthy_count
  }

  metricsHistory.value = [...metricsHistory.value.slice(-17), nextPoint]
}

function openWorkerDetail(workerId: string) {
  selectedWorkerId.value = workerId
  workerDrawerOpen.value = true
}

async function loadSystemState() {
  loading.value = true
  error.value = ''

  try {
    const [livePayload, readyPayload, healthPayload, metricsPayload] = await Promise.all([
      getSystemLiveProbe(),
      getSystemReadyProbe(),
      getSystemHealth(),
      getSystemMetrics()
    ])
    live.value = livePayload
    ready.value = readyPayload
    health.value = healthPayload
    metrics.value = metricsPayload
    appendMetricsHistory(metricsPayload)

    if (lastReadyStatus.value && lastReadyStatus.value !== readyPayload.status) {
      uiStore.pushToast({
        type: readyPayload.status === 'ready' ? 'success' : 'warning',
        title: 'Ready 状态已变化',
        message: `${lastReadyStatus.value} -> ${readyPayload.status}`
      })
    }
    lastReadyStatus.value = readyPayload.status
  } catch (loadError) {
    live.value = null
    ready.value = null
    health.value = null
    metrics.value = null
    error.value = resolvePlatformHttpErrorMessage(loadError, '系统治理快照加载失败', '系统治理')
  } finally {
    loading.value = false
  }
}

function startRefreshTimer() {
  if (typeof window === 'undefined' || refreshTimer !== null) {
    return
  }

  refreshTimer = window.setInterval(() => {
    if (autoRefresh.value) {
      void loadSystemState()
    }
  }, 5000)
}

function stopRefreshTimer() {
  if (typeof window !== 'undefined' && refreshTimer !== null) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(() => {
  void loadSystemState()
  startRefreshTimer()
})

onUnmounted(() => {
  stopRefreshTimer()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Governance"
      title="System Probes"
      description="这里把 live / ready / health / metrics 收成正式值班页。值班、联调、演示都别再去记零散接口地址，直接看这页。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="autoRefresh = !autoRefresh"
        >
          {{ autoRefresh ? '暂停轮询' : '恢复轮询' }}
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          @click="loadSystemState"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新状态
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="系统治理快照加载失败"
      :description="error"
      variant="danger"
    />

    <GuidePanel
      guide-id="system-governance"
      title="值班视角说明"
      description="这页展示的是控制面本身的可用性，不是业务页面的 UI 健康检查。先看风险提示，再看趋势，最后进 worker heartbeat 明细查原因。"
      tone="info"
    />

    <div class="grid gap-4 xl:grid-cols-4">
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

    <EmptyState
      v-if="!metrics && !loading"
      title="还没有系统快照"
      description="先确认 platform-api 已启动并且当前账号有读取系统治理接口的权限。"
      icon="activity"
      action-label="重新加载"
      @action="loadSystemState"
    />

    <template v-else-if="metrics">
      <div class="grid gap-4 xl:items-start xl:grid-cols-3">
        <SurfaceCard class="space-y-4 xl:col-span-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="alert"
              size="sm"
              class="text-primary-500"
            />
            值班风险面板
          </div>
          <div class="grid gap-3 xl:items-start xl:grid-cols-3">
            <article
              v-for="flag in riskFlags"
              :key="flag.title"
              class="rounded-2xl border px-4 py-4 shadow-sm"
              :class="flag.tone === 'danger'
                ? 'border-rose-200 bg-rose-50/80 dark:border-rose-900/40 dark:bg-rose-950/20'
                : flag.tone === 'warning'
                  ? 'border-amber-200 bg-amber-50/80 dark:border-amber-900/40 dark:bg-amber-950/20'
                  : 'border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/40 dark:bg-emerald-950/20'"
            >
              <div class="flex items-center gap-2">
                <StatusPill :tone="flag.tone === 'danger' ? 'danger' : flag.tone === 'warning' ? 'warning' : 'success'">
                  {{ flag.title }}
                </StatusPill>
              </div>
              <div class="mt-3 text-sm leading-6 text-gray-600 dark:text-dark-200">
                {{ flag.description }}
              </div>
            </article>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4 xl:col-span-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="overview"
              size="sm"
              class="text-primary-500"
            />
            指标趋势
          </div>
          <div class="grid gap-4 xl:items-start xl:grid-cols-4">
            <article
              v-for="trend in trendCards"
              :key="trend.label"
              class="pw-card-subtle px-4 py-4"
            >
              <div class="flex items-center justify-between gap-3">
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                    {{ trend.label }}
                  </div>
                  <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
                    {{ trend.value }}
                  </div>
                </div>
                <div class="text-right text-xs text-gray-500 dark:text-dark-300">
                  {{ trend.hint }}
                </div>
              </div>
              <div class="mt-4">
                <MiniTrendChart
                  :values="trend.series"
                  :stroke="trend.stroke"
                  :fill="trend.fill"
                />
              </div>
            </article>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="activity"
              size="sm"
              class="text-primary-500"
            />
            Probes
          </div>
          <div class="space-y-3">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Live
              </div>
              <div class="mt-2 flex items-center justify-between gap-3">
                <div class="text-sm text-gray-900 dark:text-white">
                  {{ live?.status || 'unknown' }}
                </div>
                <StatusPill :tone="live?.status === 'alive' ? 'success' : 'warning'">
                  {{ live?.status === 'alive' ? 'alive' : 'attention' }}
                </StatusPill>
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Ready
              </div>
              <div class="mt-2 flex items-center justify-between gap-3">
                <div class="text-sm text-gray-900 dark:text-white">
                  {{ ready?.status || 'unknown' }}
                </div>
                <StatusPill :tone="ready?.status === 'ready' ? 'success' : 'danger'">
                  {{ ready?.database_ready ? 'db ok' : 'db check' }}
                </StatusPill>
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                database {{ ready?.database_ready }} / healthy workers {{ ready?.healthy_workers }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Health
              </div>
              <div class="mt-2 flex items-center justify-between gap-3">
                <div class="text-sm text-gray-900 dark:text-white">
                  {{ health?.status || 'unknown' }}
                </div>
                <StatusPill :tone="health?.status === 'ok' ? 'success' : 'danger'">
                  {{ health?.status === 'ok' ? 'healthy' : 'degraded' }}
                </StatusPill>
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                request {{ health?.request_id || 'n/a' }} / trace {{ health?.trace_id || 'n/a' }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Auto Refresh
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ autoRefresh ? 'enabled' : 'paused' }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                5s interval / samples {{ metricsHistory.length }}
              </div>
            </div>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="overview"
              size="sm"
              class="text-primary-500"
            />
            Request Metrics
          </div>
          <div class="grid gap-3 sm:items-start sm:grid-cols-2">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Totals
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ metrics.requests.total }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                failed {{ metrics.requests.failed }} / rate {{ formatPercent(metrics.requests.failure_rate) }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Latency
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ metrics.requests.avg_duration_ms }} ms
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                max {{ metrics.requests.max_duration_ms }} ms
              </div>
            </div>
          </div>
          <div class="space-y-2">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Top Paths
            </div>
            <article
              v-for="item in metrics.requests.top_paths"
              :key="item.path"
              class="pw-card-subtle px-4 py-3"
            >
              <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                {{ item.path }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ item.count }} req / fail {{ item.failed }} / rate {{ formatPercent(item.failure_rate) }} / avg {{ item.avg_duration_ms }} ms
              </div>
            </article>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="users"
              size="sm"
              class="text-primary-500"
            />
            Worker Metrics
          </div>
          <div class="grid gap-3 sm:items-start sm:grid-cols-2">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Queue Depth
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ metrics.operations.queue_depth }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Heartbeats
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ metrics.workers.healthy_count }} healthy / {{ metrics.workers.stale_count }} stale
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Success / Fail
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ metrics.operations.succeeded_count }} / {{ metrics.operations.failed_count }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Duration
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ metrics.operations.avg_duration_ms }} ms
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                max {{ metrics.operations.max_duration_ms }} ms
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <div class="flex items-center justify-between gap-3">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Worker Heartbeats
              </div>
              <div class="text-xs text-gray-500 dark:text-dark-300">
                stale after {{ metrics.workers.stale_after_seconds }}s
              </div>
            </div>

            <EmptyState
              v-if="!workerItems.length"
              title="当前没有 worker 心跳"
              description="还没有任何 worker 上报心跳，先确认 worker 进程已启动。"
              icon="users"
            />

            <template v-else>
              <button
                v-for="worker in workerItems"
                :key="worker.worker_id"
                type="button"
                class="pw-card-subtle flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-colors hover:border-primary-200 hover:bg-primary-50/60 dark:hover:border-primary-900/40 dark:hover:bg-primary-950/20"
                @click="openWorkerDetail(worker.worker_id)"
              >
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      {{ shortId(worker.worker_id) }}
                    </div>
                    <StatusPill :tone="worker.healthy ? 'success' : 'warning'">
                      {{ worker.healthy ? 'healthy' : 'stale' }}
                    </StatusPill>
                  </div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                    {{ worker.hostname }} · pid {{ worker.pid }} · {{ worker.queue_backend }}
                  </div>
                  <div class="mt-2 text-xs text-gray-500 dark:text-dark-300">
                    heartbeat {{ formatDateTime(worker.last_heartbeat_at) }} / age {{ worker.age_seconds.toFixed(1) }}s
                  </div>
                </div>
                <BaseIcon
                  name="chevron-right"
                  size="sm"
                  class="mt-1 text-gray-400"
                />
              </button>
            </template>
          </div>
        </SurfaceCard>
      </div>
    </template>

    <BaseDrawer
      :show="workerDrawerOpen"
      title="Worker Heartbeat 详情"
      width="wide"
      @close="workerDrawerOpen = false"
    >
      <div
        v-if="selectedWorker"
        class="space-y-5"
      >
        <div class="pw-card p-5">
          <div class="flex flex-wrap items-center gap-2">
            <div class="text-base font-semibold text-gray-900 dark:text-white">
              {{ selectedWorker.worker_id }}
            </div>
            <StatusPill :tone="selectedWorker.healthy ? 'success' : 'warning'">
              {{ selectedWorker.status }}
            </StatusPill>
          </div>
          <div class="mt-4 grid gap-2 text-sm text-gray-600 dark:text-dark-200">
            <div>Hostname: {{ selectedWorker.hostname }}</div>
            <div>PID: {{ selectedWorker.pid }}</div>
            <div>Queue Backend: {{ selectedWorker.queue_backend }}</div>
            <div>Current Operation: {{ selectedWorker.current_operation_id || '--' }}</div>
            <div>Last Heartbeat: {{ formatDateTime(selectedWorker.last_heartbeat_at) }}</div>
            <div>Last Started: {{ formatDateTime(selectedWorker.last_started_at) }}</div>
            <div>Last Completed: {{ formatDateTime(selectedWorker.last_completed_at) }}</div>
            <div>Age Seconds: {{ selectedWorker.age_seconds.toFixed(1) }}</div>
          </div>
        </div>

        <SurfaceCard class="space-y-3">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
            Last Error
          </div>
          <div class="rounded-2xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-dark-800/80 dark:text-dark-200">
            {{ selectedWorker.last_error || '当前没有记录错误。' }}
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-3">
          <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
            Metadata
          </div>
          <pre class="overflow-x-auto rounded-2xl bg-slate-950 px-4 py-4 text-xs leading-6 text-slate-100">{{ formatMetadata(selectedWorker.metadata) }}</pre>
        </SurfaceCard>
      </div>
    </BaseDrawer>
  </section>
</template>

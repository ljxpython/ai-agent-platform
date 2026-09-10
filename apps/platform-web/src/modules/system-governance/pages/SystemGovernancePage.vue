<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
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
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

type MetricsHistoryPoint = {
  at: number
  requestTotal: number
  requestFailed: number
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
      hint: '数据库 是否就绪',
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
      description: `当前 ready = ${ready.value.status}，优先检查数据库连接。`,
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


  if ((metrics.value?.requests.failure_rate ?? 0) >= 0.05) {
    flags.push({
      title: '失败率偏高',
      description: `最近失败率 ${(((metrics.value?.requests.failure_rate ?? 0) * 100)).toFixed(2)}%，已经超过值班页告警阈值。`,
      tone: 'warning'
    })
  }


  if (flags.length === 0 && metrics.value) {
    flags.push({
      title: '当前没有明显风险',
      description: 'live / ready / health 口径都正常，可以继续观测趋势。',
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
  ]
})



function formatPercent(value: number | undefined) {
  return `${((value ?? 0) * 100).toFixed(2)}%`
}


function appendMetricsHistory(nextMetrics: PlatformConfigSnapshot['observability']) {
  const nextPoint: MetricsHistoryPoint = {
    at: Date.now(),
    requestTotal: nextMetrics.requests.total,
    requestFailed: nextMetrics.requests.failed,
  }

  metricsHistory.value = [...metricsHistory.value.slice(-17), nextPoint]
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
      description="这页展示的是控制面本身的可用性，不是业务页面的 UI 健康检查。先看风险提示，再看趋势，最后查看请求明细查原因。"
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
                database {{ ready?.database_ready }}
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
      </div>
    </template>
  </section>
</template>

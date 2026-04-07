<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import GuidePanel from '@/components/platform/GuidePanel.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { getPlatformConfigSnapshot, updatePlatformFeatureFlags } from '@/services/system/platform-config.service'
import type { PlatformConfigSnapshot } from '@/types/management'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

type FeatureFlagMeta = {
  label: string
  description: string
}

const featureFlagMeta: Record<string, FeatureFlagMeta> = {
  operations_enabled: {
    label: 'Operations Enabled',
    description: '是否允许前端展示和访问操作中心。'
  },
  operations_center_enabled: {
    label: 'Operations Center UI',
    description: '是否启用更完整的 operations 治理入口。'
  },
  platform_config_enabled: {
    label: 'Platform Config UI',
    description: '是否启用平台配置治理页。'
  },
  runtime_catalog_refresh_async_ready: {
    label: 'Runtime Refresh Async Ready',
    description: 'runtime 刷新链路是否已经按异步 operation 标准接通。'
  },
  policy_overlay_registry_ready: {
    label: 'Policy Overlay Ready',
    description: '项目级 runtime overlay 是否完成正式注册和治理。'
  },
  runtime_policy_overlay_enabled: {
    label: 'Runtime Policy Overlay',
    description: '是否在前端暴露项目级运行策略覆盖能力。'
  }
}

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const snapshot = ref<PlatformConfigSnapshot | null>(null)
const editableFlags = ref<Record<string, boolean>>({})
const authorization = useAuthorization()
const canWritePlatformConfig = computed(() => authorization.can('platform.config.write'))

const stats = computed(() => {
  const current = snapshot.value
  if (!current) {
    return []
  }

  return [
    {
      label: '当前环境',
      value: current.service.env,
      hint: '当前运行环境标识',
      icon: 'globe',
      tone: 'primary'
    },
    {
      label: '版本',
      value: current.service.version,
      hint: current.service.name,
      icon: 'overview',
      tone: 'success'
    },
    {
      label: '数据库',
      value: current.database.enabled ? 'enabled' : 'disabled',
      hint: `strategy: ${current.database.migration_strategy}`,
      icon: 'shield',
      tone: current.database.enabled ? 'success' : 'warning'
    },
    {
      label: '队列后端',
      value: current.operations.queue_backend,
      hint: `poll ${current.operations.worker_poll_interval_seconds}s / idle ${current.operations.worker_idle_sleep_seconds}s / artifact ${current.operations.artifact_retention_hours}h`,
      icon: 'activity',
      tone: 'danger'
    },
    {
      label: '健康 Worker',
      value: String(current.observability.workers.healthy_count),
      hint: `stale ${current.observability.workers.stale_count} / heartbeat ${current.observability.workers.heartbeat_interval_seconds}s`,
      icon: 'check',
      tone: current.observability.workers.healthy_count > 0 ? 'success' : 'warning'
    }
  ]
})

const featureFlags = computed(() => {
  return Object.entries(editableFlags.value).map(([key, value]) => ({
    key,
    value,
    meta: featureFlagMeta[key] || {
      label: key,
      description: '未登记说明的特性开关。'
    }
  }))
})

const hasPendingChanges = computed(() => {
  const current = snapshot.value?.feature_flags || {}
  const next = editableFlags.value
  const allKeys = new Set([...Object.keys(current), ...Object.keys(next)])
  return Array.from(allKeys).some((key) => current[key] !== next[key])
})

const requestStatusFamilies = computed(() => {
  return Object.entries(snapshot.value?.observability.requests.by_status_family || {})
})

const requestMethods = computed(() => {
  return Object.entries(snapshot.value?.observability.requests.by_method || {})
})

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return '未记录'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('zh-CN', { hour12: false })
}

function resetFlags() {
  editableFlags.value = { ...(snapshot.value?.feature_flags || {}) }
}

function toggleFlag(key: string) {
  editableFlags.value = {
    ...editableFlags.value,
    [key]: !editableFlags.value[key]
  }
}

async function loadSnapshot() {
  loading.value = true
  error.value = ''

  try {
    const payload = await getPlatformConfigSnapshot()
    snapshot.value = payload
    editableFlags.value = { ...payload.feature_flags }
  } catch (loadError) {
    snapshot.value = null
    editableFlags.value = {}
    error.value = resolvePlatformHttpErrorMessage(loadError, '平台配置加载失败', '平台配置')
  } finally {
    loading.value = false
  }
}

async function saveFlags() {
  if (!canWritePlatformConfig.value) {
    error.value = '当前账号没有平台配置写权限'
    return
  }
  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    const payload = await updatePlatformFeatureFlags(editableFlags.value)
    snapshot.value = payload
    editableFlags.value = { ...payload.feature_flags }
    notice.value = 'Feature flags 已保存并写回控制面。'
  } catch (saveError) {
    error.value = resolvePlatformHttpErrorMessage(saveError, 'Feature flags 保存失败', '平台配置')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSnapshot()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Governance"
      title="平台配置"
      description="这里负责展示当前控制面的运行快照，并把真正允许热更新的开关收成正式治理入口。环境变量类配置仍然只读，别在这胡乱热改。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          @click="loadSnapshot"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新快照
        </BaseButton>
        <BaseButton
          variant="secondary"
          :disabled="saving || !hasPendingChanges || !canWritePlatformConfig"
          @click="resetFlags"
        >
          还原变更
        </BaseButton>
        <BaseButton
          :disabled="saving || !hasPendingChanges || !canWritePlatformConfig"
          @click="saveFlags"
        >
          {{ canWritePlatformConfig ? (saving ? '保存中...' : '保存开关') : '当前账号只读' }}
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="平台配置加载失败"
      :description="error"
      variant="danger"
    />
    <StateBanner
      v-else-if="notice"
      title="平台配置已更新"
      :description="notice"
      variant="success"
    />

    <GuidePanel
      guide-id="platform-config-governance"
      title="治理边界说明"
      description="这页只允许治理 feature flags。服务版本、数据库策略、运行上游地址和认证模式属于只读快照，用来验证当前部署口径，不拿来做在线热改。"
      tone="info"
    />

    <EmptyState
      v-if="!snapshot && !loading"
      title="还没有平台配置快照"
      description="先尝试刷新一次，如果还拿不到，优先排查 platform-api-v2 的认证、数据库和系统接口。"
      icon="lock"
      action-label="重新加载"
      @action="loadSnapshot"
    />

    <template v-else-if="snapshot">
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

      <div class="grid gap-6 xl:items-start xl:grid-cols-2">
        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="overview"
              size="sm"
              class="text-primary-500"
            />
            服务快照
          </div>
          <div class="grid gap-3 sm:items-start sm:grid-cols-2">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Service
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.service.name }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Version
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.service.version }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Env
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.service.env }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Docs
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.service.docs_enabled ? 'enabled' : 'disabled' }}
              </div>
            </div>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="shield"
              size="sm"
              class="text-primary-500"
            />
            基础设施快照
          </div>
          <div class="grid gap-3 sm:items-start sm:grid-cols-2">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Database
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.database.enabled ? 'enabled' : 'disabled' }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                auto create: {{ snapshot.database.auto_create ? 'true' : 'false' }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Queue
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.operations.queue_backend }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ snapshot.operations.worker_poll_interval_seconds }}s / {{ snapshot.operations.worker_idle_sleep_seconds }}s
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Artifact Store
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.operations.artifact_storage_backend }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                retention {{ snapshot.operations.artifact_retention_hours }}h / cleanup {{ snapshot.operations.artifact_cleanup_batch_size }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Auth
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.auth.required ? 'required' : 'optional' }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                bootstrap admin: {{ snapshot.auth.bootstrap_admin_enabled ? 'enabled' : 'disabled' }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Runtime
              </div>
              <div class="mt-2 break-all text-sm text-gray-900 dark:text-white">
                {{ snapshot.runtime.langgraph_upstream_url }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                IDS: {{ snapshot.runtime.interaction_data_service_configured ? 'configured' : 'missing' }}
              </div>
            </div>
          </div>
        </SurfaceCard>
      </div>

      <div class="grid gap-6 xl:items-start xl:grid-cols-2">
        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="activity"
              size="sm"
              class="text-primary-500"
            />
            可观测性与请求指标
          </div>
          <div class="grid gap-3 sm:items-start sm:grid-cols-2">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Requests
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.requests.total }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                failed {{ snapshot.observability.requests.failed }} / rate {{ (snapshot.observability.requests.failure_rate * 100).toFixed(2) }}%
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Latency
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.requests.avg_duration_ms }} ms
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                max {{ snapshot.observability.requests.max_duration_ms }} ms
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Trace Headers
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.trace.request_id_header }} / {{ snapshot.observability.trace.trace_id_header }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ snapshot.observability.trace.operation_chain_source }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Methods
              </div>
              <div class="mt-2 flex flex-wrap gap-2">
                <span
                  v-for="[method, count] in requestMethods"
                  :key="method"
                  class="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600 dark:bg-dark-800 dark:text-dark-200"
                >
                  {{ method }} {{ count }}
                </span>
              </div>
            </div>
          </div>

          <div class="space-y-3">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Top Paths
            </div>
            <div class="space-y-3">
              <article
                v-for="item in snapshot.observability.requests.top_paths"
                :key="item.path"
                class="pw-card-subtle px-4 py-3"
              >
                <div class="flex items-start justify-between gap-4">
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                      {{ item.path }}
                    </div>
                    <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                      avg {{ item.avg_duration_ms }} ms / max {{ item.max_duration_ms }} ms
                    </div>
                  </div>
                  <div class="text-right text-xs text-gray-500 dark:text-dark-300">
                    <div>{{ item.count }} req</div>
                    <div>fail {{ item.failed }}</div>
                  </div>
                </div>
              </article>
            </div>

            <div class="flex flex-wrap gap-2">
              <span
                v-for="[family, count] in requestStatusFamilies"
                :key="family"
                class="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-200"
              >
                {{ family }} {{ count }}
              </span>
            </div>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="users"
              size="sm"
              class="text-primary-500"
            />
            Worker 与执行治理
          </div>
          <div class="grid gap-3 sm:items-start sm:grid-cols-2">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Queue Depth
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.operations.queue_depth }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                running {{ snapshot.observability.operations.running_count }} / succeeded {{ snapshot.observability.operations.succeeded_count }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Failure / Cancel
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.operations.failed_count }} / {{ snapshot.observability.operations.cancelled_count }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                archived {{ snapshot.observability.operations.archived_count }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Duration
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.operations.avg_duration_ms }} ms
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                max {{ snapshot.observability.operations.max_duration_ms }} ms
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Heartbeat
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.workers.heartbeat_interval_seconds }}s / stale {{ snapshot.observability.workers.stale_after_seconds }}s
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                healthy {{ snapshot.observability.workers.healthy_count }} / stale {{ snapshot.observability.workers.stale_count }}
              </div>
            </div>
          </div>

          <div class="space-y-3">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Worker Heartbeats
            </div>
            <div
              v-if="snapshot.observability.workers.items.length"
              class="space-y-3"
            >
              <article
                v-for="worker in snapshot.observability.workers.items"
                :key="worker.worker_id"
                class="pw-card-subtle px-4 py-3"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                      {{ worker.worker_id }}
                    </div>
                    <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                      {{ worker.hostname }} · pid {{ worker.pid }} · {{ worker.queue_backend }}
                    </div>
                    <div class="mt-2 text-xs text-gray-500 dark:text-dark-300">
                      last heartbeat: {{ formatDateTime(worker.last_heartbeat_at) }}
                    </div>
                    <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                      last completed: {{ formatDateTime(worker.last_completed_at) }}
                    </div>
                    <div
                      v-if="worker.last_error"
                      class="mt-2 text-xs text-rose-500 dark:text-rose-300"
                    >
                      {{ worker.last_error }}
                    </div>
                  </div>
                  <div class="flex flex-col items-end gap-2">
                    <span
                      class="rounded-full px-2.5 py-1 text-xs font-semibold"
                      :class="worker.healthy
                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200'
                        : 'bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-200'"
                    >
                      {{ worker.healthy ? 'healthy' : 'stale' }}
                    </span>
                    <span class="text-xs text-gray-500 dark:text-dark-300">
                      {{ worker.status }} / {{ worker.age_seconds }}s
                    </span>
                  </div>
                </div>
              </article>
            </div>
            <EmptyState
              v-else
              title="还没有 worker heartbeat"
              description="先启动 platform-api-v2 worker，再回来刷新这页。"
              icon="activity"
              action-label="重新加载"
              @action="loadSnapshot"
            />
          </div>
        </SurfaceCard>
      </div>

      <div class="grid gap-6 xl:items-start xl:grid-cols-3">
        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="shield"
              size="sm"
              class="text-primary-500"
            />
            安全治理
          </div>
          <div class="space-y-3">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                OIDC / SSO
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.security.oidc.enabled ? 'enabled' : 'reserved' }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                mode: {{ snapshot.security.oidc.mode }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Service Accounts
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.security.service_accounts.total_accounts }} accounts / {{ snapshot.security.service_accounts.active_tokens }} tokens
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                header {{ snapshot.security.service_accounts.api_key_header }} / ttl {{ snapshot.security.service_accounts.default_token_ttl_days }}d
              </div>
            </div>
            <div class="space-y-2">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Sensitive Config
              </div>
              <div
                v-for="(item, key) in snapshot.security.sensitive_config"
                :key="key"
                class="pw-card-subtle px-4 py-3 text-sm text-gray-700 dark:text-dark-100"
              >
                <div class="font-medium text-gray-900 dark:text-white">
                  {{ key }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  {{ item.configured ? item.masked_value || 'configured' : 'not configured' }}
                </div>
              </div>
            </div>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="globe"
              size="sm"
              class="text-primary-500"
            />
            环境治理
          </div>
          <div class="pw-card-subtle p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Current Environment
            </div>
            <div class="mt-2 text-sm text-gray-900 dark:text-white">
              {{ snapshot.environment.current }}
            </div>
            <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
              production-like: {{ snapshot.environment.production_like ? 'true' : 'false' }}
            </div>
          </div>
          <div class="pw-card-subtle p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Supported
            </div>
            <div class="mt-2 flex flex-wrap gap-2">
              <span
                v-for="item in snapshot.environment.supported"
                :key="item"
                class="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600 dark:bg-dark-800 dark:text-dark-200"
              >
                {{ item }}
              </span>
            </div>
          </div>
          <div class="pw-card-subtle p-4">
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Guards
            </div>
            <div class="mt-2 text-xs text-gray-500 dark:text-dark-300">
              auth {{ snapshot.environment.auth_required ? 'required' : 'optional' }} / docs {{ snapshot.environment.docs_enabled ? 'enabled' : 'disabled' }} / bootstrap {{ snapshot.environment.bootstrap_admin_enabled ? 'enabled' : 'disabled' }}
            </div>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="archive"
              size="sm"
              class="text-primary-500"
            />
            数据治理
          </div>
          <div class="space-y-3">
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Artifact Retention
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.data_governance.artifact_retention_hours }}h
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                cleanup batch {{ snapshot.data_governance.artifact_cleanup_batch_size }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Audit Storage
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.data_governance.audit_storage }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Export / Delete Mode
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.data_governance.export_mode }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                {{ snapshot.data_governance.delete_mode }}
              </div>
            </div>
          </div>
        </SurfaceCard>
      </div>

      <SurfaceCard class="space-y-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              Feature Flags
            </div>
            <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
              这批开关会写入控制面数据库，属于真正允许在线治理的配置。
            </div>
          </div>
          <div
            class="rounded-full px-3 py-1 text-xs font-semibold"
            :class="hasPendingChanges
              ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-200'
              : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200'"
          >
            {{ hasPendingChanges ? '有未保存变更' : '已与后端同步' }}
          </div>
        </div>

        <div class="grid gap-4 xl:items-start xl:grid-cols-2">
          <article
            v-for="flag in featureFlags"
            :key="flag.key"
            class="pw-card p-5"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0 flex-1">
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  {{ flag.meta.label }}
                </div>
                <div class="mt-1 text-xs text-gray-400 dark:text-dark-400">
                  {{ flag.key }}
                </div>
                <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
                  {{ flag.meta.description }}
                </p>
              </div>

              <button
                type="button"
                class="inline-flex h-10 min-w-[96px] items-center justify-center rounded-full border px-4 text-sm font-semibold transition"
                :class="flag.value
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-200'
                  : 'border-gray-200 bg-gray-50 text-gray-500 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300'"
                :disabled="!canWritePlatformConfig"
                @click="toggleFlag(flag.key)"
              >
                {{ flag.value ? 'enabled' : 'disabled' }}
              </button>
            </div>
          </article>
        </div>
      </SurfaceCard>
    </template>
  </section>
</template>

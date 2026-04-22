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
import StatusPill from '@/components/platform/StatusPill.vue'
import { listAudit } from '@/services/audit/audit.service'
import { listOperations } from '@/services/operations/operations.service'
import { listServiceAccounts } from '@/services/system/service-accounts.service'
import { getPlatformConfigSnapshot } from '@/services/system/platform-config.service'
import {
  getSystemHealth,
  getSystemReadyProbe,
  type SystemProbeStatus
} from '@/services/system/system-governance.service'
import type {
  ManagementAuditRow,
  ManagementOperation,
  ManagementServiceAccount,
  PermissionCode,
  PlatformConfigSnapshot
} from '@/types/management'
import { formatDateTime, shortId } from '@/utils/format'

type QuickLinkItem = {
  to: string
  label: string
  description: string
  icon: 'activity' | 'audit' | 'lock' | 'shield' | 'users'
  requiredPermissions: PermissionCode[]
  permissionMode?: 'all' | 'any'
}

const authorization = useAuthorization()
const loading = ref(false)
const error = ref('')
const snapshot = ref<PlatformConfigSnapshot | null>(null)
const health = ref<SystemProbeStatus | null>(null)
const ready = ref<SystemProbeStatus | null>(null)
const recentOperations = ref<ManagementOperation[]>([])
const recentAuditRows = ref<ManagementAuditRow[]>([])
const recentServiceAccounts = ref<ManagementServiceAccount[]>([])

const quickLinks: QuickLinkItem[] = [
  {
    to: '/workspace/operations',
    label: 'Operations',
    description: '看异步任务、队列与执行结果',
    icon: 'activity',
    requiredPermissions: ['platform.operation.read', 'project.operation.read'],
    permissionMode: 'any'
  },
  {
    to: '/workspace/audit',
    label: 'Audit',
    description: '查请求链路与治理操作记录',
    icon: 'audit',
    requiredPermissions: ['platform.audit.read', 'project.audit.read'],
    permissionMode: 'any'
  },
  {
    to: '/workspace/platform-config',
    label: 'Platform Config',
    description: '查看环境、feature flags 与配置快照',
    icon: 'lock',
    requiredPermissions: ['platform.config.read']
  },
  {
    to: '/workspace/system-governance',
    label: 'System Governance',
    description: '看 live / ready / health / metrics',
    icon: 'shield',
    requiredPermissions: ['platform.config.read']
  },
  {
    to: '/workspace/service-accounts',
    label: 'Service Accounts',
    description: '治理平台级 token 与账号权限',
    icon: 'users',
    requiredPermissions: ['platform.service_account.read']
  }
]

const visibleQuickLinks = computed(() =>
  quickLinks.filter((item) => {
    const mode = item.permissionMode === 'any' ? 'any' : 'all'
    const evaluator = (permission: PermissionCode) =>
      permission.startsWith('project.')
        ? authorization.currentProjectCan(permission) || authorization.canAnyProject(permission)
        : authorization.can(permission)

    return mode === 'any'
      ? item.requiredPermissions.some((permission) => evaluator(permission))
      : item.requiredPermissions.every((permission) => evaluator(permission))
  })
)

const heroStats = computed(() => {
  const current = snapshot.value
  return [
    {
      label: '环境',
      value: current?.service.env || '--',
      hint: current ? `${current.service.name} ${current.service.version}` : '平台快照未加载',
      icon: 'globe',
      tone: 'primary'
    },
    {
      label: 'Ready',
      value: ready.value?.status || 'unknown',
      hint: `db ${ready.value?.database_ready ?? '--'} / workers ${ready.value?.healthy_workers ?? '--'}`,
      icon: 'check',
      tone: ready.value?.status === 'ready' ? 'success' : 'warning'
    },
    {
      label: 'Health',
      value: health.value?.status || 'unknown',
      hint: health.value?.request_id || '未记录 request id',
      icon: 'shield',
      tone: health.value?.status === 'ok' ? 'success' : 'danger'
    },
    {
      label: '队列深度',
      value: current?.operations.queue_depth ?? 0,
      hint: `running ${current?.operations.running_count ?? 0} / failed ${current?.operations.failed_count ?? 0}`,
      icon: 'activity',
      tone: (current?.operations.queue_depth ?? 0) > 0 ? 'warning' : 'primary'
    },
    {
      label: '服务账号',
      value: current?.security.service_accounts.total_accounts ?? 0,
      hint: `active token ${current?.security.service_accounts.active_tokens ?? 0}`,
      icon: 'users',
      tone: 'success'
    }
  ]
})

const riskFlags = computed(() => {
  const flags: Array<{
    title: string
    description: string
    tone: 'success' | 'warning' | 'danger'
  }> = []

  if (ready.value && ready.value.status !== 'ready') {
    flags.push({
      title: 'Ready 未通过',
      description: `当前 ready = ${ready.value.status}，先看 worker 和数据库。`,
      tone: 'danger'
    })
  }

  if (health.value && health.value.status !== 'ok') {
    flags.push({
      title: 'Health 已降级',
      description: `当前 health = ${health.value.status}，值班先看 system governance。`,
      tone: 'danger'
    })
  }

  if ((snapshot.value?.observability.workers.stale_count ?? 0) > 0) {
    flags.push({
      title: '存在 stale worker',
      description: `${snapshot.value?.observability.workers.stale_count ?? 0} 个 worker 掉队。`,
      tone: 'warning'
    })
  }

  if ((snapshot.value?.observability.requests.failure_rate ?? 0) >= 0.05) {
    flags.push({
      title: '请求失败率偏高',
      description: `当前失败率 ${(((snapshot.value?.observability.requests.failure_rate ?? 0) * 100)).toFixed(2)}%。`,
      tone: 'warning'
    })
  }

  if (flags.length === 0 && snapshot.value) {
    flags.push({
      title: '控制面状态稳定',
      description: '当前可作为演示基线，未发现明显风险项。',
      tone: 'success'
    })
  }

  return flags
})

function operationTone(status: string) {
  if (status === 'succeeded') {
    return 'success'
  }
  if (status === 'failed' || status === 'cancelled') {
    return 'danger'
  }
  if (status === 'running') {
    return 'warning'
  }
  return 'info'
}

function auditTone(statusCode: number) {
  if (statusCode >= 500) {
    return 'danger'
  }
  if (statusCode >= 400) {
    return 'warning'
  }
  return 'success'
}

async function loadControlPlane() {
  loading.value = true
  error.value = ''

  const failedSections: string[] = []
  const results = await Promise.allSettled([
    getPlatformConfigSnapshot(),
    getSystemHealth(),
    getSystemReadyProbe(),
    listOperations({
      limit: 6,
      offset: 0,
      archiveScope: 'exclude'
    }),
    listAudit(
      null,
      {
        limit: 6,
        offset: 0
      }
    ),
    listServiceAccounts({
      limit: 6,
      offset: 0
    })
  ])

  const [
    snapshotResult,
    healthResult,
    readyResult,
    operationsResult,
    auditResult,
    serviceAccountsResult
  ] = results

  if (snapshotResult.status === 'fulfilled') {
    snapshot.value = snapshotResult.value
  } else {
    snapshot.value = null
    failedSections.push('platform config')
  }

  if (healthResult.status === 'fulfilled') {
    health.value = healthResult.value
  } else {
    health.value = null
    failedSections.push('health')
  }

  if (readyResult.status === 'fulfilled') {
    ready.value = readyResult.value
  } else {
    ready.value = null
    failedSections.push('ready')
  }

  if (operationsResult.status === 'fulfilled') {
    recentOperations.value = operationsResult.value.items
  } else {
    recentOperations.value = []
    failedSections.push('operations')
  }

  if (auditResult.status === 'fulfilled') {
    recentAuditRows.value = auditResult.value.items
  } else {
    recentAuditRows.value = []
    failedSections.push('audit')
  }

  if (serviceAccountsResult.status === 'fulfilled') {
    recentServiceAccounts.value = serviceAccountsResult.value.items
  } else {
    recentServiceAccounts.value = []
    failedSections.push('service accounts')
  }

  if (failedSections.length > 0) {
    error.value = `部分控制面模块加载失败：${failedSections.join('、')}`
  }

  loading.value = false
}

onMounted(() => {
  void loadControlPlane()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Governance"
      title="Control Plane"
      description="把 operations、audit、platform config、system governance、service accounts 压成一个统一组合页。演示、值班、排查先看这里，再钻到具体治理页。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          :disabled="loading"
          @click="loadControlPlane"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新总览
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="Control Plane 存在部分缺口"
      :description="error"
      variant="warning"
    />

    <GuidePanel
      guide-id="control-plane-summary"
      title="推荐使用方式"
      description="先看上方五个核心指标，再看风险项，然后顺着快捷入口进入具体治理页。这样汇报和排障都不会乱。"
      tone="success"
    />

    <div class="grid gap-4 xl:grid-cols-5">
      <MetricCard
        v-for="item in heroStats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <EmptyState
      v-if="!snapshot && !loading"
      title="控制面快照还不可用"
      description="先确认 platform-api 已启动，且当前账号能访问治理接口。"
      icon="shield"
      action-label="重新加载"
      @action="loadControlPlane"
    />

    <template v-else>
      <div class="grid gap-4 xl:items-start xl:grid-cols-3">
        <SurfaceCard class="space-y-4 xl:col-span-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="alert"
              size="sm"
              class="text-primary-500"
            />
            当前风险摘要
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
              <StatusPill :tone="flag.tone">
                {{ flag.title }}
              </StatusPill>
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
            快捷入口
          </div>
          <div class="grid gap-3 xl:items-start xl:grid-cols-5">
            <router-link
              v-for="item in visibleQuickLinks"
              :key="item.to"
              :to="item.to"
              class="pw-card-subtle px-4 py-4 transition-colors hover:border-primary-200 hover:bg-primary-50/60 dark:hover:border-primary-900/40 dark:hover:bg-primary-950/20"
            >
              <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
                <BaseIcon
                  :name="item.icon"
                  size="sm"
                  class="text-primary-500"
                />
                {{ item.label }}
              </div>
              <div class="mt-2 text-sm leading-6 text-gray-500 dark:text-dark-300">
                {{ item.description }}
              </div>
            </router-link>
          </div>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="lock"
              size="sm"
              class="text-primary-500"
            />
            Platform Posture
          </div>
          <div
            v-if="snapshot"
            class="space-y-3"
          >
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Runtime Upstream
              </div>
              <div class="mt-2 break-all text-sm text-gray-900 dark:text-white">
                {{ snapshot.runtime.langgraph_upstream_url }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Environment
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.environment.current }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                auth {{ snapshot.environment.auth_required }} / docs {{ snapshot.environment.docs_enabled }}
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Security
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                API header {{ snapshot.security.service_accounts.api_key_header }}
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                oidc {{ snapshot.security.oidc.enabled ? 'enabled' : 'disabled' }} / ttl {{ snapshot.security.service_accounts.default_token_ttl_days }}d
              </div>
            </div>
            <div class="pw-card-subtle p-4">
              <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
                Workers
              </div>
              <div class="mt-2 text-sm text-gray-900 dark:text-white">
                {{ snapshot.observability.workers.healthy_count }} healthy / {{ snapshot.observability.workers.stale_count }} stale
              </div>
              <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                heartbeat {{ snapshot.observability.workers.heartbeat_interval_seconds }}s / stale after {{ snapshot.observability.workers.stale_after_seconds }}s
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
            Recent Operations
          </div>
          <EmptyState
            v-if="!recentOperations.length"
            title="暂无 operation"
            description="当前还没有最近操作记录。"
            icon="activity"
          />
          <template v-else>
            <article
              v-for="operation in recentOperations"
              :key="operation.id"
              class="pw-card-subtle px-4 py-3"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                    {{ operation.kind }}
                  </div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                    {{ shortId(operation.id) }} · {{ formatDateTime(operation.created_at) }}
                  </div>
                </div>
                <StatusPill :tone="operationTone(operation.status)">
                  {{ operation.status }}
                </StatusPill>
              </div>
            </article>
          </template>
        </SurfaceCard>

        <SurfaceCard class="space-y-4">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="audit"
              size="sm"
              class="text-primary-500"
            />
            Recent Audit
          </div>
          <EmptyState
            v-if="!recentAuditRows.length"
            title="暂无审计记录"
            description="当前还没有最近审计轨迹。"
            icon="audit"
          />
          <template v-else>
            <article
              v-for="row in recentAuditRows"
              :key="row.id"
              class="pw-card-subtle px-4 py-3"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                    {{ row.method }} {{ row.path }}
                  </div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                    {{ row.action || 'n/a' }} · {{ formatDateTime(row.created_at) }}
                  </div>
                </div>
                <StatusPill :tone="auditTone(row.status_code)">
                  {{ row.status_code }}
                </StatusPill>
              </div>
            </article>
          </template>
        </SurfaceCard>

        <SurfaceCard
          class="space-y-4"
          :class="recentServiceAccounts.length > 1 ? 'xl:col-span-3' : ''"
        >
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <BaseIcon
              name="users"
              size="sm"
              class="text-primary-500"
            />
            Service Accounts Snapshot
          </div>
          <div
            class="grid gap-3"
            :class="recentServiceAccounts.length > 1 ? 'xl:items-start xl:grid-cols-3' : 'max-w-[420px]'"
          >
            <article
              v-for="account in recentServiceAccounts"
              :key="account.id"
              class="pw-card-subtle px-4 py-4"
            >
              <div class="flex flex-wrap items-center gap-2">
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  {{ account.name }}
                </div>
                <StatusPill :tone="account.status === 'active' ? 'success' : 'warning'">
                  {{ account.status }}
                </StatusPill>
              </div>
              <div class="mt-2 text-sm text-gray-500 dark:text-dark-300">
                {{ account.description || '暂无描述' }}
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <span
                  v-for="role in account.platform_roles"
                  :key="role"
                  class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 dark:bg-primary-950/30 dark:text-primary-200"
                >
                  {{ role }}
                </span>
              </div>
              <div class="mt-3 text-xs text-gray-500 dark:text-dark-300">
                tokens {{ account.tokens.length }} / last used {{ formatDateTime(account.last_used_at) }}
              </div>
            </article>
          </div>
        </SurfaceCard>
      </div>
    </template>
  </section>
</template>

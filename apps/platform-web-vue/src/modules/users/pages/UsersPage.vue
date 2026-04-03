<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import TablePageLayout from '@/components/layout/TablePageLayout.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import FilterToolbar from '@/components/platform/FilterToolbar.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import StatusPill from '@/components/platform/StatusPill.vue'
import { listUsersPage } from '@/services/users/users.service'
import type { ManagementUser } from '@/types/management'
import { formatDateTime, shortId } from '@/utils/format'

const queryInput = ref('')
const statusInput = ref('')
const query = ref('')
const status = ref('')
const loading = ref(false)
const error = ref('')
const total = ref(0)
const items = ref<ManagementUser[]>([])

const adminCount = computed(() => items.value.filter((item) => item.is_super_admin).length)
const activeCount = computed(() => items.value.filter((item) => item.status === 'active').length)
const stats = computed(() => [
  {
    label: '当前结果',
    value: items.value.length,
    hint: '展示最新查询返回的用户',
    icon: 'users',
    tone: 'primary'
  },
  {
    label: '管理员',
    value: adminCount.value,
    hint: '当前结果集中拥有超级管理员权限的用户',
    icon: 'shield',
    tone: 'success'
  },
  {
    label: '活跃成员',
    value: activeCount.value,
    hint: '当前结果集中状态为 active 的用户',
    icon: 'activity',
    tone: 'warning'
  }
])

async function loadUsers() {
  loading.value = true
  error.value = ''

  try {
    const payload = await listUsersPage({
      limit: 50,
      offset: 0,
      query: query.value,
      status: status.value
    })

    items.value = payload.items
    total.value = payload.total
  } catch (loadError) {
    items.value = []
    total.value = 0
    error.value = loadError instanceof Error ? loadError.message : '用户列表加载失败'
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  query.value = queryInput.value.trim()
  status.value = statusInput.value
  void loadUsers()
}

function resetFilters() {
  queryInput.value = ''
  statusInput.value = ''
  query.value = ''
  status.value = ''
  void loadUsers()
}

onMounted(() => {
  void loadUsers()
})
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Users"
      title="用户管理"
      description="用户页承担账号盘点和权限可视化。这里先把列表、筛选和状态表达统一到新的页面母版里。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="loadUsers"
        >
          <BaseIcon
            name="refresh"
            size="sm"
          />
          刷新
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="用户列表加载失败"
      :description="error"
      variant="danger"
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

    <TablePageLayout>
      <template #filters>
        <FilterToolbar>
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_220px_auto_auto]">
            <div class="relative">
              <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 dark:text-dark-400">
                <BaseIcon
                  name="search"
                  size="sm"
                />
              </div>
              <BaseInput
                v-model="queryInput"
                class="pl-10"
                placeholder="按用户名搜索"
              />
            </div>
            <BaseSelect v-model="statusInput">
              <option value="">
                全部状态
              </option>
              <option value="active">
                active
              </option>
              <option value="disabled">
                disabled
              </option>
            </BaseSelect>
            <BaseButton
              variant="secondary"
              @click="resetFilters"
            >
              重置
            </BaseButton>
            <BaseButton @click="applyFilters">
              应用筛选
            </BaseButton>
          </div>
        </FilterToolbar>
      </template>

      <template #table>
        <div
          v-if="loading"
          class="p-6 text-sm text-slate-500 dark:text-dark-300"
        >
          正在加载用户列表...
        </div>

        <div
          v-else-if="items.length"
          class="pw-table-wrapper"
        >
          <table class="pw-table">
            <thead>
              <tr>
                <th>账号</th>
                <th>邮箱</th>
                <th>角色</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>ID</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="user in items"
                :key="user.id"
              >
                <td>
                  <div class="flex items-center gap-3">
                    <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-500 dark:bg-dark-800 dark:text-dark-300">
                      <BaseIcon
                        name="user"
                        size="sm"
                      />
                    </div>
                    <div class="font-semibold text-slate-900 dark:text-white">
                      {{ user.username }}
                    </div>
                  </div>
                </td>
                <td class="text-slate-500 dark:text-dark-300">
                  {{ user.email || '未填写' }}
                </td>
                <td>
                  <StatusPill :tone="user.is_super_admin ? 'info' : 'neutral'">
                    {{ user.is_super_admin ? 'admin' : 'member' }}
                  </StatusPill>
                </td>
                <td>
                  <StatusPill :tone="user.status === 'active' ? 'success' : 'warning'">
                    {{ user.status }}
                  </StatusPill>
                </td>
                <td class="text-slate-500 dark:text-dark-300">
                  {{ formatDateTime(user.created_at) }}
                </td>
                <td class="text-slate-400 dark:text-dark-400">
                  {{ shortId(user.id) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <EmptyState
          v-else
          icon="users"
          title="没有找到用户"
          description="当前筛选条件下没有用户数据。后续创建用户、查看用户详情和项目关系可以继续挂在这套母版上。"
        />
      </template>
    </TablePageLayout>
  </section>
</template>

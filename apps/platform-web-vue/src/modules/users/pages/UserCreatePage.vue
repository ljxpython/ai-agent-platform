<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import MetricCard from '@/components/platform/MetricCard.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { createUser } from '@/services/users/users.service'

const router = useRouter()

const username = ref('')
const password = ref('')
const isSuperAdmin = ref(false)
const submitting = ref(false)
const error = ref('')
const notice = ref('')

const normalizedUsername = computed(() => username.value.trim())
const requestPreview = computed(() => ({
  username: normalizedUsername.value,
  password: password.value ? '********' : '',
  is_super_admin: isSuperAdmin.value
}))
const stats = computed(() => [
  {
    label: '用户名长度',
    value: normalizedUsername.value.length,
    hint: '后端限制 1-64 个字符',
    icon: 'user',
    tone: normalizedUsername.value.length > 0 ? 'success' : 'warning'
  },
  {
    label: '密码长度',
    value: password.value.length,
    hint: '建议至少 8 位',
    icon: 'lock',
    tone: password.value.length >= 8 ? 'success' : 'danger'
  }
])

async function handleSubmit() {
  if (!normalizedUsername.value) {
    error.value = '用户名不能为空'
    return
  }

  if (!password.value.trim()) {
    error.value = '密码不能为空'
    return
  }

  submitting.value = true
  error.value = ''
  notice.value = ''

  try {
    const created = await createUser({
      username: normalizedUsername.value,
      password: password.value,
      is_super_admin: isSuperAdmin.value
    })

    notice.value = `已创建用户：${created.username}`
    void router.replace('/workspace/users')
  } catch (createError) {
    error.value = createError instanceof Error ? createError.message : '用户创建失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Users"
      title="新建用户"
      description="创建新的系统用户。这里承接旧版 `/workspace/users/new`，不再把用户创建链路留在迁移清单里。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="void router.push('/workspace/users')"
        >
          返回列表
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="用户创建失败"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作已完成"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-4 xl:grid-cols-2">
      <MetricCard
        v-for="itemStat in stats"
        :key="itemStat.label"
        :label="itemStat.label"
        :value="itemStat.value"
        :hint="itemStat.hint"
        :icon="itemStat.icon"
        :tone="itemStat.tone"
      />
    </div>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.85fr)]">
      <SurfaceCard class="space-y-5">
        <div>
          <div class="text-lg font-semibold text-gray-900 dark:text-white">
            创建表单
          </div>
          <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
            当前页负责最小可用创建链路：用户名、密码、是否超级管理员。
          </div>
        </div>

        <label class="block">
          <span class="pw-input-label">用户名</span>
          <input
            v-model="username"
            class="pw-input"
            placeholder="请输入用户名"
            :disabled="submitting"
            maxlength="64"
          >
        </label>

        <label class="block">
          <span class="pw-input-label">密码</span>
          <input
            v-model="password"
            type="password"
            class="pw-input"
            placeholder="请输入密码"
            :disabled="submitting"
          >
        </label>

        <label class="flex items-center gap-3 rounded-2xl border border-white/70 bg-white/80 px-4 py-4 text-sm dark:border-dark-700 dark:bg-dark-900/70">
          <input
            v-model="isSuperAdmin"
            type="checkbox"
            class="pw-table-checkbox"
            :disabled="submitting"
          >
          <span class="font-medium text-gray-900 dark:text-white">Super admin</span>
        </label>

        <div class="flex justify-end">
          <BaseButton
            :disabled="submitting"
            @click="handleSubmit"
          >
            <BaseIcon
              name="users"
              size="sm"
            />
            {{ submitting ? '创建中...' : '创建用户' }}
          </BaseButton>
        </div>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="text-lg font-semibold text-gray-900 dark:text-white">
          请求预览
        </div>
        <pre class="overflow-auto whitespace-pre-wrap break-words rounded-[24px] bg-gray-950 px-4 py-4 text-xs leading-6 text-gray-100">{{ JSON.stringify(requestPreview, null, 2) }}</pre>

        <div class="rounded-2xl border border-gray-100 bg-gray-50/80 px-4 py-4 text-sm leading-7 text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-200">
          创建成功后会直接返回用户列表页。复杂邀请式流程不在这轮迁移范围里，先把正式管理链路接通。
        </div>
      </SurfaceCard>
    </div>
  </section>
</template>

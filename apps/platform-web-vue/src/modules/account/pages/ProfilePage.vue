<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { updateMe } from '@/services/users/users.service'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()
const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const username = ref('')
const email = ref('')

async function loadProfile() {
  loading.value = true
  error.value = ''

  try {
    const profile = await authStore.fetchCurrentUser()
    username.value = profile?.username || ''
    email.value = profile?.email || ''
  } catch (loadError) {
    error.value = loadError instanceof Error ? loadError.message : '个人资料加载失败'
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  const nextUsername = username.value.trim()
  if (!nextUsername) {
    error.value = '用户名不能为空'
    return
  }

  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    await updateMe({
      username: nextUsername,
      email: email.value.trim()
    })
    await authStore.fetchCurrentUser()
    notice.value = '个人资料已更新'
  } catch (saveError) {
    error.value = saveError instanceof Error ? saveError.message : '个人资料更新失败'
  } finally {
    saving.value = false
  }
}

function signOut() {
  authStore.logout()
  workspaceStore.reset()
  void router.replace('/auth/login')
}

onMounted(() => {
  void loadProfile()
})

function handleSubmit(event: Event) {
  event.preventDefault()
  void saveProfile()
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Account"
      title="我的资料"
      description="资料页只保留当前登录用户最核心的可编辑信息，别把资料和高风险安全动作搅成一锅。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="() => router.push('/workspace/security')"
        >
          <BaseIcon
            name="lock"
            size="sm"
          />
          安全设置
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="资料页出现问题"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作成功"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <SurfaceCard>
        <form
          class="space-y-5"
          @submit="handleSubmit"
        >
          <div class="flex items-center gap-4 rounded-2xl bg-slate-50 p-4 dark:bg-dark-900">
            <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-600 text-lg font-semibold text-white shadow-glow">
              {{ (authStore.user?.username || 'U').slice(0, 1).toUpperCase() }}
            </div>
            <div>
              <div class="text-base font-semibold text-slate-900 dark:text-white">
                {{ authStore.user?.username || '未加载' }}
              </div>
              <div class="mt-1 text-sm text-slate-500 dark:text-dark-300">
                {{ authStore.roleLabel }}
              </div>
            </div>
          </div>

          <div class="grid gap-5">
            <label class="grid gap-2">
              <span class="pw-input-label">用户名</span>
              <BaseInput
                v-model="username"
                placeholder="请输入用户名"
              />
            </label>

            <label class="grid gap-2">
              <span class="pw-input-label">邮箱</span>
              <BaseInput
                v-model="email"
                placeholder="可选"
              />
            </label>
          </div>

          <div class="flex flex-wrap gap-3">
            <BaseButton
              type="submit"
              :disabled="loading || saving"
            >
              {{ saving ? '保存中...' : '保存资料' }}
            </BaseButton>
            <BaseButton
              variant="ghost"
              @click="loadProfile"
            >
              <BaseIcon
                name="refresh"
                size="sm"
              />
              重新加载
            </BaseButton>
          </div>
        </form>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="pw-page-eyebrow">
          Session
        </div>
        <div class="text-sm leading-7 text-slate-500 dark:text-dark-300">
          当前登录账号：{{ authStore.user?.username || '未加载' }}
        </div>
        <div class="text-sm leading-7 text-slate-500 dark:text-dark-300">
          角色：{{ authStore.roleLabel }}
        </div>
        <BaseButton
          variant="secondary"
          @click="signOut"
        >
          <BaseIcon
            name="logout"
            size="sm"
          />
          退出登录
        </BaseButton>
      </SurfaceCard>
    </div>
  </section>
</template>

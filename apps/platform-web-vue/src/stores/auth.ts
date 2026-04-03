import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginRequest } from '@/services/auth/auth.service'
import { clearTokenSet, getAccessToken, getTokenSet, setTokenSet } from '@/services/auth/token'
import { getMe } from '@/services/users/users.service'
import type { AuthTokenSet, ManagementUser } from '@/types/management'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<ManagementUser | null>(null)
  const loading = ref(false)
  const hydrated = ref(false)

  const isAuthenticated = computed(() => Boolean(getAccessToken()) && Boolean(user.value))
  const roleLabel = computed(() => (user.value?.is_super_admin ? '管理员' : '成员'))

  async function fetchCurrentUser(): Promise<ManagementUser | null> {
    if (!getAccessToken()) {
      user.value = null
      return null
    }

    try {
      const nextUser = await getMe()
      user.value = nextUser
      return nextUser
    } catch {
      clearTokenSet()
      user.value = null
      return null
    }
  }

  async function hydrate() {
    if (hydrated.value) {
      return
    }

    hydrated.value = true
    if (!getTokenSet()) {
      user.value = null
      return
    }

    await fetchCurrentUser()
  }

  async function login(payload: { username: string; password: string }) {
    loading.value = true

    try {
      const response = await loginRequest(payload)
      const tokenSet: AuthTokenSet = {
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        tokenType: response.token_type
      }

      setTokenSet(tokenSet)
      await fetchCurrentUser()
      hydrated.value = true
    } finally {
      loading.value = false
    }
  }

  function logout() {
    clearTokenSet()
    user.value = null
  }

  return {
    user,
    loading,
    hydrated,
    isAuthenticated,
    roleLabel,
    hydrate,
    login,
    logout,
    fetchCurrentUser
  }
})

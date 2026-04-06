import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { bootstrapPlatformV2Session, login as loginRequest } from '@/services/auth/auth.service'
import {
  clearAllTokenSets,
  clearTokenSet,
  getAccessToken,
  getTokenSet,
  setTokenSet
} from '@/services/auth/token'
import { getCurrentProfile } from '@/services/identity/identity.service'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
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
      const nextUser =
        resolvePlatformClientScope('identity') === 'v2'
          ? await getCurrentProfile({ mode: 'runtime' }).catch(() => getCurrentProfile())
          : await getCurrentProfile()
      user.value = nextUser
      return nextUser
    } catch {
      clearAllTokenSets()
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
      const v2TokenSet = await bootstrapPlatformV2Session(payload)
      if (v2TokenSet) {
        setTokenSet(v2TokenSet, 'v2')
      } else {
        clearTokenSet('v2')
      }
      await fetchCurrentUser()
      hydrated.value = true
    } finally {
      loading.value = false
    }
  }

  function logout() {
    clearAllTokenSets()
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

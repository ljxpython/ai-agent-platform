import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginRequest, logout as logoutRequest } from '@/services/auth/auth.service'
import { describePlatformRole } from '@/services/auth/permissions'
import {
  clearAllTokenSets,
  getRefreshToken,
  getTokenSet,
  hasStoredAuthSession,
  setTokenSet
} from '@/services/auth/token'
import { getCurrentProfile } from '@/services/identity/identity.service'
import type { AuthTokenSet, ManagementUser } from '@/types/management'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<ManagementUser | null>(null)
  const loading = ref(false)
  const hydrated = ref(false)

  const isAuthenticated = computed(() => hasStoredAuthSession() && Boolean(user.value))
  const roleLabel = computed(() => describePlatformRole(user.value))

  async function fetchCurrentUser(): Promise<ManagementUser | null> {
    if (!hasStoredAuthSession()) {
      user.value = null
      return null
    }

    try {
      const nextUser = await getCurrentProfile()
      user.value = nextUser
      return nextUser
    } catch {
      clearSessionState()
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

  function clearSessionState() {
    clearAllTokenSets()
    user.value = null
    hydrated.value = false
  }

  function logout() {
    const refreshToken = getRefreshToken()
    clearSessionState()
    if (refreshToken) {
      void logoutRequest(refreshToken).catch(() => {
        // ignore logout upstream failure after local session is cleared
      })
    }
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
    clearSessionState,
    fetchCurrentUser
  }
})

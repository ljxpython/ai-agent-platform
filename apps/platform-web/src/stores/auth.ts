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
  const sessionEpoch = ref(0)
  let hydratePromise: Promise<void> | null = null

  const isAuthenticated = computed(() => hasStoredAuthSession() && Boolean(user.value))
  const roleLabel = computed(() => describePlatformRole(user.value))

  async function fetchCurrentUser(): Promise<ManagementUser | null> {
    const epoch = sessionEpoch.value
    if (!hasStoredAuthSession()) {
      user.value = null
      return null
    }

    try {
      const nextUser = await getCurrentProfile()
      if (epoch !== sessionEpoch.value) return null
      user.value = nextUser
      return nextUser
    } catch {
      if (epoch === sessionEpoch.value) clearSessionState()
      return null
    }
  }

  async function hydrate() {
    if (hydratePromise) return hydratePromise
    if (hydrated.value) {
      return
    }

    if (!getTokenSet()) {
      user.value = null
      hydrated.value = true
      return
    }
    const epoch = sessionEpoch.value
    const pending = fetchCurrentUser().then(() => {
      if (epoch === sessionEpoch.value) hydrated.value = true
    })
    hydratePromise = pending
    try { await pending } finally {
      if (hydratePromise === pending) hydratePromise = null
    }
  }

  async function login(payload: { username: string; password: string }) {
    clearSessionState()
    const epoch = sessionEpoch.value
    loading.value = true

    try {
      const response = await loginRequest(payload)
      if (epoch !== sessionEpoch.value) return
      const tokenSet: AuthTokenSet = {
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        tokenType: response.token_type
      }

      setTokenSet(tokenSet)
      await fetchCurrentUser()
      if (epoch === sessionEpoch.value) hydrated.value = true
    } finally {
      if (epoch === sessionEpoch.value) loading.value = false
    }
  }

  function clearSessionState() {
    sessionEpoch.value += 1
    hydratePromise = null
    clearAllTokenSets()
    try {
      for (const key of Object.keys(sessionStorage)) {
        if (key.startsWith('pw:queued-message:') || key.startsWith('pw:chat:draft:')) sessionStorage.removeItem(key)
      }
    } catch { /* Session teardown must still complete when storage is unavailable. */ }
    user.value = null
    hydrated.value = false
    loading.value = false
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
    sessionEpoch,
    isAuthenticated,
    roleLabel,
    hydrate,
    login,
    logout,
    clearSessionState,
    fetchCurrentUser
  }
})

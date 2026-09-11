import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ManagementUser } from '@/types/management'

const profile = vi.hoisted(() => vi.fn())
vi.mock('@/services/identity/identity.service', () => ({ getCurrentProfile: profile }))
vi.mock('@/services/auth/auth.service', () => ({ login: vi.fn(), logout: vi.fn() }))
import { useAuthStore } from './auth'
import { setTokenSet } from '@/services/auth/token'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  profile.mockReset()
  setTokenSet({ accessToken: 'test-access', refreshToken: 'test-refresh', tokenType: 'bearer' })
})

it('coalesces hydration and discards a profile that arrives after logout', async () => {
  let resolve!: (user: ManagementUser) => void
  profile.mockReturnValue(new Promise<ManagementUser>((done) => { resolve = done }))
  const store = useAuthStore()
  const first = store.hydrate()
  const second = store.hydrate()
  expect(profile).toHaveBeenCalledOnce()
  sessionStorage.setItem('pw:queued-message:old:p:t', 'private draft')
  sessionStorage.setItem('pw:chat:draft:old:p:a:t', 'private text')
  sessionStorage.setItem('unrelated', 'keep')
  store.clearSessionState()
  expect(sessionStorage.getItem('pw:queued-message:old:p:t')).toBeNull()
  expect(sessionStorage.getItem('pw:chat:draft:old:p:a:t')).toBeNull()
  expect(sessionStorage.getItem('unrelated')).toBe('keep')
  resolve({ id: 'old-user' } as ManagementUser)
  await Promise.all([first, second])
  expect(store.user).toBeNull()
  expect(store.hydrated).toBe(false)
  expect(store.isAuthenticated).toBe(false)
})

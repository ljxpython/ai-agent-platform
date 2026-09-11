import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ProjectAccess } from '@/types/management'

const api = vi.hoisted(() => ({ getProjectAccess: vi.fn(), listProjects: vi.fn() }))
vi.mock('@/services/projects/projects.service', () => api)
import { useWorkspaceStore } from './workspace'

beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

it('clears old permissions immediately and ignores delayed project responses', async () => {
  let resolveA!: (value: ProjectAccess) => void
  api.getProjectAccess.mockImplementation((id: string) => id === 'A'
    ? new Promise<ProjectAccess>((resolve) => { resolveA = resolve })
    : Promise.resolve({ project_id: 'B', permissions: [], roles: [] }))
  const store = useWorkspaceStore()
  const pending = store.setProjectId('A')
  await store.setProjectId('B')
  resolveA({ project_id: 'A', permissions: ['project.runtime.write'], roles: ['project_admin'] })
  await pending
  expect(store.currentProjectAccess?.project_id).toBe('B')
  expect(store.currentProjectAccess?.permissions).toEqual([])
})

it('logout invalidates in-flight hydration', async () => {
  let resolve!: (rows: []) => void
  api.listProjects.mockReturnValue(new Promise<[]>((done) => { resolve = done }))
  const store = useWorkspaceStore()
  const pending = store.hydrateContext()
  store.reset()
  resolve([])
  await pending
  expect(store.contextLoaded).toBe(false)
  expect(store.currentProjectAccess).toBeNull()
  expect(store.currentProjectId).toBe('')
})

import { defineStore } from 'pinia'
import { resolvePlatformClientScope } from '@/services/platform/control-plane'
import { listProjects, listRuntimeProjects } from '@/services/projects/projects.service'
import type { ManagementProject } from '@/types/management'

const PROJECT_STORAGE_KEY = 'pw:workspace:project-id'
const RUNTIME_PROJECT_STORAGE_KEY = 'pw:workspace:runtime-project-id'

function readProjectPreference(storageKey: string) {
  if (typeof window === 'undefined') {
    return ''
  }

  return window.localStorage.getItem(storageKey)?.trim() || ''
}

function writeProjectPreference(storageKey: string, projectId: string) {
  if (typeof window === 'undefined') {
    return
  }

  if (projectId) {
    window.localStorage.setItem(storageKey, projectId)
    return
  }

  window.localStorage.removeItem(storageKey)
}

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    currentProjectId: '',
    projects: [] as ManagementProject[],
    loading: false,
    runtimeProjectId: '',
    runtimeProjects: [] as ManagementProject[],
    runtimeLoading: false
  }),
  getters: {
    currentProject(state) {
      return state.projects.find((project) => project.id === state.currentProjectId) ?? null
    },
    runtimeProject(state) {
      return state.runtimeProjects.find((project) => project.id === state.runtimeProjectId) ?? null
    },
    runtimeScope() {
      return resolvePlatformClientScope('runtime_gateway')
    },
    runtimeContextEnabled() {
      return resolvePlatformClientScope('runtime_gateway') === 'v2'
    },
    runtimeScopedProjectId(state) {
      return resolvePlatformClientScope('runtime_gateway') === 'v2'
        ? state.runtimeProjectId
        : state.currentProjectId
    },
    runtimeScopedProjects(state) {
      return resolvePlatformClientScope('runtime_gateway') === 'v2'
        ? state.runtimeProjects
        : state.projects
    },
    runtimeScopedProject(state) {
      const activeProjects =
        resolvePlatformClientScope('runtime_gateway') === 'v2'
          ? state.runtimeProjects
          : state.projects
      const activeProjectId =
        resolvePlatformClientScope('runtime_gateway') === 'v2'
          ? state.runtimeProjectId
          : state.currentProjectId

      return activeProjects.find((project) => project.id === activeProjectId) ?? null
    }
  },
  actions: {
    hydrateProjectPreference() {
      this.currentProjectId = readProjectPreference(PROJECT_STORAGE_KEY)
    },
    setProjectId(projectId: string) {
      this.currentProjectId = projectId
      writeProjectPreference(PROJECT_STORAGE_KEY, projectId)
    },
    hydrateRuntimeProjectPreference() {
      this.runtimeProjectId = readProjectPreference(RUNTIME_PROJECT_STORAGE_KEY)
    },
    setRuntimeProjectId(projectId: string) {
      this.runtimeProjectId = projectId
      writeProjectPreference(RUNTIME_PROJECT_STORAGE_KEY, projectId)
    },
    async hydrateContext() {
      this.loading = true

      try {
        this.hydrateProjectPreference()
        const rows = await listProjects()
        this.projects = rows

        const nextProjectId =
          rows.find((project) => project.id === this.currentProjectId)?.id ||
          rows[0]?.id ||
          ''

        this.setProjectId(nextProjectId)
      } catch {
        this.projects = []
        this.setProjectId('')
      } finally {
        this.loading = false
      }
    },
    async hydrateRuntimeContext() {
      this.runtimeLoading = true

      try {
        this.hydrateRuntimeProjectPreference()
        const rows = await listRuntimeProjects()
        this.runtimeProjects = rows

        const nextProjectId =
          rows.find((project) => project.id === this.runtimeProjectId)?.id ||
          rows[0]?.id ||
          ''

        this.setRuntimeProjectId(nextProjectId)
      } catch {
        this.runtimeProjects = []
        this.setRuntimeProjectId('')
      } finally {
        this.runtimeLoading = false
      }
    },
    reset() {
      this.projects = []
      this.setProjectId('')
      this.runtimeProjects = []
      this.setRuntimeProjectId('')
      this.loading = false
      this.runtimeLoading = false
    }
  }
})

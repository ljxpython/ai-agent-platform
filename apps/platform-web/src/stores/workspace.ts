import { defineStore } from 'pinia'
import { listProjects } from '@/services/projects/projects.service'
import type { ManagementProject } from '@/types/management'

const PROJECT_STORAGE_KEY = 'pw:workspace:project-id'

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
    loading: false
  }),
  getters: {
    currentProject(state) {
      return state.projects.find((project) => project.id === state.currentProjectId) ?? null
    }
  },
  actions: {
    hydrateProjectPreference() {
      this.currentProjectId = readProjectPreference(PROJECT_STORAGE_KEY)
    },
    setProjectId(projectId: string) {
      this.currentProjectId = projectId
      writeProjectPreference(PROJECT_STORAGE_KEY, projectId.trim())
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
    reset() {
      this.projects = []
      this.setProjectId('')
      this.loading = false
    }
  }
})

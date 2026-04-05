import { defineStore } from 'pinia'
import { listProjects } from '@/services/projects/projects.service'
import type { ManagementProject } from '@/types/management'

const PROJECT_STORAGE_KEY = 'pw:workspace:project-id'

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
      if (typeof window === 'undefined') {
        return
      }

      this.currentProjectId = window.localStorage.getItem(PROJECT_STORAGE_KEY)?.trim() || ''
    },
    setProjectId(projectId: string) {
      this.currentProjectId = projectId
      if (typeof window !== 'undefined') {
        if (projectId) {
          window.localStorage.setItem(PROJECT_STORAGE_KEY, projectId)
        } else {
          window.localStorage.removeItem(PROJECT_STORAGE_KEY)
        }
      }
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

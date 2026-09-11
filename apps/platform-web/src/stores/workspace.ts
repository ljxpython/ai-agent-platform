import { defineStore } from 'pinia'
import { getProjectAccess, listProjects } from '@/services/projects/projects.service'
import type { ManagementProject, ProjectAccess } from '@/types/management'

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
    currentProjectAccess: null as ProjectAccess | null,
    loading: false,
    accessLoading: false,
    contextLoaded: false,
    error: '',
    accessEpoch: 0,
    contextEpoch: 0
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
    async setProjectId(projectId: string) {
      const id = projectId.trim()
      const epoch = ++this.accessEpoch
      this.currentProjectId = id
      this.currentProjectAccess = null
      this.accessLoading = Boolean(id)
      this.error = ''
      writeProjectPreference(PROJECT_STORAGE_KEY, id)
      try {
        const access = id ? await getProjectAccess(id) : null
        if (epoch === this.accessEpoch) this.currentProjectAccess = access
      } catch (error) {
        if (epoch === this.accessEpoch) this.error = '项目权限加载失败，请重试'
        throw error
      } finally {
        if (epoch === this.accessEpoch) this.accessLoading = false
      }
    },
    async hydrateContext() {
      const epoch = ++this.contextEpoch
      this.loading = true
      this.error = ''

      try {
        this.hydrateProjectPreference()
        const rows = await listProjects()
        if (epoch !== this.contextEpoch) return
        this.projects = rows

        const nextProjectId =
          rows.find((project) => project.id === this.currentProjectId)?.id ||
          rows[0]?.id ||
          ''

        await this.setProjectId(nextProjectId)
      } catch {
        if (epoch !== this.contextEpoch) return
        this.projects = []
        await this.setProjectId('')
        this.error = '项目列表或权限加载失败，请重试'
      } finally {
        if (epoch === this.contextEpoch) {
          this.loading = false
          this.contextLoaded = true
        }
      }
    },
    reset() {
      this.contextEpoch += 1
      this.projects = []
      void this.setProjectId('')
      this.loading = false
      this.contextLoaded = false
    }
  }
})

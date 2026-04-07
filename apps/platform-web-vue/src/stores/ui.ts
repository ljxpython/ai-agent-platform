import { defineStore } from 'pinia'

export type UiToastType = 'success' | 'error' | 'warning' | 'info'
const SIDEBAR_GROUPS_STORAGE_KEY = 'pw:ui:sidebar-expanded-groups'

export type UiToast = {
  id: string
  type: UiToastType
  title?: string
  message: string
  duration: number
}

function resolveExpandedSidebarGroups(): Record<string, boolean> {
  if (typeof window === 'undefined') {
    return {}
  }

  try {
    const rawValue = window.localStorage.getItem(SIDEBAR_GROUPS_STORAGE_KEY)
    if (!rawValue) {
      return {}
    }

    const parsed = JSON.parse(rawValue)
    if (Array.isArray(parsed)) {
      return Object.fromEntries(
        parsed
          .map((item) => String(item).trim())
          .filter(Boolean)
          .map((item) => [item, true]),
      )
    }

    if (!parsed || typeof parsed !== 'object') {
      return {}
    }

    return Object.fromEntries(
      Object.entries(parsed)
        .map(([key, value]) => [String(key).trim(), Boolean(value)] as const)
        .filter(([key]) => Boolean(key)),
    )
  } catch {
    return {}
  }
}

function persistExpandedSidebarGroups(groupState: Record<string, boolean>) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(
    SIDEBAR_GROUPS_STORAGE_KEY,
    JSON.stringify(groupState),
  )
}

export const useUiStore = defineStore('ui', {
  state: () => ({
    sidebarCollapsed: false,
    sidebarExpandedGroups: resolveExpandedSidebarGroups() as Record<string, boolean>,
    toasts: [] as UiToast[]
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    ensureSidebarExpandedGroups(groupIds: string[]) {
      const nextGroupIds = Array.from(
        new Set(
          groupIds
            .map((item) => item.trim())
            .filter(Boolean),
        ),
      )
      const nextState = Object.fromEntries(
        nextGroupIds.map((groupId) => [
          groupId,
          groupId in this.sidebarExpandedGroups
            ? Boolean(this.sidebarExpandedGroups[groupId])
            : true,
        ]),
      )

      const changed =
        Object.keys(nextState).length !== Object.keys(this.sidebarExpandedGroups).length
        || Object.entries(nextState).some(
          ([groupId, expanded]) => this.sidebarExpandedGroups[groupId] !== expanded,
        )

      if (!changed) {
        return
      }

      this.sidebarExpandedGroups = nextState
      persistExpandedSidebarGroups(this.sidebarExpandedGroups)
    },
    toggleSidebarGroup(groupId: string) {
      const normalizedGroupId = groupId.trim()
      if (!normalizedGroupId) {
        return
      }

      this.sidebarExpandedGroups = {
        ...this.sidebarExpandedGroups,
        [normalizedGroupId]: !this.sidebarExpandedGroups[normalizedGroupId],
      }
      persistExpandedSidebarGroups(this.sidebarExpandedGroups)
    },
    isSidebarGroupExpanded(groupId: string) {
      return this.sidebarExpandedGroups[groupId] !== false
    },
    pushToast(payload: {
      type?: UiToastType
      title?: string
      message: string
      duration?: number
    }) {
      const toast: UiToast = {
        id: `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        type: payload.type ?? 'info',
        title: payload.title,
        message: payload.message,
        duration: payload.duration ?? 3200
      }

      this.toasts.push(toast)

      if (typeof window !== 'undefined' && toast.duration > 0) {
        window.setTimeout(() => {
          this.removeToast(toast.id)
        }, toast.duration)
      }
    },
    removeToast(id: string) {
      this.toasts = this.toasts.filter((item) => item.id !== id)
    }
  }
})

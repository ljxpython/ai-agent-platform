import { defineStore } from 'pinia'

const GUIDE_STORAGE_KEY = 'pw:guides:dismissed'

function readDismissedIds() {
  if (typeof window === 'undefined') {
    return [] as string[]
  }

  const raw = window.localStorage.getItem(GUIDE_STORAGE_KEY)
  if (!raw) {
    return []
  }

  try {
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

function persistDismissedIds(ids: string[]) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(GUIDE_STORAGE_KEY, JSON.stringify(ids))
}

export const useGuidesStore = defineStore('guides', {
  state: () => ({
    hydrated: false,
    dismissedIds: [] as string[]
  }),
  actions: {
    init() {
      if (this.hydrated) {
        return
      }

      this.dismissedIds = readDismissedIds()
      this.hydrated = true
    },
    isDismissed(id: string) {
      return this.dismissedIds.includes(id)
    },
    dismiss(id: string) {
      if (!id.trim() || this.dismissedIds.includes(id)) {
        return
      }

      this.dismissedIds = [...this.dismissedIds, id]
      persistDismissedIds(this.dismissedIds)
    }
  }
})

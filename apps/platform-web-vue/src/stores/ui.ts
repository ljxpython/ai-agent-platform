import { defineStore } from 'pinia'

export type UiToastType = 'success' | 'error' | 'warning' | 'info'

export type UiToast = {
  id: string
  type: UiToastType
  title?: string
  message: string
  duration: number
}

export const useUiStore = defineStore('ui', {
  state: () => ({
    sidebarCollapsed: false,
    toasts: [] as UiToast[]
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
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

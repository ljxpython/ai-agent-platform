import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark'
export type ThemePreset = 'workspace'

function getInitialMode(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light'
  }

  const saved = window.localStorage.getItem('pw:theme:mode')
  if (saved === 'light' || saved === 'dark') {
    return saved
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: 'light' as ThemeMode,
    preset: 'workspace' as ThemePreset
  }),
  actions: {
    init() {
      this.mode = getInitialMode()
    },
    applyTheme() {
      this.init()
      document.documentElement.classList.toggle('dark', this.mode === 'dark')
      window.localStorage.setItem('pw:theme:mode', this.mode)
    },
    toggleMode() {
      this.mode = this.mode === 'dark' ? 'light' : 'dark'
      this.applyTheme()
    }
  }
})

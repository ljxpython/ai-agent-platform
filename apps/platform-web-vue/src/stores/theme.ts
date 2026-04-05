import { defineStore } from 'pinia'

export type ThemeMode = 'light' | 'dark'
export type ThemePreset = 'workspace'
export const THEME_STORAGE_KEY = 'pw:theme:mode'

export function resolveThemeMode(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light'
  }

  const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') {
    return saved
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyThemeMode(mode: ThemeMode) {
  if (typeof document === 'undefined') {
    return
  }

  document.documentElement.classList.toggle('dark', mode === 'dark')
  document.documentElement.dataset.themeMode = mode
  document.documentElement.style.colorScheme = mode
}

function persistThemeMode(mode: ThemeMode) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(THEME_STORAGE_KEY, mode)
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: 'light' as ThemeMode,
    preset: 'workspace' as ThemePreset
  }),
  actions: {
    init() {
      this.mode = resolveThemeMode()
      applyThemeMode(this.mode)
    },
    applyTheme() {
      applyThemeMode(this.mode)
      persistThemeMode(this.mode)
    },
    setMode(mode: ThemeMode) {
      this.mode = mode
      this.applyTheme()
    },
    toggleMode() {
      this.setMode(this.mode === 'dark' ? 'light' : 'dark')
    }
  }
})

import { computed, ref, watch } from 'vue'
import type { FilterSettingItem } from '@/components/platform/filter-settings'

function defaultVisibleKeys(items: FilterSettingItem[]) {
  return items
    .filter((item) => item.alwaysVisible || item.defaultVisible !== false)
    .map((item) => item.key)
}

function normalizeVisibleKeys(items: FilterSettingItem[], candidate: string[]) {
  const allowed = new Set(items.map((item) => item.key))
  const next = new Set(candidate.filter((key) => allowed.has(key)))

  items.forEach((item) => {
    if (item.alwaysVisible) {
      next.add(item.key)
    }
  })

  return items.filter((item) => next.has(item.key)).map((item) => item.key)
}

function readPersistedVisibleKeys(items: FilterSettingItem[], storageKey: string) {
  if (!storageKey || typeof window === 'undefined') {
    return defaultVisibleKeys(items)
  }

  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) {
      return defaultVisibleKeys(items)
    }

    return normalizeVisibleKeys(items, JSON.parse(raw) as string[])
  } catch {
    return defaultVisibleKeys(items)
  }
}

export function useVisibleFilterSettings(items: FilterSettingItem[], storageKey = '') {
  const visibleFilterKeys = ref<string[]>(readPersistedVisibleKeys(items, storageKey))
  const visibleFilterSet = computed(() => new Set(visibleFilterKeys.value))

  function setVisibleFilterKeys(nextKeys: string[]) {
    visibleFilterKeys.value = normalizeVisibleKeys(items, nextKeys)
  }

  watch(
    visibleFilterKeys,
    (nextKeys) => {
      if (!storageKey || typeof window === 'undefined') {
        return
      }

      window.localStorage.setItem(storageKey, JSON.stringify(nextKeys))
    },
    { deep: true }
  )

  return {
    visibleFilterKeys,
    visibleFilterSet,
    setVisibleFilterKeys
  }
}

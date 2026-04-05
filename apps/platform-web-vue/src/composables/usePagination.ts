import { computed, ref } from 'vue'

type UsePaginationOptions = {
  initialPageSize?: number
  storageKey?: string
}

function resolveInitialPageSize(initialPageSize: number, storageKey?: string) {
  if (!storageKey || typeof window === 'undefined') {
    return initialPageSize
  }

  const saved = window.localStorage.getItem(storageKey)
  const parsed = saved ? Number.parseInt(saved, 10) : Number.NaN
  return Number.isFinite(parsed) && parsed > 0 ? parsed : initialPageSize
}

export function usePagination(options: UsePaginationOptions = {}) {
  const initialPageSize = options.initialPageSize ?? 20
  const page = ref(1)
  const pageSize = ref(resolveInitialPageSize(initialPageSize, options.storageKey))
  const total = ref(0)

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
  const offset = computed(() => (page.value - 1) * pageSize.value)
  const from = computed(() => (total.value === 0 ? 0 : offset.value + 1))
  const to = computed(() => Math.min(offset.value + pageSize.value, total.value))

  function setPage(nextPage: number) {
    const safePage = Math.min(Math.max(Math.trunc(nextPage || 1), 1), totalPages.value)
    page.value = safePage
  }

  function setPageSize(nextPageSize: number) {
    const safePageSize = Math.max(1, Math.trunc(nextPageSize || initialPageSize))
    pageSize.value = safePageSize
    page.value = 1

    if (options.storageKey && typeof window !== 'undefined') {
      window.localStorage.setItem(options.storageKey, String(safePageSize))
    }
  }

  function setTotal(nextTotal: number) {
    total.value = Math.max(0, Math.trunc(nextTotal || 0))

    if (page.value > totalPages.value) {
      page.value = totalPages.value
    }
  }

  function resetPage() {
    page.value = 1
  }

  return {
    page,
    pageSize,
    total,
    totalPages,
    offset,
    from,
    to,
    setPage,
    setPageSize,
    setTotal,
    resetPage
  }
}

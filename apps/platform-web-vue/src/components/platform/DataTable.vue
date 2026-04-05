<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useSlots, watch } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import type { DataTableColumn } from '@/components/platform/data-table'

type DataRow = Record<string, unknown>
type PersistedSortState = {
  key: string
  order: 'asc' | 'desc'
}

const props = withDefaults(
  defineProps<{
    columns: DataTableColumn[]
    rows: DataRow[]
    loading?: boolean
    rowKey?: string | ((row: DataRow, index: number) => string | number)
    rowClass?: (
      row: DataRow,
      index: number
    ) => string | string[] | Record<string, boolean> | undefined
    page?: number
    pageSize?: number
    sortStorageKey?: string
    columnStorageKey?: string
    defaultSortKey?: string
    defaultSortOrder?: 'asc' | 'desc'
    selectable?: boolean
    selectedRowKeys?: Array<string | number>
    emptyTitle?: string
    emptyDescription?: string
    emptyIcon?: string
    emptyActionLabel?: string
    actionsLabel?: string
    selectLabel?: string
    showColumnSettings?: boolean
  }>(),
  {
    loading: false,
    rowKey: 'id',
    rowClass: undefined,
    page: 0,
    pageSize: 0,
    sortStorageKey: '',
    columnStorageKey: '',
    defaultSortKey: '',
    defaultSortOrder: 'asc',
    selectable: false,
    selectedRowKeys: () => [],
    emptyTitle: '暂无数据',
    emptyDescription: '当前条件下没有可展示的数据。',
    emptyIcon: 'sparkle',
    emptyActionLabel: '',
    actionsLabel: '操作',
    selectLabel: '选择',
    showColumnSettings: true
  }
)

const emit = defineEmits<{
  emptyAction: []
  'update:selectedRowKeys': [keys: Array<string | number>]
}>()

const slots = useSlots()
const rootRef = ref<HTMLElement | null>(null)
const selectAllRef = ref<HTMLInputElement | null>(null)
const columnMenuOpen = ref(false)
const sortKey = ref('')
const sortOrder = ref<'asc' | 'desc'>('asc')
const hiddenColumns = ref<string[]>([])
const hasMounted = ref(false)

const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: 'base'
})

const hasActionsColumn = computed(() => Boolean(slots['cell-actions']))
const columnSignature = computed(() =>
  props.columns.map((column) => `${column.key}:${column.sortable ? '1' : '0'}`).join('|')
)
const defaultHiddenColumns = computed(() =>
  props.columns.filter((column) => column.defaultHidden && !column.alwaysVisible).map((column) => column.key)
)
const toggleableColumns = computed(() => props.columns.filter((column) => !column.alwaysVisible))
const hiddenColumnSet = computed(() => new Set(hiddenColumns.value))
const visibleColumns = computed(() =>
  props.columns.filter((column) => column.alwaysVisible || !hiddenColumnSet.value.has(column.key))
)
const mobileColumns = computed(() => visibleColumns.value.filter((column) => column.key !== 'actions'))

function isSortableKey(candidate: string) {
  return props.columns.some((column) => column.key === candidate && column.sortable)
}

function normalizeSortKey(candidate: string) {
  return isSortableKey(candidate) ? candidate : ''
}

function normalizeSortOrder(candidate: unknown): 'asc' | 'desc' {
  return candidate === 'desc' ? 'desc' : 'asc'
}

function normalizeHiddenColumns(candidate: string[]) {
  const allowed = new Set(toggleableColumns.value.map((column) => column.key))
  return candidate.filter((key) => allowed.has(key))
}

function readPersistedSortState(): PersistedSortState | null {
  if (!props.sortStorageKey || typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.localStorage.getItem(props.sortStorageKey)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as Partial<PersistedSortState>
    const key = normalizeSortKey(typeof parsed.key === 'string' ? parsed.key : '')
    if (!key) {
      return null
    }

    return {
      key,
      order: normalizeSortOrder(parsed.order)
    }
  } catch {
    return null
  }
}

function writePersistedSortState() {
  if (!props.sortStorageKey || typeof window === 'undefined' || !sortKey.value) {
    return
  }

  window.localStorage.setItem(
    props.sortStorageKey,
    JSON.stringify({
      key: sortKey.value,
      order: sortOrder.value
    })
  )
}

function readPersistedHiddenColumns(): string[] | null {
  if (!props.columnStorageKey || typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.localStorage.getItem(props.columnStorageKey)
    if (!raw) {
      return null
    }

    return normalizeHiddenColumns(JSON.parse(raw) as string[])
  } catch {
    return null
  }
}

function writePersistedHiddenColumns() {
  if (!props.columnStorageKey || typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(props.columnStorageKey, JSON.stringify(hiddenColumns.value))
}

function resolveInitialSortState(): PersistedSortState | null {
  const persisted = readPersistedSortState()
  if (persisted) {
    return persisted
  }

  const defaultKey = normalizeSortKey(props.defaultSortKey)
  if (!defaultKey) {
    return null
  }

  return {
    key: defaultKey,
    order: normalizeSortOrder(props.defaultSortOrder)
  }
}

function resolveRowKey(row: DataRow, index: number) {
  if (typeof props.rowKey === 'function') {
    return props.rowKey(row, index)
  }

  if (typeof props.rowKey === 'string' && props.rowKey) {
    const candidate = row?.[props.rowKey]
    return typeof candidate === 'string' || typeof candidate === 'number' ? candidate : index
  }

  return index
}

function resolveRowClass(row: DataRow, index: number) {
  return props.rowClass?.(row, index)
}

function resolveVisibleRowIndex(index: number) {
  if (props.page > 0 && props.pageSize > 0) {
    return (props.page - 1) * props.pageSize + index
  }

  return index
}

function resolveCellValue(row: DataRow, column: DataTableColumn) {
  return row?.[column.key]
}

function resolveSortValue(row: DataRow, columnKey: string) {
  const column = props.columns.find((item) => item.key === columnKey)
  if (!column) {
    return null
  }

  return column.sortValue ? column.sortValue(row) : resolveCellValue(row, column)
}

function isNullishOrEmpty(value: unknown) {
  return value === null || value === undefined || value === ''
}

function toSortableNumber(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }

  if (typeof value === 'boolean') {
    return value ? 1 : 0
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) {
      return null
    }

    const timestamp = Date.parse(trimmed)
    if (!Number.isNaN(timestamp)) {
      return timestamp
    }

    const numeric = Number(trimmed)
    return Number.isFinite(numeric) ? numeric : null
  }

  return null
}

function toSortableString(value: unknown) {
  if (value === null || value === undefined) {
    return ''
  }

  if (typeof value === 'string') {
    return value
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }

  if (value instanceof Date) {
    return value.toISOString()
  }

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function compareValues(left: unknown, right: unknown) {
  const leftEmpty = isNullishOrEmpty(left)
  const rightEmpty = isNullishOrEmpty(right)

  if (leftEmpty && rightEmpty) {
    return 0
  }

  if (leftEmpty) {
    return 1
  }

  if (rightEmpty) {
    return -1
  }

  const leftNumber = toSortableNumber(left)
  const rightNumber = toSortableNumber(right)

  if (leftNumber !== null && rightNumber !== null) {
    if (leftNumber === rightNumber) {
      return 0
    }

    return leftNumber < rightNumber ? -1 : 1
  }

  return collator.compare(toSortableString(left), toSortableString(right))
}

const sortedRows = computed(() => {
  if (!sortKey.value) {
    return props.rows
  }

  return props.rows
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const compared = compareValues(
        resolveSortValue(left.row, sortKey.value),
        resolveSortValue(right.row, sortKey.value)
      )

      if (compared !== 0) {
        return sortOrder.value === 'asc' ? compared : -compared
      }

      return left.index - right.index
    })
    .map((item) => item.row)
})

const pagedRows = computed(() => {
  if (props.page <= 0 || props.pageSize <= 0) {
    return sortedRows.value
  }

  const start = (props.page - 1) * props.pageSize
  return sortedRows.value.slice(start, start + props.pageSize)
})

const selectedRowKeySet = computed(() => new Set(props.selectedRowKeys))
const pagedRowKeys = computed(() =>
  pagedRows.value.map((row, index) => resolveRowKey(row, resolveVisibleRowIndex(index)))
)
const pageAllSelected = computed(
  () =>
    props.selectable &&
    pagedRowKeys.value.length > 0 &&
    pagedRowKeys.value.every((key) => selectedRowKeySet.value.has(key))
)
const pagePartiallySelected = computed(
  () =>
    props.selectable &&
    pagedRowKeys.value.some((key) => selectedRowKeySet.value.has(key)) &&
    !pageAllSelected.value
)

function emitSelectedRowKeys(keys: Array<string | number>) {
  emit('update:selectedRowKeys', [...new Set(keys)])
}

function isRowSelected(row: DataRow, index: number) {
  return selectedRowKeySet.value.has(resolveRowKey(row, index))
}

function toggleRowSelection(row: DataRow, index: number, checked: boolean) {
  const rowKey = resolveRowKey(row, index)
  const nextKeys = new Set(props.selectedRowKeys)

  if (checked) {
    nextKeys.add(rowKey)
  } else {
    nextKeys.delete(rowKey)
  }

  emitSelectedRowKeys([...nextKeys])
}

function handlePageSelectionChange(event: Event) {
  togglePageSelection((event.target as HTMLInputElement).checked)
}

function handleRowSelectionChange(row: DataRow, index: number, event: Event) {
  toggleRowSelection(row, index, (event.target as HTMLInputElement).checked)
}

function togglePageSelection(checked: boolean) {
  const nextKeys = new Set(props.selectedRowKeys)

  for (const key of pagedRowKeys.value) {
    if (checked) {
      nextKeys.add(key)
    } else {
      nextKeys.delete(key)
    }
  }

  emitSelectedRowKeys([...nextKeys])
}

function toggleColumnMenu() {
  columnMenuOpen.value = !columnMenuOpen.value
}

function toggleColumn(key: string) {
  const current = new Set(hiddenColumns.value)

  if (current.has(key)) {
    current.delete(key)
  } else {
    current.add(key)
  }

  hiddenColumns.value = normalizeHiddenColumns([...current])
}

function handleSort(column: DataTableColumn) {
  if (!column.sortable) {
    return
  }

  if (sortKey.value === column.key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    return
  }

  sortKey.value = column.key
  sortOrder.value = 'asc'
}

function alignmentClass(column: DataTableColumn) {
  if (column.align === 'center') {
    return 'text-center'
  }

  if (column.align === 'right') {
    return 'text-right'
  }

  return 'text-left'
}

function handleClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) {
    columnMenuOpen.value = false
  }
}

onMounted(() => {
  const initialSortState = resolveInitialSortState()
  if (initialSortState) {
    sortKey.value = initialSortState.key
    sortOrder.value = initialSortState.order
  }

  const persistedHiddenColumns = readPersistedHiddenColumns()
  hiddenColumns.value = persistedHiddenColumns ?? normalizeHiddenColumns(defaultHiddenColumns.value)

  hasMounted.value = true
  if (selectAllRef.value) {
    selectAllRef.value.indeterminate = pagePartiallySelected.value
  }
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

watch(columnSignature, () => {
  hiddenColumns.value = normalizeHiddenColumns(hiddenColumns.value)

  const nextSortKey = normalizeSortKey(sortKey.value)
  if (nextSortKey) {
    sortKey.value = nextSortKey
    return
  }

  const fallback = resolveInitialSortState()
  sortKey.value = fallback?.key ?? ''
  sortOrder.value = fallback?.order ?? 'asc'
})

watch(hiddenColumns, () => {
  if (!hasMounted.value) {
    return
  }

  writePersistedHiddenColumns()
})

watch([sortKey, sortOrder], () => {
  if (!hasMounted.value) {
    return
  }

  writePersistedSortState()
})

watch([pageAllSelected, pagePartiallySelected], () => {
  if (selectAllRef.value) {
    selectAllRef.value.indeterminate = pagePartiallySelected.value
  }
})
</script>

<template>
  <div
    ref="rootRef"
    class="pw-data-table-root"
  >
    <div
      v-if="$slots.toolbar || (showColumnSettings && toggleableColumns.length)"
      class="pw-table-toolbar"
    >
      <div class="min-w-0 flex-1">
        <slot name="toolbar" />
      </div>

      <div class="relative flex items-center gap-2">
        <button
          v-if="showColumnSettings && toggleableColumns.length"
          type="button"
          class="pw-table-tool-button"
          @click="toggleColumnMenu"
        >
          <BaseIcon
            name="columns"
            size="sm"
          />
          <span>列设置</span>
        </button>

        <Transition
          enter-active-class="transition duration-150 ease-out"
          enter-from-class="translate-y-1 opacity-0"
          enter-to-class="translate-y-0 opacity-100"
          leave-active-class="transition duration-120 ease-in"
          leave-from-class="translate-y-0 opacity-100"
          leave-to-class="translate-y-1 opacity-0"
        >
          <div
            v-if="columnMenuOpen"
            class="pw-data-table-menu right-0 top-full mt-2 min-w-[220px]"
          >
            <div class="border-b border-gray-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:border-dark-800 dark:text-dark-500">
              可见列
            </div>
            <button
              v-for="column in toggleableColumns"
              :key="column.key"
              type="button"
              class="pw-data-table-menu-item"
              @click="toggleColumn(column.key)"
            >
              <BaseIcon
                :name="hiddenColumnSet.has(column.key) ? 'eye-off' : 'eye'"
                size="sm"
              />
              <span class="flex-1 text-left">{{ column.label }}</span>
              <BaseIcon
                v-if="!hiddenColumnSet.has(column.key)"
                name="check"
                size="sm"
                class="text-primary-500"
              />
            </button>
          </div>
        </Transition>
      </div>
    </div>

    <div
      v-if="!loading && !sortedRows.length"
      class="p-4"
    >
      <EmptyState
        :title="emptyTitle"
        :description="emptyDescription"
        :icon="emptyIcon"
        :action-label="emptyActionLabel"
        @action="emit('emptyAction')"
      />
    </div>

    <template v-else>
      <div class="space-y-3 md:hidden">
        <template v-if="loading">
          <article
            v-for="index in 4"
            :key="`mobile-loading-${index}`"
            class="rounded-[24px] border border-gray-100 bg-white/85 p-4 shadow-soft dark:border-dark-800 dark:bg-dark-950/35"
          >
            <div class="space-y-3">
              <div
                v-for="column in mobileColumns"
                :key="column.key"
                class="flex items-start justify-between gap-4"
              >
                <div class="h-4 w-20 animate-pulse rounded bg-gray-200 dark:bg-dark-700" />
                <div class="h-4 w-32 animate-pulse rounded bg-gray-200 dark:bg-dark-700" />
              </div>
              <div
                v-if="hasActionsColumn"
                class="border-t border-gray-100 pt-3 dark:border-dark-800"
              >
                <div class="h-9 w-full animate-pulse rounded-2xl bg-gray-200 dark:bg-dark-700" />
              </div>
            </div>
          </article>
        </template>

        <template v-else>
          <article
            v-for="(row, index) in pagedRows"
            :key="resolveRowKey(row, resolveVisibleRowIndex(index))"
            class="rounded-[24px] border border-gray-100 bg-white/85 p-4 shadow-soft dark:border-dark-800 dark:bg-dark-950/35"
            :class="isRowSelected(row, resolveVisibleRowIndex(index)) ? 'ring-2 ring-primary-500/20' : ''"
          >
            <div class="space-y-3">
              <div
                v-for="column in mobileColumns"
                :key="column.key"
                class="flex items-start justify-between gap-4"
              >
                <div class="min-w-[88px] text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:text-dark-500">
                  {{ column.label }}
                </div>
                <div
                  class="min-w-0 flex-1 text-right text-sm text-gray-700 dark:text-dark-200"
                  :class="alignmentClass(column)"
                >
                  <slot
                    :name="`cell-${column.key}`"
                    :row="row"
                    :value="resolveCellValue(row, column)"
                  >
                    {{
                      column.formatter
                        ? column.formatter(resolveCellValue(row, column), row)
                        : resolveCellValue(row, column)
                    }}
                  </slot>
                </div>
              </div>

              <div
                v-if="hasActionsColumn"
                class="border-t border-gray-100 pt-3 dark:border-dark-800"
              >
                <slot
                  name="cell-actions"
                  :row="row"
                />
              </div>
            </div>
          </article>
        </template>
      </div>

      <div class="hidden md:block">
        <div class="pw-table-wrapper">
          <table class="pw-table">
            <thead>
              <tr>
                <th
                  v-if="selectable"
                  class="w-12"
                >
                  <label class="flex items-center justify-center">
                    <input
                      ref="selectAllRef"
                      type="checkbox"
                      class="pw-table-checkbox"
                      :checked="pageAllSelected"
                      :disabled="loading || !pagedRowKeys.length"
                      @change="handlePageSelectionChange"
                    >
                    <span class="sr-only">{{ selectLabel }}</span>
                  </label>
                </th>
                <th
                  v-for="column in visibleColumns"
                  :key="column.key"
                  :class="[alignmentClass(column), column.headerClass]"
                >
                  <button
                    v-if="column.sortable"
                    type="button"
                    class="pw-table-sort-button"
                    @click="handleSort(column)"
                  >
                    <span>{{ column.label }}</span>
                    <BaseIcon
                      v-if="sortKey === column.key"
                      name="chevron-down"
                      size="sm"
                      class="transition"
                      :class="sortOrder === 'asc' ? 'rotate-180' : ''"
                    />
                    <BaseIcon
                      v-else
                      name="sort"
                      size="sm"
                      class="text-gray-300 dark:text-dark-500"
                    />
                  </button>
                  <span v-else>{{ column.label }}</span>
                </th>
                <th
                  v-if="hasActionsColumn"
                  class="w-[72px] text-right"
                >
                  {{ actionsLabel }}
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-if="loading">
                <tr
                  v-for="index in 5"
                  :key="index"
                >
                  <td v-if="selectable">
                    <div class="mx-auto h-4 w-4 animate-pulse rounded bg-gray-200 dark:bg-dark-700" />
                  </td>
                  <td
                    v-for="column in visibleColumns"
                    :key="column.key"
                    :class="[alignmentClass(column), column.cellClass]"
                  >
                    <div class="h-4 w-3/4 animate-pulse rounded bg-gray-200 dark:bg-dark-700" />
                  </td>
                  <td
                    v-if="hasActionsColumn"
                    class="text-right"
                  >
                    <div class="ml-auto h-9 w-9 animate-pulse rounded-xl bg-gray-200 dark:bg-dark-700" />
                  </td>
                </tr>
              </template>

              <tr
                v-for="(row, index) in pagedRows"
                v-else
                :key="resolveRowKey(row, resolveVisibleRowIndex(index))"
                :class="[
                  resolveRowClass(row, resolveVisibleRowIndex(index)),
                  isRowSelected(row, resolveVisibleRowIndex(index)) ? 'pw-table-row-selected' : ''
                ]"
              >
                <td v-if="selectable">
                  <label class="flex items-center justify-center">
                    <input
                      type="checkbox"
                      class="pw-table-checkbox"
                      :checked="isRowSelected(row, resolveVisibleRowIndex(index))"
                      @change="handleRowSelectionChange(row, resolveVisibleRowIndex(index), $event)"
                    >
                    <span class="sr-only">{{ selectLabel }}</span>
                  </label>
                </td>
                <td
                  v-for="column in visibleColumns"
                  :key="column.key"
                  :class="[alignmentClass(column), column.cellClass]"
                >
                  <slot
                    :name="`cell-${column.key}`"
                    :row="row"
                    :value="resolveCellValue(row, column)"
                  >
                    {{
                      column.formatter
                        ? column.formatter(resolveCellValue(row, column), row)
                        : resolveCellValue(row, column)
                    }}
                  </slot>
                </td>
                <td
                  v-if="hasActionsColumn"
                  class="text-right"
                >
                  <slot
                    name="cell-actions"
                    :row="row"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

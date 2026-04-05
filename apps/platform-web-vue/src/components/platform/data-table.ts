export type DataTableColumn = {
  key: string
  label: string
  sortable?: boolean
  align?: 'left' | 'center' | 'right'
  alwaysVisible?: boolean
  defaultHidden?: boolean
  headerClass?: string
  cellClass?: string
  formatter?: (value: unknown, row: Record<string, unknown>) => string
  sortValue?: (row: Record<string, unknown>) => unknown
}

export type ActionMenuItem = {
  key: string
  label: string
  icon?: string
  danger?: boolean
  disabled?: boolean
  onSelect: () => void | Promise<void>
}

export type BulkActionItem = {
  key: string
  label: string
  icon?: string
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  disabled?: boolean
  onSelect: () => void | Promise<void>
}

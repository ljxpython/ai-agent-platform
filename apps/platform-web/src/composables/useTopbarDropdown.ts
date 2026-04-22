import { nextTick, onBeforeUnmount, onMounted, ref, watch, type CSSProperties } from 'vue'

type TopbarDropdownAlignment = 'start' | 'end'

type UseTopbarDropdownOptions = {
  alignment?: TopbarDropdownAlignment
  fallbackWidth?: number
  minWidth?: number
  viewportPadding?: number
  offset?: number
}

export function useTopbarDropdown(options: UseTopbarDropdownOptions = {}) {
  const {
    alignment = 'end',
    fallbackWidth = 224,
    minWidth = 180,
    viewportPadding = 12,
    offset = 8
  } = options

  const isOpen = ref(false)
  const rootRef = ref<HTMLElement | null>(null)
  const triggerRef = ref<HTMLElement | null>(null)
  const dropdownRef = ref<HTMLElement | null>(null)
  const dropdownPlacement = ref<'top' | 'bottom'>('bottom')
  const dropdownStyle = ref<CSSProperties>({})

  function close() {
    isOpen.value = false
  }

  function open() {
    isOpen.value = true
  }

  function toggle() {
    if (isOpen.value) {
      close()
      return
    }

    open()
  }

  function updateDropdownPosition() {
    if (!isOpen.value || !triggerRef.value) {
      return
    }

    const rect = triggerRef.value.getBoundingClientRect()
    const maxViewportWidth = Math.max(minWidth, window.innerWidth - viewportPadding * 2)
    const dropdownWidth = Math.min(
      Math.max(dropdownRef.value?.offsetWidth ?? 0, fallbackWidth, minWidth),
      maxViewportWidth
    )
    const dropdownHeight = dropdownRef.value?.offsetHeight ?? 280
    const spaceBelow = window.innerHeight - rect.bottom - viewportPadding
    const spaceAbove = rect.top - viewportPadding
    const placeOnTop = spaceBelow < dropdownHeight && spaceAbove > spaceBelow
    const alignedLeft = alignment === 'start' ? rect.left : rect.right - dropdownWidth
    const clampedLeft = Math.min(
      Math.max(alignedLeft, viewportPadding),
      Math.max(viewportPadding, window.innerWidth - dropdownWidth - viewportPadding)
    )

    dropdownPlacement.value = placeOnTop ? 'top' : 'bottom'
    dropdownStyle.value = {
      position: 'fixed',
      left: `${clampedLeft}px`,
      top: placeOnTop ? 'auto' : `${rect.bottom + offset}px`,
      bottom: placeOnTop ? `${window.innerHeight - rect.top + offset}px` : 'auto',
      width: `${dropdownWidth}px`,
      maxWidth: `${maxViewportWidth}px`
    }
  }

  function handleClickOutside(event: MouseEvent) {
    const target = event.target as Node
    const clickedInsideTrigger = rootRef.value?.contains(target)
    const clickedInsideDropdown = dropdownRef.value?.contains(target)

    if (!clickedInsideTrigger && !clickedInsideDropdown) {
      close()
    }
  }

  function handleViewportChange() {
    updateDropdownPosition()
  }

  watch(isOpen, (openState) => {
    if (!openState) {
      return
    }

    nextTick(() => {
      updateDropdownPosition()
    })
  })

  onMounted(() => {
    document.addEventListener('click', handleClickOutside)
    window.addEventListener('resize', handleViewportChange)
    window.addEventListener('scroll', handleViewportChange, true)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleClickOutside)
    window.removeEventListener('resize', handleViewportChange)
    window.removeEventListener('scroll', handleViewportChange, true)
  })

  return {
    close,
    dropdownPlacement,
    dropdownRef,
    dropdownStyle,
    isOpen,
    open,
    rootRef,
    toggle,
    triggerRef,
    updateDropdownPosition
  }
}

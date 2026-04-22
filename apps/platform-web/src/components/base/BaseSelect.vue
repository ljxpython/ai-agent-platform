<script setup lang="ts">
import { Fragment, computed, nextTick, onBeforeUnmount, onMounted, ref, useSlots, watch, type CSSProperties, type VNode } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'

type Primitive = string | number | boolean | null

type SelectVariant = 'default' | 'ghost'

type SelectOptionInput = Record<string, unknown> & {
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue: Primitive
    disabled?: boolean
    placeholder?: string
    variant?: SelectVariant
    options?: SelectOptionInput[]
    valueKey?: string
    labelKey?: string
  }>(),
  {
    disabled: false,
    placeholder: '请选择',
    variant: 'default',
    options: () => [],
    valueKey: 'value',
    labelKey: 'label'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

type SelectOptionRecord = {
  value: string
  label: string
  disabled: boolean
}

const slots = useSlots()
const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const triggerRef = ref<HTMLButtonElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const optionsRef = ref<HTMLElement | null>(null)
const focusedIndex = ref(-1)
const dropdownPlacement = ref<'top' | 'bottom'>('bottom')
const dropdownStyle = ref<CSSProperties>({})
const instanceId = `pw-select-${Math.random().toString(36).slice(2, 9)}`

function extractNodeText(node: unknown): string {
  if (Array.isArray(node)) {
    return node.map((child) => extractNodeText(child)).join('')
  }

  if (typeof node === 'function') {
    return extractNodeText(node())
  }

  if (typeof node === 'string' || typeof node === 'number') {
    return String(node)
  }

  if (!node || typeof node !== 'object') {
    return ''
  }

  const vnode = node as { children?: unknown }
  if (Array.isArray(vnode.children)) {
    return vnode.children.map((child) => extractNodeText(child)).join('')
  }

  return extractNodeText(vnode.children)
}

function collectOptionNodes(nodes: unknown[]): VNode[] {
  return nodes.flatMap((node) => {
    if (!node) {
      return []
    }

    if (Array.isArray(node)) {
      return collectOptionNodes(node)
    }

    if (typeof node !== 'object') {
      return []
    }

    const vnode = node as VNode & { children?: unknown }
    if (typeof vnode.type === 'string' && vnode.type.toLowerCase() === 'option') {
      return [vnode]
    }

    if (vnode.type === Fragment && Array.isArray(vnode.children)) {
      return collectOptionNodes(vnode.children as unknown[])
    }

    if (Array.isArray(vnode.children)) {
      return collectOptionNodes(vnode.children as unknown[])
    }

    if (typeof vnode.children === 'function') {
      const renderedChildren = (vnode.children as () => unknown[])()
      return collectOptionNodes(renderedChildren)
    }

    return []
  })
}

function normalizeProvidedOption(option: SelectOptionInput): SelectOptionRecord | null {
  if (!option || typeof option !== 'object') {
    return null
  }

  const rawValue = option[props.valueKey]
  const rawLabel = option[props.labelKey]

  return {
    value: rawValue == null ? '' : String(rawValue),
    label: rawLabel == null ? '' : String(rawLabel),
    disabled: Boolean(option.disabled)
  }
}

const normalizedOptions = computed<SelectOptionRecord[]>(() => {
  if (props.options.length > 0) {
    return props.options
      .map((option) => normalizeProvidedOption(option))
      .filter((option): option is SelectOptionRecord => Boolean(option))
  }

  const nodes = collectOptionNodes(slots.default?.() ?? [])
  return nodes
    .flatMap((node) => {
      if (typeof node.type !== 'string' || node.type.toLowerCase() !== 'option') {
        return []
      }

      const propsValue = node.props ?? {}
      const rawValue = propsValue.value
      const label = extractNodeText(node.children).trim()

      return [
        {
          value: rawValue == null ? '' : String(rawValue),
          label,
          disabled: Boolean(propsValue.disabled)
        }
      ]
    })
})

const selectedValue = computed(() => (props.modelValue == null ? '' : String(props.modelValue)))
const selectedOption = computed(
  () => normalizedOptions.value.find((option) => option.value === selectedValue.value) ?? null
)
const displayLabel = computed(() => selectedOption.value?.label || props.placeholder)

function open() {
  if (props.disabled || normalizedOptions.value.length === 0) {
    return
  }
  isOpen.value = true
}

function close() {
  isOpen.value = false
  focusedIndex.value = -1
}

function toggle() {
  if (isOpen.value) {
    close()
    return
  }
  open()
}

function selectOption(option: SelectOptionRecord) {
  if (option.disabled) {
    return
  }

  emit('update:modelValue', option.value)
  close()
  triggerRef.value?.focus()
}

function updateDropdownPosition() {
  if (!isOpen.value || !triggerRef.value) {
    return
  }

  const rect = triggerRef.value.getBoundingClientRect()
  const viewportPadding = 12
  const dropdownHeight = dropdownRef.value?.offsetHeight ?? 280
  const spaceBelow = window.innerHeight - rect.bottom - viewportPadding
  const spaceAbove = rect.top - viewportPadding
  const placeOnTop = spaceBelow < dropdownHeight && spaceAbove > spaceBelow

  dropdownPlacement.value = placeOnTop ? 'top' : 'bottom'
  dropdownStyle.value = {
    position: 'fixed',
    left: `${rect.left}px`,
    top: placeOnTop ? 'auto' : `${rect.bottom + 8}px`,
    bottom: placeOnTop ? `${window.innerHeight - rect.top + 8}px` : 'auto',
    width: `${rect.width}px`,
    minWidth: `${rect.width}px`,
    maxWidth: `${Math.max(rect.width, 320)}px`
  }
}

function syncFocusedIndex() {
  const selectedIndex = normalizedOptions.value.findIndex((option) => option.value === selectedValue.value && !option.disabled)
  if (selectedIndex >= 0) {
    focusedIndex.value = selectedIndex
    return
  }

  focusedIndex.value = normalizedOptions.value.findIndex((option) => !option.disabled)
}

function scrollFocusedOptionIntoView() {
  const container = optionsRef.value
  const optionEl = container?.children[focusedIndex.value] as HTMLElement | undefined

  if (!container || !optionEl) {
    return
  }

  const optionTop = optionEl.offsetTop
  const optionBottom = optionTop + optionEl.offsetHeight
  const visibleTop = container.scrollTop
  const visibleBottom = visibleTop + container.clientHeight

  if (optionTop < visibleTop) {
    container.scrollTop = optionTop
    return
  }

  if (optionBottom > visibleBottom) {
    container.scrollTop = optionBottom - container.clientHeight
  }
}

function focusNext(direction: 1 | -1) {
  if (normalizedOptions.value.length === 0) {
    focusedIndex.value = -1
    return
  }

  let nextIndex = focusedIndex.value
  for (let step = 0; step < normalizedOptions.value.length; step += 1) {
    nextIndex = (nextIndex + direction + normalizedOptions.value.length) % normalizedOptions.value.length
    if (!normalizedOptions.value[nextIndex]?.disabled) {
      focusedIndex.value = nextIndex
      break
    }
  }

  nextTick(() => {
    scrollFocusedOptionIntoView()
  })
}

function handleTriggerKeydown(event: KeyboardEvent) {
  if (props.disabled) {
    return
  }

  if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    if (!isOpen.value) {
      open()
      return
    }
    focusNext(1)
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (!isOpen.value) {
      open()
      return
    }
    focusNext(-1)
  }
}

function handleDropdownKeydown(event: KeyboardEvent) {
  if (!isOpen.value) {
    return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    triggerRef.value?.focus()
    return
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    focusNext(1)
    return
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    focusNext(-1)
    return
  }

  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    const option = normalizedOptions.value[focusedIndex.value]
    if (option) {
      selectOption(option)
    }
  }
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  const clickedInsideTrigger = triggerRef.value?.contains(target)
  const clickedInsideDropdown = dropdownRef.value?.contains(target)

  if (!clickedInsideTrigger && !clickedInsideDropdown) {
    close()
  }
}

function handleViewportChange() {
  updateDropdownPosition()
}

watch(
  () => isOpen.value,
  (openState) => {
    if (!openState) {
      return
    }

    syncFocusedIndex()
    nextTick(() => {
      updateDropdownPosition()
      scrollFocusedOptionIntoView()
    })
  }
)

watch(
  () => props.modelValue,
  () => {
    if (isOpen.value) {
      syncFocusedIndex()
    }
  }
)

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
</script>

<template>
  <div
    ref="rootRef"
    class="relative"
  >
    <button
      :id="instanceId"
      ref="triggerRef"
      type="button"
      class="pw-select-trigger"
      :class="[
        variant === 'ghost' ? 'pw-select-trigger-ghost' : '',
        isOpen ? 'pw-select-trigger-open' : '',
        disabled ? 'pw-select-trigger-disabled' : ''
      ]"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="isOpen"
      @click="toggle"
      @keydown="handleTriggerKeydown"
    >
      <span
        class="pw-select-trigger-label"
        :class="selectedOption ? '' : 'pw-select-trigger-placeholder'"
      >
        {{ displayLabel }}
      </span>
      <BaseIcon
        name="chevron-down"
        size="sm"
        class="pw-select-trigger-icon"
        :class="isOpen ? 'rotate-180' : ''"
      />
    </button>

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="translate-y-1 opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition duration-120 ease-in"
        leave-from-class="translate-y-0 opacity-100"
        leave-to-class="translate-y-1 opacity-0"
      >
        <div
          v-if="isOpen"
          ref="dropdownRef"
          class="pw-select-dropdown"
          :class="dropdownPlacement === 'top' ? 'pw-select-dropdown-top' : ''"
          :style="dropdownStyle"
          role="listbox"
          :aria-labelledby="instanceId"
          tabindex="-1"
          @keydown="handleDropdownKeydown"
        >
          <div
            ref="optionsRef"
            class="pw-select-options"
          >
            <button
              v-for="(option, index) in normalizedOptions"
              :key="`${option.value}-${index}`"
              type="button"
              class="pw-select-option"
              :class="[
                option.value === selectedValue ? 'pw-select-option-selected' : '',
                focusedIndex === index ? 'pw-select-option-focused' : '',
                option.disabled ? 'pw-select-option-disabled' : ''
              ]"
              :disabled="option.disabled"
              @mouseenter="focusedIndex = index"
              @click="selectOption(option)"
            >
              <span class="truncate">{{ option.label || option.value }}</span>
              <BaseIcon
                v-if="option.value === selectedValue"
                name="check"
                size="sm"
                class="shrink-0 text-sky-500"
              />
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

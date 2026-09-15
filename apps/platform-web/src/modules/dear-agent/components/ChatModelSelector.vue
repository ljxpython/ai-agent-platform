<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, type CSSProperties } from 'vue'
import { RouterLink } from 'vue-router'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { RuntimeModelItem } from '@/types/management'

const props = withDefaults(
  defineProps<{
    models?: RuntimeModelItem[]
    selectedModelId?: string
    defaultModelName?: string
    disabled?: boolean
    projectId: string
  }>(),
  {
    models: () => [],
    selectedModelId: '',
    defaultModelName: '',
    disabled: false
  }
)

const emit = defineEmits<{
  'update:selectedModelId': [value: string]
}>()

const isOpen = ref(false)
const searchQuery = ref('')
const triggerRef = ref<HTMLButtonElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)
const dropdownStyle = ref<CSSProperties>({})

function formatProviderLabel(provider: string): string {
  const lower = provider.toLowerCase()
  if (lower.includes('deepseek-proxy')) return 'DeepSeek 中转渠道'
  if (lower.includes('gpt-proxy')) return 'GPT 中转渠道'
  if (lower.includes('deepseek')) return 'DeepSeek 渠道'
  if (lower.includes('openai')) return 'OpenAI 渠道'
  if (lower.includes('ollama')) return 'Ollama 本地服务'
  if (lower.includes('qwen')) return '通义千问 (DashScope)'
  if (lower.includes('doubao')) return '豆包 (火山引擎)'
  if (lower.includes('glm')) return '智谱 GLM'
  if (lower.includes('anthropic')) return 'Anthropic Claude'
  return `${provider.toUpperCase()} 渠道`
}

const searchNormalized = computed(() => searchQuery.value.trim().toLowerCase())

const filteredGroupedModels = computed(() => {
  if (!props.models || props.models.length === 0) return []
  const query = searchNormalized.value

  const map = new Map<string, RuntimeModelItem[]>()
  for (const item of props.models) {
    if (query) {
      const matchId = item.model?.toLowerCase().includes(query)
      const matchName = item.display_name?.toLowerCase().includes(query)
      const matchProvider = item.provider?.toLowerCase().includes(query)
      if (!matchId && !matchName && !matchProvider) continue
    }
    const p = item.provider || 'default'
    if (!map.has(p)) {
      map.set(p, [])
    }
    map.get(p)!.push(item)
  }

  return Array.from(map.entries()).map(([provider, items]) => ({
    provider,
    label: formatProviderLabel(provider),
    items
  }))
})

const selectedModel = computed(() => {
  if (!props.selectedModelId) return null
  return props.models?.find((m) => m.id === props.selectedModelId) ?? null
})

const currentDisplayLabel = computed(() => {
  if (!props.selectedModelId) {
    return props.defaultModelName ? `默认: ${props.defaultModelName}` : '项目默认模型'
  }
  return selectedModel.value?.display_name || props.selectedModelId
})

const currentProviderBadge = computed(() => {
  if (!selectedModel.value || !selectedModel.value.provider) return ''
  const p = selectedModel.value.provider.toLowerCase()
  if (p.includes('deepseek-proxy')) return 'DeepSeek中转'
  if (p.includes('gpt-proxy')) return 'GPT中转'
  if (p.includes('deepseek')) return 'DeepSeek'
  if (p.includes('openai')) return 'OpenAI'
  if (p.includes('ollama')) return 'Ollama'
  return selectedModel.value.provider
})

function updateDropdownPosition() {
  if (!isOpen.value || !triggerRef.value) return

  const rect = triggerRef.value.getBoundingClientRect()
  const viewportPadding = 12
  const panelWidth = Math.min(380, window.innerWidth - viewportPadding * 2)
  const panelHeight = dropdownRef.value?.offsetHeight ?? 380

  const spaceBelow = window.innerHeight - rect.bottom - viewportPadding
  const spaceAbove = rect.top - viewportPadding
  const placeOnTop = spaceAbove >= panelHeight || spaceAbove > spaceBelow

  const left = Math.min(
    Math.max(rect.left, viewportPadding),
    window.innerWidth - panelWidth - viewportPadding
  )

  dropdownStyle.value = {
    position: 'fixed',
    left: `${left}px`,
    top: placeOnTop ? 'auto' : `${rect.bottom + 8}px`,
    bottom: placeOnTop ? `${window.innerHeight - rect.top + 8}px` : 'auto',
    width: `${panelWidth}px`,
    zIndex: 9999
  }
}

function open() {
  if (props.disabled) return
  isOpen.value = true
  searchQuery.value = ''
  nextTick(() => {
    updateDropdownPosition()
    searchInputRef.value?.focus()
  })
}

function close(restoreFocus = true) {
  if (!isOpen.value) return
  isOpen.value = false
  if (restoreFocus) {
    triggerRef.value?.focus()
  }
}

function toggle() {
  if (isOpen.value) {
    close(true)
  } else {
    open()
  }
}

function selectModel(modelId: string) {
  emit('update:selectedModelId', modelId)
  close(true)
}

function handleClickOutside(event: MouseEvent) {
  if (!isOpen.value) return
  const target = event.target as Node
  if (triggerRef.value?.contains(target) || dropdownRef.value?.contains(target)) {
    return
  }
  close(false)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isOpen.value) {
    close(true)
  }
}

function handleViewportChange() {
  if (isOpen.value) {
    updateDropdownPosition()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  window.addEventListener('resize', handleViewportChange)
  window.addEventListener('scroll', handleViewportChange, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('resize', handleViewportChange)
  window.removeEventListener('scroll', handleViewportChange, true)
})
</script>

<template>
  <div class="relative inline-flex items-center shrink-0">
    <!-- 高级感触发胶囊按钮 -->
    <button
      ref="triggerRef"
      type="button"
      :disabled="disabled"
      class="group relative inline-flex h-8 items-center gap-2 rounded-lg border border-gray-200/90 bg-white/90 px-2.5 text-xs text-gray-700 shadow-xs transition-all hover:border-primary-400/80 hover:bg-white hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500/20 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 dark:border-dark-700 dark:bg-dark-800/90 dark:text-dark-200 dark:hover:border-primary-500/80 dark:hover:bg-dark-800 dark:hover:text-white"
      :class="isOpen ? 'border-primary-500 bg-white ring-2 ring-primary-500/20 dark:border-primary-500 dark:bg-dark-800' : ''"
      title="选择对话运行模型"
      aria-label="选择对话运行模型"
      aria-haspopup="dialog"
      :aria-expanded="isOpen"
      @click="toggle"
    >
      <!-- Sparkle 图标装饰 -->
      <span class="flex h-4 w-4 items-center justify-center rounded-md bg-primary-50 text-primary-600 transition group-hover:scale-110 dark:bg-primary-950/60 dark:text-primary-400">
        <BaseIcon
          name="sparkle"
          size="xs"
        />
      </span>

      <!-- 当前模型名称 -->
      <span class="font-medium truncate max-w-[110px] sm:max-w-[180px]">
        {{ currentDisplayLabel }}
      </span>

      <!-- 渠道徽标 -->
      <span
        v-if="currentProviderBadge"
        class="hidden rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500 sm:inline-block dark:bg-dark-700 dark:text-dark-300"
      >
        {{ currentProviderBadge }}
      </span>

      <!-- 旋转箭头 -->
      <BaseIcon
        name="chevron-down"
        size="xs"
        class="text-gray-400 transition-transform duration-200 group-hover:text-gray-600 dark:text-dark-400 dark:group-hover:text-dark-200"
        :class="isOpen ? 'rotate-180 text-primary-500' : ''"
      />
    </button>

    <!-- 弹出的高颜值选择面板 (Teleport) -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="opacity-0 translate-y-1 scale-98"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-100 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 translate-y-1 scale-98"
      >
        <div
          v-if="isOpen"
          ref="dropdownRef"
          role="dialog"
          aria-label="切换对话模型"
          :style="dropdownStyle"
          class="flex max-h-[460px] flex-col overflow-hidden rounded-2xl border border-gray-200/90 bg-white/95 shadow-2xl backdrop-blur-xl dark:border-dark-700 dark:bg-dark-900/95 dark:shadow-black/70"
        >
          <!-- 头部与快捷过滤 -->
          <div class="border-b border-gray-100 bg-gray-50/70 p-3 dark:border-dark-800 dark:bg-dark-950/40">
            <div class="flex items-center justify-between mb-2.5 px-0.5">
              <div class="flex items-center gap-1.5 text-xs font-semibold text-gray-800 dark:text-dark-100">
                <BaseIcon
                  name="sparkle"
                  size="xs"
                  class="text-primary-500"
                />
                <span>切换对话模型</span>
              </div>
              <span class="rounded-full bg-gray-200/70 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-dark-800 dark:text-dark-400">
                共 {{ models?.length || 0 }} 款模型
              </span>
            </div>

            <!-- 搜索框 -->
            <div class="relative flex items-center">
              <BaseIcon
                name="search"
                size="xs"
                class="pointer-events-none absolute left-2.5 text-gray-400 dark:text-dark-400"
              />
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                aria-label="搜索模型"
                placeholder="快速搜索模型名称、ID 或渠道..."
                class="w-full rounded-xl border border-gray-200/80 bg-white py-1.5 pl-8 pr-7 text-xs text-gray-900 placeholder:text-gray-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-dark-700 dark:bg-dark-900 dark:text-white dark:placeholder:text-dark-500"
              >
              <button
                v-if="searchQuery"
                type="button"
                class="absolute right-2 text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
                aria-label="清除搜索"
                @click="searchQuery = ''"
              >
                <BaseIcon
                  name="x"
                  size="xs"
                />
              </button>
            </div>
          </div>

          <!-- 模型清单区域 (滚动) -->
          <div class="flex-1 overflow-y-auto p-2 space-y-2.5">
            <!-- 推荐默认选项 (搜索时不强制隐藏，除非用户输入了筛选词且未命中) -->
            <div
              v-if="!searchQuery"
              class="group flex cursor-pointer items-center justify-between rounded-xl border p-2.5 transition"
              :class="!selectedModelId
                ? 'border-primary-300 bg-primary-50/70 text-primary-900 dark:border-primary-900/60 dark:bg-primary-950/40 dark:text-primary-200'
                : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50/80 dark:border-dark-800 dark:hover:border-dark-700 dark:hover:bg-dark-800/60'"
              role="button"
              tabindex="0"
              @keydown.enter.prevent="selectModel('')"
              @keydown.space.prevent="selectModel('')"
              @click="selectModel('')"
            >
              <div class="flex items-center gap-2.5 min-w-0">
                <div
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition"
                  :class="!selectedModelId
                    ? 'bg-primary-500 text-white shadow-xs'
                    : 'bg-gray-100 text-gray-500 dark:bg-dark-800 dark:text-dark-400 group-hover:bg-primary-50 group-hover:text-primary-600 dark:group-hover:bg-primary-950/50 dark:group-hover:text-primary-400'"
                >
                  <BaseIcon
                    name="sparkle"
                    size="sm"
                  />
                </div>
                <div class="min-w-0">
                  <div class="flex items-center gap-1.5">
                    <span class="text-xs font-semibold text-gray-900 dark:text-white">
                      跟随项目默认配置
                    </span>
                    <span class="rounded bg-emerald-50 px-1.5 py-0.2 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                      推荐
                    </span>
                  </div>
                  <p class="truncate text-[11px] text-gray-500 dark:text-dark-400 mt-0.5">
                    {{ defaultModelName ? `当前生效: ${defaultModelName}` : '使用项目默认模型' }}
                  </p>
                </div>
              </div>
              <BaseIcon
                v-if="!selectedModelId"
                name="check"
                size="sm"
                class="shrink-0 text-primary-600 dark:text-primary-400"
              />
            </div>

            <!-- 分中转站与渠道模型列表 -->
            <div
              v-for="group in filteredGroupedModels"
              :key="group.provider"
              class="space-y-1"
            >
              <!-- 渠道头 -->
              <div class="flex items-center justify-between px-2 pt-1.5 pb-0.5">
                <div class="flex items-center gap-1.5">
                  <BaseIcon
                    name="globe"
                    size="xs"
                    class="text-gray-400 dark:text-dark-500"
                  />
                  <span class="text-[11px] font-semibold text-gray-700 dark:text-dark-300">
                    {{ group.label }}
                  </span>
                  <span class="rounded bg-gray-100 px-1.5 py-0.2 text-[10px] font-mono text-gray-500 dark:bg-dark-800 dark:text-dark-400">
                    {{ group.provider }}
                  </span>
                </div>
                <span class="text-[10px] text-gray-400 dark:text-dark-500">
                  {{ group.items.length }} 款
                </span>
              </div>

              <!-- 模型卡片 -->
              <div
                v-for="model in group.items"
                :key="model.id"
                class="group flex cursor-pointer items-center justify-between rounded-xl px-2.5 py-2 transition"
                :class="selectedModelId === model.id
                  ? 'bg-primary-50/80 text-primary-900 ring-1 ring-primary-500/30 dark:bg-primary-950/50 dark:text-primary-200 dark:ring-primary-600/40'
                  : 'hover:bg-gray-100/70 dark:hover:bg-dark-800/60'"
                role="button"
                tabindex="0"
                @keydown.enter.prevent="selectModel(model.id)"
                @keydown.space.prevent="selectModel(model.id)"
                @click="selectModel(model.id)"
              >
                <div class="min-w-0 pr-2">
                  <div class="flex items-center gap-1.5">
                    <span
                      class="text-xs font-medium truncate"
                      :class="selectedModelId === model.id
                        ? 'font-semibold text-primary-900 dark:text-white'
                        : 'text-gray-800 dark:text-dark-200'"
                    >
                      {{ model.display_name || model.model }}
                    </span>
                    <span
                      v-if="model.display_name === defaultModelName"
                      class="shrink-0 rounded bg-emerald-50 px-1.5 py-0.2 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400"
                    >
                      默认
                    </span>
                  </div>
                  <div class="flex items-center gap-1.5 mt-0.5 text-[11px] font-mono text-gray-400 dark:text-dark-400">
                    <span class="truncate max-w-[210px]">{{ model.model }}</span>
                    <span
                      v-if="model.protocol"
                      class="text-[10px] opacity-70"
                    >({{ model.protocol }})</span>
                  </div>
                </div>

                <div class="shrink-0">
                  <BaseIcon
                    v-if="selectedModelId === model.id"
                    name="check"
                    size="sm"
                    class="text-primary-600 dark:text-primary-400"
                  />
                </div>
              </div>
            </div>

            <!-- 搜索无结果 -->
            <div
              v-if="filteredGroupedModels.length === 0"
              class="py-8 text-center text-xs text-gray-400 dark:text-dark-500"
            >
              未找到匹配“{{ searchQuery }}”的模型
            </div>
          </div>

          <!-- 底部管理快捷入口 -->
          <div class="border-t border-gray-100 bg-gray-50/70 px-3 py-2 text-xs flex items-center justify-between dark:border-dark-800 dark:bg-dark-950/40">
            <span class="text-[11px] text-gray-400 dark:text-dark-500">
              需要管理中转端点？
            </span>
            <RouterLink
              :to="`/workspace/projects/${projectId}/models`"
              class="inline-flex items-center gap-1 text-[11px] font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300"
              @click="close(false)"
            >
              <span>管理模型与中转站</span>
              <BaseIcon
                name="chevron-right"
                size="xs"
              />
            </RouterLink>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

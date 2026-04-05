<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDrawer from '@/components/base/BaseDrawer.vue'
import { useUiStore } from '@/stores/ui'
import { downloadBlob } from '@/utils/browser-download'
import { copyText } from '@/utils/clipboard'
import { getHistoryEntryId, getHistoryEntryPreviewText, getHistoryEntryTime, toPrettyJson } from '@/utils/threads'
import { buildChatHistoryView } from '../history-view-model'
import type { ChatInspectorFile } from '../inspector-view-model'
import { type ChatPlanTodo, type ChatPlanView } from '../plan-view-model'
import type { ThreadHistoryEntry } from '@/types/management'

type InspectorTabKey = 'overview' | 'tasks' | 'files' | 'history'
type TodoStatus = ChatPlanTodo['status']

const props = defineProps<{
  show: boolean
  initialTab: InspectorTabKey
  showHistory: boolean
  showArtifacts: boolean
  allowResetTarget: boolean
  targetText: string
  projectName: string
  activeThreadId: string
  lastRunId: string
  selectedBranch: string
  latestMessagePreview: string
  historyItems: ThreadHistoryEntry[]
  isViewingBranch: boolean
  planView: ChatPlanView
  files: ChatInspectorFile[]
  values?: Record<string, unknown> | null
  isRunning: boolean
  hasInterrupt: boolean
  sourceNote: string
  contextNotice?: string
  onUpdateState: (values: Record<string, unknown>) => Promise<boolean>
}>()

const emit = defineEmits<{
  close: []
  'select-branch': [branchId: string]
  'reset-target': []
}>()

const uiStore = useUiStore()
const activeTab = ref<InspectorTabKey>('overview')
const selectedFilePath = ref('')
const isEditing = ref(false)
const editValue = ref('')
const isSaving = ref(false)

const availableTabs = computed(() => {
  const tabs: Array<{
    key: InspectorTabKey
    label: string
    count?: number
    tone?: 'info' | 'warning' | 'success'
  }> = [
    { key: 'overview', label: '概览' },
    {
      key: 'tasks',
      label: 'ToDo',
      count: props.planView.totalTasks + props.planView.ephemeralTodos.length,
      tone: props.planView.activeTask ? 'info' : props.planView.allTasksCompleted ? 'success' : undefined
    },
    { key: 'files', label: 'Files', count: props.files.length }
  ]

  if (props.showHistory) {
    tabs.push({
      key: 'history',
      label: '历史',
      count: props.historyItems.length,
      tone: props.isViewingBranch ? 'warning' : undefined
    })
  }

  return tabs
})

const selectedFile = computed(
  () => props.files.find((item) => item.path === selectedFilePath.value) || null
)
const hasTasks = computed(
  () => props.planView.totalTasks > 0 || props.planView.ephemeralTodos.length > 0
)
const editDisabled = computed(() => props.isRunning || props.hasInterrupt || isSaving.value)
const currentTaskLabel = computed(() => props.planView.activeTask?.content || '暂无')
const historyView = computed(() =>
  buildChatHistoryView({
    items: props.historyItems,
    selectedBranch: props.selectedBranch,
    isViewingBranch: props.isViewingBranch
  })
)

watch(
  () => [props.initialTab, props.showHistory, props.show] as const,
  ([nextTab, showHistory, isOpen]) => {
    if (!isOpen) {
      return
    }

    if (nextTab === 'history' && !showHistory) {
      activeTab.value = 'overview'
      return
    }

    activeTab.value = nextTab
  },
  { immediate: true }
)

watch(
  () => props.files,
  (nextFiles) => {
    if (nextFiles.length === 0) {
      selectedFilePath.value = ''
      isEditing.value = false
      editValue.value = ''
      return
    }

    if (!selectedFilePath.value || !nextFiles.some((item) => item.path === selectedFilePath.value)) {
      selectedFilePath.value = nextFiles[0].path
      isEditing.value = false
      editValue.value = nextFiles[0].content
    }
  },
  { immediate: true, deep: true }
)

watch(selectedFile, (file) => {
  if (!isEditing.value) {
    editValue.value = file?.content || ''
  }
})

function groupTodoList(todos: ChatPlanTodo[]) {
  return {
    in_progress: todos.filter((item) => item.status === 'in_progress'),
    pending: todos.filter((item) => item.status === 'pending'),
    completed: todos.filter((item) => item.status === 'completed')
  }
}

function statusDotClass(status: TodoStatus) {
  if (status === 'completed') {
    return 'border-emerald-200 bg-emerald-500'
  }
  if (status === 'in_progress') {
    return 'border-sky-200 bg-sky-500'
  }
  return 'border-gray-200 bg-white'
}

async function handleCopyFile() {
  if (!selectedFile.value) {
    return
  }

  const copied = await copyText(selectedFile.value.content)
  uiStore.pushToast({
    type: copied ? 'success' : 'error',
    title: copied ? '已复制文件内容' : '复制失败',
    message: copied ? selectedFile.value.path : '浏览器拒绝了复制动作'
  })
}

function handleDownloadFile() {
  if (!selectedFile.value) {
    return
  }

  downloadBlob(
    new Blob([selectedFile.value.content], { type: 'text/plain;charset=utf-8' }),
    selectedFile.value.path
  )
  uiStore.pushToast({
    type: 'success',
    title: '已下载文件',
    message: selectedFile.value.path
  })
}

function handleStartEdit() {
  if (!selectedFile.value) {
    return
  }

  if (editDisabled.value) {
    uiStore.pushToast({
      type: 'warning',
      title: '当前不可编辑',
      message: '运行中或等待中断决策时，文件内容不能直接改。'
    })
    return
  }

  isEditing.value = true
  editValue.value = selectedFile.value.content
}

function handleCancelEdit() {
  isEditing.value = false
  editValue.value = selectedFile.value?.content || ''
}

async function handleSaveEdit() {
  if (!selectedFile.value) {
    return
  }

  const rawFiles = props.values?.files
  if (!rawFiles || typeof rawFiles !== 'object' || Array.isArray(rawFiles)) {
    uiStore.pushToast({
      type: 'error',
      title: '保存失败',
      message: '当前线程里没有可编辑的文件状态。'
    })
    return
  }

  const nextFiles = { ...(rawFiles as Record<string, unknown>) }
  const currentRaw = nextFiles[selectedFile.value.path]
  if (typeof currentRaw === 'string' || currentRaw == null) {
    nextFiles[selectedFile.value.path] = editValue.value
  } else if (typeof currentRaw === 'object' && !Array.isArray(currentRaw)) {
    const currentRecord = currentRaw as Record<string, unknown>
    nextFiles[selectedFile.value.path] =
      'content' in currentRecord
        ? {
            ...currentRecord,
            content: editValue.value
          }
        : editValue.value
  } else {
    nextFiles[selectedFile.value.path] = editValue.value
  }

  isSaving.value = true
  try {
    await props.onUpdateState({ files: nextFiles })
    isEditing.value = false
    uiStore.pushToast({
      type: 'success',
      title: '文件已保存',
      message: selectedFile.value.path
    })
  } catch (error) {
    uiStore.pushToast({
      type: 'error',
      title: '保存失败',
      message: error instanceof Error ? error.message : '线程状态更新失败'
    })
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <BaseDrawer
    :show="show"
    title="会话详情"
    side="right"
    width="full"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <div class="flex flex-wrap gap-2">
        <button
          v-for="tab in availableTabs"
          :key="tab.key"
          type="button"
          class="inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm transition"
          :class="
            activeTab === tab.key
              ? 'border-primary-200 bg-primary-50 text-primary-700 shadow-soft dark:border-primary-900/40 dark:bg-primary-950/20 dark:text-primary-100'
              : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700 dark:bg-dark-900 dark:text-dark-200 dark:hover:bg-dark-800 dark:hover:text-white'
          "
          @click="activeTab = tab.key"
        >
          <span>{{ tab.label }}</span>
          <span
            v-if="typeof tab.count === 'number'"
            class="rounded-full px-2 py-0.5 text-[11px]"
            :class="
              activeTab === tab.key
                ? 'bg-white/80 text-primary-700 dark:bg-dark-800 dark:text-primary-100'
                : 'bg-gray-100 text-gray-500 dark:bg-dark-800 dark:text-dark-300'
            "
          >
            {{ tab.count }}
          </span>
          <span
            v-else-if="tab.tone"
            class="inline-flex h-2.5 w-2.5 rounded-full"
            :class="
              tab.tone === 'warning'
                ? 'bg-amber-500'
                : tab.tone === 'success'
                  ? 'bg-emerald-500'
                  : 'bg-sky-500'
            "
          />
        </button>
      </div>

      <div
        v-if="activeTab === 'overview'"
        class="space-y-5"
      >
        <div class="grid gap-4 md:grid-cols-3">
          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              当前任务
            </div>
            <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
              {{ currentTaskLabel }}
            </div>
          </div>
          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              文件状态
            </div>
            <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
              {{ props.files.length }} 个文件
            </div>
          </div>
          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              历史快照
            </div>
            <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
              {{ props.showHistory ? `${props.historyItems.length} 条` : '未启用' }}
            </div>
          </div>
        </div>

        <div
          v-if="props.isViewingBranch"
          class="flex items-center justify-between gap-3 rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-4 text-sm dark:border-primary-900/40 dark:bg-primary-950/20"
        >
          <div class="min-w-0">
            <div class="font-semibold text-gray-900 dark:text-white">
              当前正在查看历史分支
            </div>
            <div class="mt-1 break-all text-xs leading-6 text-gray-500 dark:text-dark-300">
              {{ props.selectedBranch }}
            </div>
          </div>
          <BaseButton
            variant="ghost"
            @click="emit('select-branch', '')"
          >
            返回最新
          </BaseButton>
        </div>

        <div class="pw-card-glass p-4">
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
            当前上下文
          </div>
          <div class="mt-3 space-y-3 text-sm leading-7 text-gray-600 dark:text-dark-300">
            <div class="flex items-start justify-between gap-3">
              <span>Target</span>
              <span class="max-w-[320px] break-all text-right font-semibold text-gray-900 dark:text-white">{{ props.targetText }}</span>
            </div>
            <div class="flex items-start justify-between gap-3">
              <span>项目</span>
              <span class="max-w-[320px] text-right font-semibold text-gray-900 dark:text-white">{{ props.projectName || '--' }}</span>
            </div>
            <div class="flex items-start justify-between gap-3">
              <span>Thread</span>
              <span class="max-w-[320px] break-all text-right font-semibold text-gray-900 dark:text-white">{{ props.activeThreadId || '--' }}</span>
            </div>
            <div class="flex items-start justify-between gap-3">
              <span>Run</span>
              <span class="max-w-[320px] break-all text-right font-semibold text-gray-900 dark:text-white">{{ props.lastRunId || '--' }}</span>
            </div>
            <div class="flex items-start justify-between gap-3">
              <span>Branch</span>
              <span class="max-w-[320px] break-all text-right font-semibold text-gray-900 dark:text-white">
                {{ props.selectedBranch || 'latest' }}
              </span>
            </div>
            <div class="flex items-start justify-between gap-3">
              <span>最近消息</span>
              <span class="max-w-[320px] text-right text-gray-500 dark:text-dark-300">{{ props.latestMessagePreview || '暂无' }}</span>
            </div>
          </div>
        </div>

        <div
          v-if="props.sourceNote"
          class="rounded-2xl border border-sky-100 bg-sky-50/80 px-4 py-4 text-sm leading-7 text-sky-800 dark:border-sky-900/40 dark:bg-sky-950/20 dark:text-sky-100"
        >
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-500 dark:text-sky-300">
            目标来源
          </div>
          <div class="mt-2 whitespace-pre-wrap break-words">
            {{ props.sourceNote }}
          </div>
        </div>

        <div
          v-if="props.contextNotice"
          class="rounded-2xl border border-emerald-100 bg-emerald-50/80 px-4 py-4 text-sm leading-7 text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-100"
        >
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-600 dark:text-emerald-300">
            上下文说明
          </div>
          <div class="mt-2 whitespace-pre-wrap break-words">
            {{ props.contextNotice }}
          </div>
        </div>

        <div
          v-if="props.showArtifacts"
          class="pw-card-glass p-4 text-sm leading-7 text-gray-500 dark:text-dark-300"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            Artifact 侧栏
          </div>
          <p class="mt-2">
            当前 thread 如果存在 `values.ui` 条目，会在主画布右侧直接展开 artifact 侧栏。这里仅保留说明，不再重复渲染内容。
          </p>
        </div>

        <div
          v-if="props.allowResetTarget"
          class="pw-card-glass p-4"
        >
          <div class="text-sm font-semibold text-gray-900 dark:text-white">
            默认聊天目标
          </div>
          <p class="mt-2 text-sm leading-7 text-gray-500 dark:text-dark-300">
            这个动作只会清掉当前项目保存的默认聊天入口，不会删除任何 thread、消息或后端运行数据。
          </p>
          <div class="mt-4 flex justify-end">
            <BaseButton
              variant="ghost"
              @click="emit('reset-target')"
            >
              清空默认目标
            </BaseButton>
          </div>
        </div>
      </div>

      <div
        v-else-if="activeTab === 'tasks'"
        class="space-y-4"
      >
        <div
          v-if="props.planView.hasFrozenPlan"
          class="rounded-2xl border border-sky-100 bg-sky-50/80 px-4 py-4 text-sm leading-7 text-sky-800 dark:border-sky-900/40 dark:bg-sky-950/20 dark:text-sky-100"
        >
          主计划固定展示第一次 `write_todos` 生成的任务列表；后续实时 todos 只更新主计划状态，新出现的任务会单列到临时执行项。
        </div>

        <div
          v-if="hasTasks"
          class="grid gap-4 md:grid-cols-3"
        >
          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              当前任务
            </div>
            <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
              {{ props.planView.activeTask?.content || '暂无' }}
            </div>
          </div>
          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              主计划进度
            </div>
            <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
              {{ props.planView.completedTasks }}/{{ props.planView.totalTasks }}
            </div>
          </div>
          <div class="pw-card-glass p-4">
            <div class="text-xs text-gray-400 dark:text-dark-400">
              临时执行项
            </div>
            <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
              {{ props.planView.ephemeralTodos.length }}
            </div>
          </div>
        </div>

        <div
          v-if="!hasTasks"
          class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
        >
          当前还没有任务项。
        </div>

        <div
          v-for="statusKey in ['in_progress', 'pending', 'completed']"
          v-else
          :key="statusKey"
          class="space-y-3"
        >
          <template
            v-if="groupTodoList(props.planView.planTodos)[statusKey as keyof ReturnType<typeof groupTodoList>].length > 0"
          >
            <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              {{
                statusKey === 'in_progress'
                  ? 'In Progress'
                  : statusKey === 'pending'
                    ? 'Pending'
                    : 'Completed'
              }}
            </div>

            <div class="space-y-2">
              <div
                v-for="todo in groupTodoList(props.planView.planTodos)[statusKey as keyof ReturnType<typeof groupTodoList>]"
                :key="todo.id"
                class="rounded-2xl border border-white/70 bg-white/80 px-4 py-3 dark:border-dark-700 dark:bg-dark-900/70"
              >
                <div class="flex items-start gap-3">
                  <span
                    class="mt-1 inline-flex h-2.5 w-2.5 rounded-full border"
                    :class="statusDotClass(todo.status)"
                  />
                  <div class="min-w-0">
                    <div class="text-sm font-semibold text-gray-900 dark:text-white">
                      {{ todo.content }}
                    </div>
                    <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                      {{ todo.id }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <div
          v-if="props.planView.ephemeralTodos.length > 0"
          class="space-y-3"
        >
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
            临时执行项
          </div>
          <div class="space-y-2">
            <div
              v-for="todo in props.planView.ephemeralTodos"
              :key="todo.id"
              class="rounded-2xl border border-amber-100 bg-amber-50/80 px-4 py-3 dark:border-amber-900/30 dark:bg-amber-950/15"
            >
              <div class="flex items-start gap-3">
                <span
                  class="mt-1 inline-flex h-2.5 w-2.5 rounded-full border"
                  :class="statusDotClass(todo.status)"
                />
                <div class="min-w-0">
                  <div class="text-sm font-semibold text-gray-900 dark:text-white">
                    {{ todo.content }}
                  </div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                    {{ todo.id }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        v-else-if="activeTab === 'files'"
        class="space-y-4"
      >
        <div
          v-if="props.files.length === 0"
          class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
        >
          当前线程还没有文件状态。
        </div>

        <div
          v-else
          class="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]"
        >
          <div class="space-y-2">
            <button
              v-for="file in props.files"
              :key="file.path"
              type="button"
              class="block w-full rounded-2xl border px-3 py-3 text-left transition"
              :class="
                selectedFilePath === file.path
                  ? 'border-primary-200 bg-primary-50 text-primary-700 dark:border-primary-900/40 dark:bg-primary-950/20 dark:text-primary-100'
                  : 'border-white/70 bg-white/80 text-gray-600 hover:border-gray-200 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-200 dark:hover:bg-dark-800 dark:hover:text-white'
              "
              @click="selectedFilePath = file.path"
            >
              <div class="truncate text-sm font-semibold">
                {{ file.path }}
              </div>
              <div class="mt-1 text-xs opacity-70">
                {{ file.lineCount }} 行
              </div>
            </button>
          </div>

          <div
            v-if="selectedFile"
            class="space-y-3"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  {{ selectedFile.path }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  {{ selectedFile.lineCount }} 行
                </div>
              </div>

              <div class="flex flex-wrap gap-2">
                <BaseButton
                  variant="ghost"
                  @click="handleCopyFile"
                >
                  复制
                </BaseButton>
                <BaseButton
                  variant="ghost"
                  @click="handleDownloadFile"
                >
                  下载
                </BaseButton>
                <BaseButton
                  v-if="!isEditing"
                  variant="ghost"
                  @click="handleStartEdit"
                >
                  编辑
                </BaseButton>
              </div>
            </div>

            <textarea
              v-if="isEditing"
              v-model="editValue"
              rows="18"
              class="pw-input min-h-[420px] resize-y font-mono text-xs leading-6"
            />
            <pre
              v-else
              class="min-h-[420px] overflow-auto whitespace-pre-wrap break-words rounded-[24px] border border-white/70 bg-white/90 px-4 py-4 text-xs leading-6 text-gray-700 dark:border-dark-700 dark:bg-dark-900/80 dark:text-dark-100"
            >{{ selectedFile.content }}</pre>

            <div
              v-if="isEditing"
              class="flex flex-wrap justify-end gap-3"
            >
              <BaseButton
                variant="ghost"
                @click="handleCancelEdit"
              >
                取消
              </BaseButton>
              <BaseButton
                :disabled="editDisabled"
                @click="handleSaveEdit"
              >
                {{ isSaving ? '保存中...' : '保存' }}
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <div
        v-else-if="activeTab === 'history'"
        class="space-y-3"
      >
        <div
          v-if="!props.showHistory"
          class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
        >
          当前页面没有启用历史分支功能。
        </div>

        <template v-else>
          <div class="grid gap-4 md:grid-cols-3">
            <div class="pw-card-glass p-4">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                Checkpoints
              </div>
              <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                {{ historyView.totalEntries }}
              </div>
            </div>
            <div class="pw-card-glass p-4">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                分叉组
              </div>
              <div class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
                {{ historyView.branchGroupCount }}
              </div>
            </div>
            <div class="pw-card-glass p-4">
              <div class="text-xs text-gray-400 dark:text-dark-400">
                当前快照
              </div>
              <div class="mt-2 break-all text-sm font-semibold text-gray-900 dark:text-white">
                {{ historyView.activeCheckpointId || 'latest' }}
              </div>
            </div>
          </div>

          <div
            class="flex flex-col gap-3 rounded-2xl border border-primary-200 bg-primary-50/70 px-4 py-4 text-sm dark:border-primary-900/40 dark:bg-primary-950/20 sm:flex-row sm:items-center sm:justify-between"
          >
            <div class="min-w-0">
              <div class="font-semibold text-gray-900 dark:text-white">
                {{ props.isViewingBranch ? '当前正在查看历史分支' : '当前正在查看最新线程头' }}
              </div>
              <div class="mt-1 break-all text-xs leading-6 text-gray-500 dark:text-dark-300">
                {{
                  props.isViewingBranch
                    ? props.selectedBranch
                    : historyView.activeCheckpointId || 'latest'
                }}
              </div>
            </div>
            <BaseButton
              v-if="props.isViewingBranch"
              variant="ghost"
              @click="emit('select-branch', '')"
            >
              返回最新
            </BaseButton>
          </div>

          <div
            v-if="props.historyItems.length === 0"
            class="rounded-2xl border border-dashed border-gray-200 px-4 py-6 text-sm leading-7 text-gray-500 dark:border-dark-700 dark:text-dark-300"
          >
            当前 thread 还没有 checkpoint 历史，或者还没开始对话。
          </div>

          <div
            v-else
            class="space-y-4"
          >
            <div
              v-for="(entry, historyIndex) in props.historyItems"
              :key="getHistoryEntryId(entry, historyIndex)"
              class="relative pl-6"
            >
              <span class="absolute left-0 top-7 h-full w-px bg-gray-200 dark:bg-dark-700" />
              <span
                class="absolute left-[-4px] top-6 inline-flex h-3 w-3 rounded-full border-2 border-white dark:border-dark-950"
                :class="
                  historyView.items[historyIndex]?.isCurrent
                    ? 'bg-primary-500'
                    : historyView.items[historyIndex]?.isInSelectedPath
                      ? 'bg-sky-500'
                      : historyView.items[historyIndex]?.childCount
                        ? 'bg-amber-500'
                        : 'bg-gray-300 dark:bg-dark-500'
                "
              />

              <details class="rounded-2xl border border-white/70 bg-white/80 p-4 dark:border-dark-700 dark:bg-dark-900/70">
                <summary class="cursor-pointer list-none">
                  <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div class="min-w-0">
                      <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                        {{ historyView.items[historyIndex]?.preview || getHistoryEntryPreviewText(entry, historyIndex) }}
                      </div>
                      <div class="mt-1 truncate text-xs text-gray-400 dark:text-dark-400">
                        {{ historyView.items[historyIndex]?.id || getHistoryEntryId(entry, historyIndex) }}
                      </div>
                    </div>
                    <div class="shrink-0 text-xs text-gray-400 dark:text-dark-400">
                      {{ historyView.items[historyIndex]?.time || getHistoryEntryTime(entry) }}
                    </div>
                  </div>

                  <div class="mt-3 flex flex-wrap gap-2">
                    <span
                      v-if="historyView.items[historyIndex]?.isLatest"
                      class="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-200"
                    >
                      latest
                    </span>
                    <span
                      v-if="historyView.items[historyIndex]?.isCurrent"
                      class="inline-flex items-center rounded-full border border-primary-200 bg-primary-50 px-2.5 py-1 text-[11px] font-medium text-primary-700 dark:border-primary-900/40 dark:bg-primary-950/20 dark:text-primary-200"
                    >
                      当前快照
                    </span>
                    <span
                      v-if="historyView.items[historyIndex]?.isInSelectedPath && !historyView.items[historyIndex]?.isCurrent"
                      class="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-medium text-sky-700 dark:border-sky-900/40 dark:bg-sky-950/20 dark:text-sky-200"
                    >
                      当前分支路径
                    </span>
                    <span
                      v-if="(historyView.items[historyIndex]?.siblingCount || 0) > 1"
                      class="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200"
                    >
                      分叉组 {{ historyView.items[historyIndex]?.siblingCount }}
                    </span>
                    <span
                      v-if="(historyView.items[historyIndex]?.childCount || 0) > 0"
                      class="inline-flex items-center rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-[11px] font-medium text-violet-700 dark:border-violet-900/40 dark:bg-violet-950/20 dark:text-violet-200"
                    >
                      后续分支 {{ historyView.items[historyIndex]?.childCount }}
                    </span>
                    <span class="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-300">
                      {{ historyView.items[historyIndex]?.step || '--' }}
                    </span>
                    <span
                      v-if="historyView.items[historyIndex]?.source"
                      class="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-300"
                    >
                      {{ historyView.items[historyIndex]?.source }}
                    </span>
                    <span class="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-300">
                      messages {{ historyView.items[historyIndex]?.messageCount || 0 }}
                    </span>
                    <span
                      v-if="(historyView.items[historyIndex]?.taskCount || 0) > 0"
                      class="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-300"
                    >
                      tasks {{ historyView.items[historyIndex]?.taskCount || 0 }}
                    </span>
                    <span
                      v-if="historyView.items[historyIndex]?.hasInterrupts"
                      class="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-medium text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-200"
                    >
                      interrupts
                    </span>
                  </div>
                </summary>

                <div class="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div class="text-xs leading-6 text-gray-500 dark:text-dark-300">
                    <span v-if="historyView.items[historyIndex]?.parentId">
                      parent: {{ historyView.items[historyIndex]?.parentId }}
                    </span>
                    <span v-else>根 checkpoint</span>
                  </div>
                  <BaseButton
                    variant="ghost"
                    :disabled="historyView.items[historyIndex]?.isCurrent"
                    @click="emit('select-branch', historyView.items[historyIndex]?.id || getHistoryEntryId(entry, historyIndex))"
                  >
                    {{ historyView.items[historyIndex]?.selectLabel || '查看此快照' }}
                  </BaseButton>
                </div>

                <pre class="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-gray-950 px-3 py-3 text-xs leading-6 text-gray-100 dark:bg-black/50">{{ toPrettyJson(entry) }}</pre>
              </details>
            </div>
          </div>
        </template>
      </div>
    </div>
  </BaseDrawer>
</template>

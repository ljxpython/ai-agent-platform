<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useUiStore } from '@/stores/ui'
import { downloadBlob } from '@/utils/browser-download'
import { copyText } from '@/utils/clipboard'
import { buildChatPlanView, type ChatPlanTodo } from '../plan-view-model'

type PanelMode = 'tasks' | 'files' | null
type TodoStatus = ChatPlanTodo['status']

type NormalizedFile = {
  path: string
  content: string
}

const props = defineProps<{
  values?: Record<string, unknown> | null
  isRunning: boolean
  hasInterrupt: boolean
  onUpdateState: (values: Record<string, unknown>) => Promise<boolean>
}>()

const uiStore = useUiStore()
const metaOpen = ref<PanelMode>(null)
const selectedFilePath = ref('')
const isEditing = ref(false)
const editValue = ref('')
const isSaving = ref(false)
const previousTodosCount = ref(0)
const previousFilesCount = ref(0)

function normalizeFileContent(rawContent: unknown): string {
  if (typeof rawContent === 'string') {
    return rawContent
  }

  if (rawContent && typeof rawContent === 'object') {
    const fileRecord = rawContent as Record<string, unknown>
    if ('content' in fileRecord) {
      const content = fileRecord.content
      if (typeof content === 'string') {
        return content
      }
      if (Array.isArray(content)) {
        return content.map((item) => String(item)).join('\n')
      }
      if (content != null) {
        return JSON.stringify(content, null, 2)
      }
      return ''
    }

    return JSON.stringify(fileRecord, null, 2)
  }

  if (rawContent == null) {
    return ''
  }

  return String(rawContent)
}

function normalizeFiles(values?: Record<string, unknown> | null): NormalizedFile[] {
  const rawFiles = values?.files
  if (!rawFiles || typeof rawFiles !== 'object' || Array.isArray(rawFiles)) {
    return []
  }

  return Object.entries(rawFiles as Record<string, unknown>)
    .map(([path, rawContent]) => ({
      path,
      content: normalizeFileContent(rawContent)
    }))
    .sort((left, right) => left.path.localeCompare(right.path))
}

function groupTodoList(todos: ChatPlanTodo[]) {
  return {
    in_progress: todos.filter((item) => item.status === 'in_progress'),
    pending: todos.filter((item) => item.status === 'pending'),
    completed: todos.filter((item) => item.status === 'completed')
  }
}

const planView = computed(() => buildChatPlanView(props.values))
const todos = computed(() => planView.value.planTodos)
const ephemeralTodos = computed(() => planView.value.ephemeralTodos)
const files = computed(() => normalizeFiles(props.values))
const groupedTodos = computed(() => groupTodoList(todos.value))
const groupedEphemeralTodos = computed(() => groupTodoList(ephemeralTodos.value))
const totalTasks = computed(() => planView.value.totalTasks)
const completedTasks = computed(() => planView.value.completedTasks)
const activeTask = computed(() => planView.value.activeTask)
const hasFrozenPlan = computed(() => planView.value.hasFrozenPlan)
const allTasksCompleted = computed(() => planView.value.allTasksCompleted)
const hasTasks = computed(() => totalTasks.value > 0 || ephemeralTodos.value.length > 0)
const hasEphemeralTodos = computed(() => ephemeralTodos.value.length > 0)
const hasFiles = computed(() => files.value.length > 0)
const selectedFile = computed(
  () => files.value.find((item) => item.path === selectedFilePath.value) || null
)
const editDisabled = computed(() => props.isRunning || props.hasInterrupt || isSaving.value)

watch(
  () => todos.value.length,
  (nextCount) => {
    if (previousTodosCount.value === 0 && nextCount > 0) {
      metaOpen.value = metaOpen.value || 'tasks'
    }
    previousTodosCount.value = nextCount
  },
  { immediate: true }
)

watch(
  () => files.value.length,
  (nextCount) => {
    if (previousFilesCount.value === 0 && nextCount > 0) {
      metaOpen.value = metaOpen.value || 'files'
    }
    previousFilesCount.value = nextCount
  },
  { immediate: true }
)

watch(
  () => files.value,
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
    }
  },
  { immediate: true, deep: true }
)

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

  downloadBlob(new Blob([selectedFile.value.content], { type: 'text/plain;charset=utf-8' }), selectedFile.value.path)
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
  <div
    v-if="hasTasks || hasFiles"
    class="pw-panel-muted mb-4 overflow-hidden p-0"
  >
    <div class="flex flex-wrap items-center gap-2 border-b border-slate-200/80 px-4 py-3 dark:border-dark-700">
      <button
        v-if="hasTasks"
        type="button"
        class="pw-chip-toggle"
        :class="
          metaOpen === 'tasks'
            ? 'pw-chip-toggle-active'
            : ''
        "
        @click="metaOpen = metaOpen === 'tasks' ? null : 'tasks'"
      >
        <span
          class="inline-flex h-2.5 w-2.5 rounded-full border"
          :class="
            allTasksCompleted
              ? 'border-emerald-200 bg-emerald-500'
              : activeTask
                ? statusDotClass(activeTask.status)
                : 'border-gray-200 bg-white'
          "
        />
        <span>Tasks</span>
        <span class="pw-pill-count">
          {{ completedTasks }}/{{ totalTasks }}
        </span>
      </button>

      <button
        v-if="hasFiles"
        type="button"
        class="pw-chip-toggle"
        :class="
          metaOpen === 'files'
            ? 'pw-chip-toggle-active'
            : ''
        "
        @click="metaOpen = metaOpen === 'files' ? null : 'files'"
      >
        <BaseIcon
          name="file"
          size="sm"
        />
        <span>Files</span>
        <span class="pw-pill-count">
          {{ files.length }}
        </span>
      </button>

      <div class="ml-auto text-xs text-gray-400 dark:text-dark-400">
        {{
          metaOpen === 'tasks'
            ? allTasksCompleted
              ? '当前任务已全部完成'
              : activeTask
                ? `正在处理：${activeTask.content}`
                : hasEphemeralTodos
                  ? `存在 ${ephemeralTodos.length} 个临时执行项`
                  : '当前还没有任务项'
            : metaOpen === 'files'
              ? selectedFile?.path || '当前还没有文件'
              : '执行面板已折叠'
        }}
      </div>
    </div>

    <div
      v-if="metaOpen === 'tasks'"
      class="max-h-64 space-y-4 overflow-y-auto px-4 py-4"
    >
      <div
        v-if="hasFrozenPlan"
        class="pw-panel-info px-3 py-3 text-xs leading-6 text-sky-800 dark:text-sky-100"
      >
        主计划固定展示第一次 write_todos 生成的任务列表；后续实时 todos 只更新主计划状态，新出现的任务会单列到临时执行项。
      </div>

      <div
        v-if="!hasTasks"
        class="text-sm leading-7 text-gray-500 dark:text-dark-300"
      >
        当前还没有任务项。
      </div>

      <div
        v-for="statusKey in ['in_progress', 'pending', 'completed']"
        v-else
        :key="statusKey"
      >
        <template v-if="groupedTodos[statusKey as keyof typeof groupedTodos].length > 0">
          <div class="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
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
              v-for="todo in groupedTodos[statusKey as keyof typeof groupedTodos]"
              :key="todo.id"
              class="pw-panel flex items-start gap-3 px-3 py-3 text-sm text-gray-700 dark:text-dark-100"
            >
              <span
                class="mt-1 inline-flex h-2.5 w-2.5 shrink-0 rounded-full border"
                :class="statusDotClass(todo.status)"
              />
              <span class="leading-7">{{ todo.content }}</span>
            </div>
          </div>
        </template>
      </div>

      <div
        v-if="hasEphemeralTodos"
        class="space-y-2"
      >
        <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-amber-500 dark:text-amber-300">
          临时执行项
        </div>
        <div class="pw-panel-warning px-3 py-3 text-xs leading-6 text-amber-800 dark:text-amber-100">
          这些任务出现在后续运行中，不属于首次制定的主计划，因此不会覆盖上面的原始任务清单。
        </div>
        <div
          v-for="statusKey in ['in_progress', 'pending', 'completed']"
          :key="`ephemeral-${statusKey}`"
        >
          <template v-if="groupedEphemeralTodos[statusKey as keyof typeof groupedEphemeralTodos].length > 0">
            <div class="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
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
                v-for="todo in groupedEphemeralTodos[statusKey as keyof typeof groupedEphemeralTodos]"
                :key="todo.id"
                class="pw-panel-warning flex items-start gap-3 px-3 py-3 text-sm text-gray-700 dark:text-dark-100"
              >
                <span
                  class="mt-1 inline-flex h-2.5 w-2.5 shrink-0 rounded-full border"
                  :class="statusDotClass(todo.status)"
                />
                <span class="leading-7">{{ todo.content }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div
      v-else-if="metaOpen === 'files'"
      class="grid gap-3 px-4 py-4 lg:grid-cols-[220px_1fr]"
    >
      <div class="pw-panel max-h-64 overflow-y-auto p-0">
        <button
          v-for="file in files"
          :key="file.path"
          type="button"
          class="block w-full truncate border-b border-slate-100 px-3 py-2 text-left text-sm transition last:border-b-0 dark:border-dark-700"
          :class="
            selectedFilePath === file.path
              ? 'bg-primary-50 text-primary-900 dark:bg-primary-950/30 dark:text-primary-100'
              : 'text-gray-500 hover:bg-slate-50 hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-800 dark:hover:text-white'
          "
          :title="file.path"
          @click="selectedFilePath = file.path"
        >
          {{ file.path }}
        </button>
      </div>

      <div class="pw-panel min-h-[240px] overflow-hidden p-0">
        <div
          v-if="selectedFile"
          class="flex h-full flex-col"
        >
          <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-3 py-3 dark:border-dark-700">
            <div class="min-w-0 text-xs text-gray-500 dark:text-dark-300">
              <div class="truncate font-semibold text-gray-900 dark:text-white">
                {{ selectedFile.path }}
              </div>
              <div class="mt-1">
                {{ isEditing ? '编辑模式' : '只读预览' }}
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <template v-if="isEditing">
                <BaseButton
                  variant="ghost"
                  :disabled="isSaving"
                  @click="handleCancelEdit"
                >
                  <BaseIcon
                    name="x"
                    size="sm"
                  />
                  取消
                </BaseButton>
                <BaseButton
                  variant="secondary"
                  :disabled="editDisabled"
                  @click="handleSaveEdit"
                >
                  {{ isSaving ? '保存中...' : '保存' }}
                </BaseButton>
              </template>
              <BaseButton
                v-else
                variant="ghost"
                :disabled="editDisabled"
                @click="handleStartEdit"
              >
                编辑
              </BaseButton>
              <BaseButton
                variant="ghost"
                @click="handleCopyFile"
              >
                <BaseIcon
                  name="copy"
                  size="sm"
                />
                复制
              </BaseButton>
              <BaseButton
                variant="ghost"
                @click="handleDownloadFile"
              >
                <BaseIcon
                  name="download"
                  size="sm"
                />
                下载
              </BaseButton>
            </div>
          </div>

          <textarea
            v-if="isEditing"
            v-model="editValue"
            class="min-h-[220px] flex-1 resize-none bg-transparent px-4 py-3 font-mono text-xs leading-6 text-gray-800 outline-none dark:text-dark-100"
            :disabled="editDisabled"
          />
          <pre
            v-else
            class="min-h-[220px] flex-1 overflow-auto px-4 py-3 text-xs leading-6 text-gray-800 dark:text-dark-100"
          >{{ selectedFile.content || '<empty file>' }}</pre>
        </div>

        <div
          v-else
          class="px-4 py-6 text-sm leading-7 text-gray-500 dark:text-dark-300"
        >
          当前还没有可预览的文件。
        </div>
      </div>
    </div>
  </div>
</template>

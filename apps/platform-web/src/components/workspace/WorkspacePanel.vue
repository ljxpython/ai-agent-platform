<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import BaseIcon from '@/components/base/BaseIcon.vue';
import WorkspaceTree from './WorkspaceTree.vue';
import WorkspacePreview from './WorkspacePreview.vue';
import TerminalPanel from './TerminalPanel.vue';
import { useThreadWorkspace } from '@/composables/useThreadWorkspace';

const props = defineProps<{
  projectId: string;
  threadId?: string;
  collapsed?: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'update:collapsed', val: boolean): void;
  (e: 'addToChat', text: string): void;
}>();

const projectIdRef = ref(props.projectId);
const threadIdRef = ref(props.threadId || '');

watch(
  () => props.projectId,
  (p) => {
    projectIdRef.value = p || '';
  },
);

watch(
  () => props.threadId,
  (t) => {
    threadIdRef.value = t || '';
  },
);

const {
  capabilities,
  directoryCache,
  directoryLoading,
  expandedPaths,
  artifacts,
  hasNewArtifactNotice,
  selectedPath,
  previewResult,
  loadingPreview,
  previewError,
  refreshing,
  toggleDirectory,
  selectFile,
  downloadCurrentFile,
  refresh,
  clearNewArtifactNotice,
} = useThreadWorkspace(projectIdRef, threadIdRef);

// 选项卡：'files' | 'artifacts' | 'terminal'
type TabKey = 'files' | 'artifacts' | 'terminal';
const activeTab = ref<TabKey>('files');

// 全屏状态
const isMaximized = ref(false);

// 树侧边栏折叠状态
const isSidebarCollapsed = ref(false);

// 面板宽度拖拽
const panelWidth = ref(600);
const isResizing = ref(false);

// 内部侧边栏宽度拖拽
const sidebarWidth = ref(240);
const isSidebarResizing = ref(false);

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isMaximized.value) {
    isMaximized.value = false;
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
  const saved = localStorage.getItem('workspace_panel_width');
  if (saved) {
    const num = parseInt(saved, 10);
    if (!isNaN(num) && num >= 380 && num <= 1200) {
      panelWidth.value = num;
    }
  }
  const savedSidebar = localStorage.getItem('workspace_sidebar_width');
  if (savedSidebar) {
    const num = parseInt(savedSidebar, 10);
    if (!isNaN(num) && num >= 160 && num <= 560) {
      sidebarWidth.value = num;
    }
  }
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});

function startResize(e: MouseEvent) {
  isResizing.value = true;
  const startX = e.clientX;
  const startWidth = panelWidth.value;

  function onMouseMove(moveEvent: MouseEvent) {
    // 拖动左侧边缘向左增大，向右减小
    const delta = startX - moveEvent.clientX;
    const newWidth = Math.min(1200, Math.max(380, startWidth + delta));
    panelWidth.value = newWidth;
  }

  function onMouseUp() {
    isResizing.value = false;
    localStorage.setItem('workspace_panel_width', String(panelWidth.value));
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

function startSidebarResize(e: MouseEvent) {
  isSidebarResizing.value = true;
  document.body.classList.add('select-none');
  const startX = e.clientX;
  const startWidth = sidebarWidth.value;

  function onMouseMove(moveEvent: MouseEvent) {
    const delta = moveEvent.clientX - startX;
    // 动态限制：保证右侧预览区至少留有 260px
    const maxAllowed = Math.max(200, Math.min(560, panelWidth.value - 260));
    const newWidth = Math.min(maxAllowed, Math.max(160, startWidth + delta));
    sidebarWidth.value = newWidth;
  }

  function onMouseUp() {
    isSidebarResizing.value = false;
    document.body.classList.remove('select-none');
    localStorage.setItem('workspace_sidebar_width', String(sidebarWidth.value));
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

function resetSidebarWidth() {
  sidebarWidth.value = 240;
  localStorage.setItem('workspace_sidebar_width', '240');
}

function resetWidth() {
  panelWidth.value = 600;
  localStorage.setItem('workspace_panel_width', '600');
}

// 切换选项卡
function switchTab(tab: TabKey) {
  activeTab.value = tab;
  if (tab === 'artifacts') {
    clearNewArtifactNotice();
  }
}

// 选中 Artifact 产物预览
function selectArtifact(path: string) {
  void selectFile(path);
}

// 格式化大小
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// 供父组件调用的主动刷新方法
defineExpose({
  refresh,
  openTab: switchTab,
});
</script>

<template>
  <Teleport to="body" :disabled="!isMaximized">
    <aside
      class="flex h-full min-h-0 flex-col select-none transition-[width] duration-75"
      :class="[
        isMaximized
          ? 'fixed inset-0 z-[100] h-screen w-screen bg-white shadow-2xl dark:bg-dark-900'
          : 'relative border-l border-gray-200 bg-white dark:border-dark-800 dark:bg-dark-900',
        isResizing ? 'select-none' : '',
      ]"
      :style="isMaximized ? {} : { width: `${panelWidth}px` }"
    >
    <!-- 左侧可拖拽调整尺寸边框手柄 -->
    <div
      v-if="!isMaximized"
      class="group absolute -left-1 top-0 bottom-0 z-20 w-2 cursor-col-resize hover:bg-primary-500/20"
      title="拖拽调节工作区宽度，双击重置"
      @mousedown.prevent="startResize"
      @dblclick="resetWidth"
    >
      <div
        class="mx-auto h-full w-[1px] bg-transparent group-hover:bg-primary-500 transition-colors"
      />
    </div>

    <!-- 顶部主标题与操作导航栏 -->
    <div
      class="flex h-12 shrink-0 items-center justify-between border-b border-gray-200 bg-gray-50/90 px-3 dark:border-dark-800 dark:bg-dark-950/70"
    >
      <!-- Tab 切换按钮组 -->
      <div class="flex items-center gap-1">
        <!-- 1. Files Tab -->
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors"
          :class="
            activeTab === 'files'
              ? 'bg-white text-primary-600 shadow-sm dark:bg-dark-800 dark:text-primary-400'
              : 'text-gray-600 hover:bg-gray-200/60 dark:text-dark-300 dark:hover:bg-dark-800'
          "
          @click="switchTab('files')"
        >
          <BaseIcon
            name="folder"
            class="h-3.5 w-3.5"
          />
          <span>工作区</span>
        </button>

        <!-- 2. Artifacts Tab -->
        <button
          type="button"
          class="relative flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors"
          :class="
            activeTab === 'artifacts'
              ? 'bg-white text-primary-600 shadow-sm dark:bg-dark-800 dark:text-primary-400'
              : 'text-gray-600 hover:bg-gray-200/60 dark:text-dark-300 dark:hover:bg-dark-800'
          "
          @click="switchTab('artifacts')"
        >
          <BaseIcon
            name="sparkle"
            class="h-3.5 w-3.5 text-purple-500"
          />
          <span>产物库</span>
          <span
            v-if="artifacts.length > 0"
            class="rounded-full bg-gray-200 px-1.5 py-0.2 text-[10px] text-gray-700 dark:bg-dark-700 dark:text-dark-200"
          >
            {{ artifacts.length }}
          </span>
          <!-- 未读产物红点 -->
          <span
            v-if="hasNewArtifactNotice"
            class="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-red-500 animate-pulse"
          />
        </button>

        <!-- 3. Terminal Tab -->
        <button
          v-if="capabilities?.terminal !== false"
          type="button"
          class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors"
          :class="
            activeTab === 'terminal'
              ? 'bg-white text-primary-600 shadow-sm dark:bg-dark-800 dark:text-primary-400'
              : 'text-gray-600 hover:bg-gray-200/60 dark:text-dark-300 dark:hover:bg-dark-800'
          "
          @click="switchTab('terminal')"
        >
          <BaseIcon
            name="runtime"
            class="h-3.5 w-3.5 text-emerald-500"
          />
          <span>终端</span>
        </button>
      </div>

      <!-- 右侧控制按钮组 -->
      <div class="flex items-center gap-1">
        <!-- 刷新按钮 -->
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-700 disabled:opacity-40 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-200 transition-colors"
          :disabled="refreshing"
          :title="refreshing ? '正在刷新...' : '刷新工作区'"
          @click="() => refresh()"
        >
          <BaseIcon
            name="refresh"
            class="h-3.5 w-3.5"
            :class="refreshing ? 'animate-spin text-primary-600 dark:text-primary-400' : ''"
          />
        </button>

        <!-- 全屏最大化切换 -->
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-200"
          :title="isMaximized ? '退出全屏' : '全屏展开工作区'"
          @click="isMaximized = !isMaximized"
        >
          <BaseIcon
            :name="isMaximized ? 'collapse' : 'maximize'"
            class="h-3.5 w-3.5"
          />
        </button>

        <!-- 关闭面板按钮 -->
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-200"
          title="收起工作区"
          @click="emit('close')"
        >
          <BaseIcon
            name="x"
            class="h-3.5 w-3.5"
          />
        </button>
      </div>
    </div>

    <!-- 面板内容区域 -->
    <div class="relative min-h-0 flex-1 overflow-hidden">
      <!-- 视图 1：Files 文件树与主预览 -->
      <div
        v-show="activeTab === 'files'"
        class="flex h-full w-full"
      >
        <!-- 左侧文件树侧边栏 -->
        <div
          v-show="!isSidebarCollapsed"
          class="flex shrink-0 flex-col border-r border-gray-200 bg-gray-50/50 dark:border-dark-800 dark:bg-dark-950/30"
          :style="{ width: `${sidebarWidth}px` }"
        >
          <div class="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-dark-800">
            <span class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">文件目录</span>
            <button
              type="button"
              class="rounded p-1 text-gray-400 hover:text-gray-700 dark:hover:text-dark-200"
              title="收起文件树"
              @click="isSidebarCollapsed = true"
            >
              <BaseIcon
                name="chevron-left"
                class="h-3 w-3"
              />
            </button>
          </div>
          <div class="flex-1 overflow-y-auto p-2">
            <WorkspaceTree
              :directory-cache="directoryCache"
              :expanded-paths="expandedPaths"
              :directory-loading="directoryLoading"
              :selected-path="selectedPath"
              @toggle="toggleDirectory"
              @select="selectFile"
            />
          </div>
        </div>

        <!-- 文件树侧边栏可拖拽分割条 (Splitter) -->
        <div
          v-if="!isSidebarCollapsed"
          class="group relative -ml-1 w-2 z-10 flex shrink-0 cursor-col-resize items-center justify-center select-none"
          title="双击恢复默认宽度，按住拖动调整"
          @mousedown="startSidebarResize"
          @dblclick="resetSidebarWidth"
        >
          <div
            class="h-full w-[2px] transition-colors group-hover:bg-primary-500/80"
            :class="isSidebarResizing ? 'bg-primary-500' : 'bg-transparent'"
          />
        </div>

        <!-- 展开侧边栏小悬浮条 -->
        <div
          v-if="isSidebarCollapsed"
          class="flex w-6 shrink-0 items-center justify-center border-r border-gray-200 bg-gray-50/80 dark:border-dark-800 dark:bg-dark-950/40"
        >
          <button
            type="button"
            class="rounded p-1 text-gray-400 hover:text-gray-700 dark:hover:text-dark-200"
            title="展开文件树"
            @click="isSidebarCollapsed = false"
          >
            <BaseIcon
              name="chevron-right"
              class="h-3.5 w-3.5"
            />
          </button>
        </div>

        <!-- 右侧主预览区 -->
        <div class="min-w-0 flex-1">
          <WorkspacePreview
            :project-id="projectIdRef"
            :thread-id="threadIdRef"
            :path="selectedPath"
            :preview-result="previewResult"
            :loading="loadingPreview"
            :error="previewError"
            @download="downloadCurrentFile"
          />
        </div>
      </div>

      <!-- 视图 2：Artifacts 交付物列表与主预览 -->
      <div
        v-show="activeTab === 'artifacts'"
        class="flex h-full w-full"
      >
        <!-- 左侧产物列表 -->
        <div
          class="flex shrink-0 flex-col border-r border-gray-200 bg-gray-50/50 p-2 overflow-y-auto dark:border-dark-800 dark:bg-dark-950/30"
          :style="{ width: `${sidebarWidth}px` }"
        >
          <div class="mb-2 px-1 text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
            交付物列表 ({{ artifacts.length }})
          </div>

          <div
            v-if="artifacts.length === 0"
            class="py-8 text-center text-xs text-gray-400 dark:text-dark-400"
          >
            当前暂无已发布的交付物
          </div>

          <div
            v-else
            class="space-y-1.5"
          >
            <button
              v-for="item in artifacts"
              :key="item.artifact_id + item.path"
              type="button"
              class="flex w-full flex-col rounded-xl border p-2.5 text-left transition-colors"
              :class="
                selectedPath === item.path
                  ? 'border-primary-300 bg-white text-gray-900 shadow-sm dark:border-primary-800 dark:bg-dark-800 dark:text-white'
                  : 'border-transparent hover:border-gray-200 hover:bg-white text-gray-600 dark:text-dark-300 dark:hover:border-dark-700 dark:hover:bg-dark-800'
              "
              :title="item.path"
              @click="selectArtifact(item.path)"
            >
              <div class="flex items-center gap-1.5">
                <BaseIcon
                  name="sparkle"
                  class="h-3.5 w-3.5 shrink-0 text-purple-500"
                />
                <span class="truncate text-xs font-semibold" :title="item.file_name">{{ item.file_name }}</span>
              </div>
              <div class="mt-1 flex items-center justify-between text-[10px] opacity-70">
                <span class="rounded bg-gray-100 px-1 py-0.2 dark:bg-dark-700">{{ item.kind || 'artifact' }}</span>
                <span>{{ formatBytes(item.size_bytes) }}</span>
              </div>
            </button>
          </div>
        </div>

        <!-- 产物列表可拖拽分割条 (Splitter) -->
        <div
          class="group relative -ml-1 w-2 z-10 flex shrink-0 cursor-col-resize items-center justify-center select-none"
          title="双击恢复默认宽度，按住拖动调整"
          @mousedown="startSidebarResize"
          @dblclick="resetSidebarWidth"
        >
          <div
            class="h-full w-[2px] transition-colors group-hover:bg-primary-500/80"
            :class="isSidebarResizing ? 'bg-primary-500' : 'bg-transparent'"
          />
        </div>

        <!-- 右侧主预览区 -->
        <div class="min-w-0 flex-1">
          <WorkspacePreview
            :project-id="projectIdRef"
            :thread-id="threadIdRef"
            :path="selectedPath"
            :preview-result="previewResult"
            :loading="loadingPreview"
            :error="previewError"
            @download="downloadCurrentFile"
          />
        </div>
      </div>

      <!-- 视图 3：Terminal 终端控制台（使用 v-show 保持挂载） -->
      <div
        v-show="activeTab === 'terminal'"
        class="h-full w-full"
      >
        <TerminalPanel
          :project-id="projectId"
          :thread-id="threadId"
          :active="activeTab === 'terminal'"
          @add-to-chat="(text) => emit('addToChat', text)"
          @open-file="(path) => { switchTab('files'); selectFile(path); }"
        />
      </div>
    </div>
  </aside>
</Teleport>
</template>

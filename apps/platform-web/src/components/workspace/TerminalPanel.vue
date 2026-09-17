<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import BaseIcon from '@/components/base/BaseIcon.vue';
import ConfirmDialog from '@/components/base/ConfirmDialog.vue';
import {
  useThreadTerminal,
  type TerminalOutputChunk,
} from '@/composables/useThreadTerminal';

const props = defineProps<{
  projectId: string;
  threadId?: string;
  active: boolean; // 是否处于当前工作区可见前台
}>();

const emit = defineEmits<{
  (e: 'addToChat', text: string): void;
  (e: 'openFile', path: string): void;
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

// 终端实例与 DOM 容器映射
const terminalContainers = ref<Record<string, HTMLElement | null>>({});
const xtermInstances = new Map<string, { term: Terminal; fit: FitAddon }>();

// 确认创建终端弹窗
const showAcknowledgeDialog = ref(false);

const {
  sessions,
  activeTerminalId,
  creating,
  createSession,
  closeSession,
  sendInput,
  handleResize,
  setBackground,
} = useThreadTerminal(projectIdRef, threadIdRef, {
  onOutputChunk: handleOutputChunk,
});

// 监听前后台状态切换（借鉴 open-swe）
watch(
  () => props.active,
  (isActive) => {
    setBackground(!isActive);
    if (isActive) {
      void nextTick(() => {
        fitActiveTerminal();
      });
    }
  },
  { immediate: true },
);

function getTerminalTheme() {
  const isDark = document.documentElement.classList.contains('dark');
  return isDark
    ? {
        background: '#111827', // dark-900 / gray-900
        foreground: '#F3F4F6',
        cursor: '#60A5FA',
        selectionBackground: 'rgba(96, 165, 250, 0.3)',
      }
    : {
        background: '#FFFFFF',
        foreground: '#1F2937',
        cursor: '#2563EB',
        selectionBackground: 'rgba(37, 99, 235, 0.2)',
      };
}

function initTerminalInstance(terminalId: string, el: HTMLElement) {
  if (xtermInstances.has(terminalId)) return;

  const term = new Terminal({
    theme: getTerminalTheme(),
    fontFamily:
      'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    fontSize: 13,
    lineHeight: 1.3,
    cursorBlink: true,
    convertEol: true,
    scrollback: 5000,
  });

  const fit = new FitAddon();
  term.loadAddon(fit);
  term.open(el);

  try {
    fit.fit();
  } catch {
    // 忽略首次不可见时的计算错误
  }

  // 输入监听
  term.onData((data) => {
    void sendInput(terminalId, data);
  });

  // 尺寸调整
  term.onResize(({ cols, rows }) => {
    handleResize(terminalId, rows, cols);
  });

  xtermInstances.set(terminalId, { term, fit });
}

function handleOutputChunk(chunk: TerminalOutputChunk) {
  const instance = xtermInstances.get(chunk.terminalId);
  if (instance) {
    instance.term.write(chunk.data);
  }
}

function fitActiveTerminal() {
  if (!activeTerminalId.value) return;
  const instance = xtermInstances.get(activeTerminalId.value);
  if (instance) {
    try {
      instance.fit.fit();
      instance.term.focus();
    } catch {
      // 容器尺寸未稳定时容错
    }
  }
}

// 切换激活的终端
function selectTerminal(terminalId: string) {
  activeTerminalId.value = terminalId;
  void nextTick(() => {
    fitActiveTerminal();
  });
}

// 绑定 DOM 引用
function setContainerRef(terminalId: string, el: HTMLElement | null) {
  terminalContainers.value[terminalId] = el;
  if (el && !xtermInstances.has(terminalId)) {
    initTerminalInstance(terminalId, el);
    fitActiveTerminal();
  }
}

// 清除当前终端屏幕
function clearActiveTerminal() {
  if (!activeTerminalId.value) return;
  const instance = xtermInstances.get(activeTerminalId.value);
  if (instance) {
    instance.term.clear();
  }
}

// 一键将当前终端选中的文本添加到聊天框（借鉴 open-swe）
function addSelectionToChat() {
  if (!activeTerminalId.value) return;
  const instance = xtermInstances.get(activeTerminalId.value);
  if (!instance) return;
  const selection = instance.term.getSelection().trim();
  if (selection) {
    emit('addToChat', `\`\`\`bash\n${selection}\n\`\`\``);
  }
}

// 点击新建终端
function handleNewTerminalClick() {
  // 如果当前已有会话，直接创建；如果首次创建，也可以直接或弹窗确认
  if (sessions.value.length === 0) {
    showAcknowledgeDialog.value = true;
  } else {
    void createSession().then((session) => {
      if (session) {
        void nextTick(() => fitActiveTerminal());
      }
    });
  }
}

function confirmCreateFirstSession() {
  showAcknowledgeDialog.value = false;
  void createSession().then((session) => {
    if (session) {
      void nextTick(() => fitActiveTerminal());
    }
  });
}

// 监听会话列表变化，销毁已删除会话的 xterm
watch(
  () => sessions.value,
  (currentSessions) => {
    const aliveIds = new Set(currentSessions.map((s) => s.terminal_id));
    for (const [id, instance] of xtermInstances.entries()) {
      if (!aliveIds.has(id)) {
        instance.term.dispose();
        xtermInstances.delete(id);
      }
    }
  },
  { deep: true },
);

// 窗口 resize 适配
function onWindowResize() {
  if (props.active) {
    fitActiveTerminal();
  }
}

onMounted(() => {
  window.addEventListener('resize', onWindowResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize);
  for (const [, instance] of xtermInstances) {
    instance.term.dispose();
  }
  xtermInstances.clear();
});
</script>

<template>
  <div class="flex h-full w-full flex-col bg-white dark:bg-dark-900">
    <!-- 顶部终端会话二级 Tab 栏 -->
    <div
      class="flex h-10 shrink-0 items-center justify-between border-b border-gray-200 bg-gray-50/80 px-2 dark:border-dark-800 dark:bg-dark-950/60"
    >
      <div class="flex min-w-0 items-center gap-1 overflow-x-auto">
        <button
          v-for="(session, index) in sessions"
          :key="session.terminal_id"
          type="button"
          class="group flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors"
          :class="
            activeTerminalId === session.terminal_id
              ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-800 dark:text-white'
              : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-dark-300 dark:hover:bg-dark-800'
          "
          @click="selectTerminal(session.terminal_id)"
        >
          <span
            class="h-1.5 w-1.5 rounded-full"
            :class="
              session.status === 'running'
                ? 'bg-emerald-500'
                : 'bg-gray-400 dark:bg-dark-400'
            "
          />
          <span>终端 {{ index + 1 }}</span>
          <span
            v-if="session.status === 'exited'"
            class="text-[10px] opacity-70"
          >
            ({{ session.exit_code ?? 0 }})
          </span>
          <span
            class="ml-1 rounded p-0.5 opacity-0 group-hover:opacity-100 hover:bg-gray-200 dark:hover:bg-dark-700"
            title="关闭终端"
            @click.stop="closeSession(session.terminal_id)"
          >
            <BaseIcon
              name="x"
              class="h-3 w-3"
            />
          </span>
        </button>

        <!-- 新建会话按钮 -->
        <button
          v-if="sessions.length < 4"
          type="button"
          class="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-200/70 hover:text-gray-900 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-100"
          :disabled="creating"
          title="新建终端会话 (最多4个)"
          @click="handleNewTerminalClick"
        >
          <span class="text-base leading-none">+</span>
          <span v-if="sessions.length === 0">启动终端</span>
        </button>
      </div>

      <!-- 快捷操作区 -->
      <div
        v-if="sessions.length > 0"
        class="flex items-center gap-1 shrink-0"
      >
        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-200"
          title="将选中的终端文本发送到提问框"
          @click="addSelectionToChat"
        >
          <BaseIcon
            name="chat"
            class="h-3.5 w-3.5"
          />
        </button>

        <button
          type="button"
          class="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-200"
          title="清空当前屏幕"
          @click="clearActiveTerminal"
        >
          <BaseIcon
            name="archive"
            class="h-3.5 w-3.5"
          />
        </button>
      </div>
    </div>

    <!-- 终端视窗主体 -->
    <div class="relative min-h-0 flex-1 bg-white p-2 dark:bg-dark-900">
      <div
        v-if="sessions.length === 0"
        class="flex h-full flex-col items-center justify-center p-8 text-center"
      >
        <BaseIcon
          name="runtime"
          class="h-10 w-10 text-gray-300 dark:text-dark-600"
        />
        <h3 class="mt-3 text-sm font-semibold text-gray-800 dark:text-dark-100">
          工作区交互终端
        </h3>
        <p class="mt-1 max-w-sm text-xs text-gray-500 dark:text-dark-400">
          终端直接接入当前线程的容器/沙箱环境，支持交互式运行 Shell 命令。输入会直接执行，不经过 Agent 审批。
        </p>
        <button
          type="button"
          class="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-primary-700"
          :disabled="creating"
          @click="handleNewTerminalClick"
        >
          {{ creating ? '启动中...' : '启动交互终端' }}
        </button>
      </div>

      <!-- 多个终端实例保持挂载（使用 v-show，杜绝重绘与失忆） -->
      <div
        v-for="session in sessions"
        v-show="activeTerminalId === session.terminal_id"
        :key="session.terminal_id"
        :ref="(el) => setContainerRef(session.terminal_id, el as HTMLElement)"
        class="h-full w-full overflow-hidden rounded-lg bg-white dark:bg-dark-900"
      />
    </div>

    <!-- 风险确认对话框 -->
    <ConfirmDialog
      :show="showAcknowledgeDialog"
      title="启动工作区终端确认"
      message="终端输入会直接在当前线程沙箱环境中执行，不经过 Agent 审批。请谨慎操作，避免执行不可信或破坏性命令。"
      confirm-text="确认启动"
      cancel-text="取消"
      @confirm="confirmCreateFirstSession"
      @cancel="showAcknowledgeDialog = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from "vue";
import type { SkillDetail } from "@/services/dear-agent/skills.service";
import { renderMarkdown } from "@/utils/markdown";
import { copyText } from "@/utils/clipboard";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";

const props = defineProps<{
  show: boolean;
  loading: boolean;
  skill: SkillDetail | null;
  selectedPath: string;
  selectedContent: string;
  contentLoading: boolean;
  contentError: string;
}>();

const emit = defineEmits<{
  close: [];
  "select-file": [path: string];
}>();

const copySuccess = ref(false);
const isSidebarCollapsed = ref(false);
const sidebarWidth = ref(240);

watch(
  () => props.show,
  (open) => {
    if (open) isSidebarCollapsed.value = false;
  },
);

const selectedFileItem = computed(() =>
  props.skill?.manifest?.find((m) => m.path === props.selectedPath),
);

function isMarkdown(path: string): boolean {
  return path.toLowerCase().endsWith(".md");
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KiB`;
}

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
}

function startResize(event: MouseEvent) {
  event.preventDefault();
  const startX = event.clientX;
  const startWidth = sidebarWidth.value;

  const onMouseMove = (e: MouseEvent) => {
    const deltaX = e.clientX - startX;
    sidebarWidth.value = Math.min(420, Math.max(160, startWidth + deltaX));
  };

  const onMouseUp = () => {
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
    document.body.style.removeProperty("cursor");
    document.body.style.removeProperty("user-select");
  };

  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", onMouseUp);
}

onScopeDispose(() => {
  document.body.style.removeProperty("cursor");
  document.body.style.removeProperty("user-select");
});

async function copyFileContent() {
  if (!props.selectedContent) return;
  const ok = await copyText(props.selectedContent);
  if (ok) {
    copySuccess.value = true;
    setTimeout(() => {
      copySuccess.value = false;
    }, 2500);
  }
}

async function handleMarkdownCopyClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null;
  const copyButton = target?.closest("[data-copy-code]") as HTMLButtonElement | null;
  if (!copyButton) return;

  const codeElement = copyButton.closest(".pw-markdown-code")?.querySelector("code");
  const code = codeElement?.textContent || "";
  if (!code) return;

  const success = await copyText(code);
  if (success) {
    copyButton.textContent = "已复制";
    window.setTimeout(() => {
      copyButton.textContent = "复制";
    }, 1600);
  }
}
</script>

<template>
  <BaseDrawer
    :show="show"
    :title="skill?.name || '技能详情与文件预览'"
    width="2xl"
    flush
    @close="emit('close')"
  >
    <div
      v-if="loading"
      class="flex h-full items-center justify-center p-12 text-xs text-zinc-500"
    >
      正在载入技能文件清单...
    </div>

    <div v-else-if="skill" class="flex flex-col h-full overflow-hidden">
      <div class="shrink-0 border-b border-zinc-200 bg-zinc-50/80 px-5 py-3 dark:border-zinc-800 dark:bg-zinc-900/60">
        <div class="flex items-center justify-between gap-4">
          <div class="flex items-center gap-2 min-w-0">
            <span class="text-xs text-zinc-400 font-mono shrink-0">slug:</span>
            <span class="rounded bg-zinc-200/60 px-1.5 py-0.5 font-mono text-xs font-semibold text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200 truncate">
              {{ skill.slug }}
            </span>
          </div>
          <span
            :class="[
              'shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium tracking-wide',
              skill.source === 'public'
                ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300'
                : 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300'
            ]"
          >
            {{ skill.source === 'public' ? '平台公共技能' : '用户自定义' }}
          </span>
        </div>
        <p
          v-if="skill.description"
          class="mt-1 text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed line-clamp-2"
        >
          {{ skill.description }}
        </p>
      </div>

      <div class="flex flex-1 min-h-0 overflow-hidden relative">
        <div
          v-show="!isSidebarCollapsed"
          :style="{ width: sidebarWidth + 'px' }"
          class="flex flex-col shrink-0 border-r border-zinc-200 bg-zinc-50/30 dark:border-zinc-800 dark:bg-zinc-900/20 overflow-hidden select-none"
        >
          <div class="flex items-center justify-between border-b border-zinc-200/60 px-3.5 py-2.5 dark:border-zinc-800/60 shrink-0">
            <div class="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
              文件清单 ({{ skill.manifest?.length || 0 }})
            </div>
            <button
              type="button"
              class="rounded p-1 text-zinc-400 hover:bg-zinc-200/60 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 transition"
              title="收起文件清单"
              @click="toggleSidebar"
            >
              <BaseIcon name="collapse" size="xs" class="shrink-0" />
            </button>
          </div>

          <div class="flex-1 overflow-y-auto p-2 space-y-0.5">
            <button
              v-for="file in skill.manifest || []"
              :key="file.path"
              type="button"
              :class="[
                'group flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-xs transition-colors',
                selectedPath === file.path
                  ? 'bg-primary-50 font-medium text-primary-700 dark:bg-primary-950/50 dark:text-primary-300'
                  : 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800/60'
              ]"
              @click="emit('select-file', file.path)"
            >
              <div class="flex items-center gap-2 min-w-0 pr-1">
                <BaseIcon
                  :name="file.readable ? 'file' : 'shield'"
                  size="xs"
                  :class="[
                    'shrink-0',
                    file.readable ? 'text-zinc-400 group-hover:text-zinc-600' : 'text-amber-500'
                  ]"
                />
                <span class="truncate text-xs" :title="file.path">{{ file.path }}</span>
              </div>
              <span class="font-mono text-[10px] text-zinc-400 shrink-0 ml-1">
                {{ formatFileSize(file.size) }}
              </span>
            </button>
          </div>
        </div>

        <div
          v-show="!isSidebarCollapsed"
          class="group relative w-1 cursor-col-resize select-none bg-zinc-200/70 hover:bg-primary-500/80 active:bg-primary-600 dark:bg-zinc-800 transition-colors shrink-0 z-10"
          title="拖动调整文件清单宽度"
          @mousedown="startResize"
        >
          <div class="absolute inset-y-0 -left-1 -right-1 z-10" />
        </div>

        <div class="flex-1 flex flex-col min-w-0 overflow-hidden bg-white dark:bg-zinc-900">
          <div class="flex items-center justify-between border-b border-zinc-200 px-4 py-2 text-xs dark:border-zinc-800 shrink-0 bg-white dark:bg-zinc-900">
            <div class="flex items-center gap-2 min-w-0 mr-3">
              <button
                v-if="isSidebarCollapsed"
                type="button"
                class="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 transition shrink-0"
                title="展开文件清单"
                @click="toggleSidebar"
              >
                <BaseIcon name="expand" size="xs" class="shrink-0" />
              </button>

              <BaseIcon name="file" size="xs" class="text-zinc-400 shrink-0" />
              <span class="font-mono font-medium text-zinc-700 dark:text-zinc-200 truncate" :title="selectedPath">
                {{ selectedPath || '未选择文件' }}
              </span>
              <span v-if="selectedFileItem" class="font-mono text-[10px] text-zinc-400 shrink-0">
                ({{ formatFileSize(selectedFileItem.size) }})
              </span>
            </div>

            <BaseButton
              v-if="selectedContent"
              variant="secondary"
              size="xs"
              class="shrink-0 whitespace-nowrap px-2.5 py-1 text-xs"
              @click="copyFileContent"
            >
              <template #icon>
                <BaseIcon :name="copySuccess ? 'check' : 'copy'" size="xs" class="shrink-0 mr-1" />
              </template>
              <span class="whitespace-nowrap">{{ copySuccess ? '已复制' : '复制内容' }}</span>
            </BaseButton>
          </div>

          <div class="flex-1 min-h-0 overflow-y-auto px-6 py-5">
            <div v-if="contentLoading" class="py-12 text-center text-xs text-zinc-500">
              正在载入文件正文...
            </div>

            <div
              v-else-if="contentError"
              class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/40 dark:text-amber-300"
            >
              <div class="flex items-center gap-2 font-medium">
                <BaseIcon name="alert" size="xs" class="shrink-0" />
                <span>无法预览此文件</span>
              </div>
              <p class="mt-1 text-[11px] leading-relaxed">
                {{ contentError }}
              </p>
            </div>

            <div
              v-else-if="isMarkdown(selectedPath) && selectedContent"
              class="pw-markdown prose prose-sm max-w-none text-zinc-800 dark:prose-invert dark:text-zinc-200"
              @click="handleMarkdownCopyClick"
              v-html="renderMarkdown(selectedContent)"
            />

            <div
              v-else-if="selectedContent"
              class="pw-markdown-code not-prose my-0 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950"
            >
              <div class="pw-markdown-code-header flex items-center justify-between border-b border-zinc-800/80 px-4 py-2 text-[11px] font-mono text-zinc-400">
                <span>{{ selectedPath.split('.').pop() || 'text' }}</span>
                <button
                  type="button"
                  class="pw-markdown-copy rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] text-zinc-300 hover:bg-white/10 hover:text-white transition"
                  @click="copyFileContent"
                >
                  {{ copySuccess ? '已复制' : '复制' }}
                </button>
              </div>
              <pre class="m-0 overflow-x-auto p-4 font-mono text-xs leading-relaxed text-zinc-200"><code>{{ selectedContent }}</code></pre>
            </div>

            <div v-else class="py-12 text-center text-xs text-zinc-400">
              请从左侧选择要查看的文件
            </div>
          </div>
        </div>
      </div>
    </div>
  </BaseDrawer>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { WorkspaceEntry } from '@/types/workspace';
import BaseIcon from '@/components/base/BaseIcon.vue';

const props = defineProps<{
  directoryCache: Map<string, WorkspaceEntry[]>;
  expandedPaths: Set<string>;
  directoryLoading: Map<string, boolean>;
  selectedPath: string;
}>();

const emit = defineEmits<{
  (e: 'toggle', path: string): void;
  (e: 'select', path: string): void;
}>();

const rootEntries = computed(() => {
  return props.directoryCache.get('/workspace') || [];
});

function isExpanded(path: string): boolean {
  return props.expandedPaths.has(path);
}

function isLoading(path: string): boolean {
  return Boolean(props.directoryLoading.get(path));
}

function formatSize(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(entry: WorkspaceEntry): 'file' | 'sparkle' | 'archive' {
  if (entry.is_artifact) return 'sparkle';
  if (entry.mime_type?.includes('zip') || entry.name.endsWith('.zip')) return 'archive';
  return 'file';
}
</script>

<template>
  <div class="space-y-0.5 text-xs text-gray-700 select-none dark:text-dark-200">
    <div
      v-if="rootEntries.length === 0 && !isLoading('/workspace')"
      class="py-6 text-center text-gray-400 dark:text-dark-400"
    >
      工作区暂无文件
    </div>

    <!-- 递归列表或层级项渲染 -->
    <template
      v-for="item in rootEntries"
      :key="item.path"
    >
      <!-- 目录项 -->
      <div v-if="item.type === 'directory'">
        <button
          type="button"
          class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left font-medium transition-colors hover:bg-gray-100 dark:hover:bg-dark-800"
          :class="isExpanded(item.path) ? 'text-gray-900 dark:text-white' : 'text-gray-600 dark:text-dark-300'"
          :title="item.path"
          @click="emit('toggle', item.path)"
        >
          <BaseIcon
            :name="isExpanded(item.path) ? 'chevron-down' : 'chevron-right'"
            class="h-3 w-3 shrink-0 text-gray-400 dark:text-dark-400"
          />
          <BaseIcon
            name="folder"
            class="h-3.5 w-3.5 shrink-0 text-amber-500"
          />
          <span class="truncate" :title="item.name">{{ item.name }}</span>
          <span
            v-if="isLoading(item.path)"
            class="ml-auto text-[10px] text-gray-400"
          >
            加载中...
          </span>
        </button>

        <!-- 展开的二级目录内容 -->
        <div
          v-if="isExpanded(item.path)"
          class="ml-4 border-l border-gray-200 pl-2 space-y-0.5 dark:border-dark-800"
        >
          <div
            v-if="(props.directoryCache.get(item.path) || []).length === 0 && !isLoading(item.path)"
            class="py-1 text-gray-400 dark:text-dark-400"
          >
            空目录
          </div>
          <template
            v-for="sub in props.directoryCache.get(item.path) || []"
            :key="sub.path"
          >
            <!-- 二级目录 -->
            <div v-if="sub.type === 'directory'">
              <button
                type="button"
                class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-gray-100 dark:hover:bg-dark-800"
                :title="sub.path"
                @click="emit('toggle', sub.path)"
              >
                <BaseIcon
                  :name="isExpanded(sub.path) ? 'chevron-down' : 'chevron-right'"
                  class="h-3 w-3 shrink-0 text-gray-400"
                />
                <BaseIcon
                  name="folder"
                  class="h-3.5 w-3.5 shrink-0 text-amber-500"
                />
                <span class="truncate" :title="sub.name">{{ sub.name }}</span>
              </button>

              <!-- 三级内容 -->
              <div
                v-if="isExpanded(sub.path)"
                class="ml-4 border-l border-gray-200 pl-2 space-y-0.5 dark:border-dark-800"
              >
                <button
                  v-for="leaf in props.directoryCache.get(sub.path) || []"
                  :key="leaf.path"
                  type="button"
                  class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left transition-colors"
                  :class="
                    props.selectedPath === leaf.path
                      ? 'bg-primary-50 text-primary-700 font-medium dark:bg-primary-950/40 dark:text-primary-300'
                      : 'hover:bg-gray-100 dark:hover:bg-dark-800'
                  "
                  :title="leaf.path"
                  @click="emit('select', leaf.path)"
                >
                  <BaseIcon
                    :name="getFileIcon(leaf)"
                    class="h-3.5 w-3.5 shrink-0"
                    :class="leaf.is_artifact ? 'text-purple-500' : 'text-gray-400'"
                  />
                  <span class="truncate" :title="leaf.name">{{ leaf.name }}</span>
                  <span
                    v-if="leaf.size_bytes"
                    class="ml-auto text-[10px] opacity-60"
                  >
                    {{ formatSize(leaf.size_bytes) }}
                  </span>
                </button>
              </div>
            </div>

            <!-- 二级文件 -->
            <button
              v-else
              type="button"
              class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left transition-colors"
              :class="
                props.selectedPath === sub.path
                  ? 'bg-primary-50 text-primary-700 font-medium dark:bg-primary-950/40 dark:text-primary-300'
                  : 'hover:bg-gray-100 dark:hover:bg-dark-800'
              "
              :title="sub.path"
              @click="emit('select', sub.path)"
            >
              <BaseIcon
                :name="getFileIcon(sub)"
                class="h-3.5 w-3.5 shrink-0"
                :class="sub.is_artifact ? 'text-purple-500' : 'text-gray-400'"
              />
              <span class="truncate" :title="sub.name">{{ sub.name }}</span>
              <span
                v-if="sub.size_bytes"
                class="ml-auto text-[10px] opacity-60"
              >
                {{ formatSize(sub.size_bytes) }}
              </span>
            </button>
          </template>
        </div>
      </div>

      <!-- 根级直接文件 -->
      <button
        v-else
        type="button"
        class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left transition-colors"
        :class="
          props.selectedPath === item.path
            ? 'bg-primary-50 text-primary-700 font-medium dark:bg-primary-950/40 dark:text-primary-300'
            : 'hover:bg-gray-100 dark:hover:bg-dark-800'
        "
        :title="item.path"
        @click="emit('select', item.path)"
      >
        <BaseIcon
          :name="getFileIcon(item)"
          class="h-3.5 w-3.5 shrink-0"
          :class="item.is_artifact ? 'text-purple-500' : 'text-gray-400'"
        />
        <span class="truncate" :title="item.name">{{ item.name }}</span>
        <span
          v-if="item.size_bytes"
          class="ml-auto text-[10px] opacity-60"
        >
          {{ formatSize(item.size_bytes) }}
        </span>
      </button>
    </template>
  </div>
</template>

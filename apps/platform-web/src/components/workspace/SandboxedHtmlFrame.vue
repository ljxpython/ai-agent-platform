<script setup lang="ts">
import { ref } from 'vue';
import BaseIcon from '@/components/base/BaseIcon.vue';

const props = defineProps<{
  html: string;
  title?: string;
}>();

const isFullScreen = ref(false);

function toggleFullScreen() {
  isFullScreen.value = !isFullScreen.value;
}
</script>

<template>
  <div
    class="flex flex-col border border-gray-200 bg-white dark:border-dark-800 dark:bg-dark-900"
    :class="
      isFullScreen
        ? 'fixed inset-4 z-50 rounded-2xl shadow-2xl'
        : 'h-full w-full rounded-xl'
    "
  >
    <!-- 顶部安全控制条 -->
    <div
      class="flex h-10 shrink-0 items-center justify-between border-b border-gray-200 bg-gray-50/80 px-3 dark:border-dark-800 dark:bg-dark-950/60"
    >
      <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-dark-300">
        <BaseIcon
          name="shield"
          class="h-3.5 w-3.5 text-primary-500"
        />
        <span class="font-medium text-gray-700 dark:text-dark-100">
          {{ title || 'HTML 安全沙箱预览' }}
        </span>
        <span class="rounded bg-gray-200/60 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-dark-800 dark:text-dark-400">
          禁用脚本与外链
        </span>
      </div>

      <div class="flex items-center gap-1">
        <button
          type="button"
          class="rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-200"
          :title="isFullScreen ? '退出全屏' : '全屏展示'"
          @click="toggleFullScreen"
        >
          <BaseIcon
            :name="isFullScreen ? 'collapse' : 'maximize'"
            class="h-3.5 w-3.5"
          />
        </button>
      </div>
    </div>

    <!-- 沙箱 iframe -->
    <div class="relative min-h-0 flex-1 bg-white">
      <iframe
        :srcdoc="props.html"
        sandbox=""
        referrerpolicy="no-referrer"
        class="h-full w-full border-0 bg-white"
        :title="title || 'Sandboxed Preview'"
      />
    </div>
  </div>
</template>

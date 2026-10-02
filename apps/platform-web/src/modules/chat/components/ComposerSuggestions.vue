<script setup lang="ts">
import BaseIcon from "@/components/base/BaseIcon.vue";
import ConfettiButton from "@/components/base/ConfettiButton.vue";

defineProps<{
  disabled?: boolean;
}>();

const emit = defineEmits<{
  select: [prompt: string];
}>();

interface SuggestionItem {
  key: string;
  label: string;
  prompt: string;
  icon?: string;
  isSurprise?: boolean;
}

const suggestions: SuggestionItem[] = [
  {
    key: "surprise",
    label: "小惊喜",
    prompt: "给我一个小惊喜吧",
    icon: "sparkle",
    isSurprise: true,
  },
  {
    key: "write",
    label: "深度写作",
    prompt: "撰写一篇关于[主题]的深度技术博客，包含架构设计与实操建议",
    icon: "pencil",
  },
  {
    key: "research",
    label: "敏捷调研",
    prompt: "深入调研一下[主题]，总结核心技术方案、优劣势对比与关键结论",
    icon: "search",
  },
  {
    key: "data",
    label: "数据洞察",
    prompt: "分析以下数据并绘制直观图表：",
    icon: "table",
  },
  {
    key: "web",
    label: "交互单页",
    prompt: "设计并生成一个零依赖单文件的高保真现代交互网页：",
    icon: "palette",
  },
];

function handleSelect(prompt: string) {
  emit("select", prompt);
}
</script>

<template>
  <div
    class="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1 px-0.5 select-none"
    role="toolbar"
    aria-label="灵感建议"
  >
    <template v-for="item in suggestions" :key="item.key">
      <!-- 带有撒花物理动效的小惊喜胶囊按钮 -->
      <ConfettiButton
        v-if="item.isSurprise"
        :disabled="disabled"
        class="group inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-300/80 bg-gradient-to-r from-amber-500/10 via-rose-500/10 to-purple-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-800 shadow-2xs hover:border-amber-400 hover:from-amber-500/20 hover:to-purple-500/20 active:scale-95 transition-all dark:border-amber-500/40 dark:text-amber-200 dark:hover:border-amber-400 cursor-pointer"
        :title="'点击触发五彩撒花，并填入：' + item.prompt"
        @click="handleSelect(item.prompt)"
      >
        <span class="text-amber-500 dark:text-amber-300 animate-pulse">
          <BaseIcon name="sparkle" size="xs" />
        </span>
        <span>{{ item.label }}</span>
      </ConfettiButton>

      <!-- 普通灵感建议胶囊 -->
      <button
        v-else
        type="button"
        :disabled="disabled"
        class="inline-flex shrink-0 items-center gap-1 rounded-full border border-gray-200/80 bg-white/80 px-2.5 py-0.5 text-[11px] font-normal text-gray-600 shadow-2xs hover:border-primary-400 hover:bg-white hover:text-primary-600 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed transition-all dark:border-dark-700/80 dark:bg-dark-800/80 dark:text-dark-300 dark:hover:border-primary-500 dark:hover:text-primary-400 cursor-pointer"
        :title="'填入：' + item.prompt"
        @click="handleSelect(item.prompt)"
      >
        <BaseIcon
          v-if="item.icon"
          :name="item.icon as any"
          size="xs"
          class="text-gray-400 dark:text-dark-400 group-hover:text-primary-500"
        />
        <span>{{ item.label }}</span>
      </button>
    </template>
  </div>
</template>

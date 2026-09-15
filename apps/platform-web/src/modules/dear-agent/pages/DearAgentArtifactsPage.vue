<script setup lang="ts">
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import BaseIcon from "@/components/base/BaseIcon.vue";

const { activeProject } = useWorkspaceProjectContext();
</script>

<template>
  <div class="h-full overflow-y-auto p-6 md:p-8">
    <div class="mx-auto max-w-5xl space-y-6">
      <div class="flex items-center justify-between border-b border-zinc-200/80 pb-4 dark:border-zinc-800">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-950/50 dark:text-primary-400">
              <BaseIcon name="folder" size="sm" />
            </span>
            <h1 class="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              任务成果与产物
            </h1>
          </div>
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            管理由 Dear Agent 在项目 {{ activeProject?.name }} 中生成的报告、图表与文件产物
          </p>
        </div>
      </div>

      <div class="rounded-2xl border border-dashed border-zinc-300 p-12 text-center dark:border-zinc-700">
        <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500">
          <BaseIcon name="folder" size="md" />
        </div>
        <h3 class="mt-4 text-sm font-medium text-zinc-900 dark:text-zinc-100">暂无离线产物</h3>
        <p class="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          当 Dear Agent 执行生成代码、文档或分析图表时，已发布的正式交付物将自动归档于此处。
        </p>
      </div>
    </div>
  </div>
</template>

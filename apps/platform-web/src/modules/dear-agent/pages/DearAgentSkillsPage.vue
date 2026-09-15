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
              <BaseIcon name="sparkle" size="sm" />
            </span>
            <h1 class="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              Skills 技能管理
            </h1>
          </div>
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            项目 {{ activeProject?.name }} 的 Dear Agent 已加载技能与工具扩展
          </p>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400">
                <BaseIcon name="folder" size="xs" />
              </div>
              <div>
                <h3 class="text-sm font-medium text-zinc-900 dark:text-zinc-100">工作区工作流</h3>
                <span class="text-[11px] text-zinc-500">内置文件读写与执行</span>
              </div>
            </div>
            <span class="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400">已就绪</span>
          </div>
          <p class="mt-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
            支持基于沙箱的目录浏览、文件读取、批量搜索与安全沙箱执行。
          </p>
        </div>

        <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
                <BaseIcon name="info" size="xs" />
              </div>
              <div>
                <h3 class="text-sm font-medium text-zinc-900 dark:text-zinc-100">HITL 澄清中断</h3>
                <span class="text-[11px] text-zinc-500">动态表单与确认机制</span>
              </div>
            </div>
            <span class="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400">已就绪</span>
          </div>
          <p class="mt-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
            在任务不清晰或需要关键参数确认时主动发起表单交互，回答后自动恢复执行。
          </p>
        </div>

        <div class="rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-50 text-purple-600 dark:bg-purple-950/40 dark:text-purple-400">
                <BaseIcon name="shield" size="xs" />
              </div>
              <div>
                <h3 class="text-sm font-medium text-zinc-900 dark:text-zinc-100">敏感动作审批</h3>
                <span class="text-[11px] text-zinc-500">写入与执行前复核</span>
              </div>
            </div>
            <span class="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400">已就绪</span>
          </div>
          <p class="mt-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
            敏感文件覆写、产物交付前向用户发出审批请求，保障生产环境安全。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useWorkspaceStore } from '@/stores/workspace'

const { t } = useI18n()
const workspaceStore = useWorkspaceStore()
</script>

<template>
  <label class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-soft dark:border-dark-700 dark:bg-dark-900">
    <BaseIcon
      name="project"
      size="sm"
      class="text-slate-400 dark:text-dark-400"
    />
    <span class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-dark-400">
      {{ t('common.project') }}
    </span>
    <select
      class="bg-transparent pr-1 text-sm font-medium text-slate-800 outline-none dark:text-slate-100"
      :value="workspaceStore.currentProjectId"
      @change="workspaceStore.setProjectId(($event.target as HTMLSelectElement).value)"
    >
      <option
        v-for="project in workspaceStore.projects"
        :key="project.id"
        :value="project.id"
      >
        {{ project.name }}
      </option>
    </select>
  </label>
</template>

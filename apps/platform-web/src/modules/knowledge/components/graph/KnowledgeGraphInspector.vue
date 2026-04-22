<script setup lang="ts">
import type {
  KnowledgeGraphEdgeSummary,
  KnowledgeGraphNodeSummary,
  KnowledgeGraphRelationSummary,
} from '@/modules/knowledge/utils/knowledge-graph-types'

defineProps<{
  selectedNode: KnowledgeGraphNodeSummary | null
  selectedEdge: KnowledgeGraphEdgeSummary | null
  selectedNodeRelations: KnowledgeGraphRelationSummary[]
}>()

const emit = defineEmits<{
  (event: 'focus-node', nodeId: string): void
  (event: 'expand-node'): void
  (event: 'prune-node'): void
  (event: 'delete-node'): void
  (event: 'delete-edge'): void
  (event: 'clear-selection'): void
  (event: 'edit-node-property', propertyName: string): void
  (event: 'edit-edge-property', propertyName: string): void
}>()

const EDITABLE_NODE_KEYS = new Set(['description', 'entity_id', 'entity_type'])
const EDITABLE_EDGE_KEYS = new Set(['description', 'keywords'])
</script>

<template>
  <div class="w-[19rem] overflow-hidden rounded-xl border border-gray-200 bg-white/96 shadow-xl backdrop-blur-md dark:border-dark-700 dark:bg-dark-900/95">
    <div class="flex items-center justify-between gap-3 border-b border-gray-200/80 px-3 py-2 dark:border-dark-700">
      <div class="text-xs font-semibold text-gray-800 dark:text-dark-100">
        属性面板
      </div>
      <div class="flex items-center gap-1">
        <button
          v-if="selectedNode"
          type="button"
          class="rounded-md px-2 py-1 text-[11px] text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white"
          @click="emit('expand-node')"
        >
          Expand
        </button>
        <button
          v-if="selectedNode"
          type="button"
          class="rounded-md px-2 py-1 text-[11px] text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white"
          @click="emit('prune-node')"
        >
          Prune
        </button>
        <button
          v-if="selectedNode"
          type="button"
          class="rounded-md px-2 py-1 text-[11px] text-rose-500 transition hover:bg-rose-50 hover:text-rose-700 dark:text-rose-300 dark:hover:bg-rose-950/20 dark:hover:text-rose-200"
          @click="emit('delete-node')"
        >
          Delete
        </button>
        <button
          v-if="selectedEdge"
          type="button"
          class="rounded-md px-2 py-1 text-[11px] text-rose-500 transition hover:bg-rose-50 hover:text-rose-700 dark:text-rose-300 dark:hover:bg-rose-950/20 dark:hover:text-rose-200"
          @click="emit('delete-edge')"
        >
          Delete
        </button>
        <button
          v-if="selectedNode || selectedEdge"
          type="button"
          class="rounded-md px-2 py-1 text-[11px] text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-white"
          @click="emit('clear-selection')"
        >
          Close
        </button>
        <div class="text-[10px] text-gray-400 dark:text-dark-500">
          {{ selectedNode || selectedEdge ? 'selected' : 'idle' }}
        </div>
      </div>
    </div>

    <template v-if="selectedNode">
      <div class="p-3">
        <div class="rounded-xl border border-primary-100 bg-primary-50/70 p-3 dark:border-primary-900/40 dark:bg-primary-950/10">
          <div class="truncate text-base font-semibold text-gray-900 dark:text-white">
            {{ selectedNode.label }}
          </div>
          <div class="mt-1 text-sm text-gray-500 dark:text-dark-400">
            {{ selectedNode.typeLabel }} · degree {{ selectedNode.degree }}
          </div>
        </div>

        <div
          v-if="Object.entries(selectedNode.properties).length"
          class="mt-3 grid gap-2"
        >
          <div
            v-for="[key, value] in Object.entries(selectedNode.properties).slice(0, 8)"
            :key="key"
            class="rounded-lg bg-gray-50 px-3 py-2 dark:bg-dark-800/80"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="text-[11px] uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                {{ key }}
              </div>
              <button
                v-if="EDITABLE_NODE_KEYS.has(key)"
                type="button"
                class="rounded-md px-1.5 py-0.5 text-[10px] text-gray-400 transition hover:bg-white hover:text-primary-700 dark:hover:bg-dark-900 dark:hover:text-primary-300"
                @click="emit('edit-node-property', key)"
              >
                Edit
              </button>
            </div>
            <div class="mt-1 break-words text-sm text-gray-700 dark:text-dark-200">
              {{ typeof value === 'string' ? value : JSON.stringify(value) }}
            </div>
          </div>
        </div>

        <div class="mt-3">
          <div class="mb-2 flex items-center justify-between gap-3">
            <div class="text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              关联关系
            </div>
            <div class="text-xs text-gray-400 dark:text-dark-500">
              {{ selectedNodeRelations.length }}
            </div>
          </div>

          <div
            v-if="selectedNodeRelations.length"
            class="space-y-2"
          >
            <button
              v-for="relation in selectedNodeRelations"
              :key="relation.edgeId"
              type="button"
              class="w-full rounded-lg bg-gray-50 px-3 py-2 text-left transition hover:bg-primary-50 dark:bg-dark-800/80 dark:hover:bg-primary-950/20"
              @click="emit('focus-node', relation.nodeId)"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="truncate text-sm font-medium text-gray-800 dark:text-dark-100">{{ relation.nodeLabel }}</span>
                <span class="rounded-full border border-gray-200 px-2 py-0.5 text-[11px] text-gray-500 dark:border-dark-700 dark:text-dark-400">
                  {{ relation.direction === 'outgoing' ? 'out' : 'in' }}
                </span>
              </div>
              <div class="mt-1 text-xs text-gray-400 dark:text-dark-500">
                {{ relation.label }} · {{ relation.nodeTypeLabel }}
              </div>
            </button>
          </div>
        </div>

        <details class="mt-3 rounded-lg bg-gray-50 px-3 py-3 dark:bg-dark-800/80">
          <summary class="cursor-pointer text-sm font-medium text-gray-700 dark:text-dark-200">
            查看原始节点 JSON
          </summary>
          <pre class="mt-3 overflow-auto rounded-xl bg-gray-950/92 p-4 text-xs leading-6 text-white dark:bg-dark-950">{{ JSON.stringify(selectedNode, null, 2) }}</pre>
        </details>
      </div>
    </template>

    <template v-else-if="selectedEdge">
      <div class="p-3">
        <div class="rounded-xl border border-sky-100 bg-sky-50/70 p-3 dark:border-sky-900/40 dark:bg-sky-950/10">
          <div class="truncate text-base font-semibold text-gray-900 dark:text-white">
            {{ selectedEdge.label }}
          </div>
          <div class="mt-1 text-sm text-gray-500 dark:text-dark-400">
            {{ selectedEdge.source }} → {{ selectedEdge.target }} · weight {{ selectedEdge.weight }}
          </div>
        </div>

        <div
          v-if="Object.entries(selectedEdge.properties).length"
          class="mt-3 grid gap-2"
        >
          <div
            v-for="[key, value] in Object.entries(selectedEdge.properties)"
            :key="key"
            class="rounded-lg bg-gray-50 px-3 py-2 dark:bg-dark-800/80"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="text-[11px] uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                {{ key }}
              </div>
              <button
                v-if="EDITABLE_EDGE_KEYS.has(key)"
                type="button"
                class="rounded-md px-1.5 py-0.5 text-[10px] text-gray-400 transition hover:bg-white hover:text-primary-700 dark:hover:bg-dark-900 dark:hover:text-primary-300"
                @click="emit('edit-edge-property', key)"
              >
                Edit
              </button>
            </div>
            <div class="mt-1 break-words text-sm text-gray-700 dark:text-dark-200">
              {{ typeof value === 'string' ? value : JSON.stringify(value) }}
            </div>
          </div>
        </div>
      </div>
    </template>

    <p
      v-else
      class="p-4 text-sm text-gray-500 dark:text-dark-300"
    >
      点击图中的节点，或使用节点搜索 / 快速定位后，这里会展示属性和关联关系。
    </p>
  </div>
</template>

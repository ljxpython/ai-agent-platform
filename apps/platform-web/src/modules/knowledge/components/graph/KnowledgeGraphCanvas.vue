<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useKnowledgeGraphSigma } from '@/modules/knowledge/composables/useKnowledgeGraphSigma'
import type {
  KnowledgeGraphLayoutMode,
  KnowledgeGraphNodeSummary,
} from '@/modules/knowledge/utils/knowledge-graph-types'
import type {
  KnowledgeSigmaEdgeAttributes,
  KnowledgeSigmaNodeAttributes,
} from '@/modules/knowledge/utils/knowledge-graph-adapter'
import Graph from 'graphology'

const props = defineProps<{
  graph: Graph<KnowledgeSigmaNodeAttributes, KnowledgeSigmaEdgeAttributes> | null
  nodes: KnowledgeGraphNodeSummary[]
  layoutMode: KnowledgeGraphLayoutMode
  selectedNodeId: string
  searchPreviewNodeId: string
  hoveredNodeId: string
  selectedEdgeId: string
  searchQuery: string
  fitViewNonce: number
  zoomInNonce: number
  zoomOutNonce: number
  rotateLeftNonce: number
  rotateRightNonce: number
  focusNodeId: string
  showNodeLabels: boolean
  showEdgeLabels: boolean
  enableNodeDrag: boolean
}>()

const emit = defineEmits<{
  (event: 'select-node', nodeId: string): void
  (event: 'hover-node', nodeId: string): void
  (event: 'leave-node'): void
  (event: 'select-edge', edgeId: string): void
  (event: 'stage-click'): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)

useKnowledgeGraphSigma(containerRef, toRef(props, 'graph'), {
  nodes: toRef(props, 'nodes'),
  layoutMode: toRef(props, 'layoutMode'),
  selectedNodeId: toRef(props, 'selectedNodeId'),
  searchPreviewNodeId: toRef(props, 'searchPreviewNodeId'),
  hoveredNodeId: toRef(props, 'hoveredNodeId'),
  selectedEdgeId: toRef(props, 'selectedEdgeId'),
  searchQuery: toRef(props, 'searchQuery'),
  fitViewNonce: toRef(props, 'fitViewNonce'),
  zoomInNonce: toRef(props, 'zoomInNonce'),
  zoomOutNonce: toRef(props, 'zoomOutNonce'),
  rotateLeftNonce: toRef(props, 'rotateLeftNonce'),
  rotateRightNonce: toRef(props, 'rotateRightNonce'),
  focusNodeId: toRef(props, 'focusNodeId'),
  showNodeLabels: toRef(props, 'showNodeLabels'),
  showEdgeLabels: toRef(props, 'showEdgeLabels'),
  enableNodeDrag: toRef(props, 'enableNodeDrag'),
  onSelectNode: (nodeId) => emit('select-node', nodeId),
  onHoverNode: (nodeId) => emit('hover-node', nodeId),
  onLeaveNode: () => emit('leave-node'),
  onSelectEdge: (edgeId) => emit('select-edge', edgeId),
  onStageClick: () => emit('stage-click'),
})

const hasGraph = computed(() => Boolean(props.graph && props.nodes.length))
</script>

<template>
  <div class="relative h-full w-full overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-dark-800 dark:bg-dark-900/85">
    <div
      ref="containerRef"
      class="absolute inset-0"
      :class="hasGraph ? '' : 'pointer-events-none opacity-0'"
    />
    <div
      v-if="!hasGraph"
      class="absolute inset-0"
    />
  </div>
</template>

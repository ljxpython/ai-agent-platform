<script setup lang="ts">
import { useFullscreen } from '@vueuse/core'
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseDialog from '@/components/base/BaseDialog.vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import ConfirmDialog from '@/components/base/ConfirmDialog.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import { useUiStore } from '@/stores/ui'
import KnowledgeWorkspaceNav from '@/modules/knowledge/components/KnowledgeWorkspaceNav.vue'
import KnowledgeGraphCanvas from '@/modules/knowledge/components/graph/KnowledgeGraphCanvas.vue'
import KnowledgeGraphInspector from '@/modules/knowledge/components/graph/KnowledgeGraphInspector.vue'
import KnowledgeGraphLabelPanel from '@/modules/knowledge/components/graph/KnowledgeGraphLabelPanel.vue'
import KnowledgeGraphLegend from '@/modules/knowledge/components/graph/KnowledgeGraphLegend.vue'
import KnowledgeGraphSearch from '@/modules/knowledge/components/graph/KnowledgeGraphSearch.vue'
import KnowledgeGraphSettings from '@/modules/knowledge/components/graph/KnowledgeGraphSettings.vue'
import { useKnowledgeProjectRoute } from '@/modules/knowledge/composables/useKnowledgeProjectRoute'
import { useKnowledgeGraphData } from '@/modules/knowledge/composables/useKnowledgeGraphData'
import { createKnowledgeGraphSearch } from '@/modules/knowledge/composables/useKnowledgeGraphSearch'
import { useKnowledgeGraphStore } from '@/modules/knowledge/stores/knowledgeGraph'
import { buildKnowledgeGraphAdapterResult } from '@/modules/knowledge/utils/knowledge-graph-adapter'
import type { RawKnowledgeGraphEdge, RawKnowledgeGraphNode } from '@/modules/knowledge/utils/knowledge-graph-types'
import type {
  KnowledgeGraphEdgeSummary,
  KnowledgeGraphNodeSummary,
  KnowledgeGraphRelationSummary,
} from '@/modules/knowledge/utils/knowledge-graph-types'
import {
  checkProjectKnowledgeEntityExists,
  deleteProjectKnowledgeEntity,
  deleteProjectKnowledgeRelation,
  getProjectKnowledgeGraph,
  updateProjectKnowledgeEntity,
  updateProjectKnowledgeRelation,
} from '@/services/knowledge/knowledge.service'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

const { projectId, project } = useKnowledgeProjectRoute()
const authorization = useAuthorization()
const ui = useUiStore()
const canRead = computed(() => authorization.can('project.knowledge.read', projectId.value))

const graphUi = useKnowledgeGraphStore()
const graphData = useKnowledgeGraphData()

const maxDepth = ref(3)
const maxNodes = ref(200)
const graphMutationLoading = ref(false)
const graphMutationLabel = ref('正在处理知识图谱…')
const graphStageRef = ref<HTMLElement | null>(null)
const propertyDialogOpen = ref(false)
const propertyDialogTarget = ref<'node' | 'edge' | ''>('')
const propertyDialogName = ref('')
const propertyDialogValue = ref('')
const propertyDialogAllowMerge = ref(false)
const propertyDialogEntityExists = ref(false)
const propertyDialogEntityExistsChecking = ref(false)
const propertyDialogError = ref('')
const propertyDialogSaving = ref(false)
const pruneDialogOpen = ref(false)
const deleteNodeDialogOpen = ref(false)
const deleteEdgeDialogOpen = ref(false)
const { toggle: toggleFullscreen } = useFullscreen(graphStageRef)

const adaptedGraph = computed(() => buildKnowledgeGraphAdapterResult(graphData.graph.value))
const sigmaGraph = computed(() => adaptedGraph.value.graph)
const graphNodes = computed(() => adaptedGraph.value.nodes)
const graphEdges = computed(() => adaptedGraph.value.edges)
const nodeTypeLegend = computed(() => adaptedGraph.value.legend)

const searchEngine = computed(() => createKnowledgeGraphSearch(graphNodes.value))
const nodeSearchQuery = computed({
  get: () => graphUi.nodeSearchQuery,
  set: (value: string) => {
    graphUi.nodeSearchQuery = value
  },
})

const nodeSearchMatches = computed<KnowledgeGraphNodeSummary[]>(() => {
  const query = graphUi.nodeSearchQuery.trim().toLowerCase()
  if (!query) {
    return graphNodes.value
  }

  const directMatches = new Set(
    graphNodes.value
      .filter((node) => node.searchText.includes(query))
      .map((node) => node.id),
  )

  searchEngine.value.search(query).forEach((result) => {
    directMatches.add(String(result.id))
  })

  return graphNodes.value.filter((node) => directMatches.has(node.id))
})

const quickFocusNodes = computed(() => {
  const source = graphUi.nodeSearchQuery.trim()
    ? nodeSearchMatches.value
    : [...graphNodes.value].sort((left, right) => right.degree - left.degree || left.label.localeCompare(right.label))
  return source.slice(0, 8)
})

const graphStats = computed(() => {
  const nodeCount = graphNodes.value.length
  const edgeCount = graphEdges.value.length
  const isolatedCount = graphNodes.value.filter((node) => node.degree === 0).length
  return {
    nodeCount,
    edgeCount,
    isolatedCount,
    visibleCount: graphUi.nodeSearchQuery.trim() ? nodeSearchMatches.value.length : nodeCount,
  }
})

const selectedNode = computed<KnowledgeGraphNodeSummary | null>(
  () => graphNodes.value.find((item) => item.id === graphUi.selectedNodeId) ?? null,
)

const selectedEdge = computed<KnowledgeGraphEdgeSummary | null>(
  () => graphEdges.value.find((item) => item.id === graphUi.selectedEdgeId) ?? null,
)

const selectedRawNode = computed<RawKnowledgeGraphNode | null>(() => {
  const nodes = Array.isArray(graphData.graph.value?.nodes) ? (graphData.graph.value?.nodes as RawKnowledgeGraphNode[]) : []
  return nodes.find((node) => String(node.id || '') === selectedNode.value?.id) ?? null
})

const selectedNodeRelations = computed<KnowledgeGraphRelationSummary[]>(() => {
  if (!selectedNode.value) {
    return []
  }

  const nodeMap = new Map(graphNodes.value.map((node) => [node.id, node]))
  return graphEdges.value
    .filter((edge) => edge.source === selectedNode.value?.id || edge.target === selectedNode.value?.id)
    .map((edge) => {
      const outgoing = edge.source === selectedNode.value?.id
      const node = nodeMap.get(outgoing ? edge.target : edge.source)
      if (!node) {
        return null
      }
      return {
        edgeId: edge.id,
        label: edge.label || '关联',
        direction: outgoing ? 'outgoing' : 'incoming',
        nodeId: node.id,
        nodeLabel: node.label,
        nodeTypeLabel: node.typeLabel,
      }
    })
    .filter((item): item is KnowledgeGraphRelationSummary => item !== null)
})

async function refreshLabels() {
  await graphData.loadGraphLabels(projectId.value, canRead.value)
}

function resolveRawNodeEntityName(node: RawKnowledgeGraphNode | null, fallback = '') {
  const properties = node && typeof node.properties === 'object' && node.properties ? (node.properties as Record<string, unknown>) : {}
  const candidate = [properties.entity_id, properties.entity_name, properties.name, node?.id, fallback].find(
    (item) => typeof item === 'string' && item.trim(),
  )
  return String(candidate || fallback || '').trim()
}

function resolveEntityNameByNodeId(nodeId: string, fallback = '') {
  const nodes = Array.isArray(graphData.graph.value?.nodes) ? (graphData.graph.value?.nodes as RawKnowledgeGraphNode[]) : []
  const rawNode = nodes.find((node) => String(node.id || '') === nodeId) ?? null
  return resolveRawNodeEntityName(rawNode, fallback)
}

function mergeGraphPayload(
  currentGraph: Record<string, unknown> | null,
  nextGraph: Record<string, unknown> | null,
) {
  const currentNodes = Array.isArray(currentGraph?.nodes) ? (currentGraph.nodes as RawKnowledgeGraphNode[]) : []
  const currentEdges = Array.isArray(currentGraph?.edges) ? (currentGraph.edges as RawKnowledgeGraphEdge[]) : []
  const nextNodes = Array.isArray(nextGraph?.nodes) ? (nextGraph.nodes as RawKnowledgeGraphNode[]) : []
  const nextEdges = Array.isArray(nextGraph?.edges) ? (nextGraph.edges as RawKnowledgeGraphEdge[]) : []

  const nodeMap = new Map<string, RawKnowledgeGraphNode>()
  currentNodes.forEach((node) => {
    nodeMap.set(String(node.id || ''), node)
  })
  nextNodes.forEach((node) => {
    nodeMap.set(String(node.id || ''), node)
  })

  const edgeMap = new Map<string, RawKnowledgeGraphEdge>()
  const resolveEdgeKey = (edge: RawKnowledgeGraphEdge, index: number) =>
    String(edge.id || `${String(edge.source || '')}:${String(edge.target || '')}:${String(edge.type || '')}:${index}`)

  currentEdges.forEach((edge, index) => {
    edgeMap.set(resolveEdgeKey(edge, index), edge)
  })
  nextEdges.forEach((edge, index) => {
    edgeMap.set(resolveEdgeKey(edge, index), edge)
  })

  return {
    ...(currentGraph || {}),
    ...(nextGraph || {}),
    nodes: Array.from(nodeMap.values()),
    edges: Array.from(edgeMap.values()),
  }
}

function pruneNodeLocally(nodeId: string) {
  const currentGraph = graphData.graph.value
  const currentNodes = Array.isArray(currentGraph?.nodes) ? (currentGraph.nodes as RawKnowledgeGraphNode[]) : []
  const currentEdges = Array.isArray(currentGraph?.edges) ? (currentGraph.edges as RawKnowledgeGraphEdge[]) : []
  if (!currentNodes.length) {
    return
  }

  const adjacency = new Map<string, Set<string>>()
  currentNodes.forEach((node) => {
    adjacency.set(String(node.id || ''), new Set())
  })
  currentEdges.forEach((edge) => {
    const source = String(edge.source || '')
    const target = String(edge.target || '')
    adjacency.get(source)?.add(target)
    adjacency.get(target)?.add(source)
  })

  const nodesToDelete = new Set<string>([nodeId])
  for (const node of currentNodes) {
    const id = String(node.id || '')
    if (id === nodeId) {
      continue
    }
    const neighbors = Array.from(adjacency.get(id) || [])
    if (neighbors.length === 1 && neighbors[0] === nodeId) {
      nodesToDelete.add(id)
    }
  }

  if (nodesToDelete.size >= currentNodes.length) {
    ui.pushToast({
      type: 'warning',
      title: '不能删除全部节点',
      message: '当前操作会让整个子图清空，已阻止。',
    })
    return
  }

  graphData.graph.value = {
    ...(currentGraph || {}),
    nodes: currentNodes.filter((node) => !nodesToDelete.has(String(node.id || ''))),
    edges: currentEdges.filter((edge) => {
      const source = String(edge.source || '')
      const target = String(edge.target || '')
      return !nodesToDelete.has(source) && !nodesToDelete.has(target)
    }),
  }
  graphUi.clearSelection()
  ui.pushToast({
    type: 'info',
    title: '节点已裁剪',
    message: nodesToDelete.size > 1 ? `已移除 ${nodesToDelete.size} 个节点。` : '已移除当前节点。',
  })
}

async function openGraph(label: string) {
  const result = await graphData.openGraph(projectId.value, canRead.value, {
    label,
    maxDepth: maxDepth.value,
    maxNodes: maxNodes.value,
  })
  if (!result) {
    graphUi.clearSelection()
    return
  }

  graphUi.clearSelection()
  graphUi.nodeSearchQuery = ''
  graphUi.fitView()
}

async function expandSelectedNode() {
  const label = resolveRawNodeEntityName(selectedRawNode.value, selectedNode.value?.label || '')
  if (!label || !projectId.value || !canRead.value) {
    return
  }

  graphMutationLoading.value = true
  graphMutationLabel.value = '正在扩展当前节点…'
  try {
    const nextGraph = await getProjectKnowledgeGraph(projectId.value, {
      label,
      max_depth: 2,
      max_nodes: 1000,
    })
    graphData.graph.value = mergeGraphPayload(graphData.graph.value, nextGraph)
    graphUi.selectNode(selectedNode.value?.id || label)
    ui.pushToast({
      type: 'success',
      title: '节点已扩展',
      message: `${label} 的邻接子图已并入当前视图。`,
    })
  } catch (error) {
    ui.pushToast({
      type: 'error',
      title: '节点扩展失败',
      message: resolvePlatformHttpErrorMessage(error, '节点扩展失败', '知识图谱'),
    })
  } finally {
    graphMutationLoading.value = false
  }
}

async function refreshCurrentGraph() {
  if (graphData.selectedLabel.value) {
    await openGraph(graphData.selectedLabel.value)
    return
  }

  await refreshLabels()
  if (!graphData.selectedLabel.value) {
    await openGraph('*')
  }
}

function focusNodeFromUi(nodeId: string) {
  graphUi.focusNode(nodeId)
  graphUi.requestCameraFocus(nodeId)
}

function openNodePropertyDialog(propertyName: string) {
  if (!selectedNode.value) {
    return
  }
  propertyDialogTarget.value = 'node'
  propertyDialogName.value = propertyName
  propertyDialogValue.value = String(selectedNode.value.properties[propertyName] ?? '')
  propertyDialogAllowMerge.value = false
  propertyDialogError.value = ''
  propertyDialogOpen.value = true
}

function openEdgePropertyDialog(propertyName: string) {
  if (!selectedEdge.value) {
    return
  }
  propertyDialogTarget.value = 'edge'
  propertyDialogName.value = propertyName
  propertyDialogValue.value = String(selectedEdge.value.properties[propertyName] ?? '')
  propertyDialogAllowMerge.value = false
  propertyDialogError.value = ''
  propertyDialogOpen.value = true
}

function closePropertyDialog() {
  propertyDialogOpen.value = false
  propertyDialogTarget.value = ''
  propertyDialogName.value = ''
  propertyDialogValue.value = ''
  propertyDialogAllowMerge.value = false
  propertyDialogEntityExists.value = false
  propertyDialogEntityExistsChecking.value = false
  propertyDialogError.value = ''
  propertyDialogSaving.value = false
}

function confirmPruneSelectedNode() {
  pruneDialogOpen.value = false
  if (selectedNode.value) {
    pruneNodeLocally(selectedNode.value.id)
  }
}

async function deleteSelectedNodeRemote() {
  if (!projectId.value || !selectedNode.value) {
    deleteNodeDialogOpen.value = false
    return
  }

  deleteNodeDialogOpen.value = false
  graphMutationLoading.value = true
  graphMutationLabel.value = '正在删除实体…'
  const entityName = resolveRawNodeEntityName(selectedRawNode.value, selectedNode.value.label)
  try {
    await deleteProjectKnowledgeEntity(projectId.value, entityName)
    graphUi.clearSelection()
    if (graphData.selectedLabel.value === entityName) {
      await refreshLabels()
      await openGraph('*')
    } else {
      await refreshCurrentGraph()
    }
    ui.pushToast({
      type: 'success',
      title: '实体已删除',
      message: `${entityName} 已从知识图谱中删除。`,
    })
  } catch (error) {
    ui.pushToast({
      type: 'error',
      title: '实体删除失败',
      message: resolvePlatformHttpErrorMessage(error, '实体删除失败', '知识图谱'),
    })
  } finally {
    graphMutationLoading.value = false
  }
}

async function deleteSelectedEdgeRemote() {
  if (!projectId.value || !selectedEdge.value) {
    deleteEdgeDialogOpen.value = false
    return
  }

  deleteEdgeDialogOpen.value = false
  graphMutationLoading.value = true
  graphMutationLabel.value = '正在删除关系…'
  const sourceEntity = resolveEntityNameByNodeId(selectedEdge.value.source, selectedEdge.value.source)
  const targetEntity = resolveEntityNameByNodeId(selectedEdge.value.target, selectedEdge.value.target)
  try {
    await deleteProjectKnowledgeRelation(projectId.value, {
      source_entity: sourceEntity,
      target_entity: targetEntity,
    })
    graphUi.clearSelection()
    await refreshCurrentGraph()
    ui.pushToast({
      type: 'success',
      title: '关系已删除',
      message: `${sourceEntity} → ${targetEntity} 的关系已删除。`,
    })
  } catch (error) {
    ui.pushToast({
      type: 'error',
      title: '关系删除失败',
      message: resolvePlatformHttpErrorMessage(error, '关系删除失败', '知识图谱'),
    })
  } finally {
    graphMutationLoading.value = false
  }
}

async function savePropertyDialog() {
  if (!projectId.value || !propertyDialogTarget.value || !propertyDialogName.value) {
    return
  }

  propertyDialogSaving.value = true
  propertyDialogError.value = ''
  try {
    const dialogTarget = propertyDialogTarget.value
    const propertyName = propertyDialogName.value
    const propertyValue = propertyDialogValue.value.trim()
    const allowMerge = propertyDialogAllowMerge.value

    if (dialogTarget === 'node') {
      const entityName = resolveRawNodeEntityName(selectedRawNode.value, selectedNode.value?.label || '')
      const payload =
        propertyName === 'entity_id'
          ? { entity_name: propertyValue }
          : { [propertyName]: propertyValue }

      const response = await updateProjectKnowledgeEntity(projectId.value, {
        entity_name: entityName,
        updated_data: payload,
        allow_rename: propertyName === 'entity_id',
        allow_merge: propertyName === 'entity_id' ? allowMerge : false,
      })

      const operationSummary =
        response && typeof response === 'object' ? (response.operation_summary as Record<string, unknown> | undefined) : undefined
      const finalEntity =
        operationSummary && typeof operationSummary.final_entity === 'string'
          ? operationSummary.final_entity.trim()
          : ''

      closePropertyDialog()
      if (propertyName === 'entity_id' && finalEntity) {
        await openGraph(finalEntity)
      } else {
        await refreshCurrentGraph()
      }
      ui.pushToast({
        type: 'success',
        title: '节点已更新',
        message:
          operationSummary && operationSummary.merged
            ? `实体已合并到 ${String(operationSummary.final_entity || finalEntity)}。`
            : '节点属性已更新。',
      })
      return
    }

    const sourceEntity = graphNodes.value.find((node) => node.id === selectedEdge.value?.source)
    const targetEntity = graphNodes.value.find((node) => node.id === selectedEdge.value?.target)
    await updateProjectKnowledgeRelation(projectId.value, {
      source_id: resolveEntityNameByNodeId(sourceEntity?.id || '', sourceEntity?.label || selectedEdge.value?.source || ''),
      target_id: resolveEntityNameByNodeId(targetEntity?.id || '', targetEntity?.label || selectedEdge.value?.target || ''),
      updated_data: {
        [propertyName]: propertyValue,
      },
    })

    closePropertyDialog()
    await refreshCurrentGraph()
    ui.pushToast({
      type: 'success',
      title: '关系已更新',
      message: '关系属性已更新。',
    })
  } catch (error) {
    propertyDialogError.value = resolvePlatformHttpErrorMessage(error, '图谱属性更新失败', '知识图谱')
  } finally {
    propertyDialogSaving.value = false
  }
}

watch(
  () => projectId.value,
  async () => {
    graphData.reset()
    graphUi.resetGraphUiState()

    if (!projectId.value) {
      return
    }

    await refreshLabels()
    if (!graphData.selectedLabel.value) {
      await openGraph('*')
    }
  },
  { immediate: true },
)

watch(
  () => [propertyDialogOpen.value, propertyDialogTarget.value, propertyDialogName.value, propertyDialogValue.value, projectId.value] as const,
  ([isOpen, target, propertyName, propertyValue, currentProjectId], _oldValue, onCleanup) => {
    propertyDialogEntityExists.value = false
    propertyDialogEntityExistsChecking.value = false

    if (
      !isOpen ||
      target !== 'node' ||
      propertyName !== 'entity_id' ||
      !currentProjectId ||
      !propertyValue.trim() ||
      propertyValue.trim() === resolveRawNodeEntityName(selectedRawNode.value, selectedNode.value?.label || '')
    ) {
      return
    }

    propertyDialogEntityExistsChecking.value = true
    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        const exists = await checkProjectKnowledgeEntityExists(currentProjectId, propertyValue.trim())
        if (!cancelled) {
          propertyDialogEntityExists.value = exists
        }
      } finally {
        if (!cancelled) {
          propertyDialogEntityExistsChecking.value = false
        }
      }
    }, 260)

    onCleanup(() => {
      cancelled = true
      window.clearTimeout(timer)
    })
  },
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Knowledge"
      :title="project ? `${project.name} · 知识图谱` : '知识图谱'"
      description="知识图谱工作区采用正式图引擎重做：标签切换、搜索、聚焦、属性与图例统一收敛在只读浏览工作台中。"
    />

    <KnowledgeWorkspaceNav
      v-if="projectId"
      :project-id="projectId"
    />

    <StateBanner
      v-if="projectId && !canRead"
      class="mt-4"
      title="当前角色没有知识图谱读取权限"
      description="请联系项目管理员授予 project.knowledge.read 权限后，再浏览当前项目的知识图谱。"
      variant="info"
    />
    <StateBanner
      v-else-if="graphData.error.value"
      class="mt-4"
      title="知识图谱异常"
      :description="graphData.error.value"
      variant="danger"
    />

    <SurfaceCard class="mt-4 overflow-hidden">
      <div
        ref="graphStageRef"
        class="relative h-[78vh] min-h-[740px] max-h-[920px] overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-dark-800 dark:bg-dark-950/85"
      >
        <div class="absolute left-4 top-4 z-30 flex items-center gap-2">
          <span class="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-4 py-1.5 text-sm font-semibold text-gray-900 shadow-sm dark:border-dark-700 dark:bg-dark-900 dark:text-white">
            <BaseIcon
              name="graph"
              size="xs"
            />
            {{ graphData.selectedLabelDisplay.value }}
          </span>
          <span class="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 shadow-sm dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300">
            节点 · {{ graphStats.nodeCount }}
          </span>
          <span class="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 shadow-sm dark:border-dark-700 dark:bg-dark-900 dark:text-dark-300">
            关系 · {{ graphStats.edgeCount }}
          </span>
        </div>

        <div class="absolute left-4 top-16 z-30 space-y-3">
          <KnowledgeGraphLabelPanel
            v-if="graphUi.showLabelPanel"
            :labels="graphData.labels.value"
            :popular-labels="graphData.popularLabels.value"
            :query-input="graphData.queryInput.value"
            :selected-label="graphData.selectedLabel.value"
            :loading-labels="graphData.loadingLabels.value"
            :loading-graph="graphData.loadingGraph.value"
            :can-read="canRead"
            @update:query-input="graphData.queryInput.value = $event"
            @load-labels="void refreshLabels()"
            @refresh-graph="void refreshCurrentGraph()"
            @open-graph="(label) => void openGraph(label)"
          />
        </div>

        <div class="absolute right-4 top-4 z-40">
          <KnowledgeGraphSearch
            :model-value="nodeSearchQuery"
            :matches="nodeSearchMatches"
            :quick-focus-nodes="quickFocusNodes"
            @update:model-value="nodeSearchQuery = $event"
            @preview-node="graphUi.focusNodePreview($event)"
            @clear-preview="graphUi.clearFocusedNode()"
            @focus-node="focusNodeFromUi($event)"
          />
        </div>

        <div class="absolute right-4 top-24 z-30">
          <KnowledgeGraphInspector
            v-if="graphUi.showInspectorPanel"
            :selected-node="selectedNode"
            :selected-edge="selectedEdge"
            :selected-node-relations="selectedNodeRelations"
            @focus-node="focusNodeFromUi($event)"
            @expand-node="void expandSelectedNode()"
            @prune-node="pruneDialogOpen = true"
            @delete-node="deleteNodeDialogOpen = true"
            @delete-edge="deleteEdgeDialogOpen = true"
            @clear-selection="graphUi.clearSelection()"
            @edit-node-property="openNodePropertyDialog($event)"
            @edit-edge-property="openEdgePropertyDialog($event)"
          />
        </div>

        <div class="absolute bottom-4 right-4 z-20">
          <KnowledgeGraphLegend
            v-if="graphUi.showLegend"
            :items="nodeTypeLegend"
          />
        </div>

        <div class="absolute bottom-4 left-4 z-30 flex flex-col gap-2">
          <div class="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white/96 p-2 shadow-lg backdrop-blur-md dark:border-dark-700 dark:bg-dark-900/95">
            <div class="flex items-center gap-1 rounded-lg border border-gray-200/80 bg-gray-50/80 p-0.5 dark:border-dark-700 dark:bg-dark-800/70">
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md text-gray-600 transition hover:bg-white hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.zoomOut()"
              >
                <BaseIcon
                  name="zoom-out"
                  size="xs"
                />
              </button>
              <div class="h-4 w-px bg-gray-200 dark:bg-dark-700" />
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md text-gray-600 transition hover:bg-white hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.fitView()"
              >
                <BaseIcon
                  name="maximize"
                  size="xs"
                />
              </button>
              <div class="h-4 w-px bg-gray-200 dark:bg-dark-700" />
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md text-gray-600 transition hover:bg-white hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.zoomIn()"
              >
                <BaseIcon
                  name="zoom-in"
                  size="xs"
                />
              </button>
            </div>

            <div class="flex items-center gap-1 rounded-lg border border-gray-200/80 bg-gray-50/80 p-0.5 dark:border-dark-700 dark:bg-dark-800/70">
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md text-gray-600 transition hover:bg-white hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.rotateLeft()"
              >
                <BaseIcon
                  name="rotate-ccw"
                  size="xs"
                />
              </button>
              <div class="h-4 w-px bg-gray-200 dark:bg-dark-700" />
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md text-gray-600 transition hover:bg-white hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.rotateRight()"
              >
                <BaseIcon
                  name="rotate-cw"
                  size="xs"
                />
              </button>
              <div class="h-4 w-px bg-gray-200 dark:bg-dark-700" />
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md text-gray-600 transition hover:bg-white hover:text-gray-900 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.fitView()"
              >
                <BaseIcon
                  name="focus"
                  size="xs"
                />
              </button>
            </div>

            <div class="flex items-center gap-1">
              <button
                type="button"
                class="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs font-medium transition hover:border-primary-300 hover:bg-primary-50 dark:border-dark-700 dark:bg-dark-900 dark:hover:border-primary-700 dark:hover:bg-primary-950/20"
                :class="graphUi.layoutMode === 'circular' ? 'border-primary-300 bg-primary-50 text-primary-700 dark:border-primary-700 dark:bg-primary-950/20 dark:text-primary-200' : 'text-gray-700 dark:text-dark-200'"
                @click="graphUi.layoutMode = 'circular'"
              >
                <BaseIcon
                  name="graph"
                  size="xs"
                />
                环形
              </button>
            </div>

            <div class="flex items-center gap-1">
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md border border-gray-200/80 bg-gray-50/80 text-gray-600 transition hover:bg-white hover:text-gray-900 dark:border-dark-700 dark:bg-dark-800/70 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.showLegend = !graphUi.showLegend"
              >
                <BaseIcon
                  name="palette"
                  size="xs"
                />
              </button>
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md border border-gray-200/80 bg-gray-50/80 text-gray-600 transition hover:bg-white hover:text-gray-900 dark:border-dark-700 dark:bg-dark-800/70 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="toggleFullscreen"
              >
                <BaseIcon
                  name="expand"
                  size="xs"
                />
              </button>
              <button
                type="button"
                class="flex h-7 w-7 items-center justify-center rounded-md border border-gray-200/80 bg-gray-50/80 text-gray-600 transition hover:bg-white hover:text-gray-900 dark:border-dark-700 dark:bg-dark-800/70 dark:text-dark-300 dark:hover:bg-dark-900 dark:hover:text-white"
                @click="graphUi.showSettingsPanel = !graphUi.showSettingsPanel"
              >
                <BaseIcon
                  name="settings-2"
                  size="xs"
                />
              </button>
            </div>
          </div>

          <KnowledgeGraphSettings
            v-if="graphUi.showSettingsPanel"
            :max-depth="maxDepth"
            :max-nodes="maxNodes"
            :layout-mode="graphUi.layoutMode"
            :show-node-labels="graphUi.showNodeLabels"
            :show-edge-labels="graphUi.showEdgeLabels"
            :enable-node-drag="graphUi.enableNodeDrag"
            @update:max-depth="maxDepth = $event"
            @update:max-nodes="maxNodes = $event"
            @update:layout-mode="graphUi.layoutMode = $event"
            @update:show-node-labels="graphUi.showNodeLabels = $event"
            @update:show-edge-labels="graphUi.showEdgeLabels = $event"
            @update:enable-node-drag="graphUi.enableNodeDrag = $event"
          />
        </div>

        <div class="absolute inset-0 px-2 py-2">
          <div class="h-full w-full rounded-2xl border border-gray-100 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.04),_rgba(255,255,255,0)_50%)] dark:border-dark-900 dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08),_rgba(2,6,23,0)_45%)]">
            <template v-if="graphStats.nodeCount">
              <KnowledgeGraphCanvas
                :graph="sigmaGraph"
                :nodes="graphNodes"
                :layout-mode="graphUi.layoutMode"
                :selected-node-id="graphUi.selectedNodeId"
                :search-preview-node-id="graphUi.searchPreviewNodeId"
                :hovered-node-id="graphUi.hoveredNodeId"
                :selected-edge-id="graphUi.selectedEdgeId"
                :search-query="graphUi.nodeSearchQuery"
                :fit-view-nonce="graphUi.fitViewNonce"
                :zoom-in-nonce="graphUi.zoomInNonce"
                :zoom-out-nonce="graphUi.zoomOutNonce"
                :rotate-left-nonce="graphUi.rotateLeftNonce"
                :rotate-right-nonce="graphUi.rotateRightNonce"
                :focus-node-id="graphUi.focusNodeId"
                :show-node-labels="graphUi.showNodeLabels"
                :show-edge-labels="graphUi.showEdgeLabels"
                :enable-node-drag="graphUi.enableNodeDrag"
                @select-node="graphUi.selectNode($event)"
                @hover-node="graphUi.hoverNode($event)"
                @leave-node="graphUi.clearHoverNode()"
                @select-edge="graphUi.selectEdge($event)"
                @stage-click="graphUi.clearSelection()"
              />
            </template>
            <div
              v-else
              class="relative z-[1] flex h-full items-center justify-center"
            >
              <EmptyState
                title="当前标签下暂无可展示子图"
                description="可以切换到其他标签，或者提高 max_nodes / max_depth 后重新拉取。"
                icon="graph"
              />
            </div>
          </div>
        </div>

        <div
          v-if="graphData.loadingGraph.value || graphMutationLoading"
          class="absolute inset-0 z-30 flex items-center justify-center bg-white/65 backdrop-blur dark:bg-dark-950/70"
        >
          <div class="rounded-2xl border border-gray-200 bg-white px-5 py-4 text-sm text-gray-600 shadow-lg dark:border-dark-700 dark:bg-dark-950 dark:text-dark-200">
            {{ graphMutationLoading ? graphMutationLabel : '正在刷新知识图谱…' }}
          </div>
        </div>
      </div>
    </SurfaceCard>

    <BaseDialog
      :show="propertyDialogOpen"
      :title="propertyDialogTarget === 'node' ? '编辑节点属性' : '编辑关系属性'"
      width="narrow"
      @close="closePropertyDialog"
    >
      <div class="space-y-4">
        <StateBanner
          v-if="propertyDialogError"
          title="属性更新失败"
          :description="propertyDialogError"
          variant="danger"
        />

        <div class="pw-panel-muted px-4 py-4">
          <div class="text-xs uppercase tracking-[0.18em] text-gray-400 dark:text-dark-500">
            Property
          </div>
          <div class="mt-2 text-sm font-medium text-gray-800 dark:text-dark-100">
            {{ propertyDialogName }}
          </div>
        </div>

        <label class="flex flex-col gap-2">
          <span class="pw-input-label">Value</span>
          <textarea
            v-model="propertyDialogValue"
            class="pw-input min-h-[140px] resize-y"
          />
        </label>

        <label
          v-if="propertyDialogTarget === 'node' && propertyDialogName === 'entity_id'"
          class="flex items-start gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700 dark:border-dark-700 dark:bg-dark-900/70 dark:text-dark-200"
        >
          <input
            v-model="propertyDialogAllowMerge"
            type="checkbox"
            class="mt-0.5"
          >
          <span>如果新名称已存在，允许自动 merge 到已有实体。</span>
        </label>

        <div
          v-if="propertyDialogTarget === 'node' && propertyDialogName === 'entity_id' && propertyDialogValue.trim()"
          class="rounded-xl border px-4 py-3 text-sm"
          :class="
            propertyDialogEntityExists
              ? 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/30 dark:bg-amber-950/20 dark:text-amber-100'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/30 dark:bg-emerald-950/20 dark:text-emerald-100'
          "
        >
          <template v-if="propertyDialogEntityExistsChecking">
            正在检查目标实体是否已存在…
          </template>
          <template v-else-if="propertyDialogEntityExists">
            已存在同名实体。勾选上面的 merge 选项后，保存将尝试自动合并。
          </template>
          <template v-else>
            当前名称在图谱中不存在，将作为普通重命名处理。
          </template>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center gap-3">
          <BaseButton
            variant="secondary"
            :disabled="propertyDialogSaving"
            @click="closePropertyDialog"
          >
            取消
          </BaseButton>
          <BaseButton
            :disabled="propertyDialogSaving || !propertyDialogValue.trim()"
            @click="void savePropertyDialog()"
          >
            {{ propertyDialogSaving ? '保存中…' : '保存' }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <ConfirmDialog
      :show="pruneDialogOpen"
      title="裁剪当前节点"
      message="这会从当前子图里移除选中节点，并顺带清除只依赖该节点的孤立叶子节点。该操作只影响当前前端视图。"
      confirm-text="确认裁剪"
      @cancel="pruneDialogOpen = false"
      @confirm="confirmPruneSelectedNode"
    />

    <ConfirmDialog
      :show="deleteNodeDialogOpen"
      title="删除当前实体"
      :message="selectedNode ? `确认删除实体 ${selectedNode.label} 吗？这会删除该实体及其关系。` : '确认删除当前实体吗？'"
      confirm-text="确认删除"
      danger
      @cancel="deleteNodeDialogOpen = false"
      @confirm="void deleteSelectedNodeRemote()"
    />

    <ConfirmDialog
      :show="deleteEdgeDialogOpen"
      title="删除当前关系"
      :message="selectedEdge ? `确认删除关系 ${selectedEdge.source} → ${selectedEdge.target} 吗？` : '确认删除当前关系吗？'"
      confirm-text="确认删除"
      danger
      @cancel="deleteEdgeDialogOpen = false"
      @confirm="void deleteSelectedEdgeRemote()"
    />
  </section>
</template>

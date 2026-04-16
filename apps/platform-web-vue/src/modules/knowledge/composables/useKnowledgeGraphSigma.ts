import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'
import Sigma from 'sigma'
import forceAtlas2 from 'graphology-layout-forceatlas2'
import noverlap from 'graphology-layout-noverlap'
import type { Settings } from 'sigma/settings'
import type { CameraState, Coordinates, SigmaStageEventPayload } from 'sigma/types'
import Graph from 'graphology'
import type {
  KnowledgeGraphLayoutMode,
  KnowledgeGraphNodeSummary,
} from '@/modules/knowledge/utils/knowledge-graph-types'
import type {
  KnowledgeSigmaEdgeAttributes,
  KnowledgeSigmaNodeAttributes,
} from '@/modules/knowledge/utils/knowledge-graph-adapter'

type SigmaGraph = Graph<KnowledgeSigmaNodeAttributes, KnowledgeSigmaEdgeAttributes>

function buildSigmaSettings(): Partial<Settings<KnowledgeSigmaNodeAttributes, KnowledgeSigmaEdgeAttributes>> {
  return {
    renderLabels: true,
    renderEdgeLabels: false,
    enableEdgeEvents: true,
    labelDensity: 0.08,
    labelGridCellSize: 100,
    labelRenderedSizeThreshold: 10,
    defaultEdgeColor: '#94a3b8',
    defaultNodeColor: '#3b82f6',
    allowInvalidContainer: true,
    zIndex: true,
  }
}

function applyLayout(graph: SigmaGraph, layoutMode: KnowledgeGraphLayoutMode) {
  if (graph.order === 0) {
    return
  }

  if (layoutMode === 'circular') {
    let index = 0
    const angleStep = (Math.PI * 2) / graph.order
    const radius = Math.max(12, graph.order / 14)
    graph.forEachNode((node) => {
      graph.mergeNodeAttributes(node, {
        x: Math.cos(index * angleStep) * radius,
        y: Math.sin(index * angleStep) * radius,
      })
      index += 1
    })
    noverlap.assign(graph, {
      maxIterations: 120,
      settings: {
        margin: 6,
        ratio: 1.1,
      },
    })
    return
  }

  forceAtlas2.assign(graph, {
    iterations: Math.max(80, Math.min(220, graph.order * 2)),
    settings: {
      gravity: 1,
      scalingRatio: 18,
      slowDown: 8,
      barnesHutOptimize: graph.order > 200,
      strongGravityMode: false,
    },
  })

  noverlap.assign(graph, {
    maxIterations: 120,
    settings: {
      margin: 6,
      ratio: 1.2,
      speed: 3,
    },
  })
}

function computeVisibleState(
  graph: SigmaGraph,
  nodes: KnowledgeGraphNodeSummary[],
  _searchQuery: string,
  selectedNodeId: string,
  searchPreviewNodeId: string,
  hoveredNodeId: string,
  selectedEdgeId: string,
) {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]))
  const activeNodeId = searchPreviewNodeId || hoveredNodeId || selectedNodeId || ''
  const neighborIds = new Set<string>()

  if (activeNodeId && graph.hasNode(activeNodeId)) {
    graph.forEachNeighbor(activeNodeId, (neighbor) => {
      neighborIds.add(String(neighbor))
    })
  }

  graph.forEachNode((nodeId) => {
    const attributes = graph.getNodeAttributes(nodeId)
    const isSelected = selectedNodeId === nodeId
    const isPreview = searchPreviewNodeId === nodeId
    const isHovered = hoveredNodeId === nodeId
    const isNeighbor = neighborIds.has(nodeId)
    const isActive = isSelected || isPreview || isHovered
    const faded = activeNodeId ? !(isActive || isNeighbor) : false

    graph.mergeNodeAttributes(nodeId, {
      hidden: false,
      highlighted: isActive,
      forceLabel: isActive || isNeighbor,
      color: nodeMap.get(nodeId)?.color ?? attributes.color,
      size: isSelected ? attributes.size + 2 : (nodeMap.get(nodeId)?.size ?? attributes.size),
      zIndex: isActive ? 2 : isNeighbor ? 1 : 0,
    })
    graph.setNodeAttribute(nodeId, 'forceLabel', Boolean(isActive || isNeighbor))
    graph.setNodeAttribute(nodeId, 'highlighted', Boolean(isActive))
    graph.setNodeAttribute(nodeId, 'hidden', false)
    graph.setNodeAttribute(nodeId, 'color', nodeMap.get(nodeId)?.color ?? attributes.color)

    if (faded) {
      graph.setNodeAttribute(nodeId, 'size', Math.max(4, (nodeMap.get(nodeId)?.size ?? attributes.size) - 1))
    }
  })

  graph.forEachEdge((edgeId, _attributes, source, target) => {
    const connectsActiveNode = activeNodeId ? source === activeNodeId || target === activeNodeId : false
    const isSelectedEdge = selectedEdgeId === edgeId
    const faded = activeNodeId ? !(connectsActiveNode || isSelectedEdge) : false
    graph.mergeEdgeAttributes(edgeId, {
      hidden: false,
      color: isSelectedEdge ? '#1d4ed8' : connectsActiveNode ? '#2563eb' : faded ? '#cbd5e1' : '#94a3b8',
      size: isSelectedEdge ? 3.4 : connectsActiveNode ? 2.4 : faded ? 1.1 : 1.8,
    })
  })
}

function animateCameraToNode(
  sigma: Sigma<KnowledgeSigmaNodeAttributes, KnowledgeSigmaEdgeAttributes>,
  graph: SigmaGraph,
  nodeId: string,
) {
  if (!graph.hasNode(nodeId)) {
    return
  }

  sigma.setCustomBBox(null)
  const displayData = sigma.getNodeDisplayData(nodeId)
  const fallback = graph.getNodeAttributes(nodeId)
  const x = displayData?.x ?? fallback.x
  const y = displayData?.y ?? fallback.y
  const currentRatio = sigma.getCamera().ratio
  const targetRatio = currentRatio < 0.6 ? currentRatio : 0.6

  sigma.getCamera().animate(
    {
      x,
      y,
      ratio: targetRatio,
      angle: 0,
    } satisfies Partial<CameraState>,
    { duration: 260 },
  )
}

export function useKnowledgeGraphSigma(
  containerRef: Ref<HTMLDivElement | null>,
  graphRef: Ref<SigmaGraph | null>,
  state: {
    nodes: Ref<KnowledgeGraphNodeSummary[]>
    layoutMode: Ref<KnowledgeGraphLayoutMode>
    selectedNodeId: Ref<string>
    searchPreviewNodeId: Ref<string>
    hoveredNodeId: Ref<string>
    selectedEdgeId: Ref<string>
    searchQuery: Ref<string>
    fitViewNonce: Ref<number>
    zoomInNonce: Ref<number>
    zoomOutNonce: Ref<number>
    rotateLeftNonce: Ref<number>
    rotateRightNonce: Ref<number>
    focusNodeId: Ref<string>
    showNodeLabels: Ref<boolean>
    showEdgeLabels: Ref<boolean>
    enableNodeDrag: Ref<boolean>
    onSelectNode: (nodeId: string) => void
    onHoverNode: (nodeId: string) => void
    onLeaveNode: () => void
    onSelectEdge: (edgeId: string) => void
    onStageClick: () => void
  },
) {
  const sigma = shallowRef<Sigma<KnowledgeSigmaNodeAttributes, KnowledgeSigmaEdgeAttributes> | null>(null)
  const draggingNodeId = ref('')

  function destroySigma() {
    if (!sigma.value) {
      return
    }
    sigma.value.kill()
    sigma.value = null
  }

  function mountSigma() {
    if (!containerRef.value || !graphRef.value) {
      return
    }

    destroySigma()
    sigma.value = new Sigma(graphRef.value, containerRef.value, buildSigmaSettings())

    sigma.value.on('clickNode', ({ node }) => {
      state.onSelectNode(node)
    })
    sigma.value.on('enterNode', ({ node }) => {
      state.onHoverNode(node)
    })
    sigma.value.on('leaveNode', () => {
      state.onLeaveNode()
    })
    sigma.value.on('clickEdge', ({ edge }) => {
      state.onSelectEdge(edge)
    })
    sigma.value.on('clickStage', () => {
      state.onStageClick()
    })

    sigma.value.on('downNode', ({ node }) => {
      if (!state.enableNodeDrag.value || !graphRef.value) {
        return
      }
      draggingNodeId.value = node
      graphRef.value.setNodeAttribute(node, 'highlighted', true)
    })
    sigma.value.on('upStage', () => {
      if (!draggingNodeId.value || !graphRef.value) {
        return
      }
      graphRef.value.removeNodeAttribute(draggingNodeId.value, 'highlighted')
      draggingNodeId.value = ''
    })
    sigma.value.on('upNode', ({ node }) => {
      if (!draggingNodeId.value || !graphRef.value) {
        return
      }
      graphRef.value.removeNodeAttribute(node, 'highlighted')
      draggingNodeId.value = ''
    })
    sigma.value.on('leaveStage', () => {
      if (!draggingNodeId.value || !graphRef.value) {
        return
      }
      graphRef.value.removeNodeAttribute(draggingNodeId.value, 'highlighted')
      draggingNodeId.value = ''
    })
    sigma.value.on('moveBody', ({ event }: SigmaStageEventPayload) => {
      if (!draggingNodeId.value || !graphRef.value || !sigma.value) {
        return
      }
      const position = sigma.value.viewportToGraph(event as Coordinates)
      graphRef.value.mergeNodeAttributes(draggingNodeId.value, {
        x: position.x,
        y: position.y,
      })
      event.preventSigmaDefault()
      event.original.preventDefault()
      event.original.stopPropagation()
    })
  }

  watch(
    [containerRef, graphRef],
    () => {
      mountSigma()
    },
    { immediate: true },
  )

  watch(
    [graphRef, state.layoutMode],
    ([graph, layoutMode]) => {
      if (!graph) {
        return
      }
      applyLayout(graph, layoutMode)
      sigma.value?.refresh()
    },
    { immediate: true },
  )

  watch(
    [graphRef, state.selectedNodeId, state.searchPreviewNodeId, state.hoveredNodeId, state.selectedEdgeId, state.searchQuery],
    ([graph, selectedNodeId, searchPreviewNodeId, hoveredNodeId, selectedEdgeId, searchQuery]) => {
      if (!graph) {
        return
      }
      computeVisibleState(graph, state.nodes.value, searchQuery, selectedNodeId, searchPreviewNodeId, hoveredNodeId, selectedEdgeId)
      sigma.value?.refresh()
    },
    { immediate: true },
  )

  watch(
    [state.showNodeLabels, state.showEdgeLabels],
    ([showNodeLabels, showEdgeLabels]) => {
      if (!sigma.value) {
        return
      }
      sigma.value.setSetting('renderLabels', showNodeLabels)
      sigma.value.setSetting('renderEdgeLabels', showEdgeLabels)
      sigma.value.refresh()
    },
    { immediate: true },
  )

  watch(
    state.fitViewNonce,
    () => {
      if (!sigma.value) {
        return
      }
      sigma.value.getCamera().animatedReset({ duration: 300 })
    },
  )

  watch(
    state.zoomInNonce,
    () => {
      if (!sigma.value) {
        return
      }
      const camera = sigma.value.getCamera()
      camera.animate({ ratio: Math.max(0.05, camera.ratio / 1.35) }, { duration: 180 })
    },
  )

  watch(
    state.zoomOutNonce,
    () => {
      if (!sigma.value) {
        return
      }
      const camera = sigma.value.getCamera()
      camera.animate({ ratio: Math.min(10, camera.ratio * 1.35) }, { duration: 180 })
    },
  )

  watch(
    state.rotateLeftNonce,
    () => {
      if (!sigma.value) {
        return
      }
      const camera = sigma.value.getCamera()
      camera.animate({ angle: camera.angle - Math.PI / 10 }, { duration: 180 })
    },
  )

  watch(
    state.rotateRightNonce,
    () => {
      if (!sigma.value) {
        return
      }
      const camera = sigma.value.getCamera()
      camera.animate({ angle: camera.angle + Math.PI / 10 }, { duration: 180 })
    },
  )

  watch(
    [graphRef, state.focusNodeId],
    ([graph, focusNodeId]) => {
      if (!sigma.value || !graph || !focusNodeId) {
        return
      }
      animateCameraToNode(sigma.value, graph, focusNodeId)
    },
  )

  onBeforeUnmount(() => {
    destroySigma()
  })

  return {
    sigma,
    fitView() {
      sigma.value?.getCamera().animatedReset({ duration: 300 })
    },
  }
}

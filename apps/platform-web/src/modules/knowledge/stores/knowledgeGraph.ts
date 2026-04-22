import { defineStore } from 'pinia'
import type { KnowledgeGraphLayoutMode } from '@/modules/knowledge/utils/knowledge-graph-types'

export const useKnowledgeGraphStore = defineStore('knowledgeGraph', {
  state: () => ({
    selectedNodeId: '',
    hoveredNodeId: '',
    selectedEdgeId: '',
    searchPreviewNodeId: '',
    nodeSearchQuery: '',
    layoutMode: 'forceatlas2' as KnowledgeGraphLayoutMode,
    showLegend: true,
    showNodeLabels: true,
    showEdgeLabels: false,
    showLabelPanel: true,
    showSettingsPanel: false,
    showInspectorPanel: true,
    enableNodeDrag: true,
    fitViewNonce: 0,
    zoomInNonce: 0,
    zoomOutNonce: 0,
    rotateLeftNonce: 0,
    rotateRightNonce: 0,
    focusNodeId: '',
  }),
  actions: {
    resetGraphUiState() {
      this.selectedNodeId = ''
      this.hoveredNodeId = ''
      this.selectedEdgeId = ''
      this.searchPreviewNodeId = ''
      this.nodeSearchQuery = ''
      this.layoutMode = 'forceatlas2'
      this.showLegend = true
      this.showNodeLabels = true
      this.showEdgeLabels = false
      this.showLabelPanel = true
      this.showSettingsPanel = false
      this.showInspectorPanel = true
      this.enableNodeDrag = true
      this.fitViewNonce += 1
      this.zoomInNonce = 0
      this.zoomOutNonce = 0
      this.rotateLeftNonce = 0
      this.rotateRightNonce = 0
      this.focusNodeId = ''
    },
    selectNode(nodeId: string) {
      this.selectedNodeId = nodeId
      this.selectedEdgeId = ''
      this.searchPreviewNodeId = ''
      this.showInspectorPanel = true
    },
    hoverNode(nodeId: string) {
      this.hoveredNodeId = nodeId
    },
    clearHoverNode() {
      this.hoveredNodeId = ''
    },
    focusNodePreview(nodeId: string) {
      this.searchPreviewNodeId = nodeId
    },
    clearFocusedNode() {
      this.searchPreviewNodeId = ''
    },
    selectEdge(edgeId: string) {
      this.selectedEdgeId = edgeId
      this.selectedNodeId = ''
      this.showInspectorPanel = true
      this.focusNodeId = ''
    },
    clearSelection() {
      this.selectedNodeId = ''
      this.selectedEdgeId = ''
      this.searchPreviewNodeId = ''
      this.focusNodeId = ''
    },
    requestCameraFocus(nodeId: string) {
      this.focusNodeId = ''
      this.focusNodeId = nodeId
    },
    focusNode(nodeId: string) {
      this.selectedNodeId = nodeId
      this.selectedEdgeId = ''
      this.searchPreviewNodeId = ''
      this.showInspectorPanel = true
    },
    fitView() {
      this.fitViewNonce += 1
    },
    zoomIn() {
      this.zoomInNonce += 1
    },
    zoomOut() {
      this.zoomOutNonce += 1
    },
    rotateLeft() {
      this.rotateLeftNonce += 1
    },
    rotateRight() {
      this.rotateRightNonce += 1
    },
  },
})

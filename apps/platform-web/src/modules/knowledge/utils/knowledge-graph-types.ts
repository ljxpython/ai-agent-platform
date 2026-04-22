export type RawKnowledgeGraphNode = Record<string, unknown>
export type RawKnowledgeGraphEdge = Record<string, unknown>

export type KnowledgeGraphLayoutMode = 'forceatlas2' | 'circular'

export type KnowledgeGraphNodeSummary = {
  id: string
  label: string
  typeLabel: string
  degree: number
  properties: Record<string, unknown>
  searchText: string
  color: string
  size: number
}

export type KnowledgeGraphEdgeSummary = {
  id: string
  label: string
  source: string
  target: string
  properties: Record<string, unknown>
  weight: number
}

export type KnowledgeGraphRelationSummary = {
  edgeId: string
  label: string
  direction: 'outgoing' | 'incoming'
  nodeId: string
  nodeLabel: string
  nodeTypeLabel: string
}

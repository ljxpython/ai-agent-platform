import Graph from 'graphology'
import type {
  RawKnowledgeGraphNode,
  RawKnowledgeGraphEdge,
  KnowledgeGraphEdgeSummary,
  KnowledgeGraphNodeSummary,
} from './knowledge-graph-types'
import { resolveKnowledgeGraphColor, resolveKnowledgeGraphFallbackColor } from './knowledge-graph-colors'

export type KnowledgeSigmaNodeAttributes = {
  label: string
  typeLabel: string
  degree: number
  color: string
  size: number
  zIndex?: number
  properties: Record<string, unknown>
  searchText: string
  hidden?: boolean
  highlighted?: boolean
  forceLabel?: boolean
  x: number
  y: number
}

export type KnowledgeSigmaEdgeAttributes = {
  label: string
  size: number
  color: string
  weight: number
  properties: Record<string, unknown>
  hidden?: boolean
}

export type KnowledgeGraphAdapterResult = {
  graph: Graph<KnowledgeSigmaNodeAttributes, KnowledgeSigmaEdgeAttributes>
  nodes: KnowledgeGraphNodeSummary[]
  edges: KnowledgeGraphEdgeSummary[]
  legend: Array<{ label: string; color: string }>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function resolveNodeProperties(node: RawKnowledgeGraphNode) {
  return isRecord(node.properties) ? node.properties : {}
}

function resolveNodeTypeLabel(node: RawKnowledgeGraphNode) {
  const properties = resolveNodeProperties(node)
  const labels = Array.isArray(node.labels) ? node.labels : []
  const firstLabel = labels.find((item) => typeof item === 'string' && item.trim())
  const fallback = [properties.entity_type, properties.type, properties.category].find(
    (item) => typeof item === 'string' && item.trim(),
  )
  return String(firstLabel || fallback || 'unknown')
}

function resolveNodeDisplayLabel(node: RawKnowledgeGraphNode, fallbackId: string) {
  const properties = resolveNodeProperties(node)
  const candidates = [
    properties.entity_name,
    properties.name,
    properties.title,
    properties.entity_id,
    properties.id,
    node.id,
  ]
  const firstCandidate = candidates.find((item) => typeof item === 'string' && item.trim())
  if (firstCandidate) {
    return String(firstCandidate)
  }
  const labels = Array.isArray(node.labels) ? node.labels.filter((item) => typeof item === 'string') : []
  return String(labels[0] || fallbackId)
}

function resolveEdgeProperties(edge: RawKnowledgeGraphEdge) {
  return isRecord(edge.properties) ? edge.properties : {}
}

function assignInitialCircularLayout(nodes: KnowledgeGraphNodeSummary[]) {
  if (!nodes.length) {
    return new Map<string, { x: number; y: number }>()
  }

  const positions = new Map<string, { x: number; y: number }>()
  const radius = Math.max(4, nodes.length / 8)
  const step = (Math.PI * 2) / nodes.length

  nodes.forEach((node, index) => {
    positions.set(node.id, {
      x: Math.cos(step * index) * radius,
      y: Math.sin(step * index) * radius,
    })
  })

  return positions
}

export function buildKnowledgeGraphAdapterResult(rawGraph: Record<string, unknown> | null): KnowledgeGraphAdapterResult {
  const graph = new Graph<KnowledgeSigmaNodeAttributes, KnowledgeSigmaEdgeAttributes>({ multi: true })
  const rawNodes = Array.isArray(rawGraph?.nodes) ? (rawGraph.nodes as RawKnowledgeGraphNode[]) : []
  const rawEdges = Array.isArray(rawGraph?.edges) ? (rawGraph.edges as RawKnowledgeGraphEdge[]) : []
  const degreeMap = new Map<string, number>()

  for (const edge of rawEdges) {
    const source = String(edge.source || '')
    const target = String(edge.target || '')
    if (source) {
      degreeMap.set(source, (degreeMap.get(source) || 0) + 1)
    }
    if (target) {
      degreeMap.set(target, (degreeMap.get(target) || 0) + 1)
    }
  }

  const typeColorMap = new Map<string, string>()
  const nodes: KnowledgeGraphNodeSummary[] = rawNodes.map((node, index) => {
    const id = String(node.id || `node-${index}`)
    const properties = resolveNodeProperties(node)
    const label = resolveNodeDisplayLabel(node, id)
    const typeLabel = resolveNodeTypeLabel(node)
    const colorResolution = resolveKnowledgeGraphColor(typeLabel, typeColorMap)
    const nextTypeMap = colorResolution.map
    typeColorMap.clear()
    nextTypeMap.forEach((value, key) => typeColorMap.set(key, value))
    const degree = degreeMap.get(id) || 0
    const size = 7 + Math.min(degree, 12) * 0.9

    return {
      id,
      label,
      typeLabel,
      degree,
      properties,
      searchText: `${label} ${typeLabel} ${Object.values(properties).join(' ')}`.toLowerCase(),
      color: colorResolution.color || resolveKnowledgeGraphFallbackColor(),
      size,
    }
  })

  const positions = assignInitialCircularLayout(nodes)

  for (const node of nodes) {
    graph.addNode(node.id, {
      label: node.label,
      typeLabel: node.typeLabel,
      degree: node.degree,
      color: node.color,
      size: node.size,
      properties: node.properties,
      searchText: node.searchText,
      highlighted: false,
      x: positions.get(node.id)?.x ?? 0,
      y: positions.get(node.id)?.y ?? 0,
    })
  }

  const edges: KnowledgeGraphEdgeSummary[] = []
  rawEdges.forEach((edge, index) => {
    const source = String(edge.source || '')
    const target = String(edge.target || '')
    if (!source || !target || !graph.hasNode(source) || !graph.hasNode(target)) {
      return
    }
    const properties = resolveEdgeProperties(edge)
    const label = String(edge.label || edge.type || edge.relation || properties.keywords || '关联')
    const id = String(edge.id || `${source}-${target}-${index}`)
    const weightCandidate = Number(properties.weight)
    const weight = Number.isFinite(weightCandidate) && weightCandidate > 0 ? weightCandidate : 1

    graph.addEdgeWithKey(id, source, target, {
      label,
      size: Math.min(6, 1.2 + Math.sqrt(weight)),
      color: '#94a3b8',
      weight,
      properties,
    })

    edges.push({
      id,
      label,
      source,
      target,
      properties,
      weight,
    })
  })

  return {
    graph,
    nodes,
    edges,
    legend: Array.from(typeColorMap.entries()).map(([label, color]) => ({ label, color })),
  }
}

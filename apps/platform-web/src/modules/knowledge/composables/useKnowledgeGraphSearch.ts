import MiniSearch from 'minisearch'
import type { KnowledgeGraphNodeSummary } from '@/modules/knowledge/utils/knowledge-graph-types'

export function createKnowledgeGraphSearch(nodes: KnowledgeGraphNodeSummary[]) {
  const engine = new MiniSearch({
    idField: 'id',
    fields: ['label', 'typeLabel', 'searchText'],
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
      boost: {
        label: 3,
        typeLabel: 1.5,
      },
    },
  })

  engine.addAll(
    nodes.map((node) => ({
      id: node.id,
      label: node.label,
      typeLabel: node.typeLabel,
      searchText: node.searchText,
    })),
  )

  return engine
}

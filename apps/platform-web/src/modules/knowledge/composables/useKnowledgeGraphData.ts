import { computed, ref } from 'vue'
import {
  getProjectKnowledgeGraph,
  listProjectKnowledgeGraphLabels,
  listProjectKnowledgePopularGraphLabels,
  searchProjectKnowledgeGraphLabels,
} from '@/services/knowledge/knowledge.service'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

export function useKnowledgeGraphData() {
  const labels = ref<string[]>([])
  const popularLabels = ref<string[]>([])
  const queryInput = ref('')
  const loadingLabels = ref(false)
  const loadingGraph = ref(false)
  const error = ref('')
  const selectedLabel = ref('')
  const graph = ref<Record<string, unknown> | null>(null)

  const selectedLabelDisplay = computed(() =>
    selectedLabel.value === '*' ? '全部图谱' : selectedLabel.value || '未选择标签',
  )

  async function loadGraphLabels(projectId: string, canRead: boolean) {
    if (!projectId || !canRead) {
      labels.value = []
      popularLabels.value = []
      graph.value = null
      return
    }

    loadingLabels.value = true
    error.value = ''
    try {
      const [nextLabels, nextPopular] = await Promise.all([
        queryInput.value.trim()
          ? searchProjectKnowledgeGraphLabels(projectId, queryInput.value.trim(), 50)
          : listProjectKnowledgeGraphLabels(projectId),
        listProjectKnowledgePopularGraphLabels(projectId, 10),
      ])
      labels.value = nextLabels
      popularLabels.value = nextPopular
    } catch (loadError) {
      labels.value = []
      popularLabels.value = []
      error.value = resolvePlatformHttpErrorMessage(loadError, '知识图谱标签加载失败', '知识图谱')
    } finally {
      loadingLabels.value = false
    }
  }

  async function openGraph(
    projectId: string,
    canRead: boolean,
    options: {
      label: string
      maxDepth: number
      maxNodes: number
    },
  ) {
    if (!projectId || !canRead || !options.label.trim()) {
      return null
    }

    loadingGraph.value = true
    error.value = ''
    selectedLabel.value = options.label.trim()
    try {
      graph.value = await getProjectKnowledgeGraph(projectId, {
        label: selectedLabel.value,
        max_depth: options.maxDepth,
        max_nodes: options.maxNodes,
      })
      return graph.value
    } catch (graphError) {
      graph.value = null
      error.value = resolvePlatformHttpErrorMessage(graphError, '知识图谱加载失败', '知识图谱')
      return null
    } finally {
      loadingGraph.value = false
    }
  }

  function reset() {
    labels.value = []
    popularLabels.value = []
    queryInput.value = ''
    loadingLabels.value = false
    loadingGraph.value = false
    error.value = ''
    selectedLabel.value = ''
    graph.value = null
  }

  return {
    labels,
    popularLabels,
    queryInput,
    loadingLabels,
    loadingGraph,
    error,
    selectedLabel,
    selectedLabelDisplay,
    graph,
    loadGraphLabels,
    openGraph,
    reset,
  }
}

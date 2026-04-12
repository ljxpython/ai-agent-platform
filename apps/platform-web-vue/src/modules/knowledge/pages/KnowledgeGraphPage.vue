<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import SearchInput from '@/components/platform/SearchInput.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import KnowledgeWorkspaceNav from '@/modules/knowledge/components/KnowledgeWorkspaceNav.vue'
import { useKnowledgeProjectRoute } from '@/modules/knowledge/composables/useKnowledgeProjectRoute'
import {
  getProjectKnowledgeGraph,
  listProjectKnowledgeGraphLabels,
  searchProjectKnowledgeGraphLabels
} from '@/services/knowledge/knowledge.service'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

const { projectId, project } = useKnowledgeProjectRoute()
const authorization = useAuthorization()

type RawGraphNode = Record<string, unknown>
type RawGraphEdge = Record<string, unknown>
type GraphNodeLayout = RawGraphNode & {
  id: string
  label: string
  x: number
  y: number
}
type GraphEdgeLayout = RawGraphEdge & {
  sourceNode: GraphNodeLayout
  targetNode: GraphNodeLayout
}

const labels = ref<string[]>([])
const queryInput = ref('')
const loadingLabels = ref(false)
const loadingGraph = ref(false)
const error = ref('')
const selectedLabel = ref('')
const graph = ref<Record<string, unknown> | null>(null)
const selectedNodeId = ref('')
const zoom = ref(1)
const canRead = computed(() => authorization.can('project.knowledge.read', projectId.value))

const nodes = computed<RawGraphNode[]>(() =>
  Array.isArray(graph.value?.nodes) ? (graph.value?.nodes as RawGraphNode[]) : []
)
const edges = computed<RawGraphEdge[]>(() =>
  Array.isArray(graph.value?.edges) ? (graph.value?.edges as RawGraphEdge[]) : []
)
const selectedNode = computed(() => nodes.value.find((item) => String(item.id || '') === selectedNodeId.value) ?? null)
const graphNodes = computed<GraphNodeLayout[]>(() => {
  const centerX = 280
  const centerY = 220
  const count = Math.max(nodes.value.length, 1)
  const radius = count === 1 ? 0 : Math.min(160, 80 + count * 10)
  return nodes.value.map((node, index) => {
    const angle = count === 1 ? 0 : (Math.PI * 2 * index) / count
    const labels = Array.isArray(node.labels) ? node.labels : []
    return {
      ...node,
      id: String(node.id || `node-${index}`),
      label: String(labels[0] || node.id || '--'),
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle)
    }
  })
})
const graphEdges = computed<GraphEdgeLayout[]>(() => {
  const nodeMap = new Map(graphNodes.value.map((node) => [String(node.id || ''), node]))
  return edges.value
    .map((edge) => {
      const source = nodeMap.get(String(edge.source || ''))
      const target = nodeMap.get(String(edge.target || ''))
      if (!source || !target) {
        return null
      }
      return {
        ...edge,
        sourceNode: source,
        targetNode: target
      }
    })
    .filter((edge): edge is GraphEdgeLayout => edge !== null)
})

function adjustZoom(delta: number) {
  zoom.value = Math.min(2, Math.max(0.6, Number((zoom.value + delta).toFixed(2))))
}

async function loadLabels() {
  if (!projectId.value || !canRead.value) {
    labels.value = []
    graph.value = null
    return
  }
  loadingLabels.value = true
  error.value = ''
  try {
    labels.value = queryInput.value.trim()
      ? await searchProjectKnowledgeGraphLabels(projectId.value, queryInput.value.trim(), 50)
      : await listProjectKnowledgeGraphLabels(projectId.value)
  } catch (loadError) {
    labels.value = []
    error.value = resolvePlatformHttpErrorMessage(loadError, '知识图谱标签加载失败', '知识图谱')
  } finally {
    loadingLabels.value = false
  }
}

async function openGraph(label: string) {
  if (!projectId.value || !canRead.value || !label.trim()) {
    return
  }
  loadingGraph.value = true
  error.value = ''
  selectedLabel.value = label.trim()
  try {
    graph.value = await getProjectKnowledgeGraph(projectId.value, { label: selectedLabel.value })
    const firstNode = Array.isArray(graph.value?.nodes) ? graph.value?.nodes[0] : null
    selectedNodeId.value = firstNode && typeof firstNode === 'object' ? String((firstNode as Record<string, unknown>).id || '') : ''
    zoom.value = 1
  } catch (graphError) {
    graph.value = null
    selectedNodeId.value = ''
    error.value = resolvePlatformHttpErrorMessage(graphError, '知识图谱加载失败', '知识图谱')
  } finally {
    loadingGraph.value = false
  }
}

watch(
  () => projectId.value,
  () => {
    void loadLabels()
  },
  { immediate: true }
)
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Knowledge"
      :title="project ? `${project.name} · 知识图谱` : '知识图谱'"
      description="第一阶段图谱页默认先做只读浏览：标签搜索、子图查看和节点属性面板。"
    />

    <KnowledgeWorkspaceNav v-if="projectId" :project-id="projectId" />

    <StateBanner
      v-if="projectId && !canRead"
      class="mt-4"
      title="当前角色没有知识图谱读取权限"
      description="请联系项目管理员授予 project.knowledge.read 权限后，再浏览当前项目的知识图谱。"
      variant="info"
    />
    <StateBanner
      v-else-if="error"
      class="mt-4"
      title="知识图谱异常"
      :description="error"
      variant="danger"
    />

    <div class="mt-4 grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
      <SurfaceCard>
        <div class="flex items-end gap-2">
          <div class="flex-1">
            <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">标签搜索</div>
                    <SearchInput v-model="queryInput" placeholder="搜索实体标签" />
          </div>
          <BaseButton variant="secondary" :disabled="loadingLabels || !canRead" @click="loadLabels">刷新</BaseButton>
        </div>
        <div class="mt-4 max-h-[520px] overflow-auto space-y-2">
          <button
            v-for="label in labels"
            :key="label"
            type="button"
            class="w-full rounded-2xl border px-4 py-3 text-left text-sm transition"
            :class="selectedLabel === label ? 'border-primary-300 bg-primary-50 text-primary-700 dark:border-primary-900/50 dark:bg-primary-950/20 dark:text-primary-200' : 'border-gray-100 bg-white text-gray-700 hover:border-primary-200 hover:text-primary-700 dark:border-dark-800 dark:bg-dark-900 dark:text-dark-200'"
            @click="openGraph(label)"
          >
            {{ label }}
          </button>
        </div>
      </SurfaceCard>

      <template v-if="graph">
        <SurfaceCard>
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">子图概览</div>
              <div class="mt-2 text-lg font-semibold text-gray-900 dark:text-white">{{ selectedLabel || '未选择标签' }}</div>
            </div>
            <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-dark-400">
              <span>nodes={{ nodes.length }} · edges={{ edges.length }}</span>
              <BaseButton variant="secondary" @click="adjustZoom(-0.2)">缩小</BaseButton>
              <BaseButton variant="secondary" @click="zoom = 1">重置</BaseButton>
              <BaseButton variant="secondary" @click="adjustZoom(0.2)">放大</BaseButton>
            </div>
          </div>
          <div class="mt-4 overflow-auto rounded-3xl border border-gray-100 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08),_transparent_55%)] dark:border-dark-800 dark:bg-dark-950/60">
            <svg
              viewBox="0 0 560 440"
              class="h-[420px] w-full"
              :style="{ transform: `scale(${zoom})`, transformOrigin: 'center center' }"
            >
              <g v-for="edge in graphEdges" :key="String(edge.id || `${edge.source}-${edge.target}`)">
                <line
                  :x1="edge.sourceNode.x"
                  :y1="edge.sourceNode.y"
                  :x2="edge.targetNode.x"
                  :y2="edge.targetNode.y"
                  stroke="currentColor"
                  class="text-gray-300 dark:text-dark-700"
                  stroke-width="2"
                />
                <text
                  :x="(edge.sourceNode.x + edge.targetNode.x) / 2"
                  :y="(edge.sourceNode.y + edge.targetNode.y) / 2 - 6"
                  text-anchor="middle"
                  class="fill-gray-400 text-[10px] dark:fill-dark-500"
                >
                  {{ String(edge.label || edge.type || '') }}
                </text>
              </g>
              <g
                v-for="node in graphNodes"
                :key="String(node.id || '')"
                class="cursor-pointer"
                @click="selectedNodeId = String(node.id || '')"
              >
                <circle
                  :cx="node.x"
                  :cy="node.y"
                  r="30"
                  :class="selectedNodeId === String(node.id || '') ? 'fill-primary-500/90 stroke-primary-200' : 'fill-white stroke-primary-300 dark:fill-dark-900 dark:stroke-primary-900/50'"
                  stroke-width="2"
                />
                <text
                  :x="node.x"
                  :y="node.y + 4"
                  text-anchor="middle"
                  class="fill-gray-700 text-[11px] font-medium dark:fill-dark-100"
                >
                  {{ node.label }}
                </text>
              </g>
            </svg>
          </div>
          <div class="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <div class="text-sm font-medium text-gray-900 dark:text-white">Nodes</div>
              <div class="mt-3 max-h-[420px] overflow-auto space-y-2">
                <button
                  v-for="node in nodes"
                  :key="String(node.id || '')"
                  type="button"
                  class="w-full rounded-2xl border px-4 py-3 text-left text-sm transition"
                  :class="selectedNodeId === String(node.id || '') ? 'border-primary-300 bg-primary-50 text-primary-700 dark:border-primary-900/50 dark:bg-primary-950/20 dark:text-primary-200' : 'border-gray-100 bg-white text-gray-700 hover:border-primary-200 hover:text-primary-700 dark:border-dark-800 dark:bg-dark-900 dark:text-dark-200'"
                  @click="selectedNodeId = String(node.id || '')"
                >
                  <div class="font-medium">{{ String(node.id || '--') }}</div>
                  <div class="mt-1 text-xs text-gray-400 dark:text-dark-500">{{ JSON.stringify(node.labels || []) }}</div>
                </button>
              </div>
            </div>
            <div>
              <div class="text-sm font-medium text-gray-900 dark:text-white">Edges</div>
              <div class="mt-3 max-h-[420px] overflow-auto space-y-2 text-sm text-gray-600 dark:text-dark-300">
                <div
                  v-for="edge in edges"
                  :key="String(edge.id || `${edge.source}-${edge.target}`)"
                  class="rounded-2xl border border-gray-100 px-4 py-3 dark:border-dark-800"
                >
                  {{ String(edge.source || '--') }} → {{ String(edge.target || '--') }}
                </div>
              </div>
            </div>
          </div>
        </SurfaceCard>
      </template>
      <EmptyState
        v-else
        title="还没有选择要查看的子图"
        description="先在左侧搜索并选择一个标签，再加载这个项目知识空间里的图谱子图。"
        icon="graph"
      />

      <SurfaceCard>
        <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">属性面板</div>
        <template v-if="selectedNode">
          <div class="mt-3 text-sm font-medium text-gray-900 dark:text-white">{{ String(selectedNode.id || '--') }}</div>
          <pre class="mt-3 overflow-auto rounded-2xl bg-gray-950/90 p-4 text-xs leading-6 text-white dark:bg-dark-950">{{ JSON.stringify(selectedNode.properties || {}, null, 2) }}</pre>
        </template>
        <p v-else class="mt-3 text-sm text-gray-500 dark:text-dark-300">
          点击中间列表里的某个节点，这里会展示它的属性详情。
        </p>
      </SurfaceCard>
    </div>
  </section>
</template>

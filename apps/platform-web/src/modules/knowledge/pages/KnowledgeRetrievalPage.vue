<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import KnowledgeQuerySettingsPanel, {
  type KnowledgeQuerySettings,
} from '@/modules/knowledge/components/KnowledgeQuerySettingsPanel.vue'
import KnowledgeWorkspaceNav from '@/modules/knowledge/components/KnowledgeWorkspaceNav.vue'
import { useKnowledgeProjectRoute } from '@/modules/knowledge/composables/useKnowledgeProjectRoute'
import {
  queryProjectKnowledge,
  streamProjectKnowledgeQuery,
} from '@/services/knowledge/knowledge.service'
import type { KnowledgeQueryResult } from '@/types/management'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

const DEFAULT_SETTINGS: KnowledgeQuerySettings = {
  mode: 'mix',
  response_type: 'Multiple Paragraphs',
  stream: false,
  top_k: 40,
  chunk_top_k: 20,
  max_entity_tokens: 6000,
  max_relation_tokens: 8000,
  max_total_tokens: 30000,
  only_need_context: false,
  only_need_prompt: false,
  enable_rerank: true,
  user_prompt: '',
  metadata_filters: {
    tags_any: [],
    tags_all: [],
    attributes: {},
  },
  strict_scope: false,
}

const { projectId, project } = useKnowledgeProjectRoute()
const authorization = useAuthorization()

const query = ref('')
const loading = ref(false)
const error = ref('')
const result = ref<KnowledgeQueryResult | null>(null)
const querySettings = ref<KnowledgeQuerySettings>({ ...DEFAULT_SETTINGS })
const recentQueries = ref<string[]>([])
const recentPrompts = ref<string[]>([])
const retrievalHistory = ref<Array<{ query: string; response: string; createdAt: string; scopeSummary?: string }>>([])
const canRead = computed(() => authorization.can('project.knowledge.read', projectId.value))
const activeScopeSummary = computed(() => {
  const segments: string[] = []
  const tags = querySettings.value.metadata_filters?.tags_any?.filter((item) => item.trim()) || []
  if (tags.length) {
    segments.push(`tags_any=${tags.join(', ')}`)
  }

  const layerValue = querySettings.value.metadata_filters?.attributes?.layer
  const layer = Array.isArray(layerValue) ? String(layerValue[0] || '') : typeof layerValue === 'string' ? layerValue : ''
  if (layer.trim()) {
    segments.push(`layer=${layer}`)
  }

  if (querySettings.value.strict_scope) {
    segments.push('strict_scope=true')
  }

  return segments.length ? segments.join(' · ') : '全项目默认范围'
})

function projectStorageKey(suffix: string) {
  return `pw:knowledge:${projectId.value || 'none'}:${suffix}`
}

function readList(key: string) {
  if (typeof window === 'undefined') {
    return []
  }

  try {
    const raw = window.localStorage.getItem(key)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []
  } catch {
    return []
  }
}

function writeList(key: string, value: string[]) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(key, JSON.stringify(value))
}

function readSettings() {
  if (typeof window === 'undefined') {
    return { ...DEFAULT_SETTINGS }
  }

  try {
    const raw = window.localStorage.getItem(projectStorageKey('query-settings'))
    const parsed = raw ? (JSON.parse(raw) as Partial<KnowledgeQuerySettings>) : {}
    return {
      ...DEFAULT_SETTINGS,
      ...parsed,
    }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

function persistSettings() {
  if (typeof window === 'undefined' || !projectId.value) {
    return
  }

  window.localStorage.setItem(
    projectStorageKey('query-settings'),
    JSON.stringify(querySettings.value),
  )
}

function readHistory() {
  if (typeof window === 'undefined') {
    return []
  }

  try {
    const raw = window.localStorage.getItem(projectStorageKey('retrieval-history'))
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeHistory() {
  if (typeof window === 'undefined' || !projectId.value) {
    return
  }

  window.localStorage.setItem(
    projectStorageKey('retrieval-history'),
    JSON.stringify(retrievalHistory.value.slice(0, 12)),
  )
}

function pushRecent(target: typeof recentQueries, storageSuffix: string, nextValue: string) {
  const normalized = nextValue.trim()
  if (!normalized) {
    return
  }

  const nextRows = [normalized, ...target.value.filter((item) => item !== normalized)].slice(0, 10)
  target.value = nextRows
  writeList(projectStorageKey(storageSuffix), nextRows)
}

function hydrateProjectScopedState() {
  if (!projectId.value) {
    querySettings.value = { ...DEFAULT_SETTINGS }
    recentQueries.value = []
    recentPrompts.value = []
    return
  }

  querySettings.value = readSettings()
  recentQueries.value = readList(projectStorageKey('recent-queries'))
  recentPrompts.value = readList(projectStorageKey('recent-prompts'))
  retrievalHistory.value = readHistory()
}

async function runQuery() {
  if (!projectId.value || !canRead.value || !query.value.trim()) {
    return
  }

  loading.value = true
  error.value = ''

  try {
    const requestPayload = {
      query: query.value.trim(),
      ...querySettings.value,
      include_references: true,
      include_chunk_content: true,
    }
    if (querySettings.value.stream) {
      result.value = {
        response: '',
        references: [],
      }
      await streamProjectKnowledgeQuery(projectId.value, requestPayload, {
        onReferences(references) {
          result.value = {
            response: result.value?.response || '',
            references: references || [],
          }
        },
        onChunk(chunk) {
          result.value = {
            response: `${result.value?.response || ''}${chunk}`,
            references: result.value?.references || [],
          }
        },
      })
    } else {
      result.value = await queryProjectKnowledge(projectId.value, requestPayload)
    }
    pushRecent(recentQueries, 'recent-queries', query.value)
    pushRecent(recentPrompts, 'recent-prompts', querySettings.value.user_prompt)
    if (result.value?.response) {
      retrievalHistory.value = [
        {
          query: query.value.trim(),
          response: result.value.response,
          createdAt: new Date().toISOString(),
          scopeSummary: activeScopeSummary.value,
        },
        ...retrievalHistory.value.filter((item) => item.query !== query.value.trim()),
      ].slice(0, 12)
      writeHistory()
    }
  } catch (queryError) {
    result.value = null
    error.value = resolvePlatformHttpErrorMessage(queryError, '知识检索失败', '知识检索')
  } finally {
    loading.value = false
  }
}

watch(
  () => projectId.value,
  () => {
    hydrateProjectScopedState()
    result.value = null
    error.value = ''
  },
  { immediate: true },
)

watch(
  () => querySettings.value,
  () => {
    persistSettings()
  },
  { deep: true },
)
</script>

<template>
  <section class="pw-page-shell flex h-full min-h-0 flex-col overflow-y-auto">
    <PageHeader
      eyebrow="Knowledge"
      :title="project ? `${project.name} · 知识检索` : '知识检索'"
      description="对齐 LightRAG 用户工作流后，这里不再只是一个 mode 下拉，而是完整的项目级检索调试面板。"
    />

    <KnowledgeWorkspaceNav
      v-if="projectId"
      :project-id="projectId"
    />

    <StateBanner
      v-if="projectId && !canRead"
      class="mt-4"
      title="当前角色没有知识检索权限"
      description="请联系项目管理员授予 project.knowledge.read 权限后，再在当前项目下执行知识查询。"
      variant="info"
    />
    <StateBanner
      v-else-if="error"
      class="mt-4"
      title="知识检索失败"
      :description="error"
      variant="danger"
    />

    <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)] xl:items-start">
      <div class="space-y-4">
        <SurfaceCard>
          <div class="space-y-4">
            <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
              检索问题
              <textarea
                v-model="query"
                rows="5"
                class="min-h-[140px] rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 dark:border-dark-700 dark:bg-dark-900 dark:text-white"
                placeholder="例如：这个项目知识空间里和用户登录相关的规则是什么？"
              />
            </label>

            <div
              v-if="recentQueries.length"
              class="space-y-2"
            >
              <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
                Recent Queries
              </div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="item in recentQueries"
                  :key="item"
                  type="button"
                  class="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-600 transition hover:border-primary-300 hover:text-primary-700 dark:border-dark-700 dark:text-dark-300"
                  @click="query = item"
                >
                  {{ item }}
                </button>
              </div>
            </div>

            <div class="flex justify-end">
              <BaseButton
                :disabled="loading || !canRead || !query.trim()"
                @click="runQuery"
              >
                {{ loading ? '检索中…' : '发起检索' }}
              </BaseButton>
            </div>
          </div>
        </SurfaceCard>

        <template v-if="result">
          <SurfaceCard>
            <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
              响应结果
            </div>
            <div class="mt-3">
              <span class="inline-flex rounded-full border border-primary-200 bg-primary-50 px-3 py-1 text-xs text-primary-700 dark:border-primary-900/60 dark:bg-primary-950/30 dark:text-primary-300">
                {{ activeScopeSummary }}
              </span>
            </div>
            <div class="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-700 dark:text-dark-200">
              {{ result.response }}
            </div>
          </SurfaceCard>
        </template>
        <EmptyState
          v-else
          title="还没有检索结果"
          description="设置参数后发起一次真实 query，就能判断当前项目知识空间是否已经具备像 LightRAG 一样可调、可观察的检索体验。"
          icon="search"
        />

        <SurfaceCard
          v-if="retrievalHistory.length"
          class="space-y-4"
        >
          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            Retrieval History
          </div>
          <div class="space-y-3">
            <button
              v-for="item in retrievalHistory"
              :key="`${item.createdAt}-${item.query}`"
              type="button"
              class="w-full rounded-2xl border border-gray-100 px-4 py-3 text-left transition hover:border-primary-200 dark:border-dark-800"
              @click="query = item.query"
            >
              <div class="text-sm font-medium text-gray-900 dark:text-white">
                {{ item.query }}
              </div>
              <div class="mt-1 text-xs text-gray-400 dark:text-dark-500">
                {{ new Date(item.createdAt).toLocaleString() }}
              </div>
              <div
                v-if="item.scopeSummary"
                class="mt-2 text-xs text-primary-700 dark:text-primary-300"
              >
                {{ item.scopeSummary }}
              </div>
              <div class="mt-2 line-clamp-3 text-sm leading-6 text-gray-600 dark:text-dark-300">
                {{ item.response }}
              </div>
            </button>
          </div>
        </SurfaceCard>

        <SurfaceCard
          v-if="result?.references?.length"
          class="mt-4"
        >
          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">
            引用上下文
          </div>
          <div class="mt-4 space-y-3">
            <div
              v-for="reference in result.references"
              :key="`${reference.reference_id}-${reference.file_path}`"
              class="rounded-2xl border border-gray-100 px-4 py-3 dark:border-dark-800"
            >
              <div class="text-sm font-medium text-gray-900 dark:text-white">
                {{ reference.file_path }}
              </div>
              <div class="mt-1 text-xs text-gray-400 dark:text-dark-500">
                reference_id={{ reference.reference_id }}
              </div>
              <div
                v-if="reference.content?.length"
                class="mt-3 space-y-2 text-sm leading-6 text-gray-600 dark:text-dark-300"
              >
                <div
                  v-for="chunk in reference.content"
                  :key="`${reference.reference_id}-${chunk}`"
                  class="rounded-2xl bg-gray-50 px-3 py-2 dark:bg-dark-900/80"
                >
                  {{ chunk }}
                </div>
              </div>
            </div>
          </div>
        </SurfaceCard>
      </div>

      <KnowledgeQuerySettingsPanel
        v-model="querySettings"
        :recent-prompts="recentPrompts"
      />
    </div>
  </section>
</template>

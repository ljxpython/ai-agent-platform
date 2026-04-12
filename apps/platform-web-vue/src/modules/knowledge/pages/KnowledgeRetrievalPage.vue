<script setup lang="ts">
import { computed, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseSelect from '@/components/base/BaseSelect.vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import EmptyState from '@/components/platform/EmptyState.vue'
import StateBanner from '@/components/platform/StateBanner.vue'
import { useAuthorization } from '@/composables/useAuthorization'
import KnowledgeWorkspaceNav from '@/modules/knowledge/components/KnowledgeWorkspaceNav.vue'
import { useKnowledgeProjectRoute } from '@/modules/knowledge/composables/useKnowledgeProjectRoute'
import { queryProjectKnowledge } from '@/services/knowledge/knowledge.service'
import type { KnowledgeQueryResult } from '@/types/management'
import { resolvePlatformHttpErrorMessage } from '@/utils/http-error'

const { projectId, project } = useKnowledgeProjectRoute()
const authorization = useAuthorization()

const query = ref('')
const mode = ref('mix')
const loading = ref(false)
const error = ref('')
const result = ref<KnowledgeQueryResult | null>(null)
const canRead = computed(() => authorization.can('project.knowledge.read', projectId.value))

async function runQuery() {
  if (!projectId.value || !canRead.value || !query.value.trim()) {
    return
  }
  loading.value = true
  error.value = ''
  try {
    result.value = await queryProjectKnowledge(projectId.value, {
      query: query.value.trim(),
      mode: mode.value,
      include_references: true,
      include_chunk_content: true
    })
  } catch (queryError) {
    result.value = null
    error.value = resolvePlatformHttpErrorMessage(queryError, '知识检索失败', '知识检索')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Knowledge"
      :title="project ? `${project.name} · 知识检索` : '知识检索'"
      description="先验证这个项目知识空间能不能查，再去扩更复杂的智能体复用路径。"
    />

    <KnowledgeWorkspaceNav v-if="projectId" :project-id="projectId" />

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

    <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
      <SurfaceCard>
        <div class="grid gap-4 md:grid-cols-[minmax(0,1fr)_180px_auto] md:items-end">
          <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
            检索问题
            <textarea
              v-model="query"
              rows="5"
              class="min-h-[140px] rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 dark:border-dark-700 dark:bg-dark-900 dark:text-white"
              placeholder="例如：这个项目知识空间里和用户登录相关的规则是什么？"
            />
          </label>
          <label class="flex flex-col gap-2 text-sm font-medium text-gray-700 dark:text-dark-200">
            模式
            <BaseSelect v-model="mode">
              <option value="mix">mix</option>
              <option value="hybrid">hybrid</option>
              <option value="local">local</option>
              <option value="global">global</option>
              <option value="naive">naive</option>
            </BaseSelect>
          </label>
          <BaseButton :disabled="loading || !canRead || !query.trim()" @click="runQuery">
            {{ loading ? '检索中…' : '发起检索' }}
          </BaseButton>
        </div>
      </SurfaceCard>

      <template v-if="result">
        <SurfaceCard>
          <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">响应结果</div>
          <div class="mt-3 whitespace-pre-wrap text-sm leading-7 text-gray-700 dark:text-dark-200">
            {{ result.response }}
          </div>
        </SurfaceCard>
      </template>
      <EmptyState
        v-else
        title="还没有检索结果"
        description="在当前项目下输入一个真实问题后，可以快速验证这个知识空间是否已经具备可用的检索价值。"
        icon="search"
      />
    </div>

    <SurfaceCard v-if="result?.references?.length" class="mt-4">
      <div class="text-xs font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500">引用上下文</div>
      <div class="mt-4 space-y-3">
        <div
          v-for="reference in result.references"
          :key="`${reference.reference_id}-${reference.file_path}`"
          class="rounded-2xl border border-gray-100 px-4 py-3 dark:border-dark-800"
        >
          <div class="text-sm font-medium text-gray-900 dark:text-white">{{ reference.file_path }}</div>
          <div class="mt-1 text-xs text-gray-400 dark:text-dark-500">reference_id={{ reference.reference_id }}</div>
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
  </section>
</template>

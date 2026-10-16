<script setup lang="ts">
import { ref } from "vue";
import axios from "axios";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { useUiStore } from "@/stores/ui";

const props = defineProps<{
  show: boolean;
  projectId: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const uiStore = useUiStore();

export type QueryMode = "hybrid" | "local" | "global" | "naive" | "mix";

export interface Locator {
  unit: "page" | "slide" | "unknown";
  label: string;
  page_number?: number;
  slide_number?: number;
  score?: number;
}

export interface SourceItem {
  source_id: string;
  document_id: string;
  chunk_id: string;
  title: string;
  kind: string;
  preview: string;
  truncated: boolean;
  locator?: Locator;
}

export interface QueryResult {
  status: "ok" | "no_hit" | "error";
  response?: string;
  sources: SourceItem[];
}

const query = ref("");
const mode = ref<QueryMode>("hybrid");
const topK = ref(5);
const querying = ref(false);
const result = ref<QueryResult | null>(null);
const searchTime = ref<number | null>(null);

const modeOptions: { value: QueryMode; label: string; desc: string }[] = [
  {
    value: "hybrid",
    label: "Hybrid 混合检索",
    desc: "实体图谱关联 + 向量语义匹配，最全最准",
  },
  {
    value: "local",
    label: "Local 局部实体",
    desc: "聚焦具体实体周围的上下文跳数",
  },
  {
    value: "global",
    label: "Global 全局主题",
    desc: "跨文档主题抽象与宏观关系提取",
  },
  {
    value: "naive",
    label: "Naive 朴素向量",
    desc: "传统仅靠 embedding 余弦相似度召回",
  },
];

async function handleSearch() {
  const q = query.value.trim();
  if (!q) {
    uiStore.pushToast({
      type: "warning",
      title: "提示",
      message: "请输入检索问题或关键词",
    });
    return;
  }

  querying.value = true;
  result.value = null;
  const start = Date.now();

  try {
    const gatewayUrl =
      (import.meta.env.VITE_KNOWLEDGE_GATEWAY_URL as string) ||
      "http://152.136.27.196:8001";
    const res = await axios.post<QueryResult>(
      `${gatewayUrl}/internal/knowledge/query?project_id=${encodeURIComponent(props.projectId)}`,
      {
        query: q,
        top_k: topK.value,
        mode: mode.value,
        sources_version: 2,
      },
      {
        timeout: 45000,
        headers: { "Content-Type": "application/json" },
      },
    );
    result.value = res.data;
    searchTime.value = Date.now() - start;
  } catch (err: unknown) {
    const msg =
      err instanceof Error
        ? err.message
        : "检索请求失败，请确认宿主机 8001 网关可用";
    uiStore.pushToast({
      type: "error",
      title: "检索失败",
      message: msg,
    });
  } finally {
    querying.value = false;
  }
}
</script>

<template>
  <BaseDrawer
    :show="show"
    title="知识检索与可信溯源沙盒 (Playground)"
    width="xl"
    @close="emit('close')"
  >
    <div class="space-y-6 p-4">
      <!-- Search Input Area -->
      <div
        class="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-dark-700 dark:bg-dark-900"
      >
        <label
          class="block text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-dark-400"
        >
          检索测试 Query
        </label>
        <div class="mt-2 flex gap-2">
          <input
            v-model="query"
            type="text"
            placeholder="输入测试问题，如：AI长期记忆有哪些优化方式？"
            class="flex-1 rounded-xl border border-gray-200 bg-gray-50 px-3.5 py-2 text-sm text-gray-900 transition focus:border-emerald-500 focus:bg-white focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-white dark:focus:border-emerald-500"
            @keyup.enter="handleSearch"
          />
          <BaseButton
            variant="primary"
            :disabled="querying || !query.trim()"
            @click="handleSearch"
          >
            <BaseIcon name="search" size="sm" />
            {{ querying ? "检索中..." : "执行检索" }}
          </BaseButton>
        </div>

        <!-- Mode & TopK Settings -->
        <div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              class="block text-[11px] font-medium text-gray-500 dark:text-dark-400"
            >
              检索模式 (LightRAG Mode)
            </label>
            <select
              v-model="mode"
              class="mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs text-gray-900 dark:border-dark-700 dark:bg-dark-800 dark:text-white"
            >
              <option
                v-for="opt in modeOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div>
            <div class="flex items-center justify-between">
              <label
                class="block text-[11px] font-medium text-gray-500 dark:text-dark-400"
              >
                召回 Top-K 切片数
              </label>
              <span
                class="font-mono text-xs font-semibold text-emerald-600 dark:text-emerald-400"
              >
                {{ topK }}
              </span>
            </div>
            <input
              v-model.number="topK"
              type="range"
              min="1"
              max="8"
              class="mt-2 w-full accent-emerald-500"
            />
          </div>
        </div>
      </div>

      <!-- Result Area -->
      <div v-if="result" class="space-y-4">
        <!-- Status Bar -->
        <div class="flex items-center justify-between text-xs text-gray-500">
          <div class="flex items-center gap-2">
            <span class="font-medium text-gray-700 dark:text-dark-200"
              >检索状态：</span
            >
            <StatusPill :tone="result.status === 'ok' ? 'success' : 'neutral'">
              {{
                result.status === "ok" ? "命中知识切片" : "未命中内容 (no_hit)"
              }}
            </StatusPill>
          </div>
          <div v-if="searchTime" class="font-mono text-[11px]">
            耗时: {{ (searchTime / 1000).toFixed(2) }}s
          </div>
        </div>

        <!-- Synthesized Response -->
        <div
          v-if="result.response"
          class="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4 dark:border-emerald-950/60 dark:bg-emerald-950/20"
        >
          <div
            class="flex items-center gap-2 text-xs font-semibold text-emerald-800 dark:text-emerald-400"
          >
            <BaseIcon name="sparkle" size="xs" />
            LightRAG 综合解答
          </div>
          <div
            class="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-gray-800 dark:text-dark-100"
          >
            {{ result.response }}
          </div>
        </div>

        <!-- Sources Section -->
        <div>
          <div
            class="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-dark-400"
          >
            召回切片与可信页码反查 ({{ result.sources.length }} 条)
          </div>

          <div class="space-y-3">
            <div
              v-for="(src, idx) in result.sources"
              :key="src.source_id || idx"
              class="rounded-xl border border-gray-200 bg-white p-3.5 shadow-sm dark:border-dark-700 dark:bg-dark-900"
            >
              <!-- Source Header -->
              <div
                class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2 dark:border-dark-800"
              >
                <div
                  class="flex items-center gap-2 font-semibold text-gray-900 dark:text-white"
                >
                  <span
                    class="flex h-5 w-5 items-center justify-center rounded bg-gray-100 text-[10px] font-mono text-gray-600 dark:bg-dark-800 dark:text-dark-300"
                  >
                    {{ idx + 1 }}
                  </span>
                  <span class="text-xs truncate max-w-[280px]">
                    {{ src.title }}
                  </span>
                </div>

                <!-- Locator Badge (Docling 可信页码) -->
                <div v-if="src.locator" class="flex items-center gap-1.5">
                  <span
                    v-if="src.locator.unit === 'page'"
                    class="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400"
                  >
                    <BaseIcon name="file" size="xs" />
                    {{
                      src.locator.label || `第 ${src.locator.page_number} 页`
                    }}
                    <span
                      v-if="src.locator.score"
                      class="opacity-75 font-mono text-[9px]"
                    >
                      ({{ Math.round(src.locator.score * 100) }}%)
                    </span>
                  </span>
                  <span
                    v-else-if="src.locator.unit === 'slide'"
                    class="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2.5 py-0.5 text-[11px] font-semibold text-purple-700 dark:bg-purple-950/60 dark:text-purple-400"
                  >
                    <BaseIcon name="file" size="xs" />
                    {{
                      src.locator.label ||
                      `第 ${src.locator.slide_number} 页幻灯片`
                    }}
                  </span>
                  <span
                    v-else
                    class="rounded bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-dark-800"
                  >
                    纯文本切片
                  </span>
                </div>
              </div>

              <!-- Preview Content -->
              <p
                class="mt-2 text-xs leading-relaxed text-gray-600 dark:text-dark-300 line-clamp-4"
              >
                {{ src.preview }}
              </p>

              <!-- Chunk info footer -->
              <div
                class="mt-2.5 flex items-center justify-between text-[10px] font-mono text-gray-400 dark:text-dark-500"
              >
                <span>Chunk: {{ src.chunk_id }}</span>
                <span>Doc: {{ src.document_id }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </BaseDrawer>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { EvidenceDetail } from "../types";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  evidence: EvidenceDetail | null;
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

const operationTitle = computed(() => {
  if (!props.evidence) return "证据详情";
  switch (props.evidence.operation) {
    case "sql_query":
      return "只读数据库查询事实 (SQL Evidence)";
    case "source":
      return "研发源码只读快照 (Source Evidence)";
    case "documents":
      return "官方帮助与知识资料 (Document Evidence)";
    case "logs":
      return "结构化服务日志 (Logs Evidence)";
    case "public_search":
      return "公开网络检索摘要 (Public Search)";
    default:
      return `调查证据详情 (${props.evidence.operation})`;
  }
});

const sqlRows = computed(() => {
  const data = props.evidence?.data;
  if (data && Array.isArray(data.rows)) {
    return data.rows;
  }
  return [];
});

const sqlColumns = computed(() => {
  if (sqlRows.value.length === 0) return [];
  return Object.keys(sqlRows.value[0]);
});

const sources = computed(() => {
  const data = props.evidence?.data;
  if (data && Array.isArray(data.sources)) {
    return data.sources;
  }
  return [];
});
</script>

<template>
  <BaseDrawer
    :show="isOpen"
    :title="operationTitle"
    width="wide"
    @close="emit('close')"
  >
    <div v-if="evidence" class="p-4 space-y-4 text-xs font-sans">
      <!-- 证据元数据顶栏 -->
      <div
        class="flex flex-col gap-1 p-3 bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-800 rounded-xl"
      >
        <div
          class="flex items-center justify-between text-[11px] text-gray-500 dark:text-dark-400"
        >
          <span class="font-mono">编号: {{ evidence.evidence_id }}</span>
          <span>{{
            evidence.observed_at
              ? new Date(evidence.observed_at).toLocaleTimeString()
              : ""
          }}</span>
        </div>
        <div
          v-if="evidence.scope?.project_id"
          class="text-[11px] text-gray-400 font-mono"
        >
          归属项目: {{ evidence.scope.project_id }}
        </div>
      </div>

      <!-- 1. SQL 查询结果呈现 (表格) -->
      <div v-if="evidence.operation === 'sql_query'" class="space-y-3">
        <div
          class="flex items-center justify-between text-xs text-gray-600 dark:text-dark-300"
        >
          <span class="font-semibold">查询结果记录集 (只读):</span>
          <span class="font-mono text-gray-500"
            >共 {{ evidence.data?.row_count ?? sqlRows.length }} 行</span
          >
        </div>

        <div
          v-if="sqlRows.length > 0"
          class="overflow-x-auto border border-gray-200 dark:border-dark-800 rounded-lg max-h-80"
        >
          <table class="w-full text-left border-collapse text-[11px]">
            <thead
              class="bg-gray-100 dark:bg-dark-950 text-gray-600 dark:text-dark-300 border-b border-gray-200 dark:border-dark-800"
            >
              <tr>
                <th
                  v-for="col in sqlColumns"
                  :key="col"
                  class="px-2.5 py-1.5 font-mono font-semibold"
                >
                  {{ col }}
                </th>
              </tr>
            </thead>
            <tbody
              class="divide-y divide-gray-100 dark:divide-dark-800 font-mono text-gray-800 dark:text-dark-200"
            >
              <tr
                v-for="(row, idx) in sqlRows"
                :key="idx"
                class="hover:bg-gray-50 dark:hover:bg-dark-800/50"
              >
                <td
                  v-for="col in sqlColumns"
                  :key="col"
                  class="px-2.5 py-1.5 whitespace-nowrap"
                >
                  {{ row[col] }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          v-else
          class="p-6 text-center text-gray-400 border border-dashed rounded-lg"
        >
          查询成功，返回 0 条记录。
        </div>
      </div>

      <!-- 2. 源码快照呈现 (Source) -->
      <div v-else-if="evidence.operation === 'source'" class="space-y-3">
        <!-- 版本醒目标签 -->
        <div
          class="flex items-center gap-2 p-2.5 bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 rounded-xl text-sky-800 dark:text-sky-300 text-xs"
        >
          <BaseIcon
            name="branch"
            class="w-4 h-4 shrink-0 text-sky-600 dark:text-sky-400"
          />
          <span>
            只读代码快照 · 版本:
            <strong class="font-mono font-bold">{{
              evidence.data?.revision || "未知版本"
            }}</strong>
            （此为固定镜像快照，非正在运行的生产代码）
          </span>
        </div>

        <div
          v-for="(src, idx) in sources"
          :key="idx"
          class="space-y-1.5 border border-gray-200 dark:border-dark-800 rounded-xl p-3 bg-white dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between text-[11px] font-mono text-gray-700 dark:text-dark-300"
          >
            <span
              class="font-bold truncate"
              :title="src.path || src.title || ''"
            >
              📄 {{ src.path || src.title || "源码片段" }}
            </span>
            <span v-if="src.line_start != null" class="text-gray-400 shrink-0">
              L{{ src.line_start }} - L{{ src.line_end }}
            </span>
          </div>

          <pre
            class="p-2.5 bg-gray-50 dark:bg-dark-950 rounded-lg border border-gray-200/80 dark:border-dark-800 font-mono text-[11px] text-gray-800 dark:text-dark-200 overflow-x-auto leading-relaxed"
            >{{ src.text }}</pre
          >
        </div>
      </div>

      <!-- 3. 官方文档呈现 (Documents) -->
      <div v-else-if="evidence.operation === 'documents'" class="space-y-3">
        <div
          v-for="(src, idx) in sources"
          :key="idx"
          class="space-y-1.5 border border-gray-200 dark:border-dark-800 rounded-xl p-3 bg-white dark:bg-dark-900"
        >
          <div class="font-semibold text-gray-900 dark:text-white">
            📚 {{ src.title || "帮助文档" }}
          </div>
          <div
            class="text-[11px] text-gray-600 dark:text-dark-300 leading-relaxed whitespace-pre-wrap"
          >
            {{ src.text }}
          </div>
        </div>
      </div>

      <!-- 4. 公开搜索呈现 (Public Search) -->
      <div v-else-if="evidence.operation === 'public_search'" class="space-y-3">
        <div
          v-for="(src, idx) in sources"
          :key="idx"
          class="border border-gray-200 dark:border-dark-800 rounded-xl p-3 bg-white dark:bg-dark-900 space-y-1.5"
        >
          <a
            v-if="src.url"
            :href="src.url"
            target="_blank"
            rel="noopener noreferrer"
            class="font-semibold text-sky-600 hover:text-sky-700 hover:underline flex items-center gap-1"
          >
            <span>{{ src.title || src.url }}</span>
            <span class="text-[10px]">↗</span>
          </a>
          <p
            class="text-[11px] text-gray-600 dark:text-dark-300 leading-relaxed"
          >
            {{ src.snippet || src.text }}
          </p>
        </div>
      </div>

      <!-- 兜底通用呈现 -->
      <div v-else class="space-y-2">
        <pre
          class="p-3 bg-gray-50 dark:bg-dark-950 rounded-lg border border-gray-200 dark:border-dark-800 font-mono text-[11px] text-gray-800 dark:text-dark-200 overflow-x-auto"
          >{{ JSON.stringify(evidence.data || evidence, null, 2) }}</pre
        >
      </div>
    </div>
  </BaseDrawer>
</template>

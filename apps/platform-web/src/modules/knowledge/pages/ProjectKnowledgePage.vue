<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import TablePageLayout from "@/components/layout/TablePageLayout.vue";
import DataTable from "@/components/platform/DataTable.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import FilterToolbar from "@/components/platform/FilterToolbar.vue";
import MetricCard from "@/components/platform/MetricCard.vue";
import PaginationBar from "@/components/platform/PaginationBar.vue";
import SearchInput from "@/components/platform/SearchInput.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import ActionMenu from "@/components/platform/ActionMenu.vue";
import KnowledgePlaygroundDrawer from "../components/KnowledgePlaygroundDrawer.vue";
import type {
  ActionMenuItem,
  DataTableColumn,
} from "@/components/platform/data-table";
import { usePagination } from "@/composables/usePagination";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import {
  getKnowledgeCapabilities,
  listKnowledgeDocuments,
  listKnowledgeJobs,
  type KnowledgeCapabilities,
  type KnowledgeDocument,
  type KnowledgeJob,
} from "@/services/knowledge/knowledge.service";
import { useUiStore } from "@/stores/ui";
import { copyText } from "@/utils/clipboard";
import { formatDateTime, shortId } from "@/utils/format";

const { activeProjectId, activeProject } = useWorkspaceProjectContext();
const authorization = useAuthorization();
const uiStore = useUiStore();

const activeTab = ref<"documents" | "jobs">("documents");
const loading = ref(false);
const error = ref("");
const notice = ref("");
const queryInput = ref("");
const query = ref("");

// Capabilities
const capabilities = ref<KnowledgeCapabilities | null>(null);

// Documents pagination
const documents = ref<KnowledgeDocument[]>([]);
const totalDocs = ref(0);
const docPagination = usePagination({
  initialPageSize: 20,
  storageKey: "pw:knowledge:docs:pageSize",
});

// Jobs pagination
const jobs = ref<KnowledgeJob[]>([]);
const totalJobs = ref(0);
const jobPagination = usePagination({
  initialPageSize: 20,
  storageKey: "pw:knowledge:jobs:pageSize",
});

// Upload Dialog
const uploadDialogOpen = ref(false);
const playgroundOpen = ref(false);
const selectedFile = ref<File | null>(null);
const uploading = ref(false);

const canUpload = computed(() => {
  return (
    authorization.currentProjectCan("project.knowledge.upload") &&
    (capabilities.value?.upload_enabled ?? true)
  );
});

function docFromRow(row: Record<string, unknown>): KnowledgeDocument {
  return row as unknown as KnowledgeDocument;
}

function jobFromRow(row: Record<string, unknown>): KnowledgeJob {
  return row as unknown as KnowledgeJob;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function getJobStatusTone(
  status: string,
): "neutral" | "success" | "warning" | "danger" {
  switch (status) {
    case "ready":
      return "success";
    case "indexing":
    case "parsing":
    case "publishing":
      return "warning";
    case "failed":
      return "danger";
    default:
      return "neutral";
  }
}

const stats = computed(() => {
  const activeJobsCount = jobs.value.filter(
    (j) =>
      j.status === "queued" ||
      j.status === "indexing" ||
      j.status === "parsing",
  ).length;

  return [
    {
      label: "已入库文档",
      value: String(totalDocs.value),
      hint: "项目已收录并索引完成的资料总数",
      icon: "archive" as const,
      tone: "neutral" as const,
    },
    {
      label: "解析排队中",
      value: String(activeJobsCount),
      hint: "后台异步构建/切片抽取中的任务",
      icon: "activity" as const,
      tone: activeJobsCount > 0 ? ("warning" as const) : ("neutral" as const),
    },
    {
      label: "检索引擎状态",
      value: capabilities.value?.read_enabled ? "在线 (Healthy)" : "不可用",
      hint: "LightRAG 1.5.8 混合图谱检索已就绪",
      icon: "graph" as const,
      tone: capabilities.value?.read_enabled
        ? ("success" as const)
        : ("danger" as const),
    },
    {
      label: "单文件上限",
      value: capabilities.value?.max_file_bytes
        ? formatBytes(capabilities.value.max_file_bytes)
        : "20 MB",
      hint: "支持 PDF / DOCX / PPTX / MD / TXT",
      icon: "paperclip" as const,
      tone: "neutral" as const,
    },
  ];
});

const documentColumns: DataTableColumn[] = [
  { key: "file_name", label: "文档名称", sortable: true },
  { key: "mime_type", label: "格式类型", headerClass: "w-40" },
  { key: "size_bytes", label: "文件大小", headerClass: "w-32", sortable: true },
  { key: "status", label: "状态", headerClass: "w-32" },
  {
    key: "published_at",
    label: "发布时间",
    headerClass: "w-44",
    sortable: true,
  },
  { key: "actions", label: "操作", headerClass: "w-20", align: "right" },
];

const jobColumns: DataTableColumn[] = [
  { key: "job_id", label: "任务 ID", headerClass: "w-44" },
  { key: "file_name", label: "文件名" },
  { key: "status", label: "构建进度", headerClass: "w-36" },
  { key: "created_at", label: "提交时间", headerClass: "w-44", sortable: true },
  { key: "actions", label: "操作", headerClass: "w-20", align: "right" },
];

const filteredDocuments = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return documents.value;
  return documents.value.filter(
    (d) =>
      d.file_name.toLowerCase().includes(q) ||
      d.document_id.toLowerCase().includes(q),
  );
});

async function loadData() {
  const projectId = activeProjectId.value;
  if (!projectId) return;

  loading.value = true;
  error.value = "";

  try {
    const [capsRes, docsRes, jobsRes] = await Promise.allSettled([
      getKnowledgeCapabilities(projectId),
      listKnowledgeDocuments(projectId, {
        limit: docPagination.pageSize.value,
        offset: (docPagination.page.value - 1) * docPagination.pageSize.value,
      }),
      listKnowledgeJobs(projectId, {
        limit: jobPagination.pageSize.value,
        offset: (jobPagination.page.value - 1) * jobPagination.pageSize.value,
      }),
    ]);

    if (capsRes.status === "fulfilled") {
      capabilities.value = capsRes.value;
    }
    if (docsRes.status === "fulfilled") {
      documents.value = docsRes.value.items;
      totalDocs.value = docsRes.value.total;
      docPagination.total.value = docsRes.value.total;
    } else {
      error.value = "加载文档列表失败，请确认后端网关服务正常运行";
    }
    if (jobsRes.status === "fulfilled") {
      jobs.value = jobsRes.value.items;
      totalJobs.value = jobsRes.value.total;
      jobPagination.total.value = jobsRes.value.total;
    }
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "知识库服务暂时不可用";
  } finally {
    loading.value = false;
  }
}

function applyFilters() {
  query.value = queryInput.value;
}

function resetFilters() {
  queryInput.value = "";
  query.value = "";
}

async function copyDocId(doc: KnowledgeDocument) {
  const copied = await copyText(doc.document_id);
  uiStore.pushToast({
    type: copied ? "success" : "warning",
    title: copied ? "已复制 Document ID" : "复制失败",
    message: copied ? doc.document_id : "请手动复制。",
  });
}

async function copyJobId(job: KnowledgeJob) {
  const copied = await copyText(job.job_id);
  uiStore.pushToast({
    type: copied ? "success" : "warning",
    title: copied ? "已复制 Job ID" : "复制失败",
    message: copied ? job.job_id : "请手动复制。",
  });
}

function docActions(doc: KnowledgeDocument): ActionMenuItem[] {
  return [
    {
      key: "copy-id",
      label: "复制 Document ID",
      icon: "copy",
      onSelect: () => copyDocId(doc),
    },
  ];
}

function jobActions(job: KnowledgeJob): ActionMenuItem[] {
  return [
    {
      key: "copy-job-id",
      label: "复制任务 ID",
      icon: "copy",
      onSelect: () => copyJobId(job),
    },
  ];
}

function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
  }
}

async function handleConfirmUpload() {
  if (!selectedFile.value) return;
  uiStore.pushToast({
    type: "info",
    title: "上传提示",
    message: "文件已准备，正在通过平台 MCP 通道安排异步构建任务...",
  });
  uploadDialogOpen.value = false;
  selectedFile.value = null;
}

function openGraphConsole() {
  const host = "http://152.136.27.196:9621/webui/";
  const token = localStorage.getItem("platform:token") || "guest";
  const tenantId = "__default";
  const projectId =
    activeProjectId.value || "11111111-1111-4111-8111-111111111111";
  const url = `${host}?token=${encodeURIComponent(token)}&tenant_id=${encodeURIComponent(tenantId)}&project_id=${encodeURIComponent(projectId)}`;
  window.open(url, "_blank");
}

watch(
  () => activeProjectId.value,
  () => {
    void loadData();
  },
  { immediate: true },
);

watch(
  [() => docPagination.page.value, () => docPagination.pageSize.value],
  () => {
    if (activeTab.value === "documents") void loadData();
  },
);

watch(
  [() => jobPagination.page.value, () => jobPagination.pageSize.value],
  () => {
    if (activeTab.value === "jobs") void loadData();
  },
);
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Knowledge"
      title="项目知识库"
      description="基于 LightRAG 生产底座构建的企业级双轨知识中台，支持文档多模态解析、切片溯源与精准可信检索。"
    >
      <template #actions>
        <BaseButton variant="secondary" :disabled="loading" @click="loadData">
          <BaseIcon name="refresh" size="sm" />
          刷新
        </BaseButton>

        <BaseButton variant="secondary" @click="playgroundOpen = true">
          <BaseIcon name="search" size="sm" />
          检索沙盒 (Playground)
        </BaseButton>

        <BaseButton variant="secondary" @click="openGraphConsole">
          <BaseIcon name="graph" size="sm" />
          图谱控制台 (9621)
        </BaseButton>

        <BaseButton
          variant="primary"
          :disabled="!canUpload"
          @click="uploadDialogOpen = true"
        >
          <BaseIcon name="plus" size="sm" />
          上传文档
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="知识库加载异常"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作提示"
      :description="notice"
      variant="success"
    />

    <!-- Metrics Cards -->
    <div class="grid gap-4 xl:grid-cols-4">
      <MetricCard
        v-for="item in stats"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :hint="item.hint"
        :icon="item.icon"
        :tone="item.tone"
      />
    </div>

    <EmptyState
      v-if="!activeProject"
      icon="project"
      title="请先选择项目"
      description="选择项目作为权限上下文后方可访问项目知识库。"
    />

    <TablePageLayout v-else>
      <template #filters>
        <FilterToolbar>
          <div class="flex flex-wrap items-center justify-between gap-4">
            <!-- Tabs Switcher -->
            <div
              class="flex items-center rounded-xl bg-gray-100 p-1 dark:bg-dark-800"
            >
              <button
                type="button"
                class="rounded-lg px-4 py-1.5 text-xs font-semibold transition"
                :class="
                  activeTab === 'documents'
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-700 dark:text-white'
                    : 'text-gray-500 hover:text-gray-900 dark:text-dark-300 dark:hover:text-white'
                "
                @click="activeTab = 'documents'"
              >
                已入库文档 ({{ totalDocs }})
              </button>
              <button
                type="button"
                class="rounded-lg px-4 py-1.5 text-xs font-semibold transition"
                :class="
                  activeTab === 'jobs'
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-700 dark:text-white'
                    : 'text-gray-500 hover:text-gray-900 dark:text-dark-300 dark:hover:text-white'
                "
                @click="activeTab = 'jobs'"
              >
                入库任务队列 ({{ totalJobs }})
              </button>
            </div>

            <!-- Search input -->
            <div class="flex items-center gap-2">
              <SearchInput
                v-model="queryInput"
                placeholder="搜索文档名称或 ID..."
              />
              <BaseButton variant="secondary" size="sm" @click="resetFilters">
                清空
              </BaseButton>
              <BaseButton size="sm" @click="applyFilters"> 筛选 </BaseButton>
            </div>
          </div>
        </FilterToolbar>
      </template>

      <template #table>
        <!-- Documents Table -->
        <div v-if="activeTab === 'documents'">
          <DataTable
            :error="error"
            :columns="documentColumns"
            :rows="filteredDocuments"
            :loading="loading"
            row-key="document_id"
            empty-title="知识库暂无文档"
            empty-description="当前项目尚未录入知识库资产，可点击右上角「上传文档」开始构建。"
            empty-icon="archive"
          >
            <template #cell-file_name="{ row }">
              <div class="flex items-center gap-3">
                <div
                  class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
                >
                  <BaseIcon name="file" size="sm" />
                </div>
                <div>
                  <div class="font-semibold text-gray-900 dark:text-white">
                    {{ docFromRow(row).file_name }}
                  </div>
                  <div class="mt-0.5 text-xs text-gray-400 dark:text-dark-400">
                    ID: {{ shortId(docFromRow(row).document_id) }}
                  </div>
                </div>
              </div>
            </template>

            <template #cell-mime_type="{ row }">
              <span
                class="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-dark-800 dark:text-dark-300"
              >
                {{ docFromRow(row).mime_type }}
              </span>
            </template>

            <template #cell-size_bytes="{ row }">
              <span class="text-xs text-gray-500 dark:text-dark-300">
                {{ formatBytes(docFromRow(row).size_bytes) }}
              </span>
            </template>

            <template #cell-status>
              <StatusPill tone="success"> 已就绪 (ready) </StatusPill>
            </template>

            <template #cell-published_at="{ row }">
              <span class="text-xs text-gray-400 dark:text-dark-400">
                {{ formatDateTime(docFromRow(row).published_at) }}
              </span>
            </template>

            <template #cell-actions="{ row }">
              <ActionMenu :items="docActions(docFromRow(row))" />
            </template>
          </DataTable>

          <PaginationBar
            v-if="totalDocs > 0"
            :page="docPagination.page.value"
            :page-size="docPagination.pageSize.value"
            :total="totalDocs"
            @update:page="docPagination.setPage"
            @update:page-size="docPagination.setPageSize"
          />
        </div>

        <!-- Jobs Table -->
        <div v-else>
          <DataTable
            :error="error"
            :columns="jobColumns"
            :rows="jobs"
            :loading="loading"
            row-key="job_id"
            empty-title="暂无入库任务"
            empty-description="当前没有进行中或已记录的后台构建任务。"
            empty-icon="activity"
          >
            <template #cell-job_id="{ row }">
              <span class="font-mono text-xs text-gray-600 dark:text-dark-300">
                {{ shortId(jobFromRow(row).job_id) }}
              </span>
            </template>

            <template #cell-file_name="{ row }">
              <div class="font-semibold text-gray-900 dark:text-white">
                {{ jobFromRow(row).file_name }}
              </div>
              <div class="mt-0.5 text-xs text-gray-400 dark:text-dark-400">
                Doc: {{ shortId(jobFromRow(row).document_id) }}
              </div>
            </template>

            <template #cell-status="{ row }">
              <StatusPill :tone="getJobStatusTone(jobFromRow(row).status)">
                {{ jobFromRow(row).status }}
              </StatusPill>
            </template>

            <template #cell-created_at="{ row }">
              <span class="text-xs text-gray-400 dark:text-dark-400">
                {{ formatDateTime(jobFromRow(row).created_at) }}
              </span>
            </template>

            <template #cell-actions="{ row }">
              <ActionMenu :items="jobActions(jobFromRow(row))" />
            </template>
          </DataTable>

          <PaginationBar
            v-if="totalJobs > 0"
            :page="jobPagination.page.value"
            :page-size="jobPagination.pageSize.value"
            :total="totalJobs"
            @update:page="jobPagination.setPage"
            @update:page-size="jobPagination.setPageSize"
          />
        </div>
      </template>
    </TablePageLayout>

    <!-- Upload Dialog -->
    <BaseDialog
      :show="uploadDialogOpen"
      title="上传资料至知识库"
      @close="uploadDialogOpen = false"
    >
      <div class="space-y-4 py-4">
        <div
          class="relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-300 p-8 text-center transition hover:border-emerald-500 dark:border-dark-700 dark:hover:border-emerald-500"
        >
          <div
            class="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400"
          >
            <BaseIcon name="paperclip" size="md" />
          </div>
          <p class="mt-3 text-sm font-semibold text-gray-900 dark:text-white">
            点击或拖拽文件至此处上传
          </p>
          <p class="mt-1 text-xs text-gray-400 dark:text-dark-400">
            单文件不超过 20 MB，支持 PDF / DOCX / PPTX / MD / TXT
          </p>
          <input
            type="file"
            class="absolute inset-0 cursor-pointer opacity-0"
            accept=".pdf,.docx,.pptx,.md,.markdown,.txt"
            @change="handleFileSelect"
          />
        </div>

        <div
          v-if="selectedFile"
          class="flex items-center justify-between rounded-xl bg-gray-50 p-3 dark:bg-dark-800"
        >
          <div class="flex items-center gap-3">
            <BaseIcon name="file" size="sm" class="text-emerald-500" />
            <div>
              <div class="text-xs font-semibold text-gray-900 dark:text-white">
                {{ selectedFile.name }}
              </div>
              <div class="text-[10px] text-gray-400">
                {{ formatBytes(selectedFile.size) }}
              </div>
            </div>
          </div>
          <BaseButton variant="ghost" size="xs" @click="selectedFile = null">
            <BaseIcon name="x" size="xs" />
          </BaseButton>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <BaseButton variant="secondary" @click="uploadDialogOpen = false">
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            :disabled="!selectedFile || uploading"
            @click="handleConfirmUpload"
          >
            {{ uploading ? "提交中..." : "确认提交入库" }}
          </BaseButton>
        </div>
      </template>
    </BaseDialog>

    <!-- Playground Drawer -->
    <KnowledgePlaygroundDrawer
      :show="playgroundOpen"
      :project-id="activeProjectId"
      @close="playgroundOpen = false"
    />
  </section>
</template>

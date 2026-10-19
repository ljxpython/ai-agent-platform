<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import {
  getKnowledgeCapabilities,
  listKnowledgeDocuments,
  listKnowledgeJobs,
  type KnowledgeCapabilities,
  type KnowledgeDocument,
  type KnowledgeJob,
  type KnowledgeStatus,
} from "@/services/knowledge/knowledge.service";
import { useKnowledgeJobTracker } from "@/composables/useKnowledgeJobTracker";

const props = defineProps<{
  projectId: string;
}>();

const router = useRouter();
const tracker = useKnowledgeJobTracker();

function navigateToKnowledgeCenter(): void {
  void router?.push({
    name: "workspace-project-knowledge",
    params: { projectId: props.projectId },
  });
}

// 当前子视图：'documents' | 'jobs'
const activeSubTab = ref<"documents" | "jobs">("documents");

const capabilities = ref<KnowledgeCapabilities | null>(null);
const loadingCaps = ref(false);
const capsError = ref("");

// Documents 状态
const documents = ref<KnowledgeDocument[]>([]);
const documentsTotal = ref(0);
const documentsOffset = ref(0);
const documentsLimit = 20;
const loadingDocs = ref(false);
const docsError = ref("");

// Jobs 状态
const jobs = ref<KnowledgeJob[]>([]);
const jobsTotal = ref(0);
const jobsOffset = ref(0);
const jobsLimit = 20;
const loadingJobs = ref(false);
const jobsError = ref("");

let activeAbortController: AbortController | null = null;

function formatBytes(bytes?: number): string {
  if (bytes == null || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(isoStr?: string): string {
  if (!isoStr) return "--";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("zh-CN", {
      hour12: false,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

function getStatusBadge(
  status: KnowledgeStatus,
  searchable?: boolean,
): {
  label: string;
  class: string;
} {
  switch (status) {
    case "queued":
      return {
        label: "排队中",
        class:
          "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800",
      };
    case "parsing":
      return {
        label: "正在解析",
        class:
          "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800",
      };
    case "indexing":
      return {
        label: "正在建立索引",
        class:
          "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800",
      };
    case "publishing":
      return {
        label: "正在发布",
        class:
          "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
      };
    case "ready":
      if (searchable === false) {
        return {
          label: "已处理（暂不可查）",
          class:
            "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
        };
      }
      return {
        label: "已就绪",
        class:
          "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
      };
    case "failed":
      return {
        label: "处理失败",
        class:
          "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800",
      };
    default:
      return {
        label: status,
        class:
          "bg-slate-50 text-slate-700 border-border dark:bg-dark-800 dark:text-dark-300",
      };
  }
}

function getErrorDesc(code: string | null): string {
  if (!code) return "--";
  if (code.includes("disabled") || code.includes("not_configured"))
    return "未启用知识库";
  if (code.includes("denied")) return "无权限上传";
  if (code.includes("unsupported") || code.includes("format"))
    return "格式不支持";
  if (code.includes("too_large")) return "超出文件/图片上限";
  if (code.includes("queue_full") || code.includes("quota"))
    return "队列已满或超额";
  return code;
}

async function fetchCapabilities() {
  if (!props.projectId) return;
  loadingCaps.value = true;
  capsError.value = "";
  try {
    capabilities.value = await getKnowledgeCapabilities(props.projectId);
  } catch (err: unknown) {
    capsError.value = (err as Error)?.message || "无法获取知识库能力配置";
  } finally {
    loadingCaps.value = false;
  }
}

async function loadDocuments() {
  if (!props.projectId) return;
  loadingDocs.value = true;
  docsError.value = "";
  const currentPid = props.projectId;
  try {
    const page = await listKnowledgeDocuments(
      currentPid,
      {
        limit: documentsLimit,
        offset: documentsOffset.value,
      },
      activeAbortController?.signal,
    );
    if (props.projectId === currentPid) {
      documents.value = page.items;
      documentsTotal.value = page.total;
    }
  } catch (err: unknown) {
    if (
      (err as Error)?.name !== "AbortError" &&
      props.projectId === currentPid
    ) {
      docsError.value = (err as Error)?.message || "加载资料列表失败";
    }
  } finally {
    if (props.projectId === currentPid) {
      loadingDocs.value = false;
    }
  }
}

async function loadJobs() {
  if (!props.projectId) return;
  loadingJobs.value = true;
  jobsError.value = "";
  const currentPid = props.projectId;
  try {
    const page = await listKnowledgeJobs(
      currentPid,
      {
        limit: jobsLimit,
        offset: jobsOffset.value,
      },
      activeAbortController?.signal,
    );
    if (props.projectId === currentPid) {
      jobs.value = page.items;
      jobsTotal.value = page.total;

      // 注册非终态任务至 Tracker
      for (const item of page.items) {
        if (
          ["queued", "parsing", "indexing", "publishing"].includes(item.status)
        ) {
          tracker.trackJob(currentPid, item.job_id, item);
        }
      }
    }
  } catch (err: unknown) {
    if (
      (err as Error)?.name !== "AbortError" &&
      props.projectId === currentPid
    ) {
      jobsError.value = (err as Error)?.message || "加载任务历史失败";
    }
  } finally {
    if (props.projectId === currentPid) {
      loadingJobs.value = false;
    }
  }
}

async function handleRefresh() {
  await fetchCapabilities();
  if (activeSubTab.value === "documents") {
    await loadDocuments();
  } else {
    await loadJobs();
  }
}

function handleDocsPageChange(delta: number) {
  const next = documentsOffset.value + delta * documentsLimit;
  if (next >= 0 && next < documentsTotal.value) {
    documentsOffset.value = next;
    void loadDocuments();
  }
}

function handleJobsPageChange(delta: number) {
  const next = jobsOffset.value + delta * jobsLimit;
  if (next >= 0 && next < jobsTotal.value) {
    jobsOffset.value = next;
    void loadJobs();
  }
}

watch(
  () => props.projectId,
  (newPid) => {
    if (activeAbortController) {
      activeAbortController.abort();
    }
    activeAbortController = new AbortController();

    documents.value = [];
    documentsOffset.value = 0;
    documentsTotal.value = 0;
    jobs.value = [];
    jobsOffset.value = 0;
    jobsTotal.value = 0;

    if (newPid) {
      void fetchCapabilities().then(() => {
        void loadDocuments();
        void loadJobs();
      });
    }
  },
  { immediate: true },
);

watch(activeSubTab, (tab) => {
  if (tab === "documents") {
    void loadDocuments();
  } else {
    void loadJobs();
  }
});

onUnmounted(() => {
  if (activeAbortController) {
    activeAbortController.abort();
    activeAbortController = null;
  }
});
</script>

<template>
  <div class="space-y-6">
    <!-- 能力与状态横幅 -->
    <StateBanner
      v-if="capabilities && !capabilities.read_enabled"
      variant="warning"
      title="当前项目未启用知识库检索能力"
      description="知识库读写服务尚未开启或不可用，请联系管理员在平台控制台配置。"
    />

    <!-- 知识中台专属导航引导区（方案 A 交互收敛） -->
    <div
      class="flex flex-col gap-4 rounded-xl border border-primary-200/80 bg-gradient-to-r from-primary-50/70 via-slate-50 to-primary-50/30 p-4.5 dark:border-primary-900/40 dark:from-primary-950/20 dark:via-dark-900 dark:to-primary-950/10 sm:flex-row sm:items-center sm:justify-between"
    >
      <div class="flex items-start gap-3">
        <div
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-100 text-primary-600 dark:bg-primary-900/50 dark:text-primary-300"
        >
          <BaseIcon name="graph" size="md" />
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-text-main">
              项目专属 LightRAG 知识中台
            </h3>
            <span
              v-if="capabilities?.read_enabled"
              class="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800"
            >
              底座在线 (Healthy)
            </span>
            <span
              v-else
              class="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-text-sub border border-border dark:bg-dark-800"
            >
              未配置/离线
            </span>
          </div>
          <p class="mt-1 text-xs text-text-sub">
            当前项目详情仅保留轻量资料一览。完整的文档批量上传、切片溯源、检索沙盒
            (Playground) 与 9621 图谱控制台已集中收敛至左侧知识库中台。
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2 shrink-0">
        <BaseButton
          variant="primary"
          size="sm"
          class="shadow-xs whitespace-nowrap"
          data-testid="go-to-knowledge-center-btn"
          @click="navigateToKnowledgeCenter"
        >
          <BaseIcon name="chevron-right" size="xs" />
          <span>打开项目知识库中台</span>
        </BaseButton>
      </div>
    </div>

    <SurfaceCard>
      <!-- 头部：标题、统计与子Tab切换 -->
      <div
        class="flex flex-col gap-4 border-b border-border/80 pb-5 md:flex-row md:items-center md:justify-between"
      >
        <div>
          <h2
            class="text-base font-semibold text-text-main flex items-center gap-2"
          >
            <BaseIcon name="folder" size="sm" class="text-primary-600" />
            项目知识库管理
          </h2>
          <p class="mt-1 text-xs text-text-sub">
            所有项目成员均可检索已入库资料；支持文档（TXT/MD/PDF/DOCX/PPTX）与图片（PNG/JPEG，≤5MiB），单文档上限
            20MB。
          </p>
        </div>

        <div class="flex items-center gap-3">
          <!-- 子视图切换按钮组 -->
          <div
            class="inline-flex rounded-lg border border-border bg-slate-50 p-1 dark:bg-dark-800"
          >
            <button
              type="button"
              class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
              :class="
                activeSubTab === 'documents'
                  ? 'bg-white text-primary-700 shadow-xs dark:bg-dark-900 dark:text-primary-300'
                  : 'text-text-sub hover:text-text-main'
              "
              @click="activeSubTab = 'documents'"
            >
              已发布资料 ({{ documentsTotal }})
            </button>
            <button
              type="button"
              class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
              :class="
                activeSubTab === 'jobs'
                  ? 'bg-white text-primary-700 shadow-xs dark:bg-dark-900 dark:text-primary-300'
                  : 'text-text-sub hover:text-text-main'
              "
              @click="activeSubTab = 'jobs'"
            >
              入库任务历史 ({{ jobsTotal }})
            </button>
          </div>

          <BaseButton
            variant="secondary"
            size="sm"
            :loading="loadingDocs || loadingJobs || loadingCaps"
            @click="handleRefresh"
          >
            <BaseIcon name="refresh" size="xs" />
            <span>刷新</span>
          </BaseButton>
        </div>
      </div>

      <!-- 视图 1：已发布资料列表 (Documents) -->
      <div v-if="activeSubTab === 'documents'" class="pt-4">
        <StateBanner
          v-if="docsError"
          variant="danger"
          title="资料加载失败"
          :description="docsError"
          class="mb-4"
        />

        <div
          v-if="loadingDocs && !documents.length"
          class="py-12 text-center text-xs text-text-sub"
        >
          正在加载项目知识库资料……
        </div>

        <EmptyState
          v-else-if="!documents.length"
          icon="folder"
          title="暂无已发布知识资料"
          description="普通项目成员可在聊天界面上传 TXT 或 Markdown 附件，并勾选“共享至项目知识库”提交入库。"
          action-label="打开知识中台上传文档"
          @action="navigateToKnowledgeCenter"
        />

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead>
              <tr
                class="border-b border-border/80 text-[11px] font-medium text-text-sub"
              >
                <th class="py-2.5 pr-4">文件名</th>
                <th class="py-2.5 px-4">格式</th>
                <th class="py-2.5 px-4">体积</th>
                <th class="py-2.5 px-4">检索状态</th>
                <th class="py-2.5 pl-4">发布时间</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border/60">
              <tr
                v-for="doc in documents"
                :key="doc.document_id"
                class="hover:bg-slate-50/60 dark:hover:bg-dark-800/40 transition-colors"
              >
                <td class="py-3 pr-4 font-medium text-text-main">
                  <div class="flex items-center gap-2">
                    <BaseIcon
                      name="file"
                      size="xs"
                      class="text-primary-500 shrink-0"
                    />
                    <span class="truncate max-w-[280px]" :title="doc.file_name">
                      {{ doc.file_name }}
                    </span>
                  </div>
                </td>
                <td class="py-3 px-4 font-mono text-text-sub text-[11px]">
                  {{ doc.mime_type }}
                </td>
                <td class="py-3 px-4 text-text-sub">
                  {{ formatBytes(doc.size_bytes) }}
                </td>
                <td class="py-3 px-4">
                  <span
                    class="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                  >
                    <span
                      class="h-1.5 w-1.5 rounded-full bg-emerald-500"
                    ></span>
                    当前可检索
                  </span>
                </td>
                <td class="py-3 pl-4 text-text-sub">
                  {{ formatDate(doc.published_at) }}
                </td>
              </tr>
            </tbody>
          </table>

          <!-- 分页器 -->
          <div
            class="mt-4 flex items-center justify-between border-t border-border/60 pt-3 text-xs text-text-sub"
          >
            <span>共 {{ documentsTotal }} 项资料</span>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="rounded border border-border px-2 py-1 text-xs disabled:opacity-40"
                :disabled="documentsOffset === 0 || loadingDocs"
                @click="handleDocsPageChange(-1)"
              >
                上一页
              </button>
              <span
                >第
                {{ Math.floor(documentsOffset / documentsLimit) + 1 }} 页</span
              >
              <button
                type="button"
                class="rounded border border-border px-2 py-1 text-xs disabled:opacity-40"
                :disabled="
                  documentsOffset + documentsLimit >= documentsTotal ||
                  loadingDocs
                "
                @click="handleDocsPageChange(1)"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 视图 2：入库任务历史 (Jobs) -->
      <div v-else class="pt-4">
        <StateBanner
          v-if="jobsError"
          variant="danger"
          title="任务历史加载失败"
          :description="jobsError"
          class="mb-4"
        />

        <div
          v-if="loadingJobs && !jobs.length"
          class="py-12 text-center text-xs text-text-sub"
        >
          正在加载入库任务历史……
        </div>

        <EmptyState
          v-else-if="!jobs.length"
          icon="clock"
          title="暂无入库任务记录"
          description="用户在会话中发起共享提交后，异步任务受理与各阶段进度记录将展示在此处。"
          action-label="进入知识中台查看全局任务"
          @action="navigateToKnowledgeCenter"
        />

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-xs">
            <thead>
              <tr
                class="border-b border-border/80 text-[11px] font-medium text-text-sub"
              >
                <th class="py-2.5 pr-4">文件名</th>
                <th class="py-2.5 px-4">任务编号</th>
                <th class="py-2.5 px-4">处理状态</th>
                <th class="py-2.5 px-4">检索能力</th>
                <th class="py-2.5 px-4">异常说明</th>
                <th class="py-2.5 pl-4">提交时间</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border/60">
              <tr
                v-for="job in jobs"
                :key="job.job_id"
                class="hover:bg-slate-50/60 dark:hover:bg-dark-800/40 transition-colors"
              >
                <td class="py-3 pr-4 font-medium text-text-main">
                  <div class="flex items-center gap-2">
                    <BaseIcon
                      name="file"
                      size="xs"
                      class="text-text-sub shrink-0"
                    />
                    <span class="truncate max-w-[200px]" :title="job.file_name">
                      {{ job.file_name }}
                    </span>
                  </div>
                </td>
                <td class="py-3 px-4 font-mono text-[11px] text-text-sub">
                  {{ job.job_id }}
                </td>
                <td class="py-3 px-4">
                  <span
                    class="inline-block rounded-md border px-2 py-0.5 text-[10px] font-medium"
                    :class="getStatusBadge(job.status, job.searchable).class"
                  >
                    {{ getStatusBadge(job.status, job.searchable).label }}
                  </span>
                </td>
                <td class="py-3 px-4">
                  <span
                    v-if="job.searchable"
                    class="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium"
                  >
                    <span
                      class="h-1.5 w-1.5 rounded-full bg-emerald-500"
                    ></span>
                    可检索
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1 text-[11px] text-slate-400 dark:text-dark-400"
                  >
                    <span class="h-1.5 w-1.5 rounded-full bg-slate-300"></span>
                    不可查
                  </span>
                </td>
                <td class="py-3 px-4 text-text-sub text-[11px]">
                  {{ getErrorDesc(job.error_code) }}
                </td>
                <td class="py-3 pl-4 text-text-sub">
                  {{ formatDate(job.created_at) }}
                </td>
              </tr>
            </tbody>
          </table>

          <!-- 分页器 -->
          <div
            class="mt-4 flex items-center justify-between border-t border-border/60 pt-3 text-xs text-text-sub"
          >
            <span>共 {{ jobsTotal }} 项任务</span>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="rounded border border-border px-2 py-1 text-xs disabled:opacity-40"
                :disabled="jobsOffset === 0 || loadingJobs"
                @click="handleJobsPageChange(-1)"
              >
                上一页
              </button>
              <span>第 {{ Math.floor(jobsOffset / jobsLimit) + 1 }} 页</span>
              <button
                type="button"
                class="rounded border border-border px-2 py-1 text-xs disabled:opacity-40"
                :disabled="jobsOffset + jobsLimit >= jobsTotal || loadingJobs"
                @click="handleJobsPageChange(1)"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </SurfaceCard>
  </div>
</template>

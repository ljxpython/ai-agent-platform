<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatThread,
} from "@/services/threads/session.service";
import {
  downloadThreadFile,
  previewThreadFileInNewTab,
  type RuntimeFileRef,
} from "@/services/threads/files.service";
import {
  getThreadImageBlob,
  type RuntimeImageRef,
} from "@/services/threads/images.service";
import { formatThreadTime } from "@/utils/threads";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseButton from "@/components/base/BaseButton.vue";

export type ArtifactCategory = "all" | "document" | "code_data" | "chart_media" | "presentation";

export interface SessionArtifactItem {
  id: string;
  name: string;
  path: string;
  category: "document" | "code_data" | "chart_media" | "presentation";
  extension: string;
  sizeBytes?: number;
  sha256?: string;
  isBinary: boolean;
  isImage: boolean;
  isPresentation: boolean;
  threadId: string;
  runId?: string;
  step?: string;
  time?: string;
}

const route = useRoute();
const router = useRouter();
const { activeProjectId } = useWorkspaceProjectContext();

const service = computed(() =>
  createSessionService(createLanggraphAuthorizedFetch()),
);

// 会话列表状态
const threads = ref<ChatThread[]>([]);
const listLoading = ref(false);
const listError = ref("");
const threadSearch = ref("");
const selectedThreadId = ref<string>("");

// 成果列表状态
const artifactsLoading = ref(false);
const artifactsError = ref("");
const artifacts = ref<SessionArtifactItem[]>([]);
const selectedCategory = ref<ArtifactCategory>("all");
const artifactSearch = ref("");
const downloadingPath = ref<string | null>(null);
const copiedHash = ref<string | null>(null);

// 过滤后的会话
const filteredThreads = computed(() => {
  const q = threadSearch.value.trim().toLowerCase();
  if (!q) return threads.value;
  return threads.value.filter((t) => {
    const title = String(t.metadata?.title || "").toLowerCase();
    const id = t.thread_id.toLowerCase();
    return title.includes(q) || id.includes(q);
  });
});

// 选中的会话详情
const currentThread = computed(() =>
  threads.value.find((t) => t.thread_id === selectedThreadId.value),
);

// 分类筛选成果
const filteredArtifacts = computed(() => {
  let list = artifacts.value;
  if (selectedCategory.value !== "all") {
    list = list.filter((a) => a.category === selectedCategory.value);
  }
  const q = artifactSearch.value.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.path.toLowerCase().includes(q) ||
        (a.sha256 && a.sha256.toLowerCase().includes(q)),
    );
  }
  return list;
});

// 统计各分类数量
const categoryCounts = computed(() => {
  const counts = {
    all: artifacts.value.length,
    document: 0,
    code_data: 0,
    chart_media: 0,
    presentation: 0,
  };
  for (const a of artifacts.value) {
    counts[a.category]++;
  }
  return counts;
});

// 加载 Dear 会话列表
async function loadThreads() {
  if (!activeProjectId.value) return;
  listLoading.value = true;
  listError.value = "";
  try {
    const rows = await service.value.list({
      offset: 0,
      metadata: { graph_id: "dearflow_agent" },
    });
    threads.value = rows.filter(
      (t) => !t.metadata?.graph_id || t.metadata.graph_id === "dearflow_agent",
    );

    // 确定选中的会话 ID
    const routeThreadId = route.query.threadId as string;
    if (routeThreadId && threads.value.some((t) => t.thread_id === routeThreadId)) {
      selectedThreadId.value = routeThreadId;
    } else if (threads.value.length > 0 && !selectedThreadId.value) {
      selectedThreadId.value = threads.value[0].thread_id;
    }
  } catch (err) {
    listError.value = err instanceof Error ? err.message : "获取会话列表失败";
  } finally {
    listLoading.value = false;
  }
}

// 解析成果类型
function categorizePath(filePath: string): "document" | "code_data" | "chart_media" | "presentation" {
  const lower = filePath.toLowerCase();
  if (lower.endsWith(".pptx")) return "presentation";
  if (
    lower.endsWith(".png") ||
    lower.endsWith(".jpg") ||
    lower.endsWith(".jpeg") ||
    lower.endsWith(".webp") ||
    filePath.includes("/workspace/charts/") ||
    filePath.includes("/workspace/generated/")
  ) {
    return "chart_media";
  }
  if (
    lower.endsWith(".zip") ||
    lower.endsWith(".csv") ||
    lower.endsWith(".xlsx") ||
    lower.endsWith(".xls") ||
    lower.endsWith(".sql") ||
    lower.endsWith(".html") ||
    lower.endsWith(".css") ||
    lower.endsWith(".js") ||
    lower.endsWith(".py") ||
    lower.endsWith(".ts") ||
    lower.endsWith(".json")
  ) {
    return "code_data";
  }
  return "document";
}

function isBinaryExtension(ext: string): boolean {
  return [".zip", ".xlsx", ".xls", ".pptx", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bin"].includes(
    ext.toLowerCase(),
  );
}

// 加载选中会话的成果交付物
async function loadSessionArtifacts(threadId: string) {
  if (!activeProjectId.value || !threadId) {
    artifacts.value = [];
    return;
  }
  artifactsLoading.value = true;
  artifactsError.value = "";
  try {
    const history = await service.value.history(threadId);
    const discovered = new Map<string, SessionArtifactItem>();

    // 遍历历史检查点中的消息与工具调用
    for (const entry of history) {
      const values = (entry.values || {}) as Record<string, unknown>;
      const messages = Array.isArray(values.messages) ? values.messages : [];
      const rawEntry = entry as unknown as Record<string, unknown>;
      const step = typeof rawEntry.metadata === "object" &&
        rawEntry.metadata !== null &&
        (rawEntry.metadata as Record<string, unknown>).step !== undefined
        ? `Step ${(rawEntry.metadata as Record<string, unknown>).step}`
        : undefined;
      const rawCheckpoint = rawEntry.checkpoint as Record<string, unknown> | undefined;
      const checkpointId = String(rawEntry.checkpoint_id || rawCheckpoint?.checkpoint_id || "");
      const time = checkpointId ? formatThreadTime(checkpointId) : undefined;

      for (const msg of messages) {
        if (!msg || typeof msg !== "object") continue;
        const rawMsg = msg as Record<string, unknown>;

        // 1. 检查 contentBlocks / content 中的 extras 与 fileRef / imageRef
        const blocks = Array.isArray(rawMsg.contentBlocks)
          ? rawMsg.contentBlocks
          : Array.isArray(rawMsg.content)
            ? rawMsg.content
            : [];

        for (const block of blocks) {
          if (!block || typeof block !== "object") continue;
          const b = block as Record<string, unknown>;

          // 从 extras 中解析
          const extras = (b.extras || {}) as Record<string, unknown>;
          if (extras.runtime_file && typeof extras.runtime_file === "object") {
            const rf = extras.runtime_file as RuntimeFileRef;
            if (rf.path && rf.path.startsWith("/workspace/outputs/")) {
              const ext = "." + (rf.file_name?.split(".").pop() || rf.path.split(".").pop() || "txt");
              discovered.set(rf.path, {
                id: rf.path,
                name: rf.file_name || rf.path.split("/").pop() || "output",
                path: rf.path,
                category: categorizePath(rf.path),
                extension: ext,
                sizeBytes: rf.size_bytes,
                sha256: rf.sha256,
                isBinary: isBinaryExtension(ext),
                isImage: false,
                isPresentation: ext.toLowerCase() === ".pptx",
                threadId,
                step,
                time,
              });
            }
          }

          if (extras.runtime_image && typeof extras.runtime_image === "object") {
            const ri = extras.runtime_image as RuntimeImageRef;
            if (ri.path && (ri.path.startsWith("/workspace/outputs/") || ri.path.includes("/workspace/charts/") || ri.path.includes("/workspace/generated/"))) {
              const ext = "." + (ri.path.split(".").pop() || "png");
              discovered.set(ri.path, {
                id: ri.path,
                name: ri.path.split("/").pop() || "chart.png",
                path: ri.path,
                category: "chart_media",
                extension: ext,
                sizeBytes: ri.size_bytes,
                sha256: ri.sha256,
                isBinary: true,
                isImage: true,
                isPresentation: false,
                threadId,
                step,
                time,
              });
            }
          }
        }

        // 2. 文本中正则扫描受控输出路径
        const textContent =
          typeof rawMsg.content === "string"
            ? rawMsg.content
            : JSON.stringify(rawMsg.content || "");
        const outputMatches = textContent.match(/\/workspace\/outputs\/[a-zA-Z0-9_.-]+/g) || [];
        for (const p of outputMatches) {
          if (!discovered.has(p)) {
            const ext = "." + (p.split(".").pop() || "txt");
            discovered.set(p, {
              id: p,
              name: p.split("/").pop() || "file",
              path: p,
              category: categorizePath(p),
              extension: ext,
              isBinary: isBinaryExtension(ext),
              isImage: [".png", ".jpg", ".jpeg", ".webp"].includes(ext.toLowerCase()),
              isPresentation: ext.toLowerCase() === ".pptx",
              threadId,
              step,
              time,
            });
          }
        }
      }
    }

    artifacts.value = Array.from(discovered.values());
  } catch (err) {
    artifactsError.value = err instanceof Error ? err.message : "读取会话成果失败";
  } finally {
    artifactsLoading.value = false;
  }
}

// 切换会话
function selectThread(threadId: string) {
  selectedThreadId.value = threadId;
  void router.replace({
    path: route.path,
    query: { ...route.query, threadId },
  });
}

// 复制哈希
function copyHash(hash: string) {
  navigator.clipboard.writeText(hash);
  copiedHash.value = hash;
  setTimeout(() => {
    if (copiedHash.value === hash) copiedHash.value = null;
  }, 2000);
}

// 安全下载
async function handleDownload(item: SessionArtifactItem) {
  if (!activeProjectId.value || downloadingPath.value) return;
  downloadingPath.value = item.path;
  try {
    if (item.isImage) {
      const blob = await getThreadImageBlob(
        activeProjectId.value,
        item.threadId,
        item.path,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = item.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } else {
      await downloadThreadFile(
        activeProjectId.value,
        item.threadId,
        item.path,
        item.name,
      );
    }
  } catch (err) {
    alert("下载失败：" + (err instanceof Error ? err.message : "未知错误"));
  } finally {
    downloadingPath.value = null;
  }
}

// 快速预览
function handlePreview(item: SessionArtifactItem) {
  if (!activeProjectId.value) return;
  if (item.isBinary) {
    void handleDownload(item);
    return;
  }
  previewThreadFileInNewTab(activeProjectId.value, item.threadId, item.path);
}

// 格式化大小
function formatBytes(bytes?: number): string {
  if (bytes === undefined || bytes === null || bytes <= 0) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// 监听项目切换，彻底清理缓存防止数据串扰
watch(activeProjectId, () => {
  threads.value = [];
  artifacts.value = [];
  selectedThreadId.value = "";
  threadSearch.value = "";
  artifactSearch.value = "";
  void loadThreads();
});

// 监听会话切换
watch(selectedThreadId, (nextId) => {
  if (nextId) {
    void loadSessionArtifacts(nextId);
  } else {
    artifacts.value = [];
  }
});

onMounted(() => {
  void loadThreads();
});
</script>

<template>
  <div class="flex h-full w-full overflow-hidden bg-zinc-50 dark:bg-zinc-950">
    <!-- 左侧：Dear 会话切换栏 -->
    <aside class="flex w-72 shrink-0 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 lg:w-80">
      <!-- 头部 -->
      <div class="border-b border-zinc-200 p-4 dark:border-zinc-800">
        <div class="flex items-center gap-2 mb-2">
          <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-950/60 dark:text-primary-400">
            <BaseIcon name="archive" size="sm" />
          </span>
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            成果会话来源
          </h2>
        </div>
        <p class="text-[11px] text-zinc-500 dark:text-zinc-400 mb-3">
          选择具体 Dear 会话，检索其产出的正式文件与交付物
        </p>
        <BaseInput
          v-model="threadSearch"
          placeholder="搜索会话标题..."
          size="sm"
        />
      </div>

      <!-- 会话列表 -->
      <div class="flex-1 overflow-y-auto p-2 space-y-1">
        <div v-if="listLoading" class="p-4 text-center text-xs text-zinc-400">
          <BaseIcon name="refresh" size="sm" class="animate-spin inline mr-1" />
          正在读取会话...
        </div>
        <div v-else-if="listError" class="p-4 text-center text-xs text-red-500">
          {{ listError }}
        </div>
        <div v-else-if="filteredThreads.length === 0" class="p-6 text-center text-xs text-zinc-400">
          暂无 Dear 会话
        </div>
        <button
          v-for="th in filteredThreads"
          :key="th.thread_id"
          type="button"
          class="flex w-full flex-col gap-1 rounded-xl p-3 text-left text-xs transition-colors"
          :class="
            th.thread_id === selectedThreadId
              ? 'bg-primary-50 text-primary-900 font-medium dark:bg-primary-950/50 dark:text-primary-200'
              : 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800/60'
          "
          @click="selectThread(th.thread_id)"
        >
          <div class="flex items-center justify-between gap-1 w-full">
            <span class="truncate font-medium">
              {{ th.metadata?.title || "未命名会话" }}
            </span>
            <span class="text-[10px] text-zinc-400 shrink-0 font-mono">
              {{ formatThreadTime(th.updated_at) }}
            </span>
          </div>
          <span class="font-mono text-[10px] text-zinc-400 truncate w-full">
            {{ th.thread_id }}
          </span>
        </button>
      </div>
    </aside>

    <!-- 右侧：会话成果聚合浏览器 -->
    <main class="flex flex-1 flex-col overflow-hidden">
      <!-- 顶部 Header -->
      <header class="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900 shrink-0">
        <div class="space-y-0.5">
          <div class="flex items-center gap-2">
            <h1 class="text-base font-semibold text-zinc-900 dark:text-zinc-100">
              会话成果浏览器
            </h1>
            <span
              v-if="currentThread"
              class="rounded-md bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 font-mono truncate max-w-[260px]"
            >
              {{ currentThread.metadata?.title || currentThread.thread_id }}
            </span>
          </div>
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            聚合展示由 Agent 发布至 <code class="font-mono text-[11px] bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded">/workspace/outputs/</code> 的正式交付物
          </p>
        </div>

        <div class="flex items-center gap-2">
          <BaseInput
            v-model="artifactSearch"
            placeholder="搜索成果名称、路径或哈希..."
            size="sm"
            class="w-64"
          />
          <router-link
            :to="{ path: `/workspace/projects/${activeProjectId}/dear-agent/${selectedThreadId || ''}` }"
            class="inline-flex items-center gap-1 text-xs font-medium text-primary-600 hover:text-primary-700 dark:text-primary-400 px-3 py-1.5 rounded-lg border border-primary-200 hover:bg-primary-50 dark:border-primary-900 dark:hover:bg-primary-950/40"
          >
            <span>进入该会话</span>
            <BaseIcon name="chevron-right" size="xs" />
          </router-link>
        </div>
      </header>

      <!-- 分类过滤 Tab -->
      <nav class="flex items-center gap-1 border-b border-zinc-200 bg-zinc-50/60 px-6 py-2 dark:border-zinc-800 dark:bg-zinc-900/40 shrink-0 overflow-x-auto">
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0"
          :class="
            selectedCategory === 'all'
              ? 'bg-white text-zinc-900 shadow-2xs dark:bg-zinc-800 dark:text-white'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
          "
          @click="selectedCategory = 'all'"
        >
          全部成果 ({{ categoryCounts.all }})
        </button>
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0"
          :class="
            selectedCategory === 'document'
              ? 'bg-white text-zinc-900 shadow-2xs dark:bg-zinc-800 dark:text-white'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
          "
          @click="selectedCategory = 'document'"
        >
          📄 报告与文档 ({{ categoryCounts.document }})
        </button>
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0"
          :class="
            selectedCategory === 'code_data'
              ? 'bg-white text-zinc-900 shadow-2xs dark:bg-zinc-800 dark:text-white'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
          "
          @click="selectedCategory = 'code_data'"
        >
          📦 源码与数据包 ({{ categoryCounts.code_data }})
        </button>
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0"
          :class="
            selectedCategory === 'chart_media'
              ? 'bg-white text-zinc-900 shadow-2xs dark:bg-zinc-800 dark:text-white'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
          "
          @click="selectedCategory = 'chart_media'"
        >
          📊 图表与多媒体 ({{ categoryCounts.chart_media }})
        </button>
        <button
          type="button"
          class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors shrink-0"
          :class="
            selectedCategory === 'presentation'
              ? 'bg-white text-zinc-900 shadow-2xs dark:bg-zinc-800 dark:text-white'
              : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
          "
          @click="selectedCategory = 'presentation'"
        >
          📽️ 演示文稿 ({{ categoryCounts.presentation }})
        </button>
      </nav>

      <!-- 成果卡片展示网格 -->
      <section class="flex-1 overflow-y-auto p-6">
        <div v-if="artifactsLoading" class="flex h-64 items-center justify-center text-xs text-zinc-400">
          <BaseIcon name="refresh" size="md" class="animate-spin mr-2" />
          <span>正在检索会话历史成果...</span>
        </div>

        <div v-else-if="artifactsError" class="p-8 text-center text-sm text-red-500">
          {{ artifactsError }}
        </div>

        <div
          v-else-if="filteredArtifacts.length === 0"
          class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-300 py-16 text-center dark:border-zinc-800"
        >
          <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500">
            <BaseIcon name="folder" size="md" />
          </div>
          <h3 class="mt-4 text-sm font-medium text-zinc-800 dark:text-zinc-200">
            {{ artifacts.length === 0 ? "该会话暂无正式交付成果" : "无匹配成果" }}
          </h3>
          <p class="mt-1 max-w-sm text-xs text-zinc-500 dark:text-zinc-400">
            {{
              artifacts.length === 0
                ? "当 Dear Agent 执行生成代码、文档、图表或演示文稿并保存到 /workspace/outputs/ 时，将在此处集中展现。"
                : "请调整上方筛选条件或搜索关键词重新检索。"
            }}
          </p>
        </div>

        <div
          v-else
          class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
        >
          <article
            v-for="item in filteredArtifacts"
            :key="item.id"
            class="flex flex-col justify-between rounded-2xl border border-zinc-200 bg-white p-4 shadow-2xs transition-all hover:border-zinc-300 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
          >
            <div>
              <!-- 顶部类型徽标与文件名 -->
              <div class="flex items-start justify-between gap-2 mb-2">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 font-mono text-[11px] font-bold uppercase">
                    {{ item.extension.slice(1, 5) || "FILE" }}
                  </span>
                  <div class="min-w-0">
                    <h3 class="truncate text-xs font-semibold text-zinc-900 dark:text-zinc-100" :title="item.name">
                      {{ item.name }}
                    </h3>
                    <p class="truncate font-mono text-[10px] text-zinc-400" :title="item.path">
                      {{ item.path }}
                    </p>
                  </div>
                </div>

                <!-- 专属特色标签 -->
                <span
                  v-if="item.isPresentation"
                  class="shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200/80 dark:border-amber-900/60"
                >
                  图片型 PPTX
                </span>
                <span
                  v-else-if="item.isBinary"
                  class="shrink-0 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                >
                  二进制产物
                </span>
              </div>

              <!-- 成果属性信息 -->
              <div class="mt-3 space-y-1.5 rounded-lg bg-zinc-50/70 p-2.5 text-[11px] text-zinc-600 dark:bg-zinc-800/40 dark:text-zinc-400 font-mono">
                <div class="flex items-center justify-between">
                  <span>文件大小</span>
                  <span class="font-medium text-zinc-800 dark:text-zinc-200">{{ formatBytes(item.sizeBytes) }}</span>
                </div>
                <div v-if="item.sha256" class="flex items-center justify-between gap-1">
                  <span>SHA256</span>
                  <button
                    type="button"
                    class="hover:underline flex items-center gap-1 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                    :title="'点击复制完整哈希: ' + item.sha256"
                    @click="copyHash(item.sha256)"
                  >
                    <span>#{{ item.sha256.slice(0, 10) }}</span>
                    <span v-if="copiedHash === item.sha256" class="text-emerald-500 text-[10px]">已复制</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- 底部操作按钮 -->
            <div class="mt-4 flex items-center justify-between gap-2 border-t border-zinc-100 pt-3 dark:border-zinc-800">
              <button
                v-if="!item.isBinary"
                type="button"
                class="inline-flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
                @click="handlePreview(item)"
              >
                <BaseIcon name="eye" size="xs" />
                <span>在线预览</span>
              </button>
              <span v-else class="text-[10px] text-zinc-400">
                受控原字节交付
              </span>

              <BaseButton
                size="sm"
                variant="primary"
                :disabled="downloadingPath === item.path"
                @click="handleDownload(item)"
              >
                <BaseIcon
                  :name="downloadingPath === item.path ? 'refresh' : 'download'"
                  size="xs"
                  :class="{ 'animate-spin': downloadingPath === item.path }"
                />
                <span>{{ downloadingPath === item.path ? "下载中..." : "安全下载" }}</span>
              </BaseButton>
            </div>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

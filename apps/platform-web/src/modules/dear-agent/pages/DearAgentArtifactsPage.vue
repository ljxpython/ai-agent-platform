<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import { useArtifacts } from "@/composables/useArtifacts";
import { createLanggraphAuthorizedFetch } from "@/services/langgraph/client";
import {
  createSessionService,
  type ChatThread,
} from "@/services/threads/session.service";
import type { ArtifactRef } from "@/types/workspace";
import { formatThreadTime } from "@/utils/threads";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import WorkspacePreview from "@/components/workspace/WorkspacePreview.vue";

export type ArtifactCategory = "all" | "document" | "code_data" | "chart_media" | "presentation";

const route = useRoute();
const router = useRouter();
const { activeProjectId } = useWorkspaceProjectContext();

// 1. 服务装配：动态依赖 activeProjectId，带 x-project-id 请求头
const service = computed(() => {
  if (!activeProjectId.value) return null;
  return createSessionService(createLanggraphAuthorizedFetch(), activeProjectId.value);
});

// 会话列表状态
const threads = ref<ChatThread[]>([]);
const listLoading = ref(false);
const listError = ref("");
const threadSearch = ref("");
const selectedThreadId = ref<string>("");
const deepLinkError = ref("");
const threadOffset = ref(0);
const hasMoreThreads = ref(true);
const loadingMoreThreads = ref(false);

// 2. 成果列表状态：复用专用的 useArtifacts
const {
  artifacts,
  loading: artifactsLoading,
  error: artifactsError,
  hasMore: hasMoreArtifacts,
  selectedArtifact,
  selectedPath,
  previewResult,
  loadingPreview,
  previewError,
  downloadingPath,
  loadInitial: loadArtifacts,
  loadMore: loadMoreArtifacts,
  refresh: refreshArtifacts,
  selectArtifact,
  clearSelection,
  downloadArtifact,
} = useArtifacts(activeProjectId, selectedThreadId);

// 筛选与交互状态
const selectedCategory = ref<ArtifactCategory>("all");
const artifactSearch = ref("");
const copiedHash = ref<string | null>(null);
const isDrawerOpen = ref(false);

// 过滤后的会话列表
const filteredThreads = computed(() => {
  const q = threadSearch.value.trim().toLowerCase();
  if (!q) return threads.value;
  return threads.value.filter((t) => {
    const title = String(t.metadata?.title || "").toLowerCase();
    const id = t.thread_id.toLowerCase();
    return title.includes(q) || id.includes(q);
  });
});

// 当前选中的会话详情
const currentThread = computed(() =>
  threads.value.find((t) => t.thread_id === selectedThreadId.value),
);

// 成果分类解析函数
function categorizeArtifact(item: ArtifactRef): "document" | "code_data" | "chart_media" | "presentation" {
  const ext = item.file_name.split(".").pop()?.toLowerCase() || "";
  const mime = item.mime_type.toLowerCase();
  if (ext === "pptx" || mime.includes("presentation")) return "presentation";
  if (
    ["png", "jpg", "jpeg", "webp", "gif", "svg"].includes(ext) ||
    mime.startsWith("image/") ||
    item.kind === "chart"
  ) {
    return "chart_media";
  }
  if (
    ["zip", "tar", "gz", "json", "py", "ts", "js", "html", "css", "sql", "csv", "xlsx", "xls"].includes(ext) ||
    ["code", "data", "archive"].includes(item.kind)
  ) {
    return "code_data";
  }
  return "document";
}

// 分类与关键词过滤成果
const filteredArtifacts = computed(() => {
  let list = artifacts.value;
  if (selectedCategory.value !== "all") {
    list = list.filter((a) => categorizeArtifact(a) === selectedCategory.value);
  }
  const q = artifactSearch.value.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (a) =>
        a.file_name.toLowerCase().includes(q) ||
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
    counts[categorizeArtifact(a)]++;
  }
  return counts;
});

// 加载会话列表（支持分页 offset=0, 20...）
async function loadThreads(reset = false) {
  if (!service.value) return;
  if (reset) {
    threadOffset.value = 0;
    threads.value = [];
    hasMoreThreads.value = true;
    listLoading.value = true;
  } else {
    loadingMoreThreads.value = true;
  }
  listError.value = "";
  deepLinkError.value = "";

  try {
    const rows = await service.value.list({
      offset: threadOffset.value,
      metadata: { graph_id: "dearflow_agent" },
    });

    const dearThreads = rows.filter(
      (t) => !t.metadata?.graph_id || t.metadata.graph_id === "dearflow_agent",
    );

    if (reset) {
      threads.value = dearThreads;
    } else {
      threads.value = [...threads.value, ...dearThreads];
    }

    if (dearThreads.length < 20) {
      hasMoreThreads.value = false;
    } else {
      threadOffset.value += dearThreads.length;
    }

    // 路由深链处理
    const routeThreadId = route.query.threadId as string;
    if (routeThreadId && !selectedThreadId.value) {
      const exists = threads.value.find((t) => t.thread_id === routeThreadId);
      if (exists) {
        selectedThreadId.value = routeThreadId;
      } else {
        // 非首屏深链：独立 get 校验并置顶放入列表
        try {
          const detail = await service.value.get(routeThreadId);
          if (detail && (!detail.metadata?.graph_id || detail.metadata.graph_id === "dearflow_agent")) {
            threads.value = [detail, ...threads.value];
            selectedThreadId.value = routeThreadId;
          } else {
            deepLinkError.value = "指定的会话不存在或不属于当前项目";
          }
        } catch {
          deepLinkError.value = "指定的会话不存在或无权访问";
        }
      }
    } else if (threads.value.length > 0 && !selectedThreadId.value && !routeThreadId) {
      selectedThreadId.value = threads.value[0].thread_id;
    }
  } catch (err) {
    listError.value = err instanceof Error ? err.message : "获取会话列表失败";
  } finally {
    listLoading.value = false;
    loadingMoreThreads.value = false;
  }
}

// 切换会话
function selectThread(threadId: string) {
  if (selectedThreadId.value === threadId) return;
  closeDrawer();
  selectedThreadId.value = threadId;
  deepLinkError.value = "";
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

// 打开右侧滑出抽屉预览成果
function openPreview(item: ArtifactRef) {
  void selectArtifact(item);
  isDrawerOpen.value = true;
}

// 关闭右侧滑出抽屉
function closeDrawer() {
  isDrawerOpen.value = false;
  clearSelection();
}

// 安全下载
async function handleDownload(item: ArtifactRef) {
  try {
    await downloadArtifact(item);
  } catch (err) {
    alert("下载失败：" + (err instanceof Error ? err.message : "未知错误"));
  }
}

// 格式化字节大小
function formatBytes(bytes?: number): string {
  if (bytes === undefined || bytes === null || bytes <= 0) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// 键盘事件：Esc 退出抽屉
function handleKeyDown(e: KeyboardEvent) {
  if (e.key === "Escape" && isDrawerOpen.value) {
    closeDrawer();
  }
}

// 监听项目切换，清理所有状态
watch(activeProjectId, () => {
  closeDrawer();
  threads.value = [];
  selectedThreadId.value = "";
  threadSearch.value = "";
  artifactSearch.value = "";
  void loadThreads(true);
});

onMounted(() => {
  window.addEventListener("keydown", handleKeyDown);
  void loadThreads(true);
});

onUnmounted(() => {
  window.removeEventListener("keydown", handleKeyDown);
});
</script>

<template>
  <div class="relative flex h-full w-full overflow-hidden bg-zinc-50 dark:bg-zinc-950">
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
          placeholder="搜索会话标题或 ID..."
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
        <template v-else>
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

          <!-- 加载更多会话按钮 -->
          <div v-if="hasMoreThreads && !threadSearch" class="pt-2 pb-1 text-center">
            <button
              type="button"
              class="text-xs text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium disabled:opacity-50"
              :disabled="loadingMoreThreads"
              @click="loadThreads(false)"
            >
              {{ loadingMoreThreads ? "正在加载更多..." : "加载更多会话" }}
            </button>
          </div>
        </template>
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
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded-lg border border-zinc-200 px-2.5 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            title="刷新成果列表"
            @click="refreshArtifacts"
          >
            <BaseIcon name="refresh" size="xs" :class="{ 'animate-spin': artifactsLoading }" />
            <span>刷新</span>
          </button>
          <router-link
            v-if="selectedThreadId"
            :to="{ path: `/workspace/projects/${activeProjectId}/dear-agent/${selectedThreadId}` }"
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
        <!-- 深链错误提示 -->
        <div v-if="deepLinkError" class="p-8 text-center text-sm text-red-500">
          <BaseIcon name="alert" size="md" class="mx-auto mb-2 text-red-500" />
          <p>{{ deepLinkError }}</p>
        </div>

        <!-- 成果加载中 -->
        <div v-else-if="artifactsLoading" class="flex h-64 items-center justify-center text-xs text-zinc-400">
          <BaseIcon name="refresh" size="md" class="animate-spin mr-2" />
          <span>正在检索会话成果...</span>
        </div>

        <!-- 成果加载报错 -->
        <div v-else-if="artifactsError" class="p-8 text-center text-sm text-red-500">
          <BaseIcon name="alert" size="md" class="mx-auto mb-2 text-amber-500" />
          <p>{{ artifactsError }}</p>
          <button
            type="button"
            class="mt-3 inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
            @click="loadArtifacts(true)"
          >
            重试
          </button>
        </div>

        <!-- 空数据状态 -->
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

        <!-- 网格列表 -->
        <div v-else class="space-y-6">
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            <article
              v-for="item in filteredArtifacts"
              :key="item.path"
              class="flex flex-col justify-between rounded-2xl border border-zinc-200 bg-white p-4 shadow-2xs transition-all hover:border-zinc-300 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700 cursor-pointer"
              @click="openPreview(item)"
            >
              <div>
                <!-- 顶部类型徽标与文件名 -->
                <div class="flex items-start justify-between gap-2 mb-2">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 font-mono text-[11px] font-bold uppercase">
                      {{ item.file_name.split(".").pop()?.slice(0, 4) || "FILE" }}
                    </span>
                    <div class="min-w-0">
                      <h3 class="truncate text-xs font-semibold text-zinc-900 dark:text-zinc-100" :title="item.file_name">
                        {{ item.file_name }}
                      </h3>
                      <p class="truncate font-mono text-[10px] text-zinc-400" :title="item.path">
                        {{ item.path }}
                      </p>
                    </div>
                  </div>

                  <!-- 专属特色标签 -->
                  <span
                    v-if="categorizeArtifact(item) === 'presentation'"
                    class="shrink-0 rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200/80 dark:border-amber-900/60"
                  >
                    幻灯片
                  </span>
                  <span
                    v-else-if="item.preview_kind === 'download'"
                    class="shrink-0 rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                  >
                    二进制交付
                  </span>
                  <span
                    v-else
                    class="shrink-0 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                  >
                    可预览
                  </span>
                </div>

                <!-- 成果属性信息 -->
                <div class="mt-3 space-y-1.5 rounded-lg bg-zinc-50/70 p-2.5 text-[11px] text-zinc-600 dark:bg-zinc-800/40 dark:text-zinc-400 font-mono">
                  <div class="flex items-center justify-between">
                    <span>文件大小</span>
                    <span class="font-medium text-zinc-800 dark:text-zinc-200">{{ formatBytes(item.size_bytes) }}</span>
                  </div>
                  <div v-if="item.sha256" class="flex items-center justify-between gap-1">
                    <span>SHA256</span>
                    <button
                      type="button"
                      class="hover:underline flex items-center gap-1 text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
                      :title="'点击复制完整哈希: ' + item.sha256"
                      @click.stop="copyHash(item.sha256)"
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
                  type="button"
                  class="inline-flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 dark:text-primary-400 font-medium"
                  @click.stop="openPreview(item)"
                >
                  <BaseIcon name="eye" size="xs" />
                  <span>{{ item.preview_kind === 'download' ? '查看详情' : '在线预览' }}</span>
                </button>

                <BaseButton
                  size="sm"
                  variant="primary"
                  :disabled="downloadingPath === item.path"
                  @click.stop="handleDownload(item)"
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

          <!-- 分页加载更多成果 -->
          <div v-if="hasMoreArtifacts" class="text-center pt-2">
            <BaseButton
              variant="secondary"
              size="sm"
              :disabled="artifactsLoading"
              @click="loadMoreArtifacts"
            >
              <BaseIcon v-if="artifactsLoading" name="refresh" size="xs" class="animate-spin mr-1" />
              <span>加载更多成果...</span>
            </BaseButton>
          </div>
        </div>
      </section>
    </main>

    <!-- 右侧滑出抽屉（Drawer / Slide-over） -->
    <Transition
      enter-active-class="transition-opacity duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isDrawerOpen"
        class="fixed inset-0 z-40 bg-black/40 backdrop-blur-2xs"
        @click="closeDrawer"
      />
    </Transition>

    <Transition
      enter-active-class="transition-transform duration-300 ease-out"
      enter-from-class="translate-x-full"
      enter-to-class="translate-x-0"
      leave-active-class="transition-transform duration-200 ease-in"
      leave-from-class="translate-x-0"
      leave-to-class="translate-x-full"
    >
      <div
        v-if="isDrawerOpen"
        class="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col bg-white shadow-2xl dark:bg-zinc-900 border-l border-zinc-200 dark:border-zinc-800"
      >
        <!-- 抽屉顶部栏 -->
        <div class="flex h-12 items-center justify-between border-b border-zinc-200 px-4 dark:border-zinc-800 shrink-0">
          <div class="flex items-center gap-2 min-w-0">
            <span class="rounded bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-700 dark:bg-primary-950/50 dark:text-primary-300">
              成果预览
            </span>
            <span class="truncate text-xs font-medium text-zinc-600 dark:text-zinc-300" :title="selectedPath">
              {{ selectedArtifact?.file_name || selectedPath }}
            </span>
          </div>

          <button
            type="button"
            class="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200 transition-colors"
            title="关闭预览 (Esc)"
            @click="closeDrawer"
          >
            <BaseIcon name="x" size="sm" />
          </button>
        </div>

        <!-- 抽屉预览核心主体：内嵌 WorkspacePreview -->
        <div class="flex-1 overflow-hidden min-h-0">
          <WorkspacePreview
            :project-id="activeProjectId"
            :thread-id="selectedThreadId"
            :path="selectedPath"
            :preview-result="previewResult ?? null"
            :loading="loadingPreview"
            :error="previewError"
            @download="() => selectedArtifact && handleDownload(selectedArtifact)"
          />
        </div>
      </div>
    </Transition>
  </div>
</template>

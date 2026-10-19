<script setup lang="ts">
import { ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { useUiStore } from "@/stores/ui";
import {
  queryProjectKnowledge,
  type KnowledgeQueryMode,
  type KnowledgeQueryResult,
  type KnowledgeSourceItem,
} from "@/services/knowledge/knowledge.service";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: KnowledgeQueryMode;
  searchDurationMs?: number;
  sources?: KnowledgeSourceItem[];
  timestamp: string;
}

const props = defineProps<{
  projectId: string;
}>();

const uiStore = useUiStore();

const queryInput = ref("");
const querying = ref(false);
const activeMode = ref<KnowledgeQueryMode>("hybrid");
const topK = ref(5);
const messages = ref<ChatMessage[]>([]);
const activeSourcesDrawer = ref<KnowledgeSourceItem[] | null>(null);

const modeOptions: {
  value: KnowledgeQueryMode;
  label: string;
  desc: string;
  badge: string;
}[] = [
  {
    value: "hybrid",
    label: "Hybrid 混合图谱",
    desc: "融合实体知识图谱 + 密集向量语义，召回最全最准",
    badge: "推荐",
  },
  {
    value: "local",
    label: "Local 局部实体",
    desc: "聚焦特定实体周围 N 度邻居关联，精确针对具体概念",
    badge: "实体",
  },
  {
    value: "global",
    label: "Global 宏观概览",
    desc: "全局社区主题聚类汇总，回答全貌或宏观策略问题",
    badge: "全局",
  },
  {
    value: "naive",
    label: "Naive 传统向量",
    desc: "纯靠文本 embedding 余弦相似度，传统切片召回",
    badge: "基准",
  },
];

const samplePrompts = [
  "请全面梳理当前项目知识库的核心主题与结构",
  "提取知识库中涉及的关键实体与相互关系",
  "总结文档中关于技术架构与设计原则的规范",
];

function selectSamplePrompt(prompt: string) {
  queryInput.value = prompt;
}

async function handleSend() {
  const q = queryInput.value.trim();
  if (!q || querying.value) return;

  const userMsgId = `usr_${Date.now()}`;
  messages.value.push({
    id: userMsgId,
    role: "user",
    content: q,
    mode: activeMode.value,
    timestamp: new Date().toLocaleTimeString(),
  });

  queryInput.value = "";
  querying.value = true;
  const startTime = Date.now();

  try {
    const res: KnowledgeQueryResult = await queryProjectKnowledge(
      props.projectId,
      {
        query: q,
        mode: activeMode.value,
        topK: topK.value,
      },
    );

    const duration = Date.now() - startTime;
    const assistantMsgId = `asst_${Date.now()}`;

    let replyText = res.response || "";
    if (!replyText && res.status === "no_hit") {
      replyText =
        "当前知识库未检索到与您问题高度匹配的内容，建议尝试切换检索模式（如 Local 或 Global）或上传更多资料。";
    } else if (!replyText) {
      replyText = `检索完成，成功召回 ${res.sources?.length || 0} 个知识切片，但大模型未生成总结内容。`;
    }

    messages.value.push({
      id: assistantMsgId,
      role: "assistant",
      content: replyText,
      mode: activeMode.value,
      searchDurationMs: duration,
      sources: res.sources || [],
      timestamp: new Date().toLocaleTimeString(),
    });
  } catch (err: unknown) {
    const duration = Date.now() - startTime;
    const msg = err instanceof Error ? err.message : "请求知识库服务超时或异常";
    messages.value.push({
      id: `err_${Date.now()}`,
      role: "assistant",
      content: `❌ 检索失败: ${msg}`,
      searchDurationMs: duration,
      timestamp: new Date().toLocaleTimeString(),
    });
    uiStore.pushToast({
      type: "error",
      title: "检索异常",
      message: msg,
    });
  } finally {
    querying.value = false;
  }
}

function clearChat() {
  messages.value = [];
}

function openSources(sources: KnowledgeSourceItem[]) {
  activeSourcesDrawer.value = sources;
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 顶部策略控制栏 -->
    <div
      class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface px-5 py-3.5"
    >
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs font-semibold text-text-muted">检索模式:</span>
        <div class="inline-flex rounded-xl bg-slate-100 p-1 dark:bg-dark-800">
          <button
            v-for="opt in modeOptions"
            :key="opt.value"
            type="button"
            class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all"
            :class="
              activeMode === opt.value
                ? 'bg-white text-primary-700 shadow-xs font-semibold dark:bg-dark-900 dark:text-primary-300'
                : 'text-text-sub hover:text-text-main'
            "
            :title="opt.desc"
            @click="activeMode = opt.value"
          >
            <span>{{ opt.label.split(" ")[0] }}</span>
            <span
              v-if="opt.badge === '推荐'"
              class="rounded-full bg-primary-100 px-1 py-0.2 text-[9px] font-bold text-primary-800 dark:bg-primary-950 dark:text-primary-300"
            >
              {{ opt.badge }}
            </span>
          </button>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2 text-xs text-text-sub">
          <span>Top K:</span>
          <select
            v-model.number="topK"
            class="rounded-lg border border-border bg-background px-2 py-1 text-xs font-semibold focus:outline-hidden"
          >
            <option :value="3">3 条切片</option>
            <option :value="5">5 条切片</option>
            <option :value="8">8 条切片</option>
          </select>
        </div>

        <BaseButton
          v-if="messages.length > 0"
          variant="secondary"
          size="sm"
          @click="clearChat"
        >
          <BaseIcon name="trash" size="xs" />
          <span>清空记录</span>
        </BaseButton>
      </div>
    </div>

    <!-- 主对话与结果展示区域 -->
    <div
      class="relative flex flex-col rounded-2xl border border-border bg-card shadow-2xs"
      style="min-height: 540px"
    >
      <!-- 空状态与引导 -->
      <div
        v-if="messages.length === 0"
        class="flex flex-1 flex-col items-center justify-center p-8 text-center"
      >
        <div
          class="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-50 text-primary-600 dark:bg-primary-950/50 dark:text-primary-400"
        >
          <BaseIcon name="chat" size="lg" />
        </div>
        <h3 class="mt-4 text-base font-semibold text-text-main">
          LightRAG 原生多模态智能问答
        </h3>
        <p class="mt-1 max-w-md text-xs text-text-sub leading-relaxed">
          基于当前项目的知识库底座，支持实体跳数推理、全局主题抽象与传统向量召回。您可以输入任意专业问题进行精准追溯。
        </p>

        <div class="mt-6 flex flex-col items-center gap-2">
          <span
            class="text-[11px] font-semibold text-text-muted uppercase tracking-wider"
          >
            点击体验预设问答
          </span>
          <div class="flex flex-wrap justify-center gap-2">
            <button
              v-for="prompt in samplePrompts"
              :key="prompt"
              type="button"
              class="rounded-xl border border-border bg-surface px-3 py-1.5 text-xs text-text-sub transition hover:border-primary-400 hover:text-primary-600 dark:hover:border-primary-600"
              @click="selectSamplePrompt(prompt)"
            >
              {{ prompt }}
            </button>
          </div>
        </div>
      </div>

      <!-- 对话流列表 -->
      <div v-else class="flex-1 space-y-4 overflow-y-auto p-6 max-h-[600px]">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="flex flex-col gap-1.5"
          :class="msg.role === 'user' ? 'items-end' : 'items-start'"
        >
          <div class="flex items-center gap-2 px-1 text-[11px] text-text-muted">
            <span>{{ msg.role === "user" ? "你" : "LightRAG 知识助手" }}</span>
            <span>·</span>
            <span>{{ msg.timestamp }}</span>
            <span v-if="msg.searchDurationMs"
              >· 耗时 {{ msg.searchDurationMs }}ms</span
            >
          </div>

          <div
            class="max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed"
            :class="
              msg.role === 'user'
                ? 'bg-primary-600 text-white rounded-tr-xs'
                : 'bg-surface border border-border text-text-main rounded-tl-xs shadow-2xs'
            "
          >
            <div class="whitespace-pre-wrap select-text">{{ msg.content }}</div>

            <!-- 召回来源切片折叠卡 -->
            <div
              v-if="msg.sources && msg.sources.length > 0"
              class="mt-3 border-t border-border/60 pt-2.5 text-xs"
            >
              <div class="flex items-center justify-between">
                <span
                  class="font-semibold text-text-muted flex items-center gap-1"
                >
                  <BaseIcon name="paperclip" size="xs" />
                  溯源切片 ({{ msg.sources.length }})
                </span>
                <button
                  type="button"
                  class="text-primary-600 hover:underline dark:text-primary-400 font-medium"
                  @click="openSources(msg.sources)"
                >
                  查看切片详情 ➔
                </button>
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="querying"
          class="flex items-center gap-3 p-2 text-xs text-text-sub"
        >
          <div class="h-2 w-2 animate-ping rounded-full bg-primary-500"></div>
          <span>正在调用 LightRAG 混合图谱引擎检索并生成回答...</span>
        </div>
      </div>

      <!-- 底部输入框 -->
      <div class="border-t border-border p-4 bg-surface/50 rounded-b-2xl">
        <form class="flex items-end gap-2" @submit.prevent="handleSend">
          <textarea
            v-model="queryInput"
            rows="2"
            placeholder="输入您要向知识库咨询的问题（按 Enter 发送，Shift+Enter 换行）..."
            class="flex-1 resize-none rounded-xl border border-border bg-background p-3 text-xs leading-relaxed text-text-main placeholder:text-text-muted focus:border-primary-500 focus:outline-hidden dark:bg-dark-900"
            :disabled="querying"
            @keydown.enter.exact.prevent="handleSend"
          ></textarea>

          <BaseButton
            type="submit"
            variant="primary"
            :disabled="!queryInput.trim() || querying"
            class="h-10 px-5"
          >
            <BaseIcon name="sparkle" size="xs" />
            <span>{{ querying ? "检索中..." : "发送" }}</span>
          </BaseButton>
        </form>
      </div>
    </div>

    <!-- 切片详情侧滑抽屉 -->
    <div
      v-if="activeSourcesDrawer"
      class="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-2xs transition-opacity"
      @click.self="activeSourcesDrawer = null"
    >
      <div
        class="flex h-full w-full max-w-xl flex-col bg-card p-6 shadow-2xl overflow-y-auto animate-in slide-in-from-right duration-200"
      >
        <div
          class="flex items-center justify-between border-b border-border pb-4"
        >
          <div class="flex items-center gap-2">
            <BaseIcon name="file" size="md" class="text-primary-600" />
            <h3 class="text-base font-semibold text-text-main">
              召回知识切片溯源
            </h3>
          </div>
          <button
            type="button"
            class="rounded-lg p-1 text-text-muted hover:bg-slate-100 hover:text-text-main dark:hover:bg-dark-800"
            @click="activeSourcesDrawer = null"
          >
            <BaseIcon name="x" size="sm" />
          </button>
        </div>

        <div class="mt-4 space-y-4">
          <div
            v-for="(src, idx) in activeSourcesDrawer"
            :key="src.chunk_id || idx"
            class="rounded-xl border border-border bg-surface p-4 text-xs space-y-2"
          >
            <div class="flex items-center justify-between">
              <span class="font-semibold text-text-main truncate max-w-[280px]">
                {{ src.title || "未知文档" }}
              </span>
              <StatusPill tone="info">{{ src.kind || "text" }}</StatusPill>
            </div>

            <div class="text-[11px] text-text-muted font-mono">
              Chunk ID: {{ src.chunk_id }}
            </div>

            <div
              class="rounded-lg bg-background p-3 text-text-sub whitespace-pre-wrap font-sans text-xs leading-relaxed border border-border/50"
            >
              {{ src.preview }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

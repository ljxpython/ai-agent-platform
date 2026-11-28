<script setup lang="ts">
import { computed, ref, toRef, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import MarkdownContent from "@/components/platform/MarkdownContent.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import { useEvalExpertChat } from "@/modules/evaluation/composables/useEvalExpertChat";
import type { CaseUpsertPayload } from "@/services/evaluation/studio";

const props = defineProps<{
  show: boolean;
  projectId: string;
  kind: "eval_copilot" | "eval_diagnosis";
  refId: string;
  defaultModelId: string;
  modelOptions?: Array<{ label: string; value: string; isBroken?: boolean }>;
}>();

const emit = defineEmits<{
  close: [];
  adoptCases: [items: CaseUpsertPayload[]];
  casesUpdated: [];
  trialRunUpdated: [];
}>();

const projectIdRef = toRef(props, "projectId");
const kindRef = toRef(props, "kind");
const selectedModelId = ref(props.defaultModelId);

watch(
  () => props.defaultModelId,
  (val) => {
    if (!selectedModelId.value && val) selectedModelId.value = val;
  },
  { immediate: true },
);

const chat = useEvalExpertChat(projectIdRef, kindRef, selectedModelId, {
  onCasesMutated: () => emit("casesUpdated"),
  onTrialRunUpdated: () => emit("trialRunUpdated"),
});

const usableModelOptions = computed(() =>
  (props.modelOptions ?? []).filter((m) => !m.isBroken),
);

const inputDraft = ref("");
const fileInputRef = ref<HTMLInputElement | null>(null);

const title = computed(() =>
  props.kind === "eval_copilot"
    ? "AI 出题专家 · Eval Copilot"
    : "AI 白盒诊断专家 · Eval Diagnosis",
);

const quickPrompts = computed(() =>
  props.kind === "eval_copilot"
    ? [
        `请先查看 suite_id=${props.refId} 现有考题与目标图工具清单，为我设计 1 道带动态追问的多轮博弈 Case 并写入草稿`,
        `帮我检查 suite_id=${props.refId} 最近一次试跑或失败记录，指出可改进的考题或补建 1 道回归用例`,
      ]
    : [
        `请读取 run_id=${props.refId} 的概览与失败用例证据，按 Data / Retrieval / Reasoning Gap 三层归因`,
        `分析 run_id=${props.refId} 中 TTFT 偏高或工具调用异常的具体瓶颈并给出改造建议`,
      ],
);

watch(
  () => [props.kind, props.refId],
  () => {
    chat.reset();
  },
);

function triggerFilePicker() {
  fileInputRef.value?.click();
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement | null;
  if (target?.files?.length) {
    chat.addPendingFiles(target.files);
    target.value = "";
  }
}

async function submitPrompt(text?: string) {
  const payload = (text ?? inputDraft.value).trim();
  if (!payload) return;
  if (!text) inputDraft.value = "";
  await chat.send(payload, props.refId);
}

const trialIsRunning = computed(() =>
  ["queued", "running"].includes(chat.trialRunStatus.value),
);

const trialFinished = computed(() =>
  ["completed", "failed", "error", "cancelled"].includes(
    chat.trialRunStatus.value,
  ),
);
</script>

<template>
  <BaseDrawer :show="show" :title="title" width="wide" @close="emit('close')">
    <div class="flex flex-col h-full gap-3">
      <div
        class="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500 dark:text-dark-300 pb-2 border-b border-gray-100 dark:border-dark-700"
      >
        <div class="flex items-center gap-2">
          <StatusPill tone="info">{{ kind }}</StatusPill>
          <span v-if="refId" class="font-mono"
            >关联: {{ refId.slice(0, 8) }}</span
          >
        </div>
        <div class="flex items-center gap-2">
          <select
            v-if="usableModelOptions.length"
            v-model="selectedModelId"
            aria-label="选择专家模型"
            class="pw-input py-1 px-2 text-xs max-w-[200px]"
          >
            <option
              v-for="opt in usableModelOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
          <BaseButton size="sm" variant="secondary" @click="chat.reset()"
            >清空重置会话</BaseButton
          >
        </div>
      </div>

      <div
        v-if="chat.activeTrialRunId.value"
        class="flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-lg border border-primary-200 dark:border-primary-800/60 bg-primary-50/60 dark:bg-primary-950/20 text-xs"
      >
        <div class="flex items-center gap-2">
          <span class="font-mono font-semibold"
            >试跑 #{{ chat.activeTrialRunId.value.slice(0, 8) }}</span
          >
          <StatusPill :tone="trialIsRunning ? 'info' : 'neutral'">
            {{ chat.trialRunStatus.value || "queued" }}
          </StatusPill>
          <span v-if="chat.trialRunSummary.value" class="text-gray-500">
            {{ chat.trialRunSummary.value }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <BaseButton
            v-if="trialIsRunning"
            size="sm"
            variant="danger"
            @click="chat.abortActiveTrialRun()"
          >
            终止当前评测
          </BaseButton>
          <BaseButton
            v-if="trialFinished"
            size="sm"
            variant="primary"
            :disabled="chat.streaming.value"
            @click="
              submitPrompt(
                `试跑 run_id=${chat.activeTrialRunId.value} 已结束（状态：${chat.trialRunStatus.value}），请调用 get_run_progress_and_evidence 分析结果；若因 Case 写法瑕疵失败请提出修复。`,
              )
            "
          >
            让专家查看结果
          </BaseButton>
        </div>
      </div>

      <StateBanner
        v-if="chat.error.value"
        variant="danger"
        title="专家对话执行异常"
        :description="chat.error.value"
      />

      <div v-if="!chat.messages.value.length" class="space-y-2">
        <p class="text-xs font-medium text-gray-600 dark:text-dark-300">
          快捷分析指令：
        </p>
        <div class="space-y-2">
          <button
            v-for="q in quickPrompts"
            :key="q"
            type="button"
            class="w-full text-left p-2.5 rounded-lg border border-gray-200 dark:border-dark-700 text-xs hover:border-primary-400 hover:bg-primary-50/40 dark:hover:bg-primary-950/20 transition-colors"
            @click="submitPrompt(q)"
          >
            {{ q }}
          </button>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto space-y-3 pr-1">
        <div
          v-for="msg in chat.messages.value"
          :key="msg.id"
          class="p-3 rounded-lg text-xs space-y-2"
          :class="
            msg.role === 'user'
              ? 'bg-primary-50 dark:bg-primary-950/30 border border-primary-100 dark:border-primary-900/40 ml-8'
              : 'bg-gray-50 dark:bg-dark-800/70 border border-gray-200 dark:border-dark-700 mr-4'
          "
        >
          <div class="font-semibold text-[11px] text-gray-500">
            {{ msg.role === "user" ? "我" : title }}
          </div>
          <div
            v-if="msg.attachments && msg.attachments.length"
            class="flex flex-wrap gap-1.5"
          >
            <span
              v-for="fname in msg.attachments"
              :key="fname"
              class="px-2 py-0.5 rounded bg-white/80 dark:bg-dark-900 border border-primary-200 dark:border-dark-600 text-[11px] font-mono"
            >
              📎 {{ fname }}
            </span>
          </div>
          <MarkdownContent
            :content="
              msg.content ||
              (chat.streaming.value ? '正在读取规范/资料并调用工具处理...' : '')
            "
          />

          <div
            v-if="msg.candidates && msg.candidates.length > 0"
            class="mt-2 pt-2 border-t border-gray-200 dark:border-dark-700 space-y-2"
          >
            <div class="flex items-center justify-between">
              <span
                class="font-semibold text-emerald-600 dark:text-emerald-400"
              >
                识别到 {{ msg.candidates.length }} 道候选考题
              </span>
              <BaseButton
                size="sm"
                variant="primary"
                @click="emit('adoptCases', msg.candidates!)"
              >
                一键写入当前题库草稿
              </BaseButton>
            </div>
          </div>
        </div>

        <div
          v-if="chat.pendingInterrupts.value.length > 0"
          class="p-3 rounded-lg border-2 border-amber-400/80 dark:border-amber-600 bg-amber-50/70 dark:bg-amber-950/25 space-y-2 text-xs"
        >
          <div class="font-semibold text-amber-800 dark:text-amber-300">
            需要你的授权确认（HITL）
          </div>
          <div
            v-for="item in chat.pendingInterrupts.value"
            :key="item.id"
            class="space-y-1 text-[11px] text-gray-700 dark:text-dark-200"
          >
            <div>
              操作工具：<span class="font-mono font-semibold">{{
                item.actionName
              }}</span>
            </div>
            <div>{{ item.description }}</div>
            <pre
              class="p-2 rounded bg-white/80 dark:bg-dark-900 border border-amber-200 dark:border-dark-700 overflow-x-auto text-[11px]"
              >{{ item.argsSummary }}</pre
            >
          </div>
          <div class="flex items-center justify-end gap-2 pt-1">
            <BaseButton
              size="sm"
              variant="secondary"
              :disabled="chat.streaming.value"
              @click="chat.respondInterrupt('reject')"
            >
              拒绝
            </BaseButton>
            <BaseButton
              size="sm"
              variant="primary"
              :disabled="chat.streaming.value"
              @click="chat.respondInterrupt('approve')"
            >
              允许执行
            </BaseButton>
          </div>
        </div>
      </div>

      <div class="pt-2 border-t border-gray-100 dark:border-dark-700 space-y-2">
        <div
          v-if="
            chat.pendingFiles.value.length > 0 ||
            chat.uploadedMaterials.value.length > 0
          "
          class="flex flex-wrap gap-1.5 text-[11px]"
        >
          <span
            v-for="f in chat.pendingFiles.value"
            :key="`pending-${f.name}`"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-50 dark:bg-primary-950/40 text-primary-700 dark:text-primary-300 border border-primary-200 dark:border-primary-800"
          >
            待发: {{ f.name }}
            <button
              type="button"
              class="hover:text-red-500 ml-0.5"
              @click="chat.removePendingFile(f.name)"
            >
              ×
            </button>
          </span>
          <span
            v-for="u in chat.uploadedMaterials.value"
            :key="`uploaded-${u.path}`"
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 dark:bg-dark-800 text-gray-600 dark:text-dark-300"
          >
            已传: {{ u.fileName }}
          </span>
        </div>

        <div class="flex items-center gap-2">
          <input
            ref="fileInputRef"
            type="file"
            multiple
            accept=".txt,.md,.csv,.json,.pdf,.docx,.yaml,.yml"
            class="hidden"
            @change="handleFileChange"
          />
          <BaseButton
            v-if="kind === 'eval_copilot'"
            size="sm"
            variant="secondary"
            :disabled="
              chat.streaming.value || chat.pendingInterrupts.value.length > 0
            "
            @click="triggerFilePicker"
          >
            + 资料
          </BaseButton>
          <div class="flex-1">
            <BaseInput
              v-model="inputDraft"
              :disabled="chat.pendingInterrupts.value.length > 0"
              :placeholder="
                chat.pendingInterrupts.value.length > 0
                  ? '请先在上方点击「允许执行」或「拒绝」完成授权...'
                  : '输入需求、上传参考资料或排障追问，回车发送...'
              "
              @keyup.enter="submitPrompt()"
            />
          </div>
          <BaseButton
            variant="primary"
            :disabled="
              chat.streaming.value ||
              chat.pendingInterrupts.value.length > 0 ||
              !inputDraft.trim()
            "
            @click="submitPrompt()"
          >
            {{ chat.streaming.value ? "执行中..." : "发送" }}
          </BaseButton>
        </div>
      </div>
    </div>
  </BaseDrawer>
</template>

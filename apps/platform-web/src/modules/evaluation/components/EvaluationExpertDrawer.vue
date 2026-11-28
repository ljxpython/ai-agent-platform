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
}>();

const emit = defineEmits<{
  close: [];
  adoptCases: [items: CaseUpsertPayload[]];
}>();

const projectIdRef = toRef(props, "projectId");
const kindRef = toRef(props, "kind");
const modelRef = toRef(props, "defaultModelId");
const chat = useEvalExpertChat(projectIdRef, kindRef, modelRef);

const inputDraft = ref("");

const title = computed(() =>
  props.kind === "eval_copilot"
    ? "AI 出题专家 · Eval Copilot"
    : "AI 白盒诊断专家 · Eval Diagnosis",
);

const quickPrompts = computed(() =>
  props.kind === "eval_copilot"
    ? [
        `请读取 suite_id=${props.refId} 的现有考题，并生成 2 道覆盖边界异常的 Case v3 JSON 候选题目`,
        `基于 suite_id=${props.refId} 补充 1 道带延迟澄清的多轮博弈仿真题 (JSON 格式)`,
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

async function submitPrompt(text?: string) {
  const payload = (text ?? inputDraft.value).trim();
  if (!payload) return;
  if (!text) inputDraft.value = "";
  await chat.send(payload, props.refId);
}
</script>

<template>
  <BaseDrawer :show="show" :title="title" width="wide" @close="emit('close')">
    <div class="flex flex-col h-full gap-4">
      <div
        class="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500 dark:text-dark-300 pb-2 border-b border-gray-100 dark:border-dark-700"
      >
        <div class="flex items-center gap-2">
          <StatusPill tone="info">{{ kind }}</StatusPill>
          <span v-if="refId" class="font-mono"
            >关联: {{ refId.slice(0, 8) }}</span
          >
        </div>
        <BaseButton size="sm" variant="secondary" @click="chat.reset()"
          >清空重置会话</BaseButton
        >
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
          <MarkdownContent
            :content="
              msg.content ||
              (chat.streaming.value ? '正在调用工具取证并分析...' : '')
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
      </div>

      <div
        class="pt-2 border-t border-gray-100 dark:border-dark-700 flex items-center gap-2"
      >
        <div class="flex-1">
          <BaseInput
            v-model="inputDraft"
            placeholder="输入需求或排障追问，回车发送..."
            @keyup.enter="submitPrompt()"
          />
        </div>
        <BaseButton
          variant="primary"
          :disabled="chat.streaming.value || !inputDraft.trim()"
          @click="submitPrompt()"
        >
          {{ chat.streaming.value ? "思考中..." : "发送" }}
        </BaseButton>
      </div>
    </div>
  </BaseDrawer>
</template>

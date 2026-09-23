<script setup lang="ts">
import { computed, ref } from "vue";
import type { MessageReceipt } from "@/services/threads/messages.service";
import type { QueuedPromptItem } from "../composables/usePromptQueue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = withDefaults(
  defineProps<{
    queueItems?: QueuedPromptItem[];
    receipts?: MessageReceipt[];
    pendingMessage?: {
      payload: {
        client_message_id: string;
        target_run_id: string;
        content: unknown;
      };
      key: string;
      status: "sending" | "unknown" | "rejected";
    } | null;
    receiptError?: string;
    canWrite: boolean;
    canSend: boolean;
    isDraining?: boolean;
  }>(),
  {
    queueItems: () => [],
    receipts: () => [],
    pendingMessage: null,
    receiptError: "",
    isDraining: false,
  },
);

const emit = defineEmits<{
  (e: "retryPending"): void;
  (e: "restoreDraft", content?: unknown, messageId?: string): void;
  (e: "resendAsNew", content: unknown, messageId?: string): void;
  (e: "refresh"): void;
  (e: "removeItem", id: string): void;
  (e: "moveUp", index: number): void;
  (e: "moveDown", index: number): void;
  (e: "clearQueue"): void;
}>();

// Track expanded state for longer messages
const expandedMap = ref<Record<string, boolean>>({});

function toggleExpand(id: string) {
  expandedMap.value[id] = !expandedMap.value[id];
}

function extractContentText(content: unknown): string {
  if (typeof content === "string") return content.trim();
  if (Array.isArray(content)) {
    return content
      .filter((item) => item?.type === "text" && typeof item?.text === "string")
      .map((item) => item.text.trim())
      .filter(Boolean)
      .join("\n");
  }
  if (
    content &&
    typeof content === "object" &&
    "text" in content &&
    typeof (content as { text: unknown }).text === "string"
  ) {
    return (content as { text: string }).text.trim();
  }
  return "";
}

function getReasonDescription(reason?: string | null): string {
  if (!reason) return "";
  const map: Record<string, string> = {
    run_ended: "上一回合已终止，未消费",
    thread_busy: "会话繁忙",
    rejected: "已拒绝",
    timeout: "上一回合执行超时",
  };
  return map[reason] ?? reason;
}

const isPromptQueueActive = computed(() => (props.queueItems?.length ?? 0) > 0);

const totalCount = computed(() => {
  return (
    (props.queueItems?.length ?? 0) +
    props.receipts.length +
    (props.pendingMessage ? 1 : 0)
  );
});

const hasWarning = computed(() => {
  return (
    Boolean(props.receiptError) ||
    props.pendingMessage?.status === "rejected" ||
    props.receipts.some((r) => ["rejected", "not_consumed"].includes(r.status))
  );
});
</script>

<template>
  <section
    v-if="(queueItems && queueItems.length > 0) || receipts.length || pendingMessage || receiptError"
    aria-label="消息队列"
    class="mx-auto w-full max-w-3xl rounded-2xl border p-3.5 sm:p-4 text-xs shadow-xs transition-all duration-200"
    :class="[
      isPromptQueueActive
        ? 'border-blue-500/30 bg-blue-500/[0.04] dark:bg-blue-950/20'
        : hasWarning
          ? 'border-amber-500/30 bg-amber-500/[0.04] dark:bg-amber-950/20'
          : 'border-blue-500/25 bg-blue-500/[0.03] dark:bg-blue-950/15'
    ]"
  >
    <!-- Header -->
    <div class="flex items-center justify-between gap-3 pb-2.5 border-b border-border/50">
      <div class="flex items-center gap-2 min-w-0">
        <!-- Status indicator dot with pulse -->
        <span class="relative flex h-2 w-2 shrink-0 items-center justify-center">
          <span
            v-if="!hasWarning || isPromptQueueActive"
            class="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-500 opacity-75"
          />
          <span
            class="relative inline-flex h-2 w-2 rounded-full"
            :class="isPromptQueueActive ? 'bg-blue-500' : hasWarning ? 'bg-amber-500' : 'bg-blue-500'"
          />
        </span>

        <div class="flex items-center gap-2 min-w-0">
          <span class="font-medium text-foreground tracking-tight text-xs flex items-center gap-1.5">
            <span>{{ isPromptQueueActive ? "待执行消息队列" : "排队补充消息" }}</span>
            <span
              class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
              :class="
                isPromptQueueActive
                  ? 'bg-blue-500/15 text-blue-700 dark:text-blue-300'
                  : hasWarning
                    ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
                    : 'bg-blue-500/15 text-blue-700 dark:text-blue-300'
              "
            >
              {{ isPromptQueueActive ? queueItems.length : totalCount }}
            </span>
          </span>

          <span class="text-[11px] text-muted-foreground truncate hidden sm:inline">
            {{
              isPromptQueueActive
                ? "当前轮次执行完成后，将按顺序自动发出并执行"
                : hasWarning
                  ? "存在未进入上下文的补充消息，可一键发送或恢复至输入框"
                  : "在上一轮处理中发出的要求，将在当前轮次结束后按顺序处理"
            }}
          </span>
        </div>
      </div>

      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="isPromptQueueActive && queueItems.length > 1"
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors border border-transparent"
          title="清空待执行队列"
          @click="emit('clearQueue')"
        >
          <BaseIcon name="trash" size="xs" />
          <span>清空队列</span>
        </button>
        <button
          v-else-if="!isPromptQueueActive"
          type="button"
          class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-background/80 rounded-lg transition-colors border border-transparent hover:border-border/60"
          title="刷新投递状态"
          @click="emit('refresh')"
        >
          <BaseIcon name="refresh" size="xs" />
          <span>刷新</span>
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div
      v-if="receiptError"
      role="alert"
      class="mt-3 flex items-center gap-2 rounded-xl bg-destructive/10 border border-destructive/20 px-3 py-2 text-xs text-destructive font-medium"
    >
      <BaseIcon name="alert" size="xs" />
      <span>{{ receiptError }}</span>
    </div>

    <!-- Prompt Queue Items (First-class citizen) -->
    <div
      v-if="isPromptQueueActive"
      class="mt-3 space-y-2.5"
    >
      <div
        v-for="(item, index) in queueItems"
        :key="item.id"
        class="rounded-xl border border-border/70 bg-background/85 dark:bg-dark-900/80 p-3 text-xs space-y-2.5 shadow-2xs backdrop-blur-xs transition-all hover:border-border"
      >
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div class="flex items-center gap-2 min-w-0">
            <span
              class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-tight"
              :class="
                index === 0
                  ? isDraining
                    ? 'bg-blue-500/15 text-blue-700 dark:text-blue-300 ring-1 ring-blue-500/30'
                    : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-1 ring-emerald-500/30'
                  : 'bg-muted text-muted-foreground'
              "
            >
              <span
                v-if="index === 0"
                class="h-1.5 w-1.5 rounded-full"
                :class="isDraining ? 'bg-blue-500 animate-ping' : 'bg-emerald-500 animate-pulse'"
              />
              {{
                index === 0
                  ? isDraining
                    ? "#1 正在调取执行中..."
                    : "#1 下一步自动执行"
                  : `#${index + 1} 排队等待中`
              }}
            </span>
            <span v-if="index === 0" class="text-muted-foreground text-[11px] hidden sm:inline">
              {{ isDraining ? "· 正在建立会话连接" : "· 本轮结束后立即发送" }}
            </span>
          </div>

          <!-- Actions: Up, Down, Restore to Draft, Delete -->
          <div class="flex items-center gap-1.5 shrink-0 ml-auto">
            <!-- Move Up -->
            <button
              v-if="index > 0"
              type="button"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted border border-border/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="isDraining && index <= 1"
              title="上移执行顺序"
              @click="emit('moveUp', index)"
            >
              <BaseIcon name="chevron-down" size="xs" class="rotate-180" />
              <span class="hidden sm:inline">上移</span>
            </button>

            <!-- Move Down -->
            <button
              v-if="index < queueItems.length - 1"
              type="button"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted border border-border/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="isDraining && index === 0"
              title="下移执行顺序"
              @click="emit('moveDown', index)"
            >
              <BaseIcon name="chevron-down" size="xs" />
              <span class="hidden sm:inline">下移</span>
            </button>

            <!-- Restore to Draft -->
            <button
              type="button"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted border border-border/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="isDraining && index === 0"
              title="移出队列并填入输入框"
              @click="emit('restoreDraft', item.content, item.id)"
            >
              <BaseIcon name="pencil" size="xs" />
              <span>恢复草稿</span>
            </button>

            <!-- Delete -->
            <button
              type="button"
              class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-destructive/80 hover:text-destructive hover:bg-destructive/10 border border-destructive/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="isDraining && index === 0"
              title="从队列中删除"
              @click="emit('removeItem', item.id)"
            >
              <BaseIcon name="trash" size="xs" />
              <span>删除</span>
            </button>
          </div>
        </div>

        <!-- Preview Text -->
        <div
          v-if="extractContentText(item.content)"
          class="relative rounded-lg bg-muted/30 dark:bg-muted/15 border-l-2 border-primary/50 py-2 px-3 text-xs text-foreground/90 whitespace-pre-wrap break-words leading-relaxed group"
        >
          <div
            :class="{
              'line-clamp-3': !expandedMap[item.id] && extractContentText(item.content).length > 160
            }"
          >
            {{ extractContentText(item.content) }}
          </div>

          <button
            v-if="extractContentText(item.content).length > 160"
            type="button"
            class="mt-1 text-[11px] font-medium text-primary hover:underline"
            @click="toggleExpand(item.id)"
          >
            {{ expandedMap[item.id] ? "收起" : "展开全部" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Pending message -->
    <div
      v-if="!isPromptQueueActive && pendingMessage"
      class="mt-3 rounded-xl border border-border/70 bg-background/85 dark:bg-dark-900/80 p-3 text-xs space-y-2.5 shadow-2xs backdrop-blur-xs"
    >
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-2 min-w-0">
          <span
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium"
            :class="{
              'bg-blue-500/10 text-blue-600 dark:text-blue-400': pendingMessage.status === 'sending',
              'bg-destructive/10 text-destructive': pendingMessage.status === 'rejected',
              'bg-amber-500/10 text-amber-600 dark:text-amber-400': pendingMessage.status === 'unknown',
            }"
          >
            {{
              pendingMessage.status === "sending"
                ? "发送中..."
                : pendingMessage.status === "rejected"
                  ? "发送被拒绝"
                  : "结果待确认"
            }}
          </span>
          <span class="text-muted-foreground text-[11px] truncate">
            {{
              pendingMessage.status === "sending"
                ? "正在排队注入会话"
                : pendingMessage.status === "rejected"
                  ? "消息被拒绝，原草稿已保留"
                  : "网络波动导致结果未确认"
            }}
          </span>
        </div>
        <div class="flex items-center gap-1.5 shrink-0">
          <button
            v-if="pendingMessage.status === 'unknown'"
            type="button"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            :disabled="!canWrite"
            @click="emit('retryPending')"
          >
            重试发送
          </button>
          <button
            v-if="pendingMessage.status === 'rejected'"
            type="button"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium text-foreground hover:bg-muted border border-border/60 transition-colors"
            @click="emit('restoreDraft')"
          >
            恢复草稿
          </button>
        </div>
      </div>

      <!-- Preview Text -->
      <div
        v-if="extractContentText(pendingMessage.payload.content)"
        class="rounded-lg bg-muted/30 dark:bg-muted/15 border-l-2 border-primary/50 py-2 px-3 text-xs text-foreground/90 whitespace-pre-wrap break-words leading-relaxed"
      >
        {{ extractContentText(pendingMessage.payload.content) }}
      </div>
    </div>

    <!-- Receipts List (fallback / backward-compatibility) -->
    <div
      v-if="!isPromptQueueActive && receipts.length > 0"
      class="mt-3 space-y-2.5"
    >
      <div
        v-for="receipt in receipts"
        :key="receipt.message_id"
        class="rounded-xl border border-border/70 bg-background/85 dark:bg-dark-900/80 p-3 text-xs space-y-2.5 shadow-2xs backdrop-blur-xs transition-all hover:border-border"
      >
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div class="flex items-center gap-2 min-w-0">
            <span class="font-mono text-muted-foreground text-[11px]">#{{ receipt.sequence }}</span>
            <span
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium"
              :class="{
                'bg-blue-500/10 text-blue-600 dark:text-blue-400': receipt.status === 'queued',
                'bg-purple-500/10 text-purple-600 dark:text-purple-400': receipt.status === 'claimed',
                'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400': receipt.status === 'consumed',
                'bg-amber-500/15 text-amber-700 dark:text-amber-300': receipt.status === 'not_consumed',
                'bg-destructive/10 text-destructive': receipt.status === 'rejected',
              }"
            >
              {{
                {
                  queued: "排队等待中",
                  claimed: "正在注入",
                  consumed: "已写入上下文",
                  not_consumed: "未消费",
                  rejected: "已拒绝",
                }[receipt.status]
              }}
            </span>
            <span
              v-if="receipt.reason"
              class="text-muted-foreground text-[11px] truncate"
            >
              · {{ getReasonDescription(receipt.reason) }}
            </span>
          </div>

          <!-- Actions for receipt -->
          <div
            v-if="['rejected', 'not_consumed'].includes(receipt.status) && receipt.content != null"
            class="flex items-center gap-2 shrink-0 ml-auto"
          >
            <!-- 恢复到输入框 -->
            <button
              type="button"
              class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium text-foreground hover:bg-muted border border-border/60 transition-colors active:scale-95"
              title="恢复到输入框编辑"
              @click="emit('restoreDraft', receipt.content, receipt.message_id)"
            >
              <BaseIcon name="pencil" size="xs" />
              <span>恢复到输入框</span>
            </button>
            <!-- 作为新消息发送 -->
            <button
              type="button"
              class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-2xs active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="!canSend"
              :title="canSend ? '作为新消息立即发送' : '当前正在执行或不可发送'"
              @click="emit('resendAsNew', receipt.content, receipt.message_id)"
            >
              <BaseIcon name="sparkle" size="xs" />
              <span>作为新消息发送</span>
            </button>
          </div>
        </div>

        <!-- Receipt Content Preview: Styled like a stylish quotation bubble -->
        <div
          v-if="extractContentText(receipt.content)"
          class="relative rounded-lg bg-muted/30 dark:bg-muted/15 border-l-2 border-primary/50 py-2 px-3 text-xs text-foreground/90 whitespace-pre-wrap break-words leading-relaxed group"
        >
          <div
            :class="{
              'line-clamp-3': !expandedMap[receipt.message_id] && extractContentText(receipt.content).length > 160
            }"
          >
            {{ extractContentText(receipt.content) }}
          </div>

          <button
            v-if="extractContentText(receipt.content).length > 160"
            type="button"
            class="mt-1 text-[11px] font-medium text-primary hover:underline"
            @click="toggleExpand(receipt.message_id)"
          >
            {{ expandedMap[receipt.message_id] ? "收起" : "展开全部" }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

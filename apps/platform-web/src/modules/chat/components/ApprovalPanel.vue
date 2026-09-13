<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import {
  buildReviewResponses,
  type PendingReview,
  type ReviewDraft,
} from "../approvals";
import { asObject, readable } from "../transcript";

const props = defineProps<{ reviews: PendingReview[]; disabled: boolean }>();
const emit = defineEmits<{ submit: [drafts: Record<string, ReviewDraft[]>] }>();
const drafts = ref<Record<string, ReviewDraft[]>>({});
let fingerprints = new Map<string, string>();

watch(
  () => JSON.stringify(props.reviews.map((r) => [r.id, r.fingerprint])),
  () => {
    // A changed request must never inherit an approval for different arguments.
    drafts.value = Object.fromEntries(
      props.reviews.map((review) => [
        review.id,
        fingerprints.get(review.id) === review.fingerprint &&
        drafts.value[review.id]
          ? drafts.value[review.id]
          : review.actions.map((action) => ({ args: readable(action.args) })),
      ]),
    );
    fingerprints = new Map(
      props.reviews.map((review) => [review.id, review.fingerprint]),
    );
  },
  { immediate: true },
);

const validation = computed(() => {
  try {
    buildReviewResponses(props.reviews, drafts.value);
    return "";
  } catch (error) {
    return error instanceof Error ? error.message : "请完成所有决策";
  }
});


function editedFields(args: Record<string, unknown>, value?: string) {
  try {
    const edited = asObject(JSON.parse(value ?? ""));
    return Object.keys(args).filter((key) => readable(args[key]) !== readable(edited[key]));
  } catch {
    return [];
  }
}

function isEditDiff(action: PendingReview["actions"][number]): boolean {
  const args = asObject(action.args);
  return (
    action.name === "edit_file" &&
    typeof args.old_string === "string" &&
    typeof args.new_string === "string"
  );
}

function getActionPath(action: PendingReview["actions"][number]): string | undefined {
  const args = asObject(action.args);
  const path = args.file_path ?? args.path;
  return typeof path === "string" ? path : undefined;
}

function isWriteFile(action: PendingReview["actions"][number]): boolean {
  const args = asObject(action.args);
  return action.name === "write_file" && typeof args.content === "string";
}

function getWriteFileContent(action: PendingReview["actions"][number]): string {
  return String(asObject(action.args).content ?? "");
}

function isCommandExecute(action: PendingReview["actions"][number]): boolean {
  const args = asObject(action.args);
  return action.name === "execute" && typeof args.command === "string";
}

function getCommand(action: PendingReview["actions"][number]): string {
  return String(asObject(action.args).command ?? "");
}

function getActionTitle(name: string): string {
  switch (name) {
    case "edit_file":
      return "修改代码文件";
    case "write_file":
      return "写入文件";
    case "execute":
      return "执行系统命令";
    default:
      return name;
  }
}

const currentDecisionSummary = computed(() => {
  const allDrafts = Object.values(drafts.value).flat();
  const types = allDrafts.map((d) => d.type).filter(Boolean);
  if (types.includes("reject")) return "reject";
  if (types.includes("edit")) return "edit";
  if (types.length > 0 && types.every((t) => t === "approve")) return "approve";
  return "pending";
});
</script>

<template>
  <section
    v-if="reviews.length"
    aria-label="待审批操作"
    class="min-w-0 max-w-full space-y-4 overflow-hidden rounded-2xl border border-amber-300/80 bg-amber-50/40 p-4 shadow-sm backdrop-blur-sm dark:border-amber-700/50 dark:bg-amber-950/20"
  >
    <!-- 头部警示与概览 -->
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-center gap-2.5">
        <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-500/15 text-amber-600 dark:bg-amber-400/20 dark:text-amber-400">
          <BaseIcon
            name="alert"
            class="h-4 w-4"
          />
        </span>
        <div>
          <h2 class="text-sm font-semibold text-gray-900 dark:text-white">
            需要人工确认 (HITL) · {{ reviews.length }} 项请求
          </h2>
          <p class="text-xs text-gray-500 dark:text-dark-300">
            Agent 请求执行写文件或系统调用，请审查以下操作并选择决策。
          </p>
        </div>
      </div>
      <span class="rounded-full bg-amber-100 px-2.5 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
        等待决策
      </span>
    </div>

    <!-- 具体待审批项目列表 -->
    <article
      v-for="review in reviews"
      :key="review.id"
      class="min-w-0 max-w-full space-y-4"
    >
      <div class="flex items-center justify-between text-xs text-gray-400 dark:text-dark-400">
        <span>作用域: <strong class="font-medium text-gray-600 dark:text-dark-200">{{ review.namespace.join(" / ") || "主任务" }}</strong></span>
        <span class="max-w-[180px] truncate font-mono text-[11px]">{{ review.id }}</span>
      </div>

      <template v-if="review.supported">
        <fieldset
          v-for="(action, index) in review.actions"
          :key="index"
          :disabled="disabled"
          class="min-w-0 max-w-full space-y-3 overflow-hidden rounded-xl border border-gray-200/90 bg-white p-4 shadow-sm dark:border-dark-700 dark:bg-dark-900"
        >
          <!-- 操作标题与资源路径标签 -->
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2.5 dark:border-dark-800">
            <legend class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <span>{{ getActionTitle(action.name) }}</span>
              <span class="font-mono text-xs font-normal text-gray-400 dark:text-dark-400">({{ action.name }})</span>
            </legend>
            <span
              v-if="getActionPath(action)"
              class="flex items-center gap-1.5 rounded-md bg-gray-100 px-2 py-0.5 font-mono text-xs text-gray-700 dark:bg-dark-800 dark:text-dark-200"
            >
              <span>📄</span>
              <span class="max-w-[280px] truncate">{{ getActionPath(action) }}</span>
            </span>
          </div>

          <!-- 1. 代码修改 Diff 呈现 (针对 edit_file) -->
          <template v-if="isEditDiff(action)">
            <div class="min-w-0 max-w-full space-y-2">
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>拟应用的代码变更对比</span>
                <span class="text-[11px] text-gray-400">左侧为原内容，右侧为新内容</span>
              </div>
              <div class="grid gap-2 text-xs md:grid-cols-2">
                <div class="overflow-hidden rounded-lg border border-red-200/80 bg-red-50/60 dark:border-red-950/50 dark:bg-red-950/20">
                  <div class="border-b border-red-100 bg-red-100/50 px-2.5 py-1 font-mono text-[11px] font-medium text-red-700 dark:border-red-900/40 dark:bg-red-900/30 dark:text-red-300">
                    - 原代码片段 (old_string)
                  </div>
                  <pre class="max-h-60 overflow-auto p-2.5 font-mono leading-relaxed whitespace-pre-wrap break-words text-red-900 dark:text-red-200">{{ asObject(action.args).old_string }}</pre>
                </div>
                <div class="overflow-hidden rounded-lg border border-emerald-200/80 bg-emerald-50/60 dark:border-emerald-950/50 dark:bg-emerald-950/20">
                  <div class="border-b border-emerald-100 bg-emerald-100/50 px-2.5 py-1 font-mono text-[11px] font-medium text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-900/30 dark:text-emerald-300">
                    + 新代码片段 (new_string)
                  </div>
                  <pre class="max-h-60 overflow-auto p-2.5 font-mono leading-relaxed whitespace-pre-wrap break-words text-emerald-900 dark:text-emerald-200">{{ asObject(action.args).new_string }}</pre>
                </div>
              </div>
            </div>
          </template>

          <!-- 2. 写入文件内容呈现 (针对 write_file) -->
          <template v-else-if="isWriteFile(action)">
            <div class="min-w-0 max-w-full space-y-1.5">
              <div class="flex items-center justify-between text-xs text-gray-500">
                <span>拟写入的文件完整内容</span>
                <span class="font-mono text-[11px] text-gray-400">{{ getActionPath(action) }}</span>
              </div>
              <div class="overflow-hidden rounded-lg border border-sky-200/80 bg-sky-50/40 dark:border-sky-950/50 dark:bg-sky-950/20">
                <div class="border-b border-sky-100 bg-sky-100/50 px-2.5 py-1 font-mono text-[11px] font-medium text-sky-800 dark:border-sky-900/40 dark:bg-sky-900/30 dark:text-sky-300">
                  📄 文件内容预览 (content)
                </div>
                <pre class="max-h-60 overflow-auto p-2.5 font-mono text-xs leading-relaxed whitespace-pre-wrap break-words text-gray-900 dark:text-dark-100">{{ getWriteFileContent(action) }}</pre>
              </div>
            </div>
          </template>

          <!-- 3. 系统命令执行呈现 (针对 execute) -->
          <template v-else-if="isCommandExecute(action)">
            <div class="min-w-0 max-w-full space-y-1.5">
              <span class="text-xs text-gray-500">拟在 Docker 沙箱中执行的 Shell 命令</span>
              <div class="overflow-hidden rounded-lg bg-gray-950 text-xs shadow-inner">
                <div class="flex items-center gap-1.5 border-b border-gray-800 bg-gray-900/70 px-3 py-1.5">
                  <span class="h-2 w-2 rounded-full bg-red-500/70" />
                  <span class="h-2 w-2 rounded-full bg-yellow-500/70" />
                  <span class="h-2 w-2 rounded-full bg-green-500/70" />
                  <span class="ml-2 font-mono text-[10px] text-gray-400">Terminal</span>
                </div>
                <pre class="max-h-48 overflow-auto p-3 font-mono leading-relaxed whitespace-pre-wrap break-all text-gray-100"><span class="select-none text-emerald-400">$ </span>{{ getCommand(action) }}</pre>
              </div>
            </div>
          </template>

          <!-- 4. 普通参数呈现（兜底） -->
          <template v-else>
            <div class="min-w-0 max-w-full space-y-1">
              <span class="text-xs text-gray-500">调用参数</span>
              <pre class="max-h-48 overflow-auto rounded-lg border border-gray-100 bg-gray-50 p-2.5 font-mono text-xs text-gray-800 dark:border-dark-800 dark:bg-dark-800/60 dark:text-dark-100 whitespace-pre-wrap break-all">{{ readable(action.args) }}</pre>
            </div>
          </template>

          <!-- 决策操作栏：高质感药丸选项卡 -->
          <div class="pt-1">
            <div class="flex flex-wrap items-center gap-2.5">
              <span class="text-xs font-medium text-gray-700 dark:text-dark-200">处理决策:</span>

              <span
                v-if="action.allowed.includes('approve')"
                role="button"
                tabindex="0"
                data-action="approve"
                class="flex cursor-pointer select-none items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all"
                :class="drafts[review.id]![index]!.type === 'approve'
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-700 shadow-sm dark:bg-emerald-950/40 dark:text-emerald-300'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200'"
                @click="drafts[review.id]![index]!.type = 'approve'"
                @keydown.enter="drafts[review.id]![index]!.type = 'approve'"
              >
                <span>✓</span>
                <span>批准 (Approve)</span>
              </span>

              <span
                v-if="action.allowed.includes('edit')"
                role="button"
                tabindex="0"
                data-action="edit"
                class="flex cursor-pointer select-none items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all"
                :class="drafts[review.id]![index]!.type === 'edit'
                  ? 'border-amber-500 bg-amber-50 text-amber-700 shadow-sm dark:bg-amber-950/40 dark:text-amber-300'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200'"
                @click="drafts[review.id]![index]!.type = 'edit'"
                @keydown.enter="drafts[review.id]![index]!.type = 'edit'"
              >
                <span>✎</span>
                <span>修改参数 (Edit)</span>
              </span>

              <span
                v-if="action.allowed.includes('reject')"
                role="button"
                tabindex="0"
                data-action="reject"
                class="flex cursor-pointer select-none items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all"
                :class="drafts[review.id]![index]!.type === 'reject'
                  ? 'border-red-500 bg-red-50 text-red-700 shadow-sm dark:bg-red-950/40 dark:text-red-300'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200'"
                @click="drafts[review.id]![index]!.type = 'reject'"
                @keydown.enter="drafts[review.id]![index]!.type = 'reject'"
              >
                <span>✕</span>
                <span>拒绝 (Reject)</span>
              </span>
            </div>
          </div>

          <!-- 修改参数抽屉面板 -->
          <div
            v-if="drafts[review.id]![index]!.type === 'edit'"
            class="space-y-2 rounded-lg border border-amber-200/80 bg-amber-50/40 p-3 dark:border-amber-900/40 dark:bg-amber-950/20 text-xs"
          >
            <div class="flex items-center justify-between">
              <span class="font-medium text-amber-900 dark:text-amber-200">修改后参数（JSON 格式）：</span>
              <span
                class="text-[11px] font-medium"
                :class="editedFields(action.args, drafts[review.id]![index]!.args).length ? 'text-amber-700 dark:text-amber-300' : 'text-gray-400'"
                role="status"
              >
                已变更: {{ editedFields(action.args, drafts[review.id]![index]!.args).join('、') || '无' }}
              </span>
            </div>
            <textarea
              v-model="drafts[review.id]![index]!.args"
              class="pw-input min-h-32 w-full font-mono text-xs leading-relaxed"
            />
            <p class="text-[11px] text-gray-500 dark:text-dark-400">
              请确保保留原有的 JSON 数据结构与必要字段类型；提交后将使用你提供的值执行。
            </p>
          </div>

          <!-- 拒绝原因输入面板 -->
          <div
            v-if="drafts[review.id]![index]!.type === 'reject'"
            class="space-y-2 rounded-lg border border-red-200/80 bg-red-50/40 p-3 dark:border-red-950/50 dark:bg-red-950/20 text-xs"
          >
            <span class="font-medium text-red-900 dark:text-red-200">拒绝原因（将反馈给 Agent）：</span>
            <textarea
              v-model="drafts[review.id]![index]!.message"
              placeholder="例如：先不要直接改原文件，请先进行备份..."
              maxlength="2000"
              class="pw-input min-h-20 w-full text-xs"
            />
          </div>
        </fieldset>
      </template>

      <!-- 不支持的请求兜底 -->
      <template v-else>
        <p
          role="alert"
          class="rounded-lg bg-red-50 p-3 text-xs text-red-600 dark:bg-red-950/30 dark:text-red-300"
        >
          当前请求格式不支持安全审批，请联系系统管理员。
        </p>
        <pre class="max-h-48 overflow-auto whitespace-pre-wrap text-xs">{{ readable(review.raw) }}</pre>
      </template>
    </article>

    <!-- 校验提示与提交操作栏 -->
    <div class="flex flex-wrap items-center justify-between gap-3 pt-1">
      <p
        v-if="validation"
        class="text-xs text-amber-700 dark:text-amber-400"
      >
        ⚠️ {{ validation }}
      </p>
      <div
        v-else
        class="text-xs text-gray-500 dark:text-dark-300"
      >
        所有决策均已就绪，点击下方按钮完成提交
      </div>

      <BaseButton
        :disabled="disabled || !!validation"
        :variant="currentDecisionSummary === 'reject' ? 'danger' : currentDecisionSummary === 'approve' ? 'primary' : 'primary'"
        class="h-9 px-5 font-medium shadow-sm transition-all"
        @click="emit('submit', drafts)"
      >
        <span v-if="currentDecisionSummary === 'approve'">✓ 确认批准所选操作</span>
        <span v-else-if="currentDecisionSummary === 'reject'">✕ 确认驳回所选操作</span>
        <span v-else-if="currentDecisionSummary === 'edit'">✎ 提交修改参数并执行</span>
        <span v-else>提交所选决策</span>
      </BaseButton>
    </div>
  </section>
</template>

<style scoped>
fieldset {
  min-width: 0;
}
</style>

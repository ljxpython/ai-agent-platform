<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
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
const labels = { approve: "批准", reject: "拒绝", edit: "修改参数" };
function editedFields(args: Record<string, unknown>, value?: string) {
  try {
    const edited = asObject(JSON.parse(value ?? ""));
    return Object.keys(args).filter(key => readable(args[key]) !== readable(edited[key]));
  } catch { return []; }
}
</script>

<template>
  <section
    v-if="reviews.length"
    aria-label="待审批操作"
    class="space-y-4 rounded-xl border border-amber-300 bg-amber-50/50 p-4 dark:bg-amber-950/20"
  >
    <h2 class="font-medium">
      需要你的确认 · {{ reviews.length }} 项请求
    </h2>
    <article
      v-for="review in reviews"
      :key="review.id"
      class="space-y-3"
    >
      <p class="break-all text-xs text-gray-500">
        {{ review.namespace.join(" / ") || "主任务" }} · {{ review.id }}
      </p>
      <template v-if="review.supported">
        <fieldset
          v-for="(action, index) in review.actions"
          :key="index"
          :disabled="disabled"
          class="space-y-2"
        >
          <legend class="font-medium">
            {{ action.name }}
          </legend>
          <pre class="max-h-48 overflow-auto whitespace-pre-wrap text-xs">{{
            readable(action.args)
          }}</pre>
          <label class="block text-xs">处理方式
            <select
              v-model="drafts[review.id]![index]!.type"
              class="pw-input mt-1"
            >
              <option :value="undefined">请选择</option>
              <option
                v-for="kind in action.allowed"
                :key="kind"
                :value="kind"
              >
                {{ labels[kind] }}
              </option>
            </select>
          </label>
          <label
            v-if="drafts[review.id]![index]!.type === 'edit'"
            class="block text-xs"
          >修改后参数（JSON，保留原类型与字段）
            <textarea
              v-model="drafts[review.id]![index]!.args"
              class="pw-input mt-1 min-h-32 font-mono"
            />
            <span class="text-gray-500">上方为原参数，下方为本次提交值；不会更换工具。</span>
            <span
              class="mt-1 block"
              role="status"
            >变更字段：{{ editedFields(action.args, drafts[review.id]![index]!.args).join('、') || '无' }}</span>
          </label>
          <label
            v-if="drafts[review.id]![index]!.type === 'reject'"
            class="block text-xs"
          >拒绝原因
            <textarea
              v-model="drafts[review.id]![index]!.message"
              maxlength="2000"
              class="pw-input mt-1"
            />
          </label>
        </fieldset>
      </template>
      <template v-else>
        <p role="alert">
          当前请求格式不支持安全审批，请联系管理员。
        </p>
        <pre class="max-h-48 overflow-auto whitespace-pre-wrap text-xs">{{
          readable(review.raw)
        }}</pre>
      </template>
    </article>
    <p
      v-if="validation"
      class="text-xs text-gray-500"
    >
      {{ validation }}
    </p>
    <BaseButton
      :disabled="disabled || !!validation"
      @click="emit('submit', drafts)"
    >
      提交所选决策
    </BaseButton>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import { platformHttpClient } from "@/services/http/client";
import { resolvePlatformHttpErrorMessage } from "@/utils/http-error";

const props = defineProps<{
  show: boolean;
  projectId: string;
  agentId: string;
}>();
const emit = defineEmits<{ close: []; select: [ids: string[]] }>();
type Session = {
  thread_id: string;
  title: string;
  created_at: string;
  status: string;
  feedback: string[];
};
type Page = {
  items: Session[];
  scanned: number;
  next_offset: number | null;
  limited: boolean;
  notice: string;
};
const rows = ref<Session[]>([]);
const selected = ref<string[]>([]);
const since = ref("");
const until = ref("");
const feedback = ref("all");
const status = ref("all");
const next = ref<number | null>(null);
const busy = ref(false);
const error = ref("");
const notice = ref("");
let generation = 0;
async function search(offset = 0) {
  const ticket = ++generation;
  busy.value = true;
  error.value = "";
  if (!offset) {
    rows.value = [];
    selected.value = [];
  }
  try {
    const { data } = await platformHttpClient.post<Page>(
      "/api/evaluation/materials/sessions",
      {
        agent_id: props.agentId,
        offset,
        feedback: feedback.value,
        status: status.value,
        since: since.value ? new Date(since.value).toISOString() : null,
        until: until.value ? new Date(until.value).toISOString() : null,
      },
      { headers: { "X-Project-Id": props.projectId } },
    );
    if (ticket !== generation) return;
    rows.value = offset
      ? [
          ...rows.value,
          ...data.items.filter(
            (r) => !rows.value.some((old) => old.thread_id === r.thread_id),
          ),
        ]
      : data.items;
    next.value = data.next_offset;
    notice.value =
      data.notice +
      (data.limited ? " 已达到查找上限，请缩小Agent或状态范围。" : "");
  } catch (e) {
    if (ticket === generation)
      error.value = resolvePlatformHttpErrorMessage(
        e,
        "读取会话失败。",
        "评测资料筛选",
      );
  } finally {
    if (ticket === generation) busy.value = false;
  }
}
watch(
  () => [props.show, props.projectId, props.agentId],
  () => {
    generation++;
    rows.value = [];
    selected.value = [];
    next.value = null;
    if (props.show && props.agentId) void search();
  },
);
</script>
<template>
  <BaseDialog :show="show" title="筛选会话资料" @close="emit('close')">
    <div class="space-y-3">
      <p>
        当前项目和 Agent
        沿用聊天页顶部的选择。勾选最多20个会话，再确认资料范围。
      </p>
      <div class="flex flex-wrap gap-3">
        <label
          >创建时间起<input
            v-model="since"
            type="datetime-local"
            class="pw-input block"
        /></label>
        <label
          >创建时间止<input
            v-model="until"
            type="datetime-local"
            class="pw-input block"
        /></label>
        <label
          >我的反馈<select v-model="feedback" class="pw-input block">
            <option value="all">全部</option>
            <option value="positive">有好评</option>
            <option value="negative">有差评</option>
            <option value="none">无有效反馈</option>
          </select></label
        >
        <label
          >执行状态<select v-model="status" class="pw-input block">
            <option value="all">全部</option>
            <option value="idle">空闲</option>
            <option value="busy">运行中</option>
            <option value="interrupted">待审批</option>
            <option value="error">异常</option>
          </select></label
        >
      </div>
      <BaseButton :disabled="busy" @click="search()">筛选会话</BaseButton>
      <p v-if="error" role="alert" class="text-red-600">{{ error }}</p>
      <p>{{ notice }}</p>
      <div class="max-h-80 overflow-auto space-y-2">
        <label
          v-for="row in rows"
          :key="row.thread_id"
          class="flex items-start gap-2 border-b py-2"
        >
          <input
            v-model="selected"
            type="checkbox"
            :value="row.thread_id"
            :disabled="
              !selected.includes(row.thread_id) && selected.length >= 20
            "
          />
          <span
            >{{ row.title
            }}<small class="block"
              >{{ row.created_at }} · {{ row.status }} ·
              {{
                row.feedback
                  .map((r) => (r === "positive" ? "好评" : "差评"))
                  .join("、") || "无有效反馈"
              }}</small
            ></span
          >
        </label>
      </div>
      <p v-if="!rows.length && !busy">当前已查范围内没有符合条件的会话。</p>
      <BaseButton v-if="next !== null" :disabled="busy" @click="search(next!)"
        >继续查找下一批</BaseButton
      >
      <BaseButton
        :disabled="busy || !selected.length"
        @click="emit('select', [...selected])"
        >使用选中的 {{ selected.length }} 个会话</BaseButton
      >
    </div>
  </BaseDialog>
</template>

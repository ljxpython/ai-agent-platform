<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { platformHttpClient as http } from "@/services/http/client";
import { extractPlatformHttpError } from "@/utils/http-error";
import InspectionConsent from "./InspectionConsent.vue";

const props = defineProps<{
  projectId: string;
  threadId: string;
  messageId: string;
  allowExport: boolean;
  allowInspection?: boolean;
  allowImprovement?: boolean;
}>();
const open = ref(false);
const busy = ref(false);
const error = ref("");
const saved = ref("");
const linkStatus = ref("");
const linkReason = ref("");
const linkedTraceIds = ref<string[]>([]);
const projectionMessage = computed(() => {
  if (linkStatus.value === "linked")
    return `反馈已关联原生评估（${linkedTraceIds.value.length} 条 Trace）`;
  if (linkStatus.value === "pending")
    return "反馈关联处理中，可刷新状态查看结果";
  if (linkStatus.value !== "unavailable") return "";
  if (linkReason.value === "export_authorization_required")
    return "反馈已保留在本平台；尚未授权关联评测";
  if (linkReason.value === "source_revoked_or_expired")
    return "评测关联授权已失效；原生评价撤销由后台核对";
  return "暂无法关联原生评估；反馈仍保留在本平台";
});
const rating = ref<"positive" | "negative" | "withdrawn">("negative");
const comment = ref("");
const revision = ref(0);
const eventId = ref("");
const runIds = ref<string[]>([]);
const scenario = ref("");
const expected = ref("");
const synthetic = ref(false);
const pending = ref<{
  event_id: string;
  expected_revision: number;
  rating: string;
  comment: string;
} | null>(null);
const exportId = ref<string | null>(null);
const exportRequest = ref<{
  export_id: string;
  event_id: string;
  data_class: string;
  purpose: string;
  scenario: string;
  expected: string;
  synthetic_attestation: boolean;
} | null>(null);
const delivered = ref(false);
let epoch = 0;
const headers = computed(() => ({ "x-project-id": props.projectId }));
const path = computed(
  () =>
    `/api/evaluation/threads/${encodeURIComponent(props.threadId)}/messages/${encodeURIComponent(props.messageId)}/feedback`,
);

watch(
  () => [props.projectId, props.threadId, props.messageId],
  () => {
    epoch += 1;
    busy.value = false;
    rating.value = "negative";
    comment.value = "";
    exportRequest.value = null;
    open.value = false;
    pending.value = null;
    exportId.value = null;
    saved.value = "";
    linkStatus.value = "";
    linkReason.value = "";
    linkedTraceIds.value = [];
    delivered.value = false;
    synthetic.value = false;
    scenario.value = "";
    expected.value = "";
    revision.value = 0;
    eventId.value = "";
    runIds.value = [];
    error.value = "";
  },
);
async function load(current = epoch) {
  const { data } = await http.get(path.value, { headers: headers.value });
  if (current !== epoch) return null;
  revision.value = data.revision;
  eventId.value = data.event_id || "";
  runIds.value = data.run_ids || [];
  rating.value = data.rating || "negative";
  comment.value = data.comment || "";
  linkStatus.value = data.link_status || "";
  linkReason.value = data.link_reason || "";
  linkedTraceIds.value = data.mlflow_trace_ids || [];
  const currentExport = data.export;
  if (currentExport && !["revoked", "expired"].includes(currentExport.status)) {
    exportId.value = currentExport.export_id;
    delivered.value = currentExport.status === "exported";
    scenario.value = currentExport.scenario;
    expected.value = currentExport.expected;
    synthetic.value = true;
    saved.value = `合成复现状态：${currentExport.status}；导出编号：${currentExport.export_id}`;
  } else {
    exportId.value = null;
    delivered.value = false;
    synthetic.value = false;
    saved.value = currentExport
      ? currentExport.status === "revoked"
        ? "导出授权已撤销，关联题库不可新运行"
        : "导出授权已到期，关联题库不可新运行"
      : "";
  }
  return data;
}
async function show() {
  const current = epoch;
  busy.value = true;
  error.value = "";
  try {
    await load(current);
    if (current === epoch) open.value = true;
  } catch (cause) {
    if (current === epoch)
      error.value = extractPlatformHttpError(cause).message;
  } finally {
    if (current === epoch) busy.value = false;
  }
}
async function save() {
  const current = epoch;
  busy.value = true;
  error.value = "";
  pending.value ||= {
    event_id: crypto.randomUUID(),
    expected_revision: revision.value,
    rating: rating.value,
    comment: comment.value,
  };
  const request = pending.value;
  try {
    const { data } = await http.post(path.value, request, {
      headers: headers.value,
    });
    if (current !== epoch) return;
    revision.value = data.revision;
    eventId.value = data.event_id;
    runIds.value = data.run_ids || [];
    pending.value = null;
    exportId.value = null;
    delivered.value = false;
    exportRequest.value = null;
    linkStatus.value = "unavailable";
    linkReason.value = "export_authorization_required";
    linkedTraceIds.value = [];
    saved.value =
      data.rating === "withdrawn"
        ? "反馈已撤回"
        : data.rating === "negative"
          ? "反馈已保存；问题待确认"
          : "反馈已保存";
  } catch (cause) {
    if (current !== epoch) return;
    // Reconcile an uncertain write before enabling any fresh submission.
    const pendingId = request.event_id;
    try {
      const data = await load(current);
      if (current !== epoch) return;
      if (data?.event_id === pendingId) {
        pending.value = null;
        saved.value = "反馈已保存";
        return;
      }
    } catch {
      /* Keep the original request for an explicit retry. */
    }
    if (current !== epoch) return;
    const detail = extractPlatformHttpError(cause);
    if (detail.status && detail.status >= 400 && detail.status < 500)
      pending.value = null;
    error.value = detail.message;
  } finally {
    if (current === epoch) busy.value = false;
  }
}
async function authorize() {
  const current = epoch;
  busy.value = true;
  error.value = "";
  exportRequest.value ||= {
    export_id: crypto.randomUUID(),
    event_id: eventId.value,
    data_class: "synthetic",
    purpose: "regression",
    scenario: scenario.value,
    expected: expected.value,
    synthetic_attestation: synthetic.value,
  };
  try {
    const { data } = await http.post(
      "/api/evaluation/exports",
      exportRequest.value,
      { headers: headers.value },
    );
    if (current !== epoch) return;
    exportRequest.value = null;
    exportId.value = data.export_id;
    linkStatus.value = "pending";
    linkReason.value = "";
    saved.value = `合成复现已授权，状态：${data.status}；导出编号：${data.export_id}`;
  } catch (cause) {
    if (current !== epoch) return;
    const detail = extractPlatformHttpError(cause);
    if (detail.status && detail.status >= 400 && detail.status < 500)
      exportRequest.value = null;
    error.value =
      detail.message +
      (exportRequest.value ? "；接收结果待确认，请重试原授权请求。" : "");
  } finally {
    if (current === epoch) busy.value = false;
  }
}
async function deliver() {
  const current = epoch;
  busy.value = true;
  error.value = "";
  try {
    const { data } = await http.post(
      `/api/evaluation/exports/${exportId.value}/deliver`,
      {},
      { headers: headers.value },
    );
    if (current !== epoch) return;
    delivered.value = true;
    saved.value = `已接收至评测审核队列；Trace：${data.receipt.trace_id}`;
  } catch (cause) {
    if (current === epoch)
      error.value = extractPlatformHttpError(cause).message;
  } finally {
    if (current === epoch) busy.value = false;
  }
}
async function revoke() {
  const current = epoch;
  busy.value = true;
  error.value = "";
  try {
    await http.post(
      `/api/evaluation/exports/${exportId.value}/revoke`,
      {},
      { headers: headers.value },
    );
    if (current !== epoch) return;
    saved.value = "导出授权已撤销，关联题库不可新运行";
    delivered.value = false;
    exportId.value = null;
    synthetic.value = false;
    linkStatus.value = "unavailable";
    linkReason.value = "source_revoked_or_expired";
  } catch (cause) {
    if (current === epoch)
      error.value = extractPlatformHttpError(cause).message;
  } finally {
    if (current === epoch) busy.value = false;
  }
}
</script>

<template>
  <div class="text-xs">
    <button
      type="button"
      class="rounded px-1.5 py-0.5 text-gray-500 hover:bg-gray-100"
      :disabled="busy"
      @click="show"
    >
      评价回答
    </button>
    <RouterLink
      v-if="allowImprovement"
      :to="{
        name: 'workspace-evaluation',
        params: { projectId },
        query: { new: '1', thread: threadId, message: messageId },
      }"
      class="ml-2 rounded px-1.5 py-0.5 text-primary-700 dark:text-primary-300"
      >让AI帮我改进</RouterLink
    >
    <div
      v-if="open"
      role="dialog"
      aria-label="回答反馈"
      class="mt-2 max-w-xl rounded-lg border border-gray-200 bg-white p-4 text-gray-700 dark:border-dark-600 dark:bg-dark-800 dark:text-dark-200"
    >
      <p class="mb-3 font-medium">回答反馈</p>
      <fieldset :disabled="busy || !!pending" class="space-y-3">
        <label class="mr-3"
          ><input v-model="rating" type="radio" value="positive" />
          有帮助</label
        >
        <label class="mr-3"
          ><input v-model="rating" type="radio" value="negative" />
          有问题</label
        >
        <label
          ><input v-model="rating" type="radio" value="withdrawn" />
          撤回反馈</label
        >
        <label class="block"
          >说明（选填）<textarea
            v-model="comment"
            aria-label="反馈说明"
            maxlength="1000"
            class="mt-1 block w-full rounded border p-2 dark:bg-dark-900"
          />
        </label>
      </fieldset>
      <div class="mt-3 flex gap-3">
        <button
          type="button"
          class="pw-btn-primary rounded px-3 py-1"
          :disabled="busy || !!exportRequest"
          @click="save"
        >
          {{ pending ? "核对并重试原请求" : "保存反馈" }}
        </button>
        <button type="button" :disabled="busy" @click="open = false">
          关闭
        </button>
        <button type="button" :disabled="busy" @click="show">刷新状态</button>
      </div>
      <InspectionConsent
        v-if="allowInspection && runIds.length === 1"
        :scope="{ projectId, threadId, runId: runIds[0]! }"
      />
      <details
        v-if="allowExport && eventId && rating !== 'withdrawn'"
        class="mt-4"
      >
        <summary>授权合成复现用于评测</summary>
        <p class="my-2">
          仅项目管理员可提交自己会话的合成复现。授权包含评分、操作者及会话/运行标识，用于关联原生评估；不导出聊天原文或反馈备注。请勿填写真实姓名、业务资料或密钥。
        </p>
        <fieldset
          :disabled="busy || !!exportId || !!exportRequest"
          class="space-y-2"
        >
          <label class="block"
            >合成场景<textarea
              v-model="scenario"
              aria-label="合成场景"
              maxlength="12000"
              class="block w-full rounded border p-2 dark:bg-dark-900"
            />
          </label>
          <label class="block"
            >正确预期<textarea
              v-model="expected"
              aria-label="正确预期"
              maxlength="4000"
              class="block w-full rounded border p-2 dark:bg-dark-900"
            />
          </label>
          <label class="block"
            ><input v-model="synthetic" type="checkbox" />
            我确认这些材料均为合成数据，授权用于回归评测（24 小时）</label
          >
        </fieldset>
        <button
          type="button"
          class="mt-2 rounded border px-3 py-1"
          :disabled="
            busy ||
            !!exportId ||
            !synthetic ||
            !scenario.trim() ||
            !expected.trim()
          "
          @click="authorize"
        >
          {{ exportRequest ? "重试原授权请求" : "授权合成复现" }}
        </button>
        <button
          v-if="exportId"
          type="button"
          class="ml-2 rounded border px-3 py-1"
          :disabled="busy || delivered"
          @click="deliver"
        >
          发送到评测审核
        </button>
        <button
          v-if="exportId"
          type="button"
          class="ml-2 rounded border px-3 py-1"
          :disabled="busy"
          @click="revoke"
        >
          撤销导出授权
        </button>
      </details>
    </div>
    <p v-if="saved" role="status" class="mt-1 text-emerald-700">{{ saved }}</p>
    <p v-if="projectionMessage" role="status" class="mt-1 text-gray-500">
      {{ projectionMessage }}
    </p>
    <p v-if="error" role="alert" class="mt-1 text-red-600">{{ error }}</p>
  </div>
</template>

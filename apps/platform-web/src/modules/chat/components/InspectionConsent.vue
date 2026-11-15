<script setup lang="ts">
import { ref, watch } from "vue";
import { platformHttpClient as http } from "@/services/http/client";
import { extractPlatformHttpError } from "@/utils/http-error";

const props = defineProps<{
  scope: { projectId: string; threadId: string; runId: string };
}>();
const open = ref(false);
const busy = ref(false);
const error = ref("");
const input = ref("");
const output = ref("");
const consent = ref(false);
const context = ref<{
  agent_id: string;
  judge_route: string;
  budget_policy_version: string;
} | null>(null);
const pending = ref<Record<string, unknown> | null>(null);
const grant = ref<{
  export_id: string;
  status: string;
  receipt?: { status?: string };
} | null>(null);
let epoch = 0;
watch(
  () => [props.scope.projectId, props.scope.threadId, props.scope.runId],
  () => {
    epoch++;
    open.value = busy.value = consent.value = false;
    error.value = input.value = output.value = "";
    pending.value = context.value = grant.value = null;
  },
);
const headers = () => ({ "x-project-id": props.scope.projectId });
async function show() {
  const current = epoch;
  busy.value = true;
  error.value = "";
  try {
    const [run, capabilities, records] = await Promise.all([
      http.get("/api/evaluation/inspection/context", {
        headers: headers(),
        params: { thread_id: props.scope.threadId, run_id: props.scope.runId },
      }),
      http.get("/api/evaluation/capabilities", { headers: headers() }),
      http.get("/api/evaluation/inspection/exports", {
        headers: headers(),
        params: { thread_id: props.scope.threadId, run_id: props.scope.runId },
      }),
    ]);
    if (current !== epoch) return;
    if (!capabilities.data.quality_inspection || !run.data.agent_id)
      throw new Error("当前运行尚不符合巡检授权条件。");
    context.value = {
      agent_id: run.data.agent_id,
      ...capabilities.data.inspection_policy,
    };
    grant.value = records.data[0] || null;
    open.value = true;
  } catch (cause) {
    if (current === epoch)
      error.value = extractPlatformHttpError(cause).message;
  } finally {
    if (current === epoch) busy.value = false;
  }
}
async function act(operation: "authorize" | "deliver" | "revoke") {
  const current = epoch;
  busy.value = true;
  error.value = "";
  try {
    if (operation === "authorize") {
      pending.value ||= {
        export_id: crypto.randomUUID(),
        thread_id: props.scope.threadId,
        run_id: props.scope.runId,
        ...context.value,
        purpose: "quality_inspection",
        data_class: "synthetic",
        synthetic_attestation: consent.value,
        allowed_fields: ["input", "output"],
        input: input.value,
        output: output.value,
        expires_in_hours: 1,
      };
      const { data } = await http.post(
        "/api/evaluation/inspection/exports",
        pending.value,
        { headers: headers() },
      );
      if (current !== epoch) return;
      grant.value = data;
      pending.value = null;
    } else if (grant.value) {
      const { data } = await http.post(
        `/api/evaluation/exports/${grant.value.export_id}/${operation}`,
        {},
        { headers: headers() },
      );
      if (current !== epoch) return;
      grant.value = { ...grant.value, ...data };
    }
  } catch (cause) {
    if (current === epoch) {
      const detail = extractPlatformHttpError(cause);
      if (detail.status && detail.status >= 400 && detail.status < 500)
        pending.value = null;
      error.value =
        detail.message +
        (pending.value ? "；结果未确认，请重试同一授权。" : "");
    }
  } finally {
    if (current === epoch) busy.value = false;
  }
}
</script>

<template>
  <div class="mt-3 text-xs">
    <button
      type="button"
      class="rounded border px-3 py-1"
      :disabled="busy"
      @click="show"
    >
      独立质量巡检授权
    </button>
    <section
      v-if="open"
      aria-label="质量巡检授权"
      class="mt-2 space-y-3 rounded border p-3"
    >
      <p>
        仅评分下面人工重建的合成输入与输出，授权有效期 1
        小时。工具结果和检索正文不包含在内；不用于题库发布，生产采样仍关闭。
      </p>
      <p>
        裁判路由：{{ context?.judge_route }} · 预算版本：{{
          context?.budget_policy_version
        }}
      </p>
      <fieldset :disabled="busy || !!pending || !!grant" class="space-y-2">
        <label class="block"
          >合成输入<textarea
            v-model="input"
            aria-label="巡检合成输入"
            maxlength="12000"
            class="block w-full rounded border p-2 dark:bg-dark-900"
          />
        </label>
        <label class="block"
          >合成输出<textarea
            v-model="output"
            aria-label="巡检合成输出"
            maxlength="12000"
            class="block w-full rounded border p-2 dark:bg-dark-900"
          />
        </label>
        <label
          ><input v-model="consent" type="checkbox" />
          我确认不含真实业务资料或秘密，仅授权质量巡检用途</label
        >
      </fieldset>
      <div class="flex flex-wrap gap-3">
        <button
          v-if="!grant"
          type="button"
          :disabled="busy || !consent || !input.trim() || !output.trim()"
          @click="act('authorize')"
        >
          {{ pending ? "重试同一巡检授权" : "授权质量巡检" }}
        </button>
        <button
          v-if="grant?.status === 'ready'"
          type="button"
          :disabled="busy"
          @click="act('deliver')"
        >
          提交巡检抽样
        </button>
        <button
          v-if="grant && ['ready', 'exported'].includes(grant.status)"
          type="button"
          :disabled="busy"
          @click="act('revoke')"
        >
          撤销巡检授权
        </button>
        <button type="button" :disabled="busy" @click="show">
          刷新巡检状态
        </button>
        <button type="button" :disabled="busy" @click="open = false">
          收起
        </button>
      </div>
      <p v-if="grant" role="status">
        巡检授权：{{ grant.status }}；接收状态：{{
          grant.receipt?.status || "尚未接收"
        }}；编号：{{ grant.export_id }}
      </p>
    </section>
    <p v-if="error" role="alert" class="mt-2 text-red-600">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import { platformHttpClient } from "@/services/http/client";
import { resolvePlatformHttpErrorMessage } from "@/utils/http-error";
const props = defineProps<{
  projectId: string;
  threadIds: string[];
  show: boolean;
  canAuthorize?: boolean;
}>();
const emit = defineEmits<{ close: [] }>();
const title = ref("会话评测集");
const submitted = ref(false);
const consent = ref(false);
const busy = ref(false);
const error = ref("");
const requestId = ref(crypto.randomUUID());
type Receipt = {
  generation_status?: string;
  generation_error?: string;
  status: string;
  item_id?: string;
  url?: string;
  failures: { thread_id?: string; reason: string }[];
  materials: {
    title: string;
    missing: string[];
    environment: { notice: string };
  }[];
};
const receipt = ref<Receipt>();
const captureNotice = ref("");
async function capture(enabled = true) {
  busy.value = true;
  error.value = "";
  try {
    const response = await platformHttpClient.post<{ notice: string }>(
      "/api/evaluation/materials/capture",
      {
        request_id: requestId.value,
        thread_ids: props.threadIds,
        title: title.value,
        data_class: "business",
        material_consent: consent.value,
        enabled,
      },
      { headers: { "X-Project-Id": props.projectId } },
    );
    captureNotice.value = response.data.notice;
  } catch (e) {
    error.value = resolvePlatformHttpErrorMessage(
      e,
      "未能开启初态快照。",
      "会话评测资料",
    );
  } finally {
    busy.value = false;
  }
}
watch(
  () => props.show,
  (show) => {
    if (show) {
      receipt.value = undefined;
      error.value = "";
      submitted.value = false;
      requestId.value = crypto.randomUUID();
      consent.value = false;
    }
  },
);
async function send() {
  submitted.value = true;
  busy.value = true;
  error.value = "";
  try {
    receipt.value = (
      await platformHttpClient.post<Receipt>(
        "/api/evaluation/materials/send",
        {
          request_id: requestId.value,
          thread_ids: props.threadIds,
          title: title.value,
          data_class: "business",
          material_consent: consent.value,
          auto_generate: props.canAuthorize === true,
        },
        { headers: { "X-Project-Id": props.projectId } },
      )
    ).data;
    if (
      receipt.value.status === "delivered" &&
      receipt.value.generation_status !== "needs_retry" &&
      receipt.value.url
    ) {
      window.location.assign(receipt.value.url);
    }
  } catch (e) {
    error.value = resolvePlatformHttpErrorMessage(
      e,
      "资料交付回执尚未确认，请重试同一请求。",
      "会话评测资料",
    );
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <BaseDialog :show="show" title="把这段对话转为评测集" @close="emit('close')">
    <div class="space-y-4">
      <p>
        已选择 {{ threadIds.length }} 段 Agent 会话。AI
        会根据原始对话整理测试题目、预期结果和评分建议，你不需要重新描述业务。
      </p>
      <label class="block"
        >评测集名称<input
          v-model="title"
          class="pw-input mt-1 w-full"
          maxlength="120"
          :disabled="busy || submitted"
      /></label>
      <div
        class="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm space-y-2"
      >
        <p>
          接下来：带入会话与可取得的环境 → AI 自动整理 → 你检查或提出修改意见。
        </p>
        <p>
          会话来源可包含真实业务资料。常见邮箱、手机号和身份证号会脱敏，疑似密钥会拦截；请确认其他敏感内容也适合此次用途。工具结果可作为来源证据查看，默认不发给评测模型。
        </p>
        <p v-if="canAuthorize">
          本次授权 AI 整理 24
          小时，使用当前配置的受管评测模型。不会自动发布题库或运行被测
          Agent；隔离回归在确认题目后另行授权。
        </p>
        <p v-else>
          你可以提交资料。AI
          整理需要项目资料负责人在评测平台确认用途，确认后开始生成；本次不会发送给模型。
        </p>
      </div>
      <label class="flex items-start gap-2"
        ><input
          v-model="consent"
          type="checkbox"
          :disabled="busy || submitted"
          class="mt-1"
        />{{
          canAuthorize
            ? "我有权将这些会话用于评测，并同意把脱敏后的对话和获准环境资料交给评测 AI 整理。"
            : "我有权将这些会话作为评测资料提交，等待项目资料负责人确认 AI 用途。"
        }}</label
      >
      <details class="text-sm">
        <summary class="cursor-pointer">
          需要重现文件操作？查看初始文件采集
        </summary>
        <p class="my-2">
          只为后续运行保留上传文本的运行前状态，24小时有效；已有会话缺失的初态不能补造。缺初态时AI会说明限制，或建议先评历史回答。
        </p>
        <BaseButton
          :disabled="!canAuthorize || !consent || busy || submitted"
          @click="capture(true)"
          >开启后续文件初态采集</BaseButton
        >
        <BaseButton
          :disabled="!canAuthorize || !consent || busy || submitted"
          @click="capture(false)"
          >停止初态采集</BaseButton
        >
      </details>
      <p v-if="captureNotice" role="status">{{ captureNotice }}</p>
      <p v-if="error" role="alert" class="text-red-600">{{ error }}</p>
      <template v-if="receipt">
        <p role="status">
          {{
            receipt.status === "delivered"
              ? "会话已保存到评测集"
              : receipt.status === "partial"
                ? "部分会话已保存，请核对下方未成功的来源"
                : "未完成转换"
          }}
        </p>
        <p v-if="receipt.generation_error" role="alert">
          {{ receipt.generation_error }}
        </p>
        <p v-for="failure in receipt.failures" :key="failure.thread_id">
          {{ failure.thread_id }}：{{ failure.reason }}
        </p>
        <div v-for="material in receipt.materials" :key="material.title">
          <p>{{ material.title }}</p>
          <p v-for="missing in material.missing" :key="missing">
            {{ missing }}
          </p>
          <p>{{ material.environment.notice }}</p>
        </div>
        <a
          v-if="receipt.url"
          :href="receipt.url"
          class="text-primary-600 underline"
          >查看评测集与 AI 整理进度</a
        >
      </template>
      <BaseButton
        :disabled="
          !consent ||
          !title.trim() ||
          busy ||
          (receipt?.status === 'delivered' &&
            receipt?.generation_status !== 'needs_retry')
        "
        @click="send"
        >{{
          busy
            ? "正在转换，请稍候…"
            : submitted
              ? "重试同一转换"
              : "转换并查看 AI 建议"
        }}</BaseButton
      >
    </div>
  </BaseDialog>
</template>

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
        {
          headers: { "X-Project-Id": props.projectId },
          timeout: 180000,
        },
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
  <BaseDialog :show="show" title="转为评测集" @close="emit('close')">
    <div class="space-y-4 text-sm">
      <!-- 极简会话资料概览卡片 -->
      <div
        class="flex items-center gap-3 rounded-lg border border-primary-100 bg-primary-50/60 p-3 text-xs text-primary-900 dark:border-primary-900/40 dark:bg-primary-950/30 dark:text-primary-200"
      >
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary-100 text-primary-600 dark:bg-primary-900/60 dark:text-primary-300"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.8"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
            />
          </svg>
        </div>
        <div class="min-w-0 space-y-0.5">
          <div class="font-semibold text-gray-900 dark:text-white">
            已选择 {{ threadIds.length }} 段会话资料
          </div>
          <div class="text-[11px] text-gray-500 dark:text-dark-400">
            AI 将根据对话上下文自动提炼测试用例与预期评分规则，无需手动手写。
          </div>
        </div>
      </div>

      <!-- 评测集名称表单 -->
      <div>
        <label
          class="block text-xs font-medium text-gray-700 dark:text-dark-300 mb-1"
        >
          评测集名称
        </label>
        <input
          v-model="title"
          class="pw-input w-full"
          placeholder="请输入评测集名称，如：11月业务退款核对"
          maxlength="120"
          :disabled="busy || submitted"
        />
      </div>

      <!-- 隐私与安全微标提示（取代冗长免责认罪书） -->
      <div
        class="flex items-center gap-2 rounded-md border border-gray-100 bg-gray-50/80 px-2.5 py-1.5 text-xs text-gray-500 dark:border-dark-800 dark:bg-dark-800/40 dark:text-dark-400"
      >
        <svg
          class="h-3.5 w-3.5 shrink-0 text-emerald-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="2"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z"
          />
        </svg>
        <span class="text-[11px]">
          敏感信息（手机号、邮箱、密钥等）由系统自动脱敏过滤与安全保护
        </span>
      </div>

      <!-- 优雅的单行确认项 -->
      <label
        class="flex items-center gap-2.5 py-0.5 cursor-pointer select-none text-xs text-gray-700 dark:text-dark-200"
      >
        <input
          v-model="consent"
          type="checkbox"
          :disabled="busy || submitted"
          class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-dark-600 dark:bg-dark-800 shrink-0"
        />
        <span>
          {{
            canAuthorize
              ? "确认将脱敏后的会话与环境资料交给评测 AI 整理生成题目"
              : "确认提交该会话作为评测资料（等待项目资料负责人确认 AI 用途）"
          }}
        </span>
      </label>

      <!-- 高级选项：初态采集收敛折叠 -->
      <details
        class="group rounded-lg border border-gray-200/60 bg-gray-50/40 p-2.5 text-xs dark:border-dark-800 dark:bg-dark-900/40"
      >
        <summary
          class="flex cursor-pointer select-none items-center justify-between font-medium text-gray-600 hover:text-gray-900 dark:text-dark-300 dark:hover:text-white transition-colors"
        >
          <span>高级选项：运行前文件初态采集</span>
          <span
            class="text-[10px] text-gray-400 transition-transform group-open:rotate-180"
            >▼</span
          >
        </summary>
        <div
          class="mt-2 space-y-2 border-t border-gray-200/50 pt-2 dark:border-dark-800/80"
        >
          <p class="text-[11px] text-gray-500 dark:text-dark-400">
            为后续测试保留上传文本的运行前状态（24小时有效）；缺初态时 AI
            将以历史回答为准。
          </p>
          <div class="flex items-center gap-2">
            <BaseButton
              size="xs"
              variant="secondary"
              :disabled="!canAuthorize || !consent || busy || submitted"
              @click="capture(true)"
            >
              开启后续文件初态采集
            </BaseButton>
            <BaseButton
              size="xs"
              variant="secondary"
              :disabled="!canAuthorize || !consent || busy || submitted"
              @click="capture(false)"
            >
              停止初态采集
            </BaseButton>
          </div>
        </div>
      </details>

      <p
        v-if="captureNotice"
        role="status"
        class="text-xs text-emerald-600 dark:text-emerald-400"
      >
        {{ captureNotice }}
      </p>
      <p
        v-if="error"
        role="alert"
        class="text-xs text-red-600 dark:text-red-400"
      >
        {{ error }}
      </p>

      <!-- 交付结果反馈卡片 -->
      <template v-if="receipt">
        <div
          class="rounded-lg border p-3 text-xs space-y-1.5"
          :class="
            receipt.status === 'delivered'
              ? 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-800/50 dark:bg-emerald-950/20'
              : 'border-amber-200 bg-amber-50/50 dark:border-amber-800/50 dark:bg-amber-950/20'
          "
        >
          <div
            class="font-medium flex items-center justify-between"
            role="status"
          >
            <span>
              {{
                receipt.status === "delivered"
                  ? "✅ 会话已成功保存到评测集"
                  : receipt.status === "partial"
                    ? "⚠️ 部分会话已保存，请核对失败项"
                    : "❌ 未完成转换"
              }}
            </span>
            <a
              v-if="receipt.url"
              :href="receipt.url"
              class="text-primary-600 font-semibold underline hover:text-primary-700 dark:text-primary-400"
            >
              前往评测工作台查看 AI 整理进度 →
            </a>
          </div>
          <p v-if="receipt.generation_error" role="alert" class="text-red-600">
            {{ receipt.generation_error }}
          </p>
          <p
            v-for="failure in receipt.failures"
            :key="failure.thread_id"
            class="text-red-600"
          >
            {{ failure.thread_id }}：{{ failure.reason }}
          </p>
          <div
            v-for="material in receipt.materials"
            :key="material.title"
            class="text-gray-600 dark:text-dark-300"
          >
            <p class="font-medium">{{ material.title }}</p>
            <p
              v-for="missing in material.missing"
              :key="missing"
              class="text-amber-600 text-[11px]"
            >
              缺失说明：{{ missing }}
            </p>
            <p
              v-if="material.environment?.notice"
              class="text-[11px] text-gray-500"
            >
              {{ material.environment.notice }}
            </p>
          </div>
        </div>
      </template>

      <!-- 底部动作按钮 -->
      <BaseButton
        class="w-full justify-center !py-2 text-xs font-semibold shadow-2xs"
        :disabled="
          !consent ||
          !title.trim() ||
          busy ||
          (receipt?.status === 'delivered' &&
            receipt?.generation_status !== 'needs_retry')
        "
        @click="send"
      >
        {{
          busy
            ? "正在转换，请稍候…"
            : submitted
              ? "重试同一转换"
              : "转换并查看 AI 建议"
        }}
      </BaseButton>
    </div>
  </BaseDialog>
</template>

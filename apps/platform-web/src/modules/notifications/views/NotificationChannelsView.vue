<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useNotificationCenterStore } from "../stores/useNotificationCenterStore";
import type { CreateChannelRequest, NotificationChannelItem } from "../types";

const store = useNotificationCenterStore();

const showModal = ref(false);
const editingChannel = ref<NotificationChannelItem | null>(null);
const feedbackMsg = ref<{ type: "success" | "error"; text: string } | null>(
  null,
);

const form = reactive<CreateChannelRequest>({
  name: "",
  channel_type: "feishu",
  endpoint_url: "",
  secret_token: "",
  is_enabled: true,
  subscribed_events: ["agent_error", "budget_exceeded", "eval_degraded"],
});

function openAddModal() {
  editingChannel.value = null;
  form.name = "";
  form.channel_type = "feishu";
  form.endpoint_url = "";
  form.secret_token = "";
  form.is_enabled = true;
  form.subscribed_events = ["agent_error", "budget_exceeded", "eval_degraded"];
  showModal.value = true;
}

function openEditModal(ch: NotificationChannelItem) {
  editingChannel.value = ch;
  form.name = ch.name;
  form.channel_type = ch.channel_type;
  form.endpoint_url = ch.endpoint_url;
  form.secret_token = ch.secret_token || "";
  form.is_enabled = ch.is_enabled;
  form.subscribed_events = [...(ch.subscribed_events || [])];
  showModal.value = true;
}

async function handleSave() {
  if (!form.name || !form.endpoint_url) {
    feedbackMsg.value = {
      type: "error",
      text: "请填写渠道名称与有效 Webhook 地址",
    };
    return;
  }
  try {
    if (editingChannel.value) {
      await store.editChannel(editingChannel.value.id, {
        name: form.name,
        endpoint_url: form.endpoint_url,
        secret_token: form.secret_token || null,
        is_enabled: form.is_enabled,
        subscribed_events: form.subscribed_events,
      });
      feedbackMsg.value = { type: "success", text: "渠道配置更新成功" };
    } else {
      await store.addChannel({
        name: form.name,
        channel_type: form.channel_type,
        endpoint_url: form.endpoint_url,
        secret_token: form.secret_token || null,
        is_enabled: form.is_enabled,
        subscribed_events: form.subscribed_events,
      });
      feedbackMsg.value = { type: "success", text: "新增通知渠道成功" };
    }
    showModal.value = false;
  } catch (err: unknown) {
    feedbackMsg.value = { type: "error", text: `保存失败: ${String(err)}` };
  }
}

async function handleDelete(id: string) {
  if (!confirm("确定要删除此通知渠道吗？")) return;
  try {
    await store.removeChannel(id);
    feedbackMsg.value = { type: "success", text: "渠道已移除" };
  } catch (err: unknown) {
    feedbackMsg.value = { type: "error", text: `删除失败: ${String(err)}` };
  }
}

async function handleToggle(ch: NotificationChannelItem) {
  try {
    await store.editChannel(ch.id, { is_enabled: !ch.is_enabled });
  } catch (err: unknown) {
    feedbackMsg.value = { type: "error", text: `状态更新失败: ${String(err)}` };
  }
}

async function handleTest(ch: NotificationChannelItem) {
  feedbackMsg.value = null;
  const res = await store.runTestChannel(ch.id);
  if (res.success) {
    feedbackMsg.value = {
      type: "success",
      text: `🎉 测试成功！已向 [${ch.name}] 发送飞书互动测试卡片，请在群内查看。`,
    };
  } else {
    feedbackMsg.value = {
      type: "error",
      text: `❌ 发送失败: ${res.message}`,
    };
  }
}

function maskUrl(url: string): string {
  if (!url) return "";
  if (url.length <= 30) return url;
  return `${url.slice(0, 32)}...${url.slice(-8)}`;
}

onMounted(() => {
  void store.loadChannels();
});
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-6 p-6">
    <!-- 头部区域 -->
    <div
      class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-gray-200 dark:border-dark-800 pb-5"
    >
      <div>
        <h1
          class="text-xl font-bold tracking-tight text-gray-900 dark:text-white"
        >
          🔔 告警与通知推送配置
        </h1>
        <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
          集中管理飞书群自定义机器人、邮件及 Webhook 渠道，实现 Agent
          异常死循环、AI 网关限流与评测退化全自动告警。
        </p>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none"
        @click="openAddModal"
      >
        <span>+ 新增通知渠道</span>
      </button>
    </div>

    <!-- 顶部反馈提示条 -->
    <div
      v-if="feedbackMsg"
      class="rounded-lg p-3 text-xs font-medium transition-all animate-in fade-in flex items-center justify-between"
      :class="
        feedbackMsg.type === 'success'
          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-500/20'
          : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300 border border-rose-500/20'
      "
    >
      <span>{{ feedbackMsg.text }}</span>
      <button
        class="text-xs opacity-60 hover:opacity-100"
        @click="feedbackMsg = null"
      >
        ✕
      </button>
    </div>

    <!-- 渠道列表 -->
    <div
      v-if="store.channels.length === 0"
      class="rounded-2xl border border-dashed border-gray-300 p-12 text-center dark:border-dark-700"
    >
      <span class="text-4xl">🤖</span>
      <h3 class="mt-2 text-sm font-semibold text-gray-900 dark:text-white">
        暂未配置任何通知渠道
      </h3>
      <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
        添加一个飞书自定义机器人 Webhook，发生故障时第一时间直达你的飞书群！
      </p>
      <button
        type="button"
        class="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700"
        @click="openAddModal"
      >
        立即添加飞书机器人
      </button>
    </div>

    <div v-else class="grid gap-4 sm:grid-cols-2">
      <div
        v-for="ch in store.channels"
        :key="ch.id"
        class="relative flex flex-col justify-between rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-all hover:shadow-md dark:border-dark-700 dark:bg-dark-800/80"
        :class="{ 'opacity-60': !ch.is_enabled }"
      >
        <div>
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-2.5">
              <span
                class="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-xl dark:bg-blue-950/50"
              >
                {{ ch.channel_type === "feishu" ? "🐦" : "📬" }}
              </span>
              <div>
                <h3 class="text-sm font-bold text-gray-900 dark:text-white">
                  {{ ch.name }}
                </h3>
                <span
                  class="text-[10px] font-medium uppercase tracking-wider text-gray-400 dark:text-dark-400"
                >
                  {{ ch.channel_type }} ·
                  {{ ch.is_enabled ? "已启用" : "已停用" }}
                </span>
              </div>
            </div>

            <!-- 开关切换 -->
            <button
              type="button"
              class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
              :class="
                ch.is_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-dark-600'
              "
              @click="handleToggle(ch)"
            >
              <span
                class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out"
                :class="ch.is_enabled ? 'translate-x-4' : 'translate-x-0'"
              />
            </button>
          </div>

          <!-- Webhook 地址 -->
          <div
            class="mt-4 rounded bg-gray-50 p-2 font-mono text-[11px] text-gray-600 dark:bg-dark-900 dark:text-dark-300 break-all"
          >
            {{ maskUrl(ch.endpoint_url) }}
          </div>

          <!-- 订阅事件 Badge -->
          <div class="mt-3 flex flex-wrap gap-1.5">
            <span
              v-for="evt in ch.subscribed_events"
              :key="evt"
              class="rounded bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600 dark:bg-dark-700 dark:text-dark-300"
            >
              {{ evt }}
            </span>
          </div>
        </div>

        <!-- 底部快捷操作条 -->
        <div
          class="mt-5 flex items-center justify-between border-t border-gray-100 pt-3 dark:border-dark-700/60"
        >
          <button
            type="button"
            class="inline-flex items-center gap-1 rounded bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-600 hover:bg-blue-100 dark:bg-blue-950/40 dark:text-blue-400 transition-colors"
            :disabled="store.isTesting"
            @click="handleTest(ch)"
          >
            <span>🔔</span>
            <span>{{ store.isTesting ? "正在投递..." : "测试连通性" }}</span>
          </button>

          <div class="flex items-center gap-2">
            <button
              type="button"
              class="text-xs text-gray-500 hover:text-gray-800 dark:hover:text-dark-200"
              @click="openEditModal(ch)"
            >
              编辑
            </button>
            <button
              type="button"
              class="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400"
              @click="handleDelete(ch.id)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-in fade-in"
    >
      <div
        class="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-dark-700 dark:bg-dark-900"
      >
        <h3 class="text-base font-bold text-gray-900 dark:text-white">
          {{ editingChannel ? "编辑通知渠道" : "添加飞书/通知渠道" }}
        </h3>
        <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
          填入飞书自定义机器人 Webhook，即可即时推送富文本交互卡片。
        </p>

        <div class="mt-4 space-y-4">
          <div>
            <label
              class="block text-xs font-medium text-gray-700 dark:text-dark-300"
              >渠道名称</label
            >
            <input
              v-model="form.name"
              type="text"
              placeholder="例如：生产智能客服告警群"
              class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:border-blue-500 focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-white"
            />
          </div>

          <div>
            <label
              class="block text-xs font-medium text-gray-700 dark:text-dark-300"
              >渠道类型</label
            >
            <select
              v-model="form.channel_type"
              class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:border-blue-500 focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-white"
            >
              <option value="feishu">
                🐦 飞书群自定义机器人 (Feishu Interactive Card)
              </option>
              <option value="dingtalk">钉钉群自定义机器人 (DingTalk)</option>
              <option value="wechat">企业微信群机器人 (WeChat Work)</option>
              <option value="email">邮件 SMTP (mailto://...)</option>
              <option value="webhook">通用外部 Webhook</option>
            </select>
          </div>

          <div>
            <label
              class="block text-xs font-medium text-gray-700 dark:text-dark-300"
              >Webhook 地址 (Endpoint URL)</label
            >
            <input
              v-model="form.endpoint_url"
              type="text"
              placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
              class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-900 font-mono focus:border-blue-500 focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-white"
            />
          </div>

          <div>
            <label
              class="block text-xs font-medium text-gray-700 dark:text-dark-300"
              >签名密钥 Secret (可选)</label
            >
            <input
              v-model="form.secret_token"
              type="password"
              placeholder="若飞书机器人开启了签名校验请填写"
              class="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-900 font-mono focus:border-blue-500 focus:outline-none dark:border-dark-700 dark:bg-dark-800 dark:text-white"
            />
          </div>
        </div>

        <div
          class="mt-6 flex items-center justify-end gap-3 border-t border-gray-100 pt-4 dark:border-dark-800"
        >
          <button
            type="button"
            class="rounded-lg px-4 py-2 text-xs font-medium text-gray-600 hover:bg-gray-100 dark:text-dark-300 dark:hover:bg-dark-800"
            @click="showModal = false"
          >
            取消
          </button>
          <button
            type="button"
            class="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700"
            @click="handleSave"
          >
            保存并生效
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

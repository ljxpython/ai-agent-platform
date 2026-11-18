<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import BaseDialog from "@/components/base/BaseDialog.vue";
import { useWorkspaceStore } from "@/stores/workspace";
import { useNotificationCenterStore } from "../stores/useNotificationCenterStore";
import type {
  ChannelType,
  NotificationChannelItem,
  NotificationItem,
} from "../types";
import {
  cleanNotificationTitle,
  getNotificationActionInfo,
  getNotificationLevelBadge,
  resolveNotificationActionUrl,
} from "../utils/notification-action";

const route = useRoute();
const router = useRouter();
const store = useNotificationCenterStore();

// Tab 状态：history（历史消息大盘）与 channels（渠道配置）
const activeTab = ref<"history" | "channels">(
  route.query.tab === "channels" ? "channels" : "history",
);

watch(
  () => route.query.tab,
  (newTab) => {
    if (newTab === "channels" || newTab === "history") {
      activeTab.value = newTab;
    }
  },
);

function switchTab(tab: "history" | "channels") {
  activeTab.value = tab;
  void router.replace({
    query: {
      ...route.query,
      tab,
    },
  });
}

// 历史消息大盘过滤与交互状态
const filterStatus = ref<"all" | "unread" | "read">("all");
const filterLevel = ref<"all" | "critical" | "warning" | "info">("all");
const searchKeyword = ref<string>("");
const selectedNotification = ref<NotificationItem | null>(null);

const statusCounts = computed(() => {
  const all = store.items.length;
  const unread = store.items.filter((i) => i.status === "unread").length;
  const read = store.items.filter((i) => i.status === "read").length;
  return { all, unread, read };
});

const levelCounts = computed(() => {
  const critical = store.items.filter(
    (i) => i.level === "critical" || i.level === "error",
  ).length;
  const warning = store.items.filter((i) => i.level === "warning").length;
  const info = store.items.filter((i) => i.level === "info").length;
  return { critical, warning, info };
});

const filteredNotifications = computed(() => {
  return store.items.filter((item) => {
    // 状态过滤
    if (filterStatus.value === "unread" && item.status !== "unread") {
      return false;
    }
    if (filterStatus.value === "read" && item.status !== "read") {
      return false;
    }
    // 级别过滤
    if (filterLevel.value !== "all" && item.level !== filterLevel.value) {
      return false;
    }
    // 关键字搜索
    if (searchKeyword.value.trim()) {
      const kw = searchKeyword.value.trim().toLowerCase();
      const matchTitle = item.title.toLowerCase().includes(kw);
      const matchContent = item.content.toLowerCase().includes(kw);
      if (!matchTitle && !matchContent) return false;
    }
    return true;
  });
});

function formatRelativeTime(dateStr: string): string {
  try {
    const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
    if (diff < 60) return "刚刚";
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    return `${Math.floor(diff / 86400)} 天前`;
  } catch {
    return dateStr;
  }
}

function formatAbsoluteTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleString("zh-CN", { hour12: false });
  } catch {
    return dateStr;
  }
}

async function handleViewDetail(item: NotificationItem) {
  if (item.status === "unread") {
    await store.markRead(item.id);
  }
  selectedNotification.value = item;
}

function executeNotificationAction(item: NotificationItem, event?: Event) {
  if (event) {
    event.stopPropagation();
  }
  if (item.status === "unread") {
    void store.markRead(item.id);
  }
  const resolved = resolveNotificationActionUrl(item);
  if (!resolved) return;

  selectedNotification.value = null;

  if (resolved.startsWith("http://") || resolved.startsWith("https://")) {
    window.open(resolved, "_blank");
  } else {
    void router.push(resolved);
  }
}

const workspaceStore = useWorkspaceStore();

// 可选订阅的告警事件枚举清单
const AVAILABLE_EVENTS = [
  {
    key: "agent_error",
    label: "Agent 死循环与执行报错",
    icon: "🤖",
    desc: "连续重复调用拦截、工具超时或单回合推理失败",
  },
  {
    key: "eval_degraded",
    label: "评测集退化与生成异常",
    icon: "📊",
    desc: "评测指标退化、材料转换包含敏感密钥或生成中断",
  },
  {
    key: "budget_exceeded",
    label: "Token 与预算限额告警",
    icon: "💰",
    desc: "AI 网关 Token 超限预警、模型调用预算熔断",
  },
  {
    key: "model_provider_error",
    label: "大模型供应商网络与限流",
    icon: "⚡",
    desc: "模型上游 429 Rate Limit、503 不可用与自动退避",
  },
  {
    key: "system_alert",
    label: "系统底层与基础设施异常",
    icon: "🖥️",
    desc: "微服务连通性中断、数据库连接池与关键探针失败",
  },
];

function getProjectScopeInfo(projectIds: string[] | undefined) {
  if (!projectIds || projectIds.length === 0) {
    return {
      isGlobal: true,
      text: "🌐 全局通用 (所有项目)",
      tooltip: "接收全平台所有项目的告警",
    };
  }
  const names = projectIds.map((id) => {
    const found = workspaceStore.projects.find((p) => p.id === id);
    return found ? found.name : id.slice(0, 8);
  });
  if (names.length === 1) {
    return {
      isGlobal: false,
      text: `📁 所属项目: ${names[0]}`,
      tooltip: `专属项目: ${names[0]} (${projectIds[0]})`,
    };
  }
  return {
    isGlobal: false,
    text: `📁 专属 ${projectIds.length} 个项目: ${names.slice(0, 2).join(", ")}${projectIds.length > 2 ? "..." : ""}`,
    tooltip: `已绑定项目: ${names.join(", ")}`,
  };
}

function getEventBadgeInfo(eventKey: string) {
  const found = AVAILABLE_EVENTS.find((e) => e.key === eventKey);
  if (found) {
    return { label: `${found.icon} ${found.label}` };
  }
  return { label: `📌 ${eventKey}` };
}

// 渠道配置状态与操作
const showModal = ref(false);
const editingChannel = ref<NotificationChannelItem | null>(null);
const feedbackMsg = ref<{ type: "success" | "error"; text: string } | null>(
  null,
);

const isAllProjects = ref(true);
const selectedProjectIds = ref<string[]>([]);

const form = reactive({
  name: "",
  channel_type: "feishu" as ChannelType,
  endpoint_url: "",
  secret_token: "",
  is_enabled: true,
  subscribed_events: [
    "agent_error",
    "budget_exceeded",
    "eval_degraded",
    "model_provider_error",
  ],
});

function toggleProject(id: string) {
  const idx = selectedProjectIds.value.indexOf(id);
  if (idx === -1) {
    selectedProjectIds.value = [...selectedProjectIds.value, id];
  } else {
    selectedProjectIds.value = selectedProjectIds.value.filter((p) => p !== id);
  }
  isAllProjects.value = false;
}

function selectAllProjects() {
  isAllProjects.value = false;
  selectedProjectIds.value = workspaceStore.projects.map((p) => p.id);
}

function clearAllProjects() {
  selectedProjectIds.value = [];
}

function switchToGlobal() {
  isAllProjects.value = true;
  selectedProjectIds.value = [];
}

function switchToCustom() {
  isAllProjects.value = false;
  if (
    selectedProjectIds.value.length === 0 &&
    workspaceStore.projects.length > 0
  ) {
    selectedProjectIds.value = [workspaceStore.projects[0].id];
  }
}

function toggleEvent(key: string) {
  const current = form.subscribed_events || [];
  const idx = current.indexOf(key);
  if (idx === -1) {
    form.subscribed_events = [...current, key];
  } else {
    form.subscribed_events = current.filter((k) => k !== key);
  }
}

function selectAllEvents() {
  form.subscribed_events = AVAILABLE_EVENTS.map((e) => e.key);
}

function clearAllEvents() {
  form.subscribed_events = [];
}

function openAddModal() {
  editingChannel.value = null;
  form.name = "";
  form.channel_type = "feishu";
  form.endpoint_url = "";
  form.secret_token = "";
  form.is_enabled = true;
  isAllProjects.value = true;
  selectedProjectIds.value = [];
  form.subscribed_events = [
    "agent_error",
    "budget_exceeded",
    "eval_degraded",
    "model_provider_error",
  ];
  showModal.value = true;
}

function openEditModal(ch: NotificationChannelItem) {
  editingChannel.value = ch;
  form.name = ch.name;
  form.channel_type = ch.channel_type;
  form.endpoint_url = ch.endpoint_url;
  form.secret_token = ch.secret_token || "";
  form.is_enabled = ch.is_enabled;
  const pIds = ch.project_ids || [];
  isAllProjects.value = pIds.length === 0;
  selectedProjectIds.value = [...pIds];
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
  if (!isAllProjects.value && selectedProjectIds.value.length === 0) {
    feedbackMsg.value = {
      type: "error",
      text: "请至少勾选一个专属项目，或切换为全局通用模式",
    };
    return;
  }
  if (!form.subscribed_events || form.subscribed_events.length === 0) {
    feedbackMsg.value = {
      type: "error",
      text: "请至少勾选一个订阅告警类别",
    };
    return;
  }

  const payloadProjectIds = isAllProjects.value ? [] : selectedProjectIds.value;

  try {
    if (editingChannel.value) {
      await store.editChannel(editingChannel.value.id, {
        name: form.name,
        project_ids: payloadProjectIds,
        endpoint_url: form.endpoint_url,
        secret_token: form.secret_token || null,
        is_enabled: form.is_enabled,
        subscribed_events: form.subscribed_events,
      });
      feedbackMsg.value = { type: "success", text: "渠道配置更新成功" };
    } else {
      await store.addChannel({
        name: form.name,
        project_ids: payloadProjectIds,
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
  void store.fetchFeed();
});
</script>

<template>
  <div class="mx-auto w-full max-w-6xl xl:max-w-7xl space-y-6 pb-12">
    <!-- 头部区域 -->
    <div
      class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-gray-200 dark:border-dark-800 pb-5"
    >
      <div>
        <h1
          class="text-xl font-bold tracking-tight text-gray-900 dark:text-white flex items-center gap-2"
        >
          <span>🔔 统一通知与告警管理中心</span>
        </h1>
        <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
          集中查看 Agent
          异常拦截流水、评测集生成通知与历史告警，配置飞书机器人与多渠道推送。
        </p>
      </div>

      <div class="flex items-center gap-3">
        <button
          v-if="activeTab === 'channels'"
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none"
          @click="openAddModal"
        >
          <span>+ 新增通知渠道</span>
        </button>
        <button
          v-else-if="store.unreadCount > 0"
          type="button"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-300 dark:border-dark-700 bg-white dark:bg-dark-800 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-dark-200 shadow-2xs hover:bg-gray-50 dark:hover:bg-dark-700 transition-colors"
          @click="store.markAllRead"
        >
          <span>全部标为已读</span>
        </button>
      </div>
    </div>

    <!-- 顶部主导航 Tab -->
    <div
      class="flex items-center justify-between border-b border-gray-200 dark:border-dark-800"
    >
      <nav class="-mb-px flex space-x-6 text-sm font-medium">
        <button
          type="button"
          class="flex items-center gap-2 border-b-2 py-3 px-1 transition-colors"
          :class="
            activeTab === 'history'
              ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-bold'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200'
          "
          @click="switchTab('history')"
        >
          <span>📋 消息与告警历史</span>
          <span
            v-if="store.unreadCount > 0"
            class="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-600 dark:bg-red-950/50 dark:text-red-400"
          >
            {{ store.unreadCount }}
          </span>
        </button>

        <button
          type="button"
          class="flex items-center gap-2 border-b-2 py-3 px-1 transition-colors"
          :class="
            activeTab === 'channels'
              ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400 font-bold'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200'
          "
          @click="switchTab('channels')"
        >
          <span>⚙️ 推送渠道配置</span>
          <span
            class="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-dark-800 dark:text-dark-300"
          >
            {{ store.channels.length }}
          </span>
        </button>
      </nav>
    </div>

    <!-- 反馈提示条 -->
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

    <!-- TAB 1: 消息与告警历史 -->
    <div v-if="activeTab === 'history'" class="space-y-4">
      <!-- 搜索与多维过滤条 -->
      <div
        class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white p-3.5 shadow-2xs dark:border-dark-700 dark:bg-dark-800/80"
      >
        <!-- 左侧状态与级别 -->
        <div class="flex flex-wrap items-center gap-2">
          <!-- 状态过滤（带实时计数） -->
          <div
            class="inline-flex rounded-lg bg-gray-100 p-0.5 text-xs dark:bg-dark-900"
          >
            <button
              v-for="st in [
                { key: 'all', label: `全部 (${statusCounts.all})` },
                { key: 'unread', label: `未读 (${statusCounts.unread})` },
                { key: 'read', label: `已读 (${statusCounts.read})` },
              ]"
              :key="st.key"
              type="button"
              class="rounded-md px-2.5 py-1 font-medium transition-colors"
              :class="
                filterStatus === st.key
                  ? 'bg-white text-gray-900 shadow-2xs dark:bg-dark-700 dark:text-white'
                  : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-white'
              "
              @click="filterStatus = st.key as any"
            >
              {{ st.label }}
            </button>
          </div>

          <div class="h-4 w-px bg-gray-200 dark:bg-dark-700 mx-1" />

          <!-- 级别过滤（带实时计数） -->
          <div
            class="inline-flex rounded-lg bg-gray-100 p-0.5 text-xs dark:bg-dark-900"
          >
            <button
              v-for="lv in [
                { key: 'all', label: '全部级别' },
                { key: 'critical', label: `🚨 严重 (${levelCounts.critical})` },
                { key: 'warning', label: `⚠️ 警告 (${levelCounts.warning})` },
                { key: 'info', label: `ℹ️ 信息 (${levelCounts.info})` },
              ]"
              :key="lv.key"
              type="button"
              class="rounded-md px-2.5 py-1 font-medium transition-colors"
              :class="
                filterLevel === lv.key
                  ? 'bg-white text-gray-900 shadow-2xs dark:bg-dark-700 dark:text-white'
                  : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-white'
              "
              @click="filterLevel = lv.key as any"
            >
              {{ lv.label }}
            </button>
          </div>
        </div>

        <!-- 右侧搜索框与刷新 -->
        <div class="flex items-center gap-2">
          <div class="relative">
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="搜索标题或内容..."
              class="w-48 sm:w-64 rounded-lg border border-gray-300 dark:border-dark-600 bg-gray-50/50 dark:bg-dark-900 py-1.5 pl-8 pr-3 text-xs text-gray-900 dark:text-white placeholder-gray-400 focus:border-blue-500 focus:outline-none"
            />
            <span class="absolute left-2.5 top-2 text-xs text-gray-400"
              >🔍</span
            >
          </div>

          <button
            type="button"
            class="rounded-lg border border-gray-200 p-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:border-dark-700 dark:text-dark-300 dark:hover:bg-dark-700 transition-colors"
            title="刷新列表"
            @click="store.fetchFeed()"
          >
            🔄
          </button>
        </div>
      </div>

      <!-- 历史消息列表容器（保持最小高度稳定承托） -->
      <div class="min-h-[460px] flex flex-col justify-between">
        <div
          v-if="store.isFetching && store.items.length === 0"
          class="rounded-2xl border border-gray-200 bg-white p-12 text-center text-xs text-gray-400 dark:border-dark-800 dark:bg-dark-900"
        >
          正在加载历史消息记录...
        </div>

        <div
          v-else-if="filteredNotifications.length === 0"
          class="rounded-2xl border border-dashed border-gray-200 bg-white p-16 text-center dark:border-dark-800 dark:bg-dark-900 my-auto"
        >
          <span class="text-4xl">🎉</span>
          <h4 class="mt-3 text-sm font-semibold text-gray-900 dark:text-white">
            暂无符合筛选条件的消息
          </h4>
          <p class="mt-1.5 text-xs text-gray-400 dark:text-dark-400">
            当前筛选条件下无记录，系统持续平稳运行中。
          </p>
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="item in filteredNotifications"
            :key="item.id"
            class="group relative flex flex-col justify-between rounded-xl border border-gray-200 bg-white p-4 shadow-2xs transition-all hover:border-blue-200 hover:shadow-sm dark:border-dark-700 dark:bg-dark-800/80 dark:hover:border-blue-900/50"
            :class="{
              'bg-blue-50/20 dark:bg-blue-950/15 border-blue-100 dark:border-blue-950/60':
                item.status === 'unread',
            }"
          >
            <!-- 消息卡片主要内容 -->
            <div class="flex flex-col gap-2">
              <div class="flex items-start justify-between gap-3">
                <div class="flex min-w-0 flex-1 items-center gap-2">
                  <!-- 未读小蓝点 -->
                  <span
                    v-if="item.status === 'unread'"
                    class="h-2 w-2 shrink-0 rounded-full bg-blue-600 dark:bg-blue-400 ring-2 ring-blue-100 dark:ring-blue-950"
                    title="未读消息"
                  />

                  <!-- 等级 Badge -->
                  <span
                    class="inline-flex shrink-0 whitespace-nowrap items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold tracking-wide"
                    :class="getNotificationLevelBadge(item.level).class"
                  >
                    {{ getNotificationLevelBadge(item.level).label }}
                  </span>

                  <!-- 类别 Tag -->
                  <span
                    class="shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-dark-300 capitalize"
                  >
                    {{ item.category }}
                  </span>

                  <!-- 干净标题 -->
                  <h3
                    class="truncate text-sm text-gray-900 dark:text-white"
                    :class="
                      item.status === 'unread' ? 'font-bold' : 'font-medium'
                    "
                    :title="item.title"
                  >
                    {{ cleanNotificationTitle(item.title) }}
                  </h3>
                </div>

                <!-- 时间展示 -->
                <span
                  class="shrink-0 whitespace-nowrap text-xs text-gray-400 dark:text-dark-400 font-mono"
                  :title="formatAbsoluteTime(item.created_at)"
                >
                  {{ formatRelativeTime(item.created_at) }}
                </span>
              </div>

              <!-- 正文描述 -->
              <p
                class="text-xs leading-relaxed text-gray-600 dark:text-dark-300"
                :class="item.status === 'unread' ? 'pl-4' : ''"
              >
                {{ item.content }}
              </p>
            </div>

            <!-- 卡片底栏操作区 -->
            <div
              class="mt-3 flex items-center justify-between border-t border-gray-100 pt-2.5 dark:border-dark-700/60"
              :class="item.status === 'unread' ? 'pl-4' : ''"
            >
              <!-- 详细元数据提示 -->
              <div class="flex items-center gap-2">
                <span
                  v-if="
                    item.extra_metadata &&
                    Object.keys(item.extra_metadata).length > 0
                  "
                  class="text-[11px] text-gray-400 dark:text-dark-500 font-mono"
                >
                  已附加排障上下文 ({{
                    Object.keys(item.extra_metadata).length
                  }}
                  项)
                </span>
              </div>

              <!-- 操作按钮组 -->
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="rounded-lg px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 dark:text-dark-300 dark:hover:bg-dark-700 transition-colors"
                  @click="handleViewDetail(item)"
                >
                  查看详情 / 上下文
                </button>

                <button
                  v-if="resolveNotificationActionUrl(item)"
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg px-3 py-1 text-xs font-semibold text-white shadow-2xs transition-colors"
                  :class="
                    item.level === 'critical' || item.level === 'error'
                      ? 'bg-rose-600 hover:bg-rose-700'
                      : 'bg-blue-600 hover:bg-blue-700'
                  "
                  @click="executeNotificationAction(item, $event)"
                >
                  <span>{{ getNotificationActionInfo(item).label }}</span>
                  <span>→</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 列表底座摘要栏：锚定视觉下限，彻底消除塌陷感 -->
        <div
          class="mt-6 flex flex-wrap items-center justify-between border-t border-gray-200/60 dark:border-dark-800/80 pt-3 text-[11px] text-gray-400 dark:text-dark-500"
        >
          <div class="flex items-center gap-2">
            <span
              class="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500"
            />
            <span>实时监控与推送就绪</span>
            <span>·</span>
            <span>当前筛选显示 {{ filteredNotifications.length }} 条记录</span>
          </div>
          <div>
            <span
              >未读 {{ statusCounts.unread }} 条 / 已读
              {{ statusCounts.read }} 条 / 总计 {{ statusCounts.all }} 条</span
            >
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: 推送渠道配置 -->
    <div v-else-if="activeTab === 'channels'" class="space-y-6">
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
                  <div class="mt-1 flex flex-wrap items-center gap-1.5">
                    <span
                      class="text-[10px] font-medium uppercase tracking-wider text-gray-400 dark:text-dark-400"
                    >
                      {{ ch.channel_type }} ·
                      {{ ch.is_enabled ? "已启用" : "已停用" }}
                    </span>
                    <span class="text-gray-300 dark:text-dark-600">·</span>
                    <span
                      class="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium"
                      :class="
                        !getProjectScopeInfo(ch.project_ids).isGlobal
                          ? 'bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300 border border-purple-500/20'
                          : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-500/20'
                      "
                      :title="getProjectScopeInfo(ch.project_ids).tooltip"
                    >
                      {{ getProjectScopeInfo(ch.project_ids).text }}
                    </span>
                  </div>
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
                class="rounded bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-700 dark:bg-dark-700 dark:text-dark-300 flex items-center gap-1"
              >
                {{ getEventBadgeInfo(evt).label }}
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
    </div>

    <!-- 消息详情弹窗 -->
    <BaseDialog
      :show="!!selectedNotification"
      :title="cleanNotificationTitle(selectedNotification?.title || '通知详情')"
      width="normal"
      @close="selectedNotification = null"
    >
      <div v-if="selectedNotification" class="space-y-4">
        <!-- 头部等级与时间 -->
        <div
          class="flex items-center justify-between border-b border-gray-100 pb-3 dark:border-dark-800"
        >
          <div class="flex items-center gap-2">
            <span
              class="inline-flex shrink-0 whitespace-nowrap items-center rounded-md border px-2 py-0.5 text-xs font-semibold"
              :class="
                getNotificationLevelBadge(selectedNotification.level).class
              "
            >
              {{ getNotificationLevelBadge(selectedNotification.level).label }}
            </span>
            <span class="text-xs text-gray-500 dark:text-dark-400 capitalize">
              {{ selectedNotification.category }}
            </span>
          </div>
          <span class="text-xs text-gray-400 dark:text-dark-500 font-mono">
            {{ formatAbsoluteTime(selectedNotification.created_at) }}
          </span>
        </div>

        <!-- 消息正文 -->
        <div
          class="rounded-xl bg-gray-50/70 p-3.5 text-xs leading-relaxed text-gray-800 dark:bg-dark-800/60 dark:text-dark-200 break-words whitespace-pre-wrap"
        >
          {{ selectedNotification.content }}
        </div>

        <!-- 告警与诊断元数据 (如有) -->
        <div
          v-if="
            selectedNotification.extra_metadata &&
            Object.keys(selectedNotification.extra_metadata).length > 0
          "
          class="space-y-1.5"
        >
          <h4
            class="text-[11px] font-semibold text-gray-500 dark:text-dark-400 uppercase tracking-wider"
          >
            排障上下文与元数据
          </h4>
          <div
            class="max-h-48 overflow-y-auto rounded-lg bg-gray-100/90 p-2.5 font-mono text-[11px] text-gray-700 dark:bg-dark-900/90 dark:text-dark-300"
          >
            <pre class="whitespace-pre-wrap break-all">{{
              JSON.stringify(selectedNotification.extra_metadata, null, 2)
            }}</pre>
          </div>
        </div>

        <!-- 弹窗底部操作按钮 -->
        <div
          class="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-dark-800"
        >
          <button
            type="button"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-100 dark:text-dark-400 dark:hover:bg-dark-800 transition-colors"
            @click="selectedNotification = null"
          >
            关闭
          </button>

          <button
            v-if="resolveNotificationActionUrl(selectedNotification)"
            type="button"
            class="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors"
            :class="
              selectedNotification.level === 'critical' ||
              selectedNotification.level === 'error'
                ? 'bg-rose-600 hover:bg-rose-700'
                : 'bg-blue-600 hover:bg-blue-700'
            "
            @click="executeNotificationAction(selectedNotification)"
          >
            <span>{{
              getNotificationActionInfo(selectedNotification).label
            }}</span>
            <span>→</span>
          </button>
        </div>
      </div>
    </BaseDialog>

    <!-- 新增/编辑渠道弹窗 -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-in fade-in"
    >
      <div
        class="w-full max-w-lg rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-dark-700 dark:bg-dark-900"
      >
        <h3 class="text-base font-bold text-gray-900 dark:text-white">
          {{ editingChannel ? "编辑通知渠道" : "添加飞书/通知渠道" }}
        </h3>
        <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
          配置飞书机器人或 Webhook，指定专属项目与订阅的告警类别。
        </p>

        <div class="mt-4 space-y-4 max-h-[75vh] overflow-y-auto pr-1">
          <!-- 渠道名称 -->
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

          <!-- 推送范围 / 适用项目 (多选支持) -->
          <div>
            <div class="flex items-center justify-between">
              <label
                class="block text-xs font-medium text-gray-700 dark:text-dark-300"
              >
                推送范围 / 适用项目
              </label>
              <div class="flex items-center gap-2 text-[11px]">
                <button
                  type="button"
                  class="transition-colors"
                  :class="
                    isAllProjects
                      ? 'font-bold text-blue-600 dark:text-blue-400'
                      : 'text-gray-500 hover:text-gray-800 dark:text-dark-400 dark:hover:text-dark-200'
                  "
                  @click="switchToGlobal"
                >
                  🌐 全局通用
                </button>
                <span class="text-gray-300 dark:text-dark-600">|</span>
                <button
                  type="button"
                  class="transition-colors"
                  :class="
                    !isAllProjects
                      ? 'font-bold text-blue-600 dark:text-blue-400'
                      : 'text-gray-500 hover:text-gray-800 dark:text-dark-400 dark:hover:text-dark-200'
                  "
                  @click="switchToCustom"
                >
                  📁 专属项目 (多选)
                </button>
              </div>
            </div>

            <!-- 全局模式说明条 -->
            <div
              v-if="isAllProjects"
              class="mt-1.5 flex items-center justify-between rounded-lg border border-emerald-200/80 bg-emerald-50/60 p-2.5 text-xs text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300"
            >
              <div class="flex items-center gap-1.5">
                <span class="text-sm">🌐</span>
                <span
                  >当前已设为<strong>全局通用</strong>：汇总推送全平台所有项目的告警</span
                >
              </div>
              <button
                type="button"
                class="text-[11px] font-medium text-emerald-700 underline hover:text-emerald-900 dark:text-emerald-400"
                @click="switchToCustom"
              >
                改为多选指定
              </button>
            </div>

            <!-- 专属多项目勾选区域 -->
            <div v-else class="mt-1.5 space-y-1.5">
              <div
                class="flex items-center justify-between px-0.5 text-[11px] text-gray-500 dark:text-dark-400"
              >
                <span
                  >已选择
                  <strong class="text-blue-600 dark:text-blue-400">{{
                    selectedProjectIds.length
                  }}</strong>
                  / {{ workspaceStore.projects.length }} 个项目</span
                >
                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    class="text-blue-600 hover:underline dark:text-blue-400 font-medium"
                    @click="selectAllProjects"
                  >
                    全选
                  </button>
                  <span class="text-gray-300 dark:text-dark-600">|</span>
                  <button
                    type="button"
                    class="text-gray-500 hover:underline dark:text-dark-400"
                    @click="clearAllProjects"
                  >
                    清空
                  </button>
                </div>
              </div>

              <div
                class="grid max-h-36 grid-cols-1 gap-1.5 overflow-y-auto rounded-lg border border-gray-200 p-1.5 sm:grid-cols-2 dark:border-dark-700 dark:bg-dark-800/50"
              >
                <label
                  v-for="proj in workspaceStore.projects"
                  :key="proj.id"
                  class="flex cursor-pointer items-center gap-2 rounded-md border p-1.5 text-xs transition-colors"
                  :class="
                    selectedProjectIds.includes(proj.id)
                      ? 'border-blue-500 bg-blue-50/60 font-medium text-blue-900 dark:border-blue-500/80 dark:bg-blue-950/40 dark:text-blue-200'
                      : 'border-gray-200 hover:bg-gray-50 text-gray-700 dark:border-dark-700 dark:hover:bg-dark-800 dark:text-dark-300'
                  "
                >
                  <input
                    type="checkbox"
                    :checked="selectedProjectIds.includes(proj.id)"
                    class="h-3.5 w-3.5 rounded text-blue-600 focus:ring-blue-500"
                    @change="toggleProject(proj.id)"
                  />
                  <div class="min-w-0 flex-1 truncate">
                    <div class="truncate">{{ proj.name }}</div>
                    <div
                      class="font-mono text-[10px] text-gray-400 dark:text-dark-500"
                    >
                      {{ proj.id.slice(0, 8) }}
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <!-- 渠道类型 -->
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

          <!-- Webhook 地址 -->
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

          <!-- 签名密钥 -->
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

          <!-- 订阅告警类别 (多选) -->
          <div>
            <div class="flex items-center justify-between pb-1">
              <label
                class="block text-xs font-medium text-gray-700 dark:text-dark-300"
              >
                订阅告警类别 (Subscribed Events)
              </label>
              <div class="flex items-center gap-2 text-[11px]">
                <button
                  type="button"
                  class="text-blue-600 hover:underline dark:text-blue-400 font-medium"
                  @click="selectAllEvents"
                >
                  全选
                </button>
                <span class="text-gray-300 dark:text-dark-600">|</span>
                <button
                  type="button"
                  class="text-gray-500 hover:underline dark:text-dark-400"
                  @click="clearAllEvents"
                >
                  清空
                </button>
              </div>
            </div>

            <div class="space-y-2 mt-1">
              <label
                v-for="evt in AVAILABLE_EVENTS"
                :key="evt.key"
                class="flex items-start gap-2.5 rounded-lg border p-2.5 transition-colors cursor-pointer"
                :class="
                  form.subscribed_events?.includes(evt.key)
                    ? 'border-blue-500 bg-blue-50/40 dark:border-blue-500/70 dark:bg-blue-950/20'
                    : 'border-gray-200 hover:border-gray-300 dark:border-dark-700 dark:hover:border-dark-600'
                "
              >
                <input
                  type="checkbox"
                  :checked="form.subscribed_events?.includes(evt.key)"
                  class="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                  @change="toggleEvent(evt.key)"
                />
                <div class="flex-1 min-w-0">
                  <div
                    class="flex items-center gap-1.5 text-xs font-semibold text-gray-900 dark:text-white"
                  >
                    <span>{{ evt.icon }}</span>
                    <span>{{ evt.label }}</span>
                    <span
                      class="font-mono text-[10px] text-gray-400 dark:text-dark-500"
                      >({{ evt.key }})</span
                    >
                  </div>
                  <p
                    class="text-[11px] text-gray-500 dark:text-dark-400 mt-0.5"
                  >
                    {{ evt.desc }}
                  </p>
                </div>
              </label>
            </div>
            <p
              v-if="
                !form.subscribed_events || form.subscribed_events.length === 0
              "
              class="mt-1 text-[11px] text-rose-500"
            >
              ⚠️ 请至少选择一个订阅告警类别，否则该渠道无法接收任何推送。
            </p>
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

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { listAgents } from "@/services/agents/agents.service";
import type { Agent } from "@/services/agents/types";
import { listRuntimeModels } from "@/services/runtime/runtime.service";
import type { RuntimeModelItem } from "@/types/management";
import { useSchedulePreview } from "../composables/useSchedulePreview";
import { useScheduledTaskForm } from "../composables/useScheduledTaskForm";
import type { ScheduledTask } from "../types";
import { describeCron } from "../utils/cron";
import { COMMON_TIMEZONES, formatDisplayTime } from "../utils/timezone";
import CronScheduleInput from "./CronScheduleInput.vue";
import OnceScheduleInput from "./OnceScheduleInput.vue";
import ScheduledTaskCard from "./ScheduledTaskCard.vue";

const props = defineProps<{
  show: boolean;
  projectId: string;
  task?: ScheduledTask | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "saved", task: ScheduledTask): void;
}>();

const {
  isEdit,
  title,
  prompt,
  agentKey,
  scheduleType,
  cron,
  runAt,
  timezone,
  threadMode,
  threadId,
  selectedModelId,
  previewPayload,
  submitting,
  submitError,
  submit,
} = useScheduledTaskForm(
  () => props.projectId,
  () => props.task,
  (saved) => emit("saved", saved),
);

const projIdRef = computed(() => props.projectId);
const { times: previewTimes, loading: previewLoading } = useSchedulePreview(
  projIdRef,
  previewPayload,
);

const availableAgents = ref<Agent[]>([]);
const availableModels = ref<RuntimeModelItem[]>([]);
const showAdvanced = ref(false);

async function loadOptions() {
  if (!props.projectId) return;
  try {
    const [agentRes, modelRes] = await Promise.all([
      listAgents(props.projectId, { limit: 100 }),
      listRuntimeModels(props.projectId),
    ]);
    availableAgents.value = agentRes.items || [];
    availableModels.value = modelRes.models || [];
  } catch {
    // 优雅降级
  }
}

watch(
  () => props.show,
  (val) => {
    if (val) loadOptions();
  },
);
onMounted(loadOptions);

const agentOptions = computed(() =>
  availableAgents.value.map((a) => ({
    value: a.graph_id || a.id,
    label: `${a.name} (${a.graph_id || a.id})`,
  })),
);

const modelOptions = computed(() => [
  { value: "", label: "默认（跟随项目默认模型）" },
  ...availableModels.value.map((m) => ({
    value: m.id,
    label: `${m.display_name || m.model} (${m.provider})`,
  })),
]);

// 构造右侧 1:1 动态仿真卡片
const simulatedTask = computed<ScheduledTask>(() => ({
  id: "simulator-preview",
  title: title.value.trim() || "未命名任务",
  prompt: prompt.value.trim() || "等待输入提示词指令...",
  agent_key: agentKey.value || "未选择 Agent",
  schedule_type: scheduleType.value,
  cron: cron.value,
  run_at: runAt.value,
  timezone: timezone.value,
  thread_mode: threadMode.value,
  thread_id: threadId.value,
  context: {},
  enabled: true,
  schedule_status: "active",
  next_run_at: previewTimes.value[0] || null,
  owner_id: "current-user",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}));
</script>

<template>
  <BaseDrawer
    :show="show"
    :title="isEdit ? '编辑定时任务' : '创建定时任务'"
    width="2xl"
    @close="emit('close')"
  >
    <div class="space-y-5">
      <StateBanner
        v-if="submitError"
        variant="danger"
        title="操作失败"
        :description="submitError"
      />

      <!-- 双栏响应式工作台 -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <!-- 左侧：表单配置区 (7 cols) -->
        <div class="lg:col-span-7 space-y-4">
          <!-- 基础信息卡片 -->
          <SurfaceCard title="基础信息">
            <div class="space-y-3.5 p-3.5">
              <div>
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                >
                  任务标题 <span class="text-rose-500">*</span>
                </label>
                <input
                  v-model="title"
                  type="text"
                  placeholder="例如：每日项目研究动态汇总"
                  class="w-full h-9 px-3 text-xs rounded-lg border border-border/80 bg-surface transition focus:border-primary focus:ring-2 focus:ring-primary/20 dark:bg-dark-800"
                  maxlength="120"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                >
                  执行智能体 (Agent) <span class="text-rose-500">*</span>
                </label>
                <div
                  v-if="isEdit"
                  class="text-xs px-3 py-2 rounded-lg bg-muted/60 border border-border/40 font-mono text-muted-foreground flex items-center gap-2"
                >
                  <BaseIcon
                    name="lock"
                    size="xs"
                    class="text-muted-foreground"
                  />
                  <span>{{ agentKey }}（已锁定）</span>
                </div>
                <BaseSelect
                  v-else
                  v-model="agentKey"
                  :options="agentOptions"
                  placeholder="请选择执行该任务的 Agent"
                />
              </div>

              <div>
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                >
                  提示词 (Prompt) <span class="text-rose-500">*</span>
                </label>
                <textarea
                  v-model="prompt"
                  rows="3"
                  placeholder="输入触发调度时自动发送给智能体的初始 Prompt 指令..."
                  class="w-full p-2.5 text-xs rounded-lg border border-border/80 bg-surface transition focus:border-primary focus:ring-2 focus:ring-primary/20 resize-y dark:bg-dark-800 leading-relaxed"
                  maxlength="100000"
                />
              </div>
            </div>
          </SurfaceCard>

          <!-- 调度排期卡片 -->
          <SurfaceCard title="调度计划">
            <div class="space-y-4 p-3.5">
              <!-- 分段控制器 Segmented Control -->
              <div>
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                  >调度类型</label
                >
                <div
                  v-if="isEdit"
                  class="text-xs px-3 py-2 rounded-lg bg-muted/60 border border-border/40 font-mono text-muted-foreground flex items-center gap-2"
                >
                  <BaseIcon name="lock" size="xs" />
                  <span
                    >{{
                      scheduleType === "cron"
                        ? "周期任务 (Cron)"
                        : "单次任务 (Once)"
                    }}（已锁定）</span
                  >
                </div>
                <div
                  v-else
                  class="flex rounded-xl bg-surface-subtle p-1 border border-border/60"
                >
                  <button
                    type="button"
                    class="flex-1 py-1.5 text-xs font-medium rounded-lg transition-all"
                    :class="
                      scheduleType === 'cron'
                        ? 'bg-surface text-foreground shadow-xs font-semibold'
                        : 'text-muted-foreground hover:text-foreground'
                    "
                    @click="scheduleType = 'cron'"
                  >
                    周期循环 (Cron)
                  </button>
                  <button
                    type="button"
                    class="flex-1 py-1.5 text-xs font-medium rounded-lg transition-all"
                    :class="
                      scheduleType === 'once'
                        ? 'bg-surface text-foreground shadow-xs font-semibold'
                        : 'text-muted-foreground hover:text-foreground'
                    "
                    @click="scheduleType = 'once'"
                  >
                    单次定时 (Once)
                  </button>
                </div>
              </div>

              <div>
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                  >基准时区</label
                >
                <BaseSelect v-model="timezone" :options="COMMON_TIMEZONES" />
              </div>

              <!-- 周期输入器 -->
              <div v-if="scheduleType === 'cron'">
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                  >执行周期设定</label
                >
                <CronScheduleInput v-model="cron" />
              </div>

              <!-- 单次时间输入器 -->
              <div v-else>
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                  >单次执行时间</label
                >
                <OnceScheduleInput v-model="runAt" :timezone="timezone" />
              </div>
            </div>
          </SurfaceCard>

          <!-- 高级配置折叠区（优雅手风琴样式） -->
          <div
            class="rounded-xl border border-border/60 bg-surface overflow-hidden"
          >
            <button
              type="button"
              class="w-full flex items-center justify-between p-3.5 text-xs font-medium text-foreground hover:bg-muted/40 transition-colors select-none"
              @click="showAdvanced = !showAdvanced"
            >
              <div class="flex items-center gap-2">
                <BaseIcon
                  name="settings-2"
                  size="xs"
                  class="text-muted-foreground"
                />
                <span>高级选项（模型指定与会话模式）</span>
              </div>
              <span
                class="text-muted-foreground text-[10px] transform transition-transform"
                :class="showAdvanced ? 'rotate-180' : ''"
                >▼</span
              >
            </button>

            <div
              v-if="showAdvanced"
              class="p-3.5 pt-0 space-y-3.5 border-t border-border/30"
            >
              <div class="pt-3">
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                  >覆盖模型连接</label
                >
                <BaseSelect v-model="selectedModelId" :options="modelOptions" />
              </div>

              <div>
                <label
                  class="block text-xs font-semibold text-foreground mb-1.5"
                  >会话隔离模式</label
                >
                <div
                  v-if="isEdit"
                  class="text-xs px-3 py-2 rounded-lg bg-muted/60 border border-border/40 font-mono text-muted-foreground"
                >
                  {{
                    threadMode === "fresh"
                      ? "独立新会话 (fresh)"
                      : "复用已有会话 (reuse)"
                  }}（已锁定）
                </div>
                <div v-else class="space-y-2">
                  <div
                    class="flex rounded-xl bg-surface-subtle p-1 border border-border/60"
                  >
                    <button
                      type="button"
                      class="flex-1 py-1.5 text-xs rounded-lg transition-all"
                      :class="
                        threadMode === 'fresh'
                          ? 'bg-surface text-foreground shadow-xs font-semibold'
                          : 'text-muted-foreground'
                      "
                      @click="threadMode = 'fresh'"
                    >
                      独立新会话 (推荐)
                    </button>
                    <button
                      type="button"
                      class="flex-1 py-1.5 text-xs rounded-lg transition-all"
                      :class="
                        threadMode === 'reuse'
                          ? 'bg-amber-500/10 text-amber-600 font-semibold shadow-xs'
                          : 'text-muted-foreground'
                      "
                      @click="threadMode = 'reuse'"
                    >
                      复用已有会话
                    </button>
                  </div>
                  <div v-if="threadMode === 'reuse'" class="space-y-2 pt-1">
                    <div
                      class="p-2.5 text-xs rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 leading-relaxed"
                    >
                      ⚠️ 警告：复用历史会话将累积上下文，请确保指定 Thread
                      已存在且当前账号具备写入权限。
                    </div>
                    <input
                      v-model="threadId"
                      type="text"
                      placeholder="请输入已有 Thread 的 UUID"
                      class="w-full h-9 px-3 text-xs font-mono rounded-lg border border-border/80 bg-surface focus:border-primary"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：Live Inspector 实时排期透视与仿真 (5 cols) -->
        <div class="lg:col-span-5 space-y-4">
          <!-- 1. 所见即所得卡片仿真看板 -->
          <div class="space-y-2">
            <div
              class="flex items-center justify-between text-xs font-semibold text-foreground px-1"
            >
              <span class="flex items-center gap-1.5">
                <BaseIcon name="sparkle" size="xs" class="text-primary" />
                <span>实时效果仿真</span>
              </span>
              <span class="text-[10px] text-muted-foreground font-normal"
                >所见即所得</span
              >
            </div>
            <!-- 仿真卡片 -->
            <ScheduledTaskCard :task="simulatedTask" :can-write="false" />
          </div>

          <!-- 2. 排期穿梭时间轴 -->
          <SurfaceCard title="预计执行节拍 (Timeline)">
            <div class="p-3.5 space-y-3 text-xs">
              <div
                class="flex items-center justify-between text-muted-foreground pb-2 border-b border-border/40"
              >
                <span>周期概要</span>
                <span class="font-medium text-foreground">
                  {{
                    scheduleType === "cron"
                      ? describeCron(cron)
                      : "单次指定执行"
                  }}
                </span>
              </div>

              <!-- 时间轴节点 -->
              <div class="space-y-2.5 pt-1">
                <div class="flex items-center justify-between">
                  <span class="font-semibold text-foreground"
                    >未来派发计划</span
                  >
                  <span
                    v-if="previewLoading"
                    class="text-[11px] text-primary animate-pulse"
                    >预测计算中...</span
                  >
                </div>

                <div
                  v-if="previewTimes.length === 0"
                  class="py-6 text-center text-muted-foreground rounded-xl bg-surface-subtle border border-dashed border-border/60"
                >
                  暂无预测节拍（请核对时间配置）
                </div>

                <div
                  v-else
                  class="relative pl-5 space-y-3 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-border/70"
                >
                  <div
                    v-for="(timeStr, idx) in previewTimes"
                    :key="timeStr"
                    class="relative flex items-center justify-between text-xs"
                  >
                    <!-- 轴上小圆点 -->
                    <span
                      class="absolute -left-5 h-2.5 w-2.5 rounded-full border-2 border-surface"
                      :class="
                        idx === 0
                          ? 'bg-primary ring-2 ring-primary/20'
                          : 'bg-muted-foreground/60'
                      "
                    />
                    <div class="flex flex-col">
                      <span class="font-mono text-foreground font-medium">
                        {{ formatDisplayTime(timeStr, timezone) }}
                      </span>
                      <span class="text-[10px] text-muted-foreground">
                        {{
                          idx === 0 ? "首轮派发时间" : `第 ${idx + 1} 轮调度`
                        }}
                      </span>
                    </div>
                    <span
                      v-if="idx === 0"
                      class="px-2 py-0.5 text-[10px] rounded-full bg-primary/10 text-primary font-semibold"
                    >
                      下次就绪
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </SurfaceCard>

          <!-- 3. 安全托管摘要 -->
          <div
            class="rounded-xl border border-border/50 bg-surface-subtle p-3 text-xs text-muted-foreground space-y-1.5"
          >
            <div class="flex items-center gap-1.5 font-medium text-foreground">
              <BaseIcon name="shield" size="xs" class="text-emerald-500" />
              <span>无人值守安全护栏</span>
            </div>
            <p class="text-[11px] leading-relaxed">
              每次派发由服务端执行 HMAC-SHA256 签名代行验证。如遇到人工审批
              (HITL) 工具将安全中止并留痕。
            </p>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex items-center gap-2.5">
        <BaseButton
          variant="secondary"
          :disabled="submitting"
          @click="emit('close')"
        >
          取消
        </BaseButton>
        <BaseButton
          variant="primary"
          :loading="submitting"
          class="px-5 shadow-xs"
          @click="submit"
        >
          {{ isEdit ? "保存变更" : "立即创建" }}
        </BaseButton>
      </div>
    </template>
  </BaseDrawer>
</template>

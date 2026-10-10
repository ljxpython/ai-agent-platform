<script setup lang="ts">
import { computed } from "vue";
import type { StopRequest, Uncertainty } from "../stop/types";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = defineProps<{
  show: boolean;
  receipt: StopRequest | null;
  projectId?: string;
  threadId?: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const report = computed(() => props.receipt?.report ?? null);

const uncertaintyDescriptions: Record<Uncertainty, string> = {
  checkpoint_unavailable: "部分任务检查点不可用，未持久化中间状态",
  progress_unavailable: "业务计划或阶段进度未能完全记录",
  external_effect_unknown: "部分已执行的外部工具副作用无法确认是否可撤销",
  resource_cleanup_unconfirmed: "容器或后台执行进程尚未确认完全退出释放",
};

function formatIso(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}
</script>

<template>
  <BaseDrawer
    :show="props.show"
    title="会话停止状态与证据报告"
    width="wide"
    @close="emit('close')"
  >
    <div
      v-if="props.receipt"
      data-testid="run-stop-report-details"
      class="space-y-5 p-4 text-xs"
    >
      <!-- 1. 核心状态总览卡片 -->
      <div
        class="rounded-xl border border-gray-200/80 bg-gray-50/50 p-4 shadow-2xs dark:border-dark-700/80 dark:bg-dark-900/50"
      >
        <div class="mb-3 flex items-center justify-between">
          <span class="font-semibold text-gray-900 dark:text-gray-100">
            执行与资源状态
          </span>
          <span
            class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium"
            :class="{
              'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300':
                props.receipt.phase === 'stopped' ||
                props.receipt.phase === 'no_active_run',
              'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300':
                props.receipt.phase === 'confirmation_unavailable' ||
                props.receipt.resource_cleanup === 'unconfirmed',
              'bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300':
                props.receipt.phase === 'stopping' ||
                props.receipt.phase === 'accepted',
              'bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300':
                props.receipt.phase === 'rejected',
            }"
          >
            {{ props.receipt.phase }}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div class="rounded-lg bg-white p-2.5 shadow-2xs dark:bg-dark-800">
            <div class="text-gray-500 dark:text-dark-400">固定目标总数</div>
            <div
              class="mt-1 text-sm font-bold text-gray-900 dark:text-gray-100"
            >
              {{ props.receipt.target_count ?? 0 }}
            </div>
          </div>
          <div class="rounded-lg bg-white p-2.5 shadow-2xs dark:bg-dark-800">
            <div class="text-gray-500 dark:text-dark-400">队列已取消任务</div>
            <div
              class="mt-1 text-sm font-bold text-gray-900 dark:text-gray-100"
            >
              {{ props.receipt.queue?.pending_cancelled_count ?? 0 }}
            </div>
          </div>
          <div class="rounded-lg bg-white p-2.5 shadow-2xs dark:bg-dark-800">
            <div class="text-gray-500 dark:text-dark-400">资源清理状态</div>
            <div
              class="mt-1 text-sm font-bold"
              :class="{
                'text-emerald-600 dark:text-emerald-400':
                  props.receipt.resource_cleanup === 'confirmed',
                'text-amber-600 dark:text-amber-400':
                  props.receipt.resource_cleanup === 'unconfirmed' ||
                  props.receipt.resource_cleanup === 'pending',
                'text-gray-700 dark:text-dark-200':
                  props.receipt.resource_cleanup === 'not_required',
              }"
            >
              {{ props.receipt.resource_cleanup }}
            </div>
          </div>
        </div>

        <div class="mt-3 space-y-1 text-2xs text-gray-500 dark:text-dark-400">
          <div>停止请求时间：{{ formatIso(props.receipt.requested_at) }}</div>
          <div v-if="props.receipt.confirmed_at">
            最终确认时间：{{ formatIso(props.receipt.confirmed_at) }}
          </div>
          <div v-if="props.receipt.request_id">
            查询请求编号：{{ props.receipt.request_id }}
          </div>
        </div>
      </div>

      <!-- 2. 不确定性告警（Uncertainties） -->
      <div
        v-if="report && report.uncertainties.length > 0"
        class="rounded-xl border border-amber-200/90 bg-amber-50/80 p-3.5 dark:border-amber-900/60 dark:bg-amber-950/30"
      >
        <div
          class="mb-2 flex items-center gap-1.5 font-semibold text-amber-900 dark:text-amber-200"
        >
          <BaseIcon name="alert" class="h-4 w-4" />
          <span>需关注的未知与未确认项</span>
        </div>
        <ul
          class="space-y-1.5 pl-5 list-disc text-amber-800 dark:text-amber-300"
        >
          <li v-for="item in report.uncertainties" :key="item">
            {{ uncertaintyDescriptions[item] || item }}
          </li>
        </ul>
      </div>

      <!-- 3. 截断提醒 -->
      <div
        v-if="report?.truncated"
        class="rounded-lg border border-blue-200/80 bg-blue-50/60 p-2.5 text-2xs text-blue-800 dark:border-blue-900/60 dark:bg-blue-950/30 dark:text-blue-300"
      >
        报告证据项已做有界截断，停止确认覆盖完整目标。
      </div>

      <!-- 3.5. 后台长任务清理快照摘要 -->
      <div
        v-if="
          report?.background_tasks &&
          (report.background_tasks.target_count ?? 0) > 0
        "
        class="rounded-xl border border-blue-200/80 bg-blue-50/40 p-3.5 shadow-2xs dark:border-blue-900/50 dark:bg-blue-950/20"
      >
        <div class="mb-2 flex items-center justify-between">
          <span
            class="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-1.5"
          >
            <BaseIcon name="runtime" class="h-3.5 w-3.5 text-primary-500" />
            后台长任务清理快照
          </span>
          <span
            v-if="(report.background_tasks.cleanup_unconfirmed_count ?? 0) > 0"
            class="rounded bg-amber-100 px-1.5 py-0.5 text-2xs font-semibold text-amber-800 dark:bg-amber-900/50 dark:text-amber-300"
          >
            {{ report.background_tasks.cleanup_unconfirmed_count }} 项未完全确认
          </span>
          <span
            v-else
            class="rounded bg-emerald-100 px-1.5 py-0.5 text-2xs font-semibold text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300"
          >
            全部已清理
          </span>
        </div>
        <div
          class="grid grid-cols-2 gap-2 text-2xs text-gray-600 dark:text-dark-300"
        >
          <div>
            快照目标总数:
            <span class="font-mono font-semibold">{{
              report.background_tasks.target_count ?? 0
            }}</span>
          </div>
          <div>
            确认清理完成:
            <span
              class="font-mono font-semibold text-emerald-600 dark:text-emerald-400"
              >{{ report.background_tasks.cleanup_confirmed_count ?? 0 }}</span
            >
          </div>
          <div>
            未确认清理数:
            <span
              class="font-mono font-semibold"
              :class="
                (report.background_tasks.cleanup_unconfirmed_count ?? 0) > 0
                  ? 'text-amber-600 dark:text-amber-400'
                  : ''
              "
              >{{
                report.background_tasks.cleanup_unconfirmed_count ?? 0
              }}</span
            >
          </div>
          <div>
            通知已抑制数:
            <span class="font-mono font-semibold">{{
              report.background_tasks.notifications_suppressed_count ?? 0
            }}</span>
          </div>
        </div>
      </div>

      <!-- 4. 工具证据与计划进度（Progress） -->
      <div v-if="report && report.progress.length > 0" class="space-y-2">
        <h4 class="font-semibold text-gray-900 dark:text-gray-100">
          已保存进度与工具回执 ({{ report.progress.length }})
        </h4>
        <div class="space-y-1.5">
          <div
            v-for="(p, idx) in report.progress"
            :key="idx"
            class="flex items-center justify-between rounded-lg border border-gray-200/70 bg-white p-2.5 shadow-2xs dark:border-dark-700/70 dark:bg-dark-800"
          >
            <div class="flex items-center gap-2 truncate">
              <span
                class="rounded px-1.5 py-0.5 text-2xs font-medium"
                :class="
                  p.kind === 'saved_plan'
                    ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/50 dark:text-purple-300'
                    : 'bg-sky-100 text-sky-800 dark:bg-sky-950/50 dark:text-sky-300'
                "
              >
                {{ p.kind === "saved_plan" ? "执行计划" : "工具回执" }}
              </span>
              <span
                class="truncate font-medium text-gray-800 dark:text-gray-200"
              >
                {{ p.label }}
              </span>
            </div>
            <span
              class="shrink-0 text-2xs font-semibold"
              :class="{
                'text-emerald-600 dark:text-emerald-400':
                  p.observed_status === 'completed' ||
                  p.observed_status === 'recorded',
                'text-blue-600 dark:text-blue-400':
                  p.observed_status === 'in_progress',
                'text-gray-500 dark:text-dark-400':
                  p.observed_status === 'pending',
              }"
            >
              {{ p.observed_status }}
            </span>
          </div>
        </div>
      </div>

      <!-- 5. 授权产物成果（Artifacts） -->
      <div v-if="report && report.artifacts.length > 0" class="space-y-2">
        <h4 class="font-semibold text-gray-900 dark:text-gray-100">
          已生成的工作区成果 ({{ report.artifacts.length }})
        </h4>
        <div class="space-y-1.5">
          <div
            v-for="art in report.artifacts"
            :key="art.artifact_id"
            class="flex items-center justify-between rounded-lg border border-gray-200/70 bg-white p-2.5 shadow-2xs dark:border-dark-700/70 dark:bg-dark-800"
          >
            <div class="flex items-center gap-2 truncate">
              <BaseIcon
                name="file"
                class="h-3.5 w-3.5 shrink-0 text-gray-400"
              />
              <span
                class="truncate font-mono text-2xs text-gray-700 dark:text-gray-300"
              >
                {{ art.path }}
              </span>
            </div>
            <span
              class="shrink-0 text-2xs text-emerald-600 dark:text-emerald-400"
            >
              已受权保存
            </span>
          </div>
        </div>
      </div>

      <!-- 6. 检查点（Checkpoints） -->
      <div v-if="report && report.checkpoints.length > 0" class="space-y-2">
        <h4 class="font-semibold text-gray-900 dark:text-gray-100">
          已提交检查点 ({{ report.checkpoints.length }})
        </h4>
        <div class="space-y-1.5">
          <div
            v-for="cp in report.checkpoints"
            :key="cp.run_id"
            class="rounded-lg border border-gray-200/70 bg-white p-2.5 shadow-2xs dark:border-dark-700/70 dark:bg-dark-800"
          >
            <div
              class="flex items-center justify-between text-2xs text-gray-500 dark:text-dark-400"
            >
              <span class="font-mono">Run: {{ cp.run_id }}</span>
              <span>{{ formatIso(cp.checkpoint_at) }}</span>
            </div>
            <div
              class="mt-1 font-mono text-2xs text-gray-700 dark:text-gray-300 truncate"
            >
              CP: {{ cp.checkpoint_id }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      v-else
      class="flex h-40 flex-col items-center justify-center p-4 text-center text-xs text-gray-400 dark:text-dark-500"
    >
      <BaseIcon name="info" class="h-6 w-6 mb-2 opacity-50" />
      <span>暂无停止报告回执数据</span>
    </div>
  </BaseDrawer>
</template>

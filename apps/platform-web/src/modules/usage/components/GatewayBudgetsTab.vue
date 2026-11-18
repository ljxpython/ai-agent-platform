<script setup lang="ts">
import { ref, computed } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import CreateBudgetPolicyModal from "./CreateBudgetPolicyModal.vue";
import DeleteBudgetPolicyModal from "./DeleteBudgetPolicyModal.vue";
import {
  useGatewayBudgets,
  calculateBudgetRatio,
  formatDurationLabel,
} from "../composables/useGatewayBudgets";
import type { BudgetItem, CreateBudgetPolicyInput } from "../types";

const props = defineProps<{
  scopeMode: "platform" | "project";
  currentProjectId?: string;
  canWrite: boolean;
  canManageGlobal?: boolean;
}>();

const {
  items,
  isLoading,
  error,
  loadBudgets,
  createBudget,
  updateBudget,
  deleteBudget,
} = useGatewayBudgets({
  projectId: computed(() => props.currentProjectId),
  scopeMode: computed(() => props.scopeMode),
});

const isCreateModalOpen = ref(false);
const editingItem = ref<BudgetItem | null>(null);
const deletingItem = ref<BudgetItem | null>(null);
const actionError = ref<string | null>(null);

function handleOpenCreate() {
  editingItem.value = null;
  actionError.value = null;
  isCreateModalOpen.value = true;
}

function handleOpenEdit(item: BudgetItem) {
  editingItem.value = item;
  actionError.value = null;
  isCreateModalOpen.value = true;
}

function handleCloseModal() {
  isCreateModalOpen.value = false;
  editingItem.value = null;
  actionError.value = null;
}

function handleOpenDelete(item: BudgetItem) {
  deletingItem.value = item;
  actionError.value = null;
}

function handleCloseDelete() {
  deletingItem.value = null;
}

async function handleModalSubmit(payload: CreateBudgetPolicyInput) {
  actionError.value = null;
  try {
    if (editingItem.value) {
      await updateBudget(editingItem.value.id, payload);
    } else {
      await createBudget(payload);
    }
    handleCloseModal();
  } catch (err: unknown) {
    const e = err as { message?: string; code?: string };
    if (e.code === "budget_policy_limit") {
      actionError.value =
        "当前租户预算策略存档已达上限 (200条)，请联系平台管理员归档或清理历史策略。";
    } else if (e.code === "budget_policy_changed") {
      actionError.value = "策略已被他人修改，请刷新列表后重试。";
    } else {
      actionError.value = e.message || "保存预算策略失败，请重试。";
    }
  }
}

async function handleConfirmDelete() {
  if (!deletingItem.value) return;
  actionError.value = null;
  try {
    await deleteBudget(deletingItem.value.id);
    handleCloseDelete();
  } catch (err: unknown) {
    const e = err as { message?: string };
    actionError.value = e.message || "删除策略失败，请重试。";
  }
}

// 格式化日期为本地带时区展示
function formatDate(isoStr?: string | null): string {
  if (!isoStr) return "—";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return isoStr;
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- 顶栏说明与操作栏 -->
    <SurfaceCard class="p-4 sm:p-5">
      <div
        class="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
      >
        <div>
          <h2
            class="text-base font-semibold text-gray-900 dark:text-dark-100 flex items-center gap-2"
          >
            <span>预算策略与财务熔断治理</span>
            <span
              class="text-xs px-2 py-0.5 rounded-full bg-primary-50 dark:bg-primary-950/40 text-primary-600 dark:text-primary-400 font-normal"
            >
              Active Control
            </span>
          </h2>
          <p class="text-xs text-gray-500 dark:text-dark-400 mt-1">
            针对平台全局或当前项目设置自然周期资金限额（USD）。支持软告警（ALERT）与硬阻断（REJECT
            429 熔断）。
          </p>
        </div>

        <div class="flex items-center gap-2.5 shrink-0">
          <BaseButton
            variant="secondary"
            size="sm"
            :loading="isLoading"
            @click="loadBudgets"
          >
            <template #icon>
              <BaseIcon name="refresh" class="w-4 h-4" />
            </template>
            刷新
          </BaseButton>

          <BaseButton
            v-if="canWrite"
            variant="primary"
            size="sm"
            @click="handleOpenCreate"
          >
            <template #icon>
              <BaseIcon name="plus" class="w-4 h-4" />
            </template>
            新建预算策略
          </BaseButton>
        </div>
      </div>
    </SurfaceCard>

    <!-- 错误警告提示 -->
    <div
      v-if="error || actionError"
      class="p-4 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/50 flex items-start gap-3 text-sm text-red-700 dark:text-red-300"
    >
      <BaseIcon name="alert" class="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
      <div class="flex-1">
        <p class="font-medium">{{ error || actionError }}</p>
      </div>
      <button
        class="text-xs underline hover:no-underline text-red-600 dark:text-red-400"
        @click="loadBudgets"
      >
        重新加载
      </button>
    </div>

    <!-- 策略列表表格 -->
    <SurfaceCard class="overflow-hidden">
      <div
        v-if="isLoading && items.length === 0"
        class="p-8 text-center text-sm text-gray-500 dark:text-dark-400"
      >
        <BaseIcon
          name="refresh"
          class="w-6 h-6 animate-spin mx-auto mb-2 text-primary-500"
        />
        加载预算策略中...
      </div>

      <div
        v-else-if="items.length === 0"
        class="p-12 text-center text-gray-500 dark:text-dark-400"
      >
        <BaseIcon name="overview" class="w-10 h-10 mx-auto mb-3 opacity-40" />
        <h3 class="text-sm font-medium text-gray-900 dark:text-dark-100">
          暂无配置预算策略
        </h3>
        <p
          class="text-xs text-gray-500 dark:text-dark-400 mt-1 max-w-sm mx-auto"
        >
          创建预算策略以限制每日、每周或每月的模型消耗，防范脚本死循环与超支风险。
        </p>
        <div v-if="canWrite" class="mt-4">
          <BaseButton variant="primary" size="sm" @click="handleOpenCreate">
            立即创建首个策略
          </BaseButton>
        </div>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead
            class="bg-gray-50/75 dark:bg-dark-850/50 border-b border-gray-200 dark:border-dark-700 text-xs text-gray-500 dark:text-dark-400 font-medium"
          >
            <tr>
              <th class="py-3 px-4">作用域 / 目标</th>
              <th class="py-3 px-4">限额与动作</th>
              <th class="py-3 px-4">自然周期窗口</th>
              <th class="py-3 px-4 min-w-[280px]">已用额度 / 进度</th>
              <th class="py-3 px-4">生效状态</th>
              <th v-if="canWrite" class="py-3 px-4 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 dark:divide-dark-700">
            <tr
              v-for="item in items"
              :key="item.id"
              class="hover:bg-gray-50/50 dark:hover:bg-dark-800/40 transition-colors"
            >
              <!-- 作用域 -->
              <td class="py-3.5 px-4 font-mono">
                <div class="flex items-center gap-1.5">
                  <span
                    :class="[
                      'text-xs px-2 py-0.5 rounded font-medium',
                      item.scope === 'GLOBAL'
                        ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300'
                        : 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300',
                    ]"
                  >
                    {{ item.scope }}
                  </span>
                  <span
                    v-if="item.scope === 'PROJECT' && item.project_id"
                    class="text-xs text-gray-400 dark:text-dark-400 truncate max-w-[120px]"
                    :title="item.project_id"
                  >
                    {{ item.project_id.slice(0, 8) }}...
                  </span>
                </div>
              </td>

              <!-- 限额与动作 -->
              <td class="py-3.5 px-4">
                <div class="flex flex-col">
                  <span class="font-semibold text-gray-900 dark:text-dark-100">
                    ${{ item.budget_amount }}
                  </span>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span
                      :class="[
                        'text-[10px] px-1.5 py-0.2 rounded font-medium',
                        item.action === 'REJECT'
                          ? 'bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900/40'
                          : 'bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-900/40',
                      ]"
                    >
                      {{ item.action }}
                    </span>
                    <span class="text-xs text-gray-500 dark:text-dark-400">
                      {{ formatDurationLabel(item.duration) }}
                    </span>
                  </div>
                </div>
              </td>

              <!-- 自然周期窗口 -->
              <td class="py-3.5 px-4 text-xs text-gray-500 dark:text-dark-400">
                <div>起: {{ formatDate(item.window_start) }}</div>
                <div>止: {{ formatDate(item.window_end) }}</div>
              </td>

              <!-- 三态进度条呈现 (核心亮点) -->
              <td class="py-3.5 px-4">
                <div class="space-y-1.5">
                  <!-- 进度条计算 -->
                  <template v-if="item.accounting_status === 'complete'">
                    <!-- 状态 1: 完整账务 -->
                    <div class="flex items-center justify-between text-xs">
                      <span class="font-mono text-gray-700 dark:text-dark-300">
                        ${{ item.current_spend || "0.00" }} / ${{
                          item.budget_amount
                        }}
                      </span>
                      <span
                        :class="[
                          'font-mono font-medium',
                          calculateBudgetRatio(
                            item.current_spend,
                            item.budget_amount,
                          ).isOverBudget
                            ? 'text-red-600 dark:text-red-400 flex items-center gap-1'
                            : calculateBudgetRatio(
                                  item.current_spend,
                                  item.budget_amount,
                                ).ratio >= 0.8
                              ? 'text-amber-600 dark:text-amber-400'
                              : 'text-gray-500 dark:text-dark-400',
                        ]"
                      >
                        <BaseIcon
                          v-if="
                            calculateBudgetRatio(
                              item.current_spend,
                              item.budget_amount,
                            ).isOverBudget
                          "
                          name="alert"
                          class="w-3.5 h-3.5"
                        />
                        {{
                          calculateBudgetRatio(
                            item.current_spend,
                            item.budget_amount,
                          ).percentStr
                        }}
                      </span>
                    </div>

                    <!-- 进度条轨道 -->
                    <div
                      class="w-full h-2 rounded-full bg-gray-100 dark:bg-dark-700 overflow-hidden"
                    >
                      <div
                        :class="[
                          'h-full transition-all duration-300',
                          calculateBudgetRatio(
                            item.current_spend,
                            item.budget_amount,
                          ).isOverBudget
                            ? 'bg-red-500 dark:bg-red-600'
                            : calculateBudgetRatio(
                                  item.current_spend,
                                  item.budget_amount,
                                ).ratio >= 0.8
                              ? 'bg-amber-500 dark:bg-amber-600'
                              : 'bg-primary-500 dark:bg-primary-600',
                        ]"
                        :style="{
                          width: `${calculateBudgetRatio(item.current_spend, item.budget_amount).ratio * 100}%`,
                        }"
                      />
                    </div>
                  </template>

                  <!-- 状态 2: 校准恢复中 (Reconciling) -->
                  <template
                    v-else-if="item.accounting_status === 'reconciling'"
                  >
                    <div
                      class="flex items-center justify-between text-xs text-blue-600 dark:text-blue-400"
                    >
                      <span class="flex items-center gap-1.5">
                        <BaseIcon name="refresh" class="w-3 h-3 animate-spin" />
                        账务校准中 (已知 ${{ item.known_spend || "0.00" }})
                      </span>
                      <span>—</span>
                    </div>
                    <div
                      class="w-full h-2 rounded-full bg-blue-100/60 dark:bg-blue-950/40 animate-pulse"
                    />
                  </template>

                  <!-- 状态 3: 不可核实 (Unverifiable) -->
                  <template v-else>
                    <div class="flex items-center justify-between text-xs">
                      <span
                        :class="[
                          'flex items-center gap-1 font-medium',
                          item.is_exceeded
                            ? 'text-red-600 dark:text-red-400'
                            : 'text-amber-600 dark:text-amber-400',
                        ]"
                      >
                        <BaseIcon name="alert" class="w-3.5 h-3.5 shrink-0" />
                        {{
                          item.is_exceeded
                            ? "已知部分已超标 (审计中)"
                            : "账务状态受阻"
                        }}
                      </span>
                      <span class="font-mono text-gray-500 dark:text-dark-400">
                        已知 ${{ item.known_spend || "0.00" }}
                      </span>
                    </div>
                    <div
                      class="w-full h-2 rounded-full bg-gray-200 dark:bg-dark-700 overflow-hidden"
                    >
                      <div
                        :class="[
                          'h-full',
                          item.is_exceeded
                            ? 'w-full bg-red-500/70'
                            : 'w-1/3 bg-amber-500/70',
                        ]"
                        style="
                          background-image: repeating-linear-gradient(
                            45deg,
                            transparent,
                            transparent 4px,
                            rgba(255, 255, 255, 0.25) 4px,
                            rgba(255, 255, 255, 0.25) 8px
                          );
                        "
                      />
                    </div>
                  </template>
                </div>
              </td>

              <!-- 生效状态 -->
              <td class="py-3.5 px-4">
                <span
                  :class="[
                    'text-xs px-2 py-0.5 rounded-full inline-flex items-center gap-1 font-medium',
                    item.sync_status === 'applied'
                      ? 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300'
                      : 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300',
                  ]"
                >
                  <span
                    :class="[
                      'w-1.5 h-1.5 rounded-full',
                      item.sync_status === 'applied'
                        ? 'bg-green-500'
                        : 'bg-amber-500 animate-ping',
                    ]"
                  />
                  {{ item.sync_status === "applied" ? "生效中" : "同步就绪中" }}
                </span>
              </td>

              <!-- 操作区 -->
              <td v-if="canWrite" class="py-3.5 px-4 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button
                    class="text-xs font-medium text-gray-600 dark:text-dark-300 hover:text-primary-600 dark:hover:text-primary-400 p-1"
                    title="编辑策略"
                    @click="handleOpenEdit(item)"
                  >
                    编辑
                  </button>
                  <button
                    class="text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-700 p-1"
                    title="删除策略"
                    @click="handleOpenDelete(item)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SurfaceCard>

    <!-- 弹窗部分 -->
    <CreateBudgetPolicyModal
      :show="isCreateModalOpen"
      :editing-item="editingItem"
      :scope-mode="scopeMode"
      :current-project-id="currentProjectId"
      :can-manage-global="canManageGlobal"
      @close="handleCloseModal"
      @submit="handleModalSubmit"
    />

    <DeleteBudgetPolicyModal
      :show="Boolean(deletingItem)"
      :item="deletingItem"
      @confirm="handleConfirmDelete"
      @cancel="handleCloseDelete"
    />
  </div>
</template>

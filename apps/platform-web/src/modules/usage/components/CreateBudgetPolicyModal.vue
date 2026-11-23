<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import type {
  BudgetItem,
  CreateBudgetPolicyInput,
  BudgetDurationUnit,
  BudgetTargetScope,
  BudgetAction,
} from "../types";
import { stripTrailingZeros } from "../composables/useGatewayBudgets";

const props = defineProps<{
  show: boolean;
  editingItem?: BudgetItem | null;
  scopeMode: "platform" | "project";
  currentProjectId?: string;
  canManageGlobal?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  submit: [input: CreateBudgetPolicyInput];
}>();

const form = reactive({
  scope: "PROJECT" as BudgetTargetScope,
  project_id: "" as string,
  budget_amount: "" as string,
  duration_unit: "MONTHS" as BudgetDurationUnit,
  action: "REJECT" as BudgetAction,
});

const validationError = ref<string | null>(null);

const isEditing = computed(() => Boolean(props.editingItem));

// 作用域选择控制：Project 模式下强制锁定为 PROJECT
const isScopeLocked = computed(() => {
  return isEditing.value || props.scopeMode === "project";
});

// 重置表单状态
function resetForm() {
  if (props.editingItem) {
    form.scope = props.editingItem.scope;
    form.project_id = props.editingItem.project_id || "";
    form.budget_amount = stripTrailingZeros(props.editingItem.budget_amount);
    form.duration_unit = props.editingItem.duration.unit;
    form.action = props.editingItem.action;
  } else {
    form.scope = props.scopeMode === "project" ? "PROJECT" : "GLOBAL";
    form.project_id =
      props.scopeMode === "project" ? props.currentProjectId || "" : "";
    form.budget_amount = "";
    form.duration_unit = "MONTHS";
    form.action = "REJECT";
  }
  validationError.value = null;
}

watch(
  () => [props.show, props.editingItem],
  () => {
    if (props.show) {
      resetForm();
    }
  },
  { immediate: true },
);

// 金额输入守卫：严格限制纯文本正浮点数，最多 12 位小数
function handleAmountInput(e: Event) {
  const target = e.target as HTMLInputElement;
  let val = target.value.trim();

  // 只允许数字和一个小数点
  val = val.replace(/[^\d.]/g, "");
  const parts = val.split(".");
  if (parts.length > 2) {
    val = `${parts[0]}.${parts.slice(1).join("")}`;
  }
  if (parts[1] && parts[1].length > 12) {
    val = `${parts[0]}.${parts[1].slice(0, 12)}`;
  }
  form.budget_amount = val;
  validationError.value = null;
}

function handleSubmit() {
  validationError.value = null;

  if (!form.budget_amount || form.budget_amount === "0") {
    validationError.value = "请输入大于 0 的有效预算金额";
    return;
  }

  const num = Number(form.budget_amount);
  if (!Number.isFinite(num) || num <= 0) {
    validationError.value = "预算金额必须为正数";
    return;
  }

  if (num >= 1e16) {
    validationError.value = "预算金额超出系统上限";
    return;
  }

  if (form.scope === "PROJECT" && !form.project_id.trim()) {
    validationError.value = "项目作用域必须指定所属项目 ID";
    return;
  }

  const payload: CreateBudgetPolicyInput = {
    scope: form.scope,
    project_id: form.scope === "PROJECT" ? form.project_id.trim() : null,
    budget_amount: form.budget_amount,
    budget_unit: "USD",
    duration: {
      unit: form.duration_unit,
      value: 1,
    },
    action: form.action,
  };

  emit("submit", payload);
}
</script>

<template>
  <BaseDialog
    :show="show"
    :title="isEditing ? '编辑预算策略' : '新建预算策略'"
    width="normal"
    @close="emit('close')"
  >
    <div class="space-y-4 py-2">
      <!-- 作用域选择 -->
      <div>
        <label
          class="block text-sm font-medium text-gray-700 dark:text-dark-200 mb-1"
        >
          生效作用域
        </label>
        <select
          v-model="form.scope"
          :disabled="isScopeLocked"
          class="w-full rounded-md border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-800 px-3 py-2 text-sm text-gray-900 dark:text-dark-100 disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="PROJECT">当前项目 (PROJECT)</option>
          <option
            value="GLOBAL"
            :disabled="!canManageGlobal && scopeMode === 'platform'"
          >
            平台全局 (GLOBAL) - 跨租户所有项目兜底
          </option>
        </select>
        <p
          v-if="scopeMode === 'project'"
          class="mt-1 text-xs text-gray-500 dark:text-dark-400"
        >
          在项目视图下仅能为当前项目配置独立预算。
        </p>
      </div>

      <!-- 预算金额输入 -->
      <div>
        <label
          class="block text-sm font-medium text-gray-700 dark:text-dark-200 mb-1"
        >
          预算限额 (USD) <span class="text-red-500">*</span>
        </label>
        <div class="relative rounded-md shadow-sm">
          <div
            class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3"
          >
            <span class="text-gray-500 sm:text-sm">$</span>
          </div>
          <input
            type="text"
            :value="form.budget_amount"
            placeholder="例如 200.00"
            class="block w-full rounded-md border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-800 pl-7 pr-12 py-2 text-sm text-gray-900 dark:text-dark-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
            @input="handleAmountInput"
          />
          <div
            class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3"
          >
            <span class="text-gray-500 sm:text-xs">USD (最多12位小数)</span>
          </div>
        </div>
      </div>

      <!-- 重置周期 -->
      <div>
        <label
          class="block text-sm font-medium text-gray-700 dark:text-dark-200 mb-1"
        >
          自然重置周期
        </label>
        <select
          v-model="form.duration_unit"
          class="w-full rounded-md border border-gray-300 dark:border-dark-600 bg-white dark:bg-dark-800 px-3 py-2 text-sm text-gray-900 dark:text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="MONTHS">每月 (自然月 1 日 UTC 00:00 重置)</option>
          <option value="WEEKS">每周 (每周日 UTC 00:00 重置)</option>
          <option value="DAYS">每日 (每日午夜 UTC 00:00 重置)</option>
        </select>
        <p class="mt-1 text-xs text-gray-500 dark:text-dark-400">
          时间窗口基于 UTC
          自然日历左闭右开自动对齐滚动，到期后已用费用自动清零。
        </p>
      </div>

      <!-- 超额动作 -->
      <div>
        <label
          class="block text-sm font-medium text-gray-700 dark:text-dark-200 mb-1"
        >
          超额执行动作
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label
            :class="[
              'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors',
              form.action === 'REJECT'
                ? 'border-red-500 bg-red-50/50 dark:bg-red-950/20'
                : 'border-gray-200 dark:border-dark-700 hover:bg-gray-50 dark:hover:bg-dark-800',
            ]"
          >
            <div>
              <div class="text-sm font-medium text-gray-900 dark:text-dark-100">
                REJECT (硬阻断熔断)
              </div>
              <div class="text-xs text-gray-500 dark:text-dark-400 mt-0.5">
                超额后阻止后续模型调用打回 429
              </div>
            </div>
            <input
              v-model="form.action"
              type="radio"
              value="REJECT"
              class="text-red-600 focus:ring-red-500"
            />
          </label>

          <label
            :class="[
              'flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors',
              form.action === 'ALERT'
                ? 'border-amber-500 bg-amber-50/50 dark:bg-amber-950/20'
                : 'border-gray-200 dark:border-dark-700 hover:bg-gray-50 dark:hover:bg-dark-800',
            ]"
          >
            <div>
              <div class="text-sm font-medium text-gray-900 dark:text-dark-100">
                ALERT (软告警通知)
              </div>
              <div class="text-xs text-gray-500 dark:text-dark-400 mt-0.5">
                首次超额推送系统通知，请求继续放行
              </div>
            </div>
            <input
              v-model="form.action"
              type="radio"
              value="ALERT"
              class="text-amber-600 focus:ring-amber-500"
            />
          </label>
        </div>
      </div>

      <!-- 校验错误警告 -->
      <div
        v-if="validationError"
        class="p-2.5 rounded bg-red-50 dark:bg-red-900/30 text-xs text-red-600 dark:text-red-400"
      >
        {{ validationError }}
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-3">
        <BaseButton variant="secondary" @click="emit('close')">
          取消
        </BaseButton>
        <BaseButton variant="primary" @click="handleSubmit">
          {{ isEditing ? "保存修改" : "确认创建" }}
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

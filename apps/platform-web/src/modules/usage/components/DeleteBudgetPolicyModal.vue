<script setup lang="ts">
import ConfirmDialog from "@/components/base/ConfirmDialog.vue";
import type { BudgetItem } from "../types";
import {
  formatDurationLabel,
  formatActionLabel,
  formatBudgetAmount,
} from "../composables/useGatewayBudgets";

defineProps<{
  show: boolean;
  item?: BudgetItem | null;
}>();

const emit = defineEmits<{
  confirm: [];
  cancel: [];
}>();
</script>

<template>
  <ConfirmDialog
    :show="show"
    title="删除预算策略"
    :message="
      item
        ? `确认删除限额为 $${formatBudgetAmount(item.budget_amount)} (${formatDurationLabel(item.duration)}，${formatActionLabel(item.action)}) 的预算策略？删除后系统将不再对此范围执行周期性限额约束。`
        : '确认删除该预算策略？'
    "
    confirm-text="确认删除"
    cancel-text="取消"
    danger
    @confirm="emit('confirm')"
    @cancel="emit('cancel')"
  />
</template>

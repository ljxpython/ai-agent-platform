<script setup lang="ts">
import { ref, watch } from "vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";

const props = withDefaults(
  defineProps<{
    show: boolean;
    busy?: boolean;
  }>(),
  {
    busy: false,
  },
);

const emit = defineEmits<{
  close: [];
  confirm: [];
}>();

const acknowledged = ref(false);

watch(
  () => props.show,
  (open) => {
    if (!open) {
      acknowledged.value = false;
    }
  },
);

function handleCancel() {
  acknowledged.value = false;
  emit("close");
}

function handleConfirm() {
  if (!acknowledged.value || props.busy) return;
  emit("confirm");
}
</script>

<template>
  <BaseDialog
    :show="show"
    title="确认切换至「允许工作区操作」"
    width="normal"
    @close="handleCancel"
  >
    <div class="space-y-4 text-sm text-gray-600 dark:text-dark-200">
      <div class="rounded-lg border border-amber-200 bg-amber-50/80 p-3 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200">
        <div class="flex items-start gap-2.5">
          <BaseIcon
            name="alert"
            class="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400"
          />
          <div class="text-xs leading-5">
            <span class="font-semibold">受控工作区免审批策略：</span>
            开启后，Agent 在受控工作区范围内的日常研发操作将不再逐次暂停请求确认，可自主推进多步任务。
          </div>
        </div>
      </div>

      <div class="space-y-2">
        <h4 class="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-dark-400">
          受此策略影响的权限边界
        </h4>
        <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div class="rounded-lg border border-emerald-200/80 bg-emerald-50/50 p-2.5 dark:border-emerald-900/50 dark:bg-emerald-950/20">
            <div class="flex items-center gap-1.5 font-medium text-emerald-800 dark:text-emerald-300 text-xs mb-1">
              <BaseIcon
                name="check"
                size="xs"
                class="text-emerald-600 dark:text-emerald-400"
              />
              <span>免逐次审批工具</span>
            </div>
            <ul class="text-[11px] text-emerald-700 dark:text-emerald-400/90 space-y-0.5 list-disc list-inside">
              <li>写入文件 (<code class="font-mono">write_file</code>)</li>
              <li>编辑文件 (<code class="font-mono">edit_file</code>)</li>
              <li>受限命令 (<code class="font-mono">execute</code>)</li>
            </ul>
          </div>

          <div class="rounded-lg border border-blue-200/80 bg-blue-50/50 p-2.5 dark:border-blue-900/50 dark:bg-blue-950/20">
            <div class="flex items-center gap-1.5 font-medium text-blue-800 dark:text-blue-300 text-xs mb-1">
              <BaseIcon
                name="shield"
                size="xs"
                class="text-blue-600 dark:text-blue-400"
              />
              <span>仍强制拦截审批</span>
            </div>
            <ul class="text-[11px] text-blue-700 dark:text-blue-400/90 space-y-0.5 list-disc list-inside">
              <li>预览部署 (<code class="font-mono">deploy_preview</code>)</li>
              <li>技能治理与发布</li>
              <li>凭据、权限与外部副作用</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="border-t border-gray-100 pt-3 dark:border-dark-800">
        <label class="flex items-start gap-2.5 cursor-pointer select-none">
          <input
            v-model="acknowledged"
            type="checkbox"
            class="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-dark-700 dark:bg-dark-900"
            data-testid="risk-acknowledge-checkbox"
          />
          <span class="text-xs leading-relaxed text-gray-700 dark:text-dark-200">
            我已了解上述工作区自动操作范围及不可突破的安全底线，确认对当前会话开启工作区操作免审批。
          </span>
        </label>
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <BaseButton
          variant="secondary"
          size="sm"
          :disabled="busy"
          @click="handleCancel"
        >
          取消
        </BaseButton>
        <BaseButton
          variant="primary"
          size="sm"
          :disabled="!acknowledged || busy"
          data-testid="risk-confirm-button"
          @click="handleConfirm"
        >
          <span v-if="busy">正在保存...</span>
          <span v-else>确认开启</span>
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

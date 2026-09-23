<script setup lang="ts">
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import type { ProviderStation } from "./ProviderStationCard.vue";
import type { RuntimeModelItem } from "@/types/management";

defineProps<{
  deleteDialogState: {
    open: boolean;
    model: RuntimeModelItem | null;
    busy: boolean;
  };
  deleteStationDialogState: {
    open: boolean;
    station: ProviderStation | null;
    busy: boolean;
  };
}>();

const emit = defineEmits<{
  (e: "close-delete-model"): void;
  (e: "confirm-delete-model"): void;
  (e: "close-delete-station"): void;
  (e: "confirm-delete-station"): void;
}>();
</script>

<template>
  <BaseDialog
    :show="deleteDialogState.open"
    title="删除模型"
    width="narrow"
    @close="emit('close-delete-model')"
  >
    <div class="space-y-3 text-sm text-gray-600 dark:text-dark-300">
      <p>
        确定要删除模型
        <strong class="font-mono text-gray-900 dark:text-white">
          {{ deleteDialogState.model?.display_name || deleteDialogState.model?.model }}
        </strong>
        吗？
      </p>
      <p class="text-xs text-rose-600 dark:text-rose-400">
        ⚠️ 此操作将永久移除该模型配置。若有正在使用该模型的任务或 Agent，可能会导致调用失败。
      </p>
    </div>
    <template #footer>
      <div class="flex justify-end gap-3">
        <BaseButton
          variant="secondary"
          :disabled="deleteDialogState.busy"
          @click="emit('close-delete-model')"
        >
          取消
        </BaseButton>
        <BaseButton
          variant="danger"
          :disabled="deleteDialogState.busy"
          @click="emit('confirm-delete-model')"
        >
          {{ deleteDialogState.busy ? "正在删除…" : "确认删除" }}
        </BaseButton>
      </div>
    </template>
  </BaseDialog>

  <BaseDialog
    :show="deleteStationDialogState.open"
    :title="`删除提供商「${deleteStationDialogState.station?.name || ''}」`"
    width="normal"
    @close="emit('close-delete-station')"
  >
    <div class="space-y-3 text-sm text-gray-600 dark:text-dark-300">
      <p>
        确定要删除提供商
        <strong class="font-semibold text-gray-900 dark:text-white">
          {{ deleteStationDialogState.station?.name }}
        </strong>
        <span class="font-mono text-xs text-gray-500">
          ({{ deleteStationDialogState.station?.provider }})
        </span>
        及其包含的全部
        <strong class="text-rose-600 dark:text-rose-400">
          {{ deleteStationDialogState.station?.models.length || 0 }} 个模型配置
        </strong>
        吗？
      </p>
      <div
        v-if="deleteStationDialogState.station?.models.length"
        class="max-h-36 overflow-y-auto rounded-lg border border-gray-100 bg-gray-50 p-2 text-xs font-mono dark:border-dark-800 dark:bg-dark-900"
      >
        <div
          v-for="m in deleteStationDialogState.station.models"
          :key="m.id"
          class="flex items-center justify-between py-1 border-b border-gray-100 last:border-0 dark:border-dark-800"
        >
          <span class="truncate text-gray-800 dark:text-dark-200">
            {{ m.display_name || m.model }}
          </span>
          <span class="text-gray-400 dark:text-dark-500 text-[11px] ml-2 shrink-0">
            {{ m.model }}
          </span>
        </div>
      </div>
      <p class="text-xs text-rose-600 dark:text-rose-400">
        ⚠️ 此操作将永久移除该提供商下的所有模型接入及凭据。若有智能体正绑定这些模型，可能会导致调用失败。
      </p>
    </div>
    <template #footer>
      <div class="flex justify-end gap-3">
        <BaseButton
          variant="secondary"
          :disabled="deleteStationDialogState.busy"
          @click="emit('close-delete-station')"
        >
          取消
        </BaseButton>
        <BaseButton
          variant="danger"
          :disabled="deleteStationDialogState.busy"
          @click="emit('confirm-delete-station')"
        >
          {{
            deleteStationDialogState.busy
              ? "正在删除…"
              : `确认删除 (${deleteStationDialogState.station?.models.length || 0} 个模型)`
          }}
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

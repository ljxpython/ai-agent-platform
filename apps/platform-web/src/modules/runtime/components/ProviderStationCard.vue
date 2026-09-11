<script setup lang="ts">
import { ref } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import ActionMenu from "@/components/platform/ActionMenu.vue";
import StatusPill from "@/components/platform/StatusPill.vue";
import type { ActionMenuItem } from "@/components/platform/data-table";
import { useUiStore } from "@/stores/ui";
import type { RuntimeModelItem } from "@/types/management";
import { copyText } from "@/utils/clipboard";

export interface ProviderStation {
  id: string;
  name: string;
  provider: string;
  baseUrl: string;
  protocol: string;
  credentialConfigured: boolean;
  modelCount: number;
  enabledCount: number;
  models: RuntimeModelItem[];
  isDefaultStation: boolean;
}

const props = withDefaults(
  defineProps<{
    station: ProviderStation;
    getModelActions: (model: RuntimeModelItem) => ActionMenuItem[];
    defaultExpanded?: boolean;
    canManage?: boolean;
    defaultModelIds?: string[];
    authorizedModelIds?: string[];
  }>(),
  {
    defaultExpanded: true,
    canManage: false,
    defaultModelIds: () => [],
    authorizedModelIds: () => [],
  },
);

const emit = defineEmits<{
  "add-model": [station: ProviderStation];
  "view-detail": [model: RuntimeModelItem];
}>();

const uiStore = useUiStore();
const isExpanded = ref(props.defaultExpanded);

async function handleCopy(label: string, text: string) {
  const copied = await copyText(text);
  uiStore.pushToast({
    type: copied ? "success" : "warning",
    title: copied ? `已复制 ${label}` : "复制失败",
    message: copied ? text : "请手动复制该内容。",
  });
}
</script>

<template>
  <div
    class="pw-panel overflow-hidden border border-gray-200/90 bg-white shadow-sm transition-all hover:border-gray-300 dark:border-dark-700 dark:bg-dark-900 dark:hover:border-dark-600"
  >
    <!-- 中转站卡片头部 -->
    <div
      class="border-b border-gray-100 bg-gray-50/50 px-5 py-4 dark:border-dark-800 dark:bg-dark-950/40"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <!-- 左侧：中转站标识与端点 -->
        <div class="flex items-center gap-3">
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 shadow-sm dark:bg-primary-950/50 dark:text-primary-400"
          >
            <BaseIcon
              name="globe"
              size="md"
            />
          </div>
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ station.name }}
              </h3>
              <span
                class="rounded-md bg-gray-200/70 px-2 py-0.5 text-[11px] font-mono text-gray-700 dark:bg-dark-800 dark:text-dark-300"
              >
                {{ station.provider }}
              </span>
              <span
                class="rounded-md bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700 dark:bg-sky-950/40 dark:text-sky-300"
              >
                {{ station.protocol }}
              </span>
              <span
                v-if="station.isDefaultStation"
                class="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
              >
                <BaseIcon
                  name="check"
                  size="xs"
                />
                包含默认模型
              </span>
            </div>
            <div
              class="mt-1 flex items-center gap-2 text-xs text-gray-500 dark:text-dark-400"
            >
              <span class="font-medium text-gray-400 dark:text-dark-500">端点:</span>
              <span
                class="font-mono text-[11px] text-gray-600 dark:text-dark-300 truncate max-w-xs md:max-w-md"
              >
                {{ station.baseUrl || "无特定端点" }}
              </span>
              <button
                v-if="station.baseUrl"
                type="button"
                class="text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
                title="复制端点 Base URL"
                @click="handleCopy('接入端点', station.baseUrl)"
              >
                <BaseIcon
                  name="copy"
                  size="xs"
                />
              </button>
            </div>
          </div>
        </div>

        <!-- 右侧：凭据、模型数及快捷操作 -->
        <div class="flex items-center gap-2.5">
          <div
            class="flex items-center gap-1.5 rounded-lg border border-gray-200/70 bg-white px-2.5 py-1 text-xs dark:border-dark-700 dark:bg-dark-800"
          >
            <span
              class="h-2 w-2 rounded-full"
              :class="
                station.credentialConfigured ? 'bg-emerald-500' : 'bg-amber-500'
              "
            />
            <span
              :class="
                station.credentialConfigured
                  ? 'text-gray-700 dark:text-dark-200'
                  : 'text-amber-600 dark:text-amber-400'
              "
            >
              {{
                station.credentialConfigured ? "凭据均已配置" : "部分凭据未配置"
              }}
            </span>
          </div>

          <div
            class="rounded-lg bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-dark-800 dark:text-dark-300"
          >
            共 {{ station.modelCount }} 个模型 ({{ station.enabledCount }} 启用)
          </div>

          <BaseButton
            v-if="canManage"
            variant="secondary"
            size="sm"
            @click="emit('add-model', station)"
          >
            <BaseIcon
              name="plus"
              size="xs"
            />
            <span>添加模型</span>
          </BaseButton>

          <button
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200/70 bg-white text-gray-500 transition hover:bg-gray-100 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-300 dark:hover:bg-dark-700"
            :title="isExpanded ? '收起模型列表' : '展开模型列表'"
            @click="isExpanded = !isExpanded"
          >
            <BaseIcon
              name="chevron-down"
              size="sm"
              class="transition-transform duration-200"
              :class="isExpanded ? 'rotate-180' : ''"
            />
          </button>
        </div>
      </div>
    </div>

    <!-- 中转站包含的模型列表（可折叠） -->
    <div
      v-show="isExpanded"
      class="divide-y divide-gray-100 dark:divide-dark-800"
    >
      <div
        v-if="station.models.length === 0"
        class="py-6 text-center text-xs text-gray-400 dark:text-dark-500"
      >
        该中转站暂无模型配置
      </div>
      <div
        v-else
        class="overflow-x-auto"
      >
        <table class="w-full text-left text-xs">
          <thead
            class="border-b border-gray-100 bg-gray-50/40 text-[11px] font-semibold text-gray-500 dark:border-dark-800 dark:bg-dark-950/20 dark:text-dark-400"
          >
            <tr>
              <th class="px-5 py-2.5">
                Model ID
              </th>
              <th class="px-4 py-2.5">
                Display Name
              </th>
              <th class="px-3 py-2.5">
                默认项
              </th>
              <th class="px-3 py-2.5">
                项目授权
              </th>
              <th class="px-3 py-2.5">
                状态
              </th>
              <th class="px-3 py-2.5">
                凭据
              </th>
              <th class="px-4 py-2.5 text-right">
                操作
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100/70 dark:divide-dark-800/60">
            <tr
              v-for="model in station.models"
              :key="model.id"
              class="group transition-colors hover:bg-gray-50/60 dark:hover:bg-dark-800/40"
            >
              <td
                class="px-5 py-3 font-mono font-medium text-gray-900 dark:text-white"
              >
                <div class="flex items-center gap-1.5">
                  <span class="truncate max-w-[200px]">{{ model.model }}</span>
                  <button
                    type="button"
                    class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600 transition dark:hover:text-dark-200"
                    title="复制 Model ID"
                    @click="handleCopy('Model ID', model.model)"
                  >
                    <BaseIcon
                      name="copy"
                      size="xs"
                    />
                  </button>
                </div>
              </td>
              <td
                class="px-4 py-3 font-medium text-gray-800 dark:text-dark-200 truncate max-w-[240px]"
              >
                {{ model.display_name || "--" }}
              </td>
              <td class="px-3 py-3">
                <span
                  v-if="defaultModelIds.includes(model.id)"
                  class="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
                >
                  <BaseIcon
                    name="check"
                    size="xs"
                  />
                  default
                </span>
                <span
                  v-else
                  class="text-gray-400 text-[11px] dark:text-dark-500"
                >
                  --
                </span>
              </td>
              <td class="px-3 py-3">
                {{
                  authorizedModelIds.includes(model.id) ? "已授权" : "未授权"
                }}
              </td>
              <td class="px-3 py-3">
                <StatusPill
                  :tone="model.enabled === false ? 'danger' : 'success'"
                >
                  {{ model.enabled === false ? "disabled" : "enabled" }}
                </StatusPill>
              </td>
              <td class="px-3 py-3">
                <StatusPill
                  :tone="model.credential_configured ? 'success' : 'warning'"
                >
                  {{ model.credential_configured ? "configured" : "missing" }}
                </StatusPill>
              </td>
              <td class="px-4 py-3 text-right">
                <ActionMenu :items="getModelActions(model)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

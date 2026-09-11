<script setup lang="ts">
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { useUiStore } from "@/stores/ui";
import type { RuntimeModelItem } from "@/types/management";
import { copyText } from "@/utils/clipboard";

const props = defineProps<{
  show: boolean;
  model: RuntimeModelItem | null;
  canManage?: boolean;
  isProjectDefault?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  edit: [model: RuntimeModelItem];
}>();

const uiStore = useUiStore();

async function handleCopy(label: string, value?: string) {
  if (!value) return;
  const copied = await copyText(value);
  uiStore.pushToast({
    type: copied ? "success" : "warning",
    title: copied ? `已复制 ${label}` : "复制失败",
    message: copied ? value : "请手动复制该内容。",
  });
}

function handleEdit() {
  if (props.model) {
    emit("edit", props.model);
  }
}
</script>

<template>
  <BaseDialog
    :show="show"
    title="模型详情"
    width="normal"
    @close="emit('close')"
  >
    <div
      v-if="model"
      class="space-y-5"
    >
      <!-- 头部状态指示区 -->
      <div
        class="rounded-xl border border-gray-100 bg-gray-50/70 p-4 dark:border-dark-800 dark:bg-dark-950/40"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-center gap-2.5">
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-950/50 dark:text-primary-400"
            >
              <BaseIcon
                name="sparkle"
                size="sm"
              />
            </div>
            <div>
              <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
                {{ model.display_name || model.model }}
              </h3>
              <p class="text-xs text-gray-500 dark:text-dark-400 font-mono">
                {{ model.model }}
              </p>
            </div>
          </div>
          <div class="flex items-center gap-1.5 flex-wrap justify-end">
            <span
              v-if="isProjectDefault"
              class="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
            >
              <BaseIcon
                name="check"
                size="xs"
              />
              默认模型
            </span>
            <span
              class="inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium"
              :class="
                model.enabled !== false
                  ? 'bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-400'
                  : 'bg-gray-100 text-gray-500 dark:bg-dark-800 dark:text-dark-400'
              "
            >
              {{ model.enabled !== false ? "已启用" : "已停用" }}
            </span>
          </div>
        </div>
      </div>

      <!-- 详细指标网格 -->
      <div class="grid gap-3.5 sm:grid-cols-2 text-xs">
        <div
          class="rounded-lg border border-gray-100 bg-white p-3 shadow-sm dark:border-dark-800 dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between text-gray-500 dark:text-dark-400"
          >
            <span>Model ID</span>
            <button
              type="button"
              class="text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
              title="复制 Model ID"
              @click="handleCopy('Model ID', model.model)"
            >
              <BaseIcon
                name="copy"
                size="xs"
              />
            </button>
          </div>
          <div
            class="mt-1 font-mono font-medium text-gray-900 dark:text-white truncate"
          >
            {{ model.model }}
          </div>
        </div>

        <div
          class="rounded-lg border border-gray-100 bg-white p-3 shadow-sm dark:border-dark-800 dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between text-gray-500 dark:text-dark-400"
          >
            <span>Display Name</span>
          </div>
          <div class="mt-1 font-medium text-gray-900 dark:text-white truncate">
            {{ model.display_name || "--" }}
          </div>
        </div>

        <div
          class="rounded-lg border border-gray-100 bg-white p-3 shadow-sm dark:border-dark-800 dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between text-gray-500 dark:text-dark-400"
          >
            <span>提供商 (Provider)</span>
          </div>
          <div class="mt-1 font-medium text-gray-900 dark:text-white truncate">
            {{ model.provider || "default" }}
          </div>
        </div>

        <div
          class="rounded-lg border border-gray-100 bg-white p-3 shadow-sm dark:border-dark-800 dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between text-gray-500 dark:text-dark-400"
          >
            <span>通讯协议 (Protocol)</span>
          </div>
          <div
            class="mt-1 font-mono font-medium text-gray-900 dark:text-white truncate"
          >
            {{ model.protocol || "openai-compatible" }}
          </div>
        </div>

        <div
          class="sm:col-span-2 rounded-lg border border-gray-100 bg-white p-3 shadow-sm dark:border-dark-800 dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between text-gray-500 dark:text-dark-400"
          >
            <span>接入端点 (Base URL)</span>
            <button
              v-if="model.base_url"
              type="button"
              class="text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
              title="复制 Base URL"
              @click="handleCopy('Base URL', model.base_url)"
            >
              <BaseIcon
                name="copy"
                size="xs"
              />
            </button>
          </div>
          <div
            class="mt-1 font-mono text-xs font-medium text-gray-900 dark:text-white break-all"
          >
            {{ model.base_url || "--" }}
          </div>
        </div>

        <div
          class="rounded-lg border border-gray-100 bg-white p-3 shadow-sm dark:border-dark-800 dark:bg-dark-900"
        >
          <div class="text-gray-500 dark:text-dark-400">
            凭据状态
          </div>
          <div class="mt-1 flex items-center gap-1.5 font-medium">
            <span
              class="h-2 w-2 rounded-full"
              :class="
                model.credential_configured ? 'bg-emerald-500' : 'bg-amber-500'
              "
            />
            <span
              :class="
                model.credential_configured
                  ? 'text-emerald-700 dark:text-emerald-400'
                  : 'text-amber-700 dark:text-amber-400'
              "
            >
              {{
                model.credential_configured ? "API 凭据已配置" : "未检测到凭据"
              }}
            </span>
          </div>
        </div>

        <div
          class="rounded-lg border border-gray-100 bg-white p-3 shadow-sm dark:border-dark-800 dark:bg-dark-900"
        >
          <div
            class="flex items-center justify-between text-gray-500 dark:text-dark-400"
          >
            <span>记录 UUID</span>
            <button
              v-if="model.id"
              type="button"
              class="text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
              title="复制 记录 UUID"
              @click="handleCopy('记录 UUID', model.id)"
            >
              <BaseIcon
                name="copy"
                size="xs"
              />
            </button>
          </div>
          <div
            class="mt-1 font-mono font-medium text-gray-900 dark:text-white truncate"
          >
            {{ model.id || "--" }}
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2.5">
        <BaseButton
          variant="secondary"
          size="sm"
          @click="emit('close')"
        >
          关闭
        </BaseButton>
        <BaseButton
          v-if="canManage"
          size="sm"
          @click="handleEdit"
        >
          <BaseIcon
            name="settings-2"
            size="xs"
          />
          编辑配置
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

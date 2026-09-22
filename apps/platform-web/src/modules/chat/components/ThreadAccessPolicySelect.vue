<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, type CSSProperties } from "vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import type { AccessPolicy } from "@/services/threads/session.service";
import ThreadAccessRiskDialog from "./ThreadAccessRiskDialog.vue";

const props = withDefaults(
  defineProps<{
    modelValue?: AccessPolicy;
    disabled?: boolean;
    loading?: boolean;
    canWrite?: boolean;
    canFullAccess?: boolean;
    tooltip?: string;
  }>(),
  {
    modelValue: "review",
    disabled: false,
    loading: false,
    canWrite: true,
    tooltip: "",
  },
);

const emit = defineEmits<{
  "update:modelValue": [value: AccessPolicy];
  change: [value: AccessPolicy];
}>();

const isOpen = ref(false);
const showRiskDialog = ref(false);
const pendingTargetPolicy = ref<AccessPolicy>("workspace_write");
const triggerRef = ref<HTMLButtonElement | null>(null);
const dropdownRef = ref<HTMLElement | null>(null);
const dropdownStyle = ref<CSSProperties>({});

const currentPolicy = computed<AccessPolicy>(() => props.modelValue || "review");

const isWorkspaceWrite = computed(() => currentPolicy.value === "workspace_write");
const isFullAccess = computed(() => currentPolicy.value === "full_access");

const currentLabel = computed(() => {
  if (isFullAccess.value) return "全权负责 (Full access)";
  if (isWorkspaceWrite.value) return "允许工作区操作";
  return "审阅每项操作";
});

const effectiveTooltip = computed(() => {
  if (props.tooltip) return props.tooltip;
  if (!props.canWrite) return "无项目写权限，无法调整访问策略";
  if (props.disabled) return "当前状态下不可更改策略";
  if (isFullAccess.value) return "当前为全权负责模式：所有工具审批默认全部放行，极高自主权";
  if (isWorkspaceWrite.value) return "当前为受控工作区免审模式：写文件与执行命令无需确认";
  return "当前为逐项审阅模式：写文件与执行命令须人工确认";
});

function updateDropdownPosition() {
  if (!isOpen.value || !triggerRef.value) return;

  const rect = triggerRef.value.getBoundingClientRect();
  const menuHeight = 240;
  const spaceBelow = window.innerHeight - rect.bottom;
  const showAbove = spaceBelow < menuHeight && rect.top > menuHeight;

  dropdownStyle.value = {
    position: "fixed",
    left: `${Math.max(12, Math.min(rect.left, window.innerWidth - 300))}px`,
    top: showAbove ? "auto" : `${rect.bottom + 6}px`,
    bottom: showAbove ? `${window.innerHeight - rect.top + 6}px` : "auto",
    width: "300px",
    zIndex: 9999,
  };
}

function toggleDropdown() {
  if (props.disabled || props.loading) return;
  isOpen.value = !isOpen.value;
  if (isOpen.value) {
    nextTick(() => updateDropdownPosition());
  }
}

function handlePointerDown(event: PointerEvent) {
  if (!isOpen.value) return;
  const target = event.target as Node | null;
  if (
    triggerRef.value?.contains(target) ||
    dropdownRef.value?.contains(target)
  ) {
    return;
  }
  isOpen.value = false;
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === "Escape" && isOpen.value) {
    event.preventDefault();
    isOpen.value = false;
  }
}

function selectPolicy(target: AccessPolicy) {
  if (!props.canWrite || (target === "full_access" && props.canFullAccess === false)) return;
  isOpen.value = false;
  if (target === currentPolicy.value) return;

  if (target === "workspace_write" || target === "full_access") {
    pendingTargetPolicy.value = target;
    showRiskDialog.value = true;
    return;
  }

  // 降级为 review 不需要二次确认
  emit("update:modelValue", "review");
  emit("change", "review");
}

function confirmRiskUpgrade() {
  const target = pendingTargetPolicy.value;
  showRiskDialog.value = false;
  if (!props.canWrite || (target === "full_access" && props.canFullAccess === false)) return;
  emit("update:modelValue", target);
  emit("change", target);
}

onMounted(() => {
  window.addEventListener("pointerdown", handlePointerDown);
  window.addEventListener("keydown", handleKeyDown);
  window.addEventListener("resize", updateDropdownPosition);
  window.addEventListener("scroll", updateDropdownPosition, true);
});

onBeforeUnmount(() => {
  window.removeEventListener("pointerdown", handlePointerDown);
  window.removeEventListener("keydown", handleKeyDown);
  window.removeEventListener("resize", updateDropdownPosition);
  window.removeEventListener("scroll", updateDropdownPosition, true);
});
</script>

<template>
  <div class="relative inline-block text-left">
    <button
      ref="triggerRef"
      type="button"
      class="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium shadow-2xs transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500/20 disabled:cursor-not-allowed disabled:opacity-50"
      :class="[
        isFullAccess
          ? 'border-red-300 bg-red-50/80 text-red-900 hover:bg-red-100/70 hover:border-red-400 dark:border-red-800/80 dark:bg-red-950/40 dark:text-red-200 dark:hover:bg-red-900/60'
          : isWorkspaceWrite
            ? 'border-amber-300 bg-amber-50/80 text-amber-900 hover:bg-amber-100/70 hover:border-amber-400 dark:border-amber-800/80 dark:bg-amber-950/40 dark:text-amber-200 dark:hover:bg-amber-900/60'
            : 'border-gray-200/80 bg-white/90 text-gray-600 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:border-dark-700/80 dark:bg-dark-800/90 dark:text-dark-300 dark:hover:border-dark-600 dark:hover:text-white',
        isOpen ? 'ring-2 ring-primary-500/20 border-primary-500' : ''
      ]"
      :disabled="disabled || loading"
      :title="effectiveTooltip"
      aria-haspopup="true"
      :aria-expanded="isOpen"
      data-testid="access-policy-trigger"
      @click="toggleDropdown"
    >
      <!-- Shield 图标: 根据当前档位切换 (借鉴 deepseek-harness 设计) -->
      <span
        class="flex h-3.5 w-3.5 shrink-0 items-center justify-center"
        :class="[
          isFullAccess
            ? 'text-red-600 dark:text-red-400'
            : isWorkspaceWrite
              ? 'text-amber-600 dark:text-amber-400'
              : 'text-blue-500 dark:text-blue-400'
        ]"
      >
        <!-- Full access: 盾牌 + 感叹号 (图 1 同款) -->
        <svg
          v-if="isFullAccess"
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M8.20554 0.899994L14.7901 3.36857V7.01026C14.7901 12 11.0466 14.2103 8.20554 15.3C5.36446 14.2103 1.62012 12 1.62012 7.01026V3.36857L8.20554 0.899994Z"
            stroke="currentColor"
            stroke-width="1.3"
            stroke-linejoin="round"
          />
          <path
            d="M8 5V8.5"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
          />
          <circle
            cx="8"
            cy="11"
            r="0.8"
            fill="currentColor"
          />
        </svg>

        <!-- Workspace write: 盾牌 + 编辑铅笔 -->
        <svg
          v-else-if="isWorkspaceWrite"
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M8.08887 0.251709C8.20479 0.23085 8.32486 0.241168 8.43652 0.282959L15.0215 2.75171C15.2787 2.84819 15.4492 3.09414 15.4492 3.3689V7.0105C15.4492 7.10986 15.4441 7.2081 15.4414 7.30542C15.0285 7.07175 14.5905 6.87695 14.1309 6.73022V3.82495L8.20508 1.60327L2.2793 3.82495V7.0105C2.27936 9.7171 3.4745 11.5379 5.02734 12.7947C5.01025 12.9942 5 13.1962 5 13.4001C5.00001 13.7617 5.02722 14.1169 5.08008 14.4636C2.91555 13.0393 0.961014 10.752 0.960938 7.0105V3.3689C0.960938 3.09417 1.13146 2.84821 1.38867 2.75171L7.97461 0.282959L8.08887 0.251709Z"
            fill="currentColor"
          />
          <path d="M11.3525 5.64688V6.85688H5V5.64688H11.3525Z" fill="currentColor" />
          <path d="M9.5824 8.29376V9.50376H5V8.29376H9.5824Z" fill="currentColor" />
        </svg>

        <!-- Review: 盾牌 + 校验勾 -->
        <svg
          v-else
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M8.20554 0.899994L14.7901 3.36857V7.01026C14.7901 12 11.0466 14.2103 8.20554 15.3C5.36446 14.2103 1.62012 12 1.62012 7.01026V3.36857L8.20554 0.899994Z"
            stroke="currentColor"
            stroke-width="1.3"
            stroke-linejoin="round"
          />
          <path
            d="M12.1654 5.7552L8.9447 9.41475C8.73044 9.65816 8.53628 9.8804 8.35774 10.0423C8.1713 10.2114 7.94235 10.3717 7.64016 10.4254C7.48207 10.4535 7.32 10.4552 7.16151 10.4294C6.85843 10.3801 6.62728 10.2223 6.43836 10.0559C6.25752 9.89653 6.06037 9.67732 5.84264 9.43705L4.72925 8.20897L5.63557 7.38707L6.74897 8.61594C6.98603 8.87755 7.12974 9.03533 7.24673 9.13839C7.31033 9.19443 7.34485 9.21476 7.35823 9.22122C7.38068 9.22484 7.40352 9.22515 7.42593 9.22122C7.40522 9.22502 7.42893 9.23294 7.53583 9.136C7.65132 9.03126 7.79316 8.87139 8.02643 8.60638L11.2479 4.94763L12.1654 5.7552Z"
            fill="currentColor"
          />
        </svg>
      </span>

      <span class="truncate max-w-[130px]">{{ currentLabel }}</span>

      <!-- 旋转的小箭头 -->
      <span
        class="text-gray-400 transition-transform duration-200"
        :class="isOpen ? 'rotate-180' : ''"
      >
        <BaseIcon
          name="chevron-down"
          size="xs"
        />
      </span>
    </button>

    <!-- Teleport Popover -->
    <Teleport to="body">
      <div
        v-if="isOpen"
        ref="dropdownRef"
        :style="dropdownStyle"
        class="overflow-hidden rounded-xl border border-gray-200/90 bg-white/95 p-1.5 shadow-xl backdrop-blur-md dark:border-dark-700/90 dark:bg-dark-900/95"
        role="menu"
        aria-orientation="vertical"
        data-testid="access-policy-dropdown"
      >
        <div class="px-2 py-1.5 border-b border-gray-100 dark:border-dark-800 text-[11px] font-semibold text-gray-500 dark:text-dark-400 flex items-center justify-between">
          <span>会话访问策略</span>
          <span
            v-if="loading"
            class="text-primary-600 dark:text-primary-400 text-[10px]"
          >
            保存中...
          </span>
        </div>

        <div class="py-1 space-y-1">
          <!-- Option: Review -->
          <button
            type="button"
            class="w-full text-left rounded-lg p-2 transition-colors flex items-start gap-2.5 group"
            :class="
              currentPolicy === 'review'
                ? 'bg-blue-50/70 text-blue-900 dark:bg-blue-950/40 dark:text-blue-200'
                : 'hover:bg-gray-50 dark:hover:bg-dark-800 text-gray-800 dark:text-dark-100'
            "
            role="menuitem"
            data-testid="policy-option-review"
            @click="selectPolicy('review')"
          >
            <span class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-blue-500">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M8.20554 0.899994L14.7901 3.36857V7.01026C14.7901 12 11.0466 14.2103 8.20554 15.3C5.36446 14.2103 1.62012 12 1.62012 7.01026V3.36857L8.20554 0.899994Z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" />
                <path d="M12.1654 5.7552L8.9447 9.41475C8.73044 9.65816 8.53628 9.8804 8.35774 10.0423C8.1713 10.2114 7.94235 10.3717 7.64016 10.4254C7.48207 10.4535 7.32 10.4552 7.16151 10.4294C6.85843 10.3801 6.62728 10.2223 6.43836 10.0559C6.25752 9.89653 6.06037 9.67732 5.84264 9.43705L4.72925 8.20897L5.63557 7.38707L6.74897 8.61594C6.98603 8.87755 7.12974 9.03533 7.24673 9.13839C7.31033 9.19443 7.34485 9.21476 7.35823 9.22122C7.38068 9.22484 7.40352 9.22515 7.42593 9.22122C7.40522 9.22502 7.42893 9.23294 7.53583 9.136C7.65132 9.03126 7.79316 8.87139 8.02643 8.60638L11.2479 4.94763L12.1654 5.7552Z" fill="currentColor" />
              </svg>
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold">审阅每项操作</span>
                <span class="text-[10px] text-gray-400 font-normal">默认</span>
              </div>
              <p class="text-[11px] text-gray-500 dark:text-dark-400 leading-normal mt-0.5">
                写文件、编辑与受限命令均须逐次审批，安全严格受控。
              </p>
            </div>
            <BaseIcon
              v-if="currentPolicy === 'review'"
              name="check"
              size="xs"
              class="shrink-0 text-blue-600 dark:text-blue-400 mt-1"
            />
          </button>

          <!-- Option: Workspace Write -->
          <button
            type="button"
            class="w-full text-left rounded-lg p-2 transition-colors flex items-start gap-2.5 group"
            :class="
              currentPolicy === 'workspace_write'
                ? 'bg-amber-50/80 text-amber-950 dark:bg-amber-950/40 dark:text-amber-200'
                : 'hover:bg-gray-50 dark:hover:bg-dark-800 text-gray-800 dark:text-dark-100'
            "
            role="menuitem"
            data-testid="policy-option-workspace-write"
            @click="selectPolicy('workspace_write')"
          >
            <span class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-amber-600 dark:text-amber-400">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M8.08887 0.251709C8.20479 0.23085 8.32486 0.241168 8.43652 0.282959L15.0215 2.75171C15.2787 2.84819 15.4492 3.09414 15.4492 3.3689V7.0105C15.4492 7.10986 15.4441 7.2081 15.4414 7.30542C15.0285 7.07175 14.5905 6.87695 14.1309 6.73022V3.82495L8.20508 1.60327L2.2793 3.82495V7.0105C2.27936 9.7171 3.4745 11.5379 5.02734 12.7947C5.01025 12.9942 5 13.1962 5 13.4001C5.00001 13.7617 5.02722 14.1169 5.08008 14.4636C2.91555 13.0393 0.961014 10.752 0.960938 7.0105V3.3689C0.960938 3.09417 1.13146 2.84821 1.38867 2.75171L7.97461 0.282959L8.08887 0.251709Z" fill="currentColor" />
                <path d="M11.3525 5.64688V6.85688H5V5.64688H11.3525Z" fill="currentColor" />
                <path d="M9.5824 8.29376V9.50376H5V8.29376H9.5824Z" fill="currentColor" />
              </svg>
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold">允许工作区操作</span>
                <span class="text-[10px] text-amber-700 dark:text-amber-300 font-medium">免审批</span>
              </div>
              <p class="text-[11px] text-gray-500 dark:text-dark-400 leading-normal mt-0.5">
                工作区内写文件与执行命令直接运行，高风险操作仍需审批。
              </p>
            </div>
            <BaseIcon
              v-if="currentPolicy === 'workspace_write'"
              name="check"
              size="xs"
              class="shrink-0 text-amber-600 dark:text-amber-400 mt-1"
            />
          </button>

          <!-- Option: Full access (全权负责，图 1 同款) -->
          <button
            type="button"
            class="w-full text-left rounded-lg p-2 transition-colors flex items-start gap-2.5 group"
            :class="
              currentPolicy === 'full_access'
                ? 'bg-red-50/80 text-red-950 dark:bg-red-950/40 dark:text-red-200'
                : 'hover:bg-gray-50 dark:hover:bg-dark-800 text-gray-800 dark:text-dark-100'
            "
            role="menuitem"
            data-testid="policy-option-full-access"
            :disabled="canFullAccess === false"
            @click="selectPolicy('full_access')"
          >
            <span class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-red-600 dark:text-red-400">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M8.20554 0.899994L14.7901 3.36857V7.01026C14.7901 12 11.0466 14.2103 8.20554 15.3C5.36446 14.2103 1.62012 12 1.62012 7.01026V3.36857L8.20554 0.899994Z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" />
                <path d="M8 5V8.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                <circle cx="8" cy="11" r="0.8" fill="currentColor" />
              </svg>
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-red-600 dark:text-red-400">Full access (全权负责)</span>
                <span class="text-[10px] text-red-600 dark:text-red-400 font-medium">全放行</span>
              </div>
              <p class="text-[11px] text-gray-500 dark:text-dark-400 leading-normal mt-0.5">
                {{ canFullAccess === false ? '仅私人会话所有者可启用；共享不会授予此权限。' : '默认放行所有工具审批，AI 拥有最高自主权，不暂停任务。' }}
              </p>
            </div>
            <BaseIcon
              v-if="currentPolicy === 'full_access'"
              name="check"
              size="xs"
              class="shrink-0 text-red-600 dark:text-red-400 mt-1"
            />
          </button>
        </div>
      </div>
    </Teleport>

    <!-- 风险确认对话框 -->
    <ThreadAccessRiskDialog
      :show="showRiskDialog"
      :busy="loading"
      :target-policy="pendingTargetPolicy"
      @close="showRiskDialog = false"
      @confirm="confirmRiskUpgrade"
    />
  </div>
</template>

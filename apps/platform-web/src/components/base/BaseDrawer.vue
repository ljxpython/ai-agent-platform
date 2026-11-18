<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import BaseIcon from "@/components/base/BaseIcon.vue";

type DrawerSide = "left" | "right";
type DrawerWidth = "narrow" | "normal" | "wide" | "xl" | "2xl" | "full";

const props = withDefaults(
  defineProps<{
    show: boolean;
    title: string;
    side?: DrawerSide;
    width?: DrawerWidth;
    flush?: boolean;
    closeOnEscape?: boolean;
    closeOnClickOutside?: boolean;
    resizable?: boolean;
    customWidth?: number;
    minWidth?: number;
    maxWidth?: number;
  }>(),
  {
    side: "right",
    width: "normal",
    flush: false,
    closeOnEscape: true,
    closeOnClickOutside: true,
    resizable: false,
    customWidth: undefined,
    minWidth: 420,
    maxWidth: undefined,
  },
);

const emit = defineEmits<{
  (e: "close"): void;
  (e: "update:customWidth", width: number): void;
  (e: "resize", width: number): void;
}>();

const { t } = useI18n();
const drawerRef = ref<HTMLElement | null>(null);
let previousActiveElement: HTMLElement | null = null;

const internalWidth = ref<number | null>(props.customWidth ?? null);

watch(
  () => props.customWidth,
  (val) => {
    if (typeof val === "number") {
      internalWidth.value = val;
    }
  },
);

const panelStyle = computed(() => {
  if (internalWidth.value) {
    return {
      width: `min(${internalWidth.value}px, 96vw)`,
    };
  }
  return {};
});

const isResizing = ref(false);

function startResize(_e: MouseEvent) {
  if (!props.resizable) return;
  isResizing.value = true;
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";

  const onMouseMove = (moveEvent: MouseEvent) => {
    if (!isResizing.value) return;
    const minW = props.minWidth ?? 420;
    const maxW =
      props.maxWidth ??
      (typeof window !== "undefined"
        ? Math.max(window.innerWidth - 60, minW)
        : 1400);
    let newWidth = internalWidth.value ?? 520;
    if (props.side === "right") {
      newWidth = window.innerWidth - moveEvent.clientX;
    } else {
      newWidth = moveEvent.clientX;
    }
    const clamped = Math.max(minW, Math.min(maxW, newWidth));
    internalWidth.value = clamped;
    emit("update:customWidth", clamped);
    emit("resize", clamped);
  };

  const onMouseUp = () => {
    isResizing.value = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
  };

  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", onMouseUp);
}

function widthClass(width: DrawerWidth) {
  switch (width) {
    case "narrow":
      return "w-screen sm:w-[320px] sm:max-w-[92vw]";
    case "wide":
      return "w-screen sm:w-[520px] sm:max-w-[96vw]";
    case "xl":
      return "w-screen sm:w-[min(840px,96vw)]";
    case "2xl":
      return "w-screen sm:w-[min(1040px,96vw)]";
    case "full":
      return "w-screen sm:w-[min(1280px,98vw)]";
    default:
      return "w-screen sm:w-[420px] sm:max-w-[94vw]";
  }
}

function panelPositionClass(side: DrawerSide) {
  return side === "left" ? "left-0" : "right-0";
}

function panelTransitionClass(side: DrawerSide, phase: "from" | "to") {
  if (side === "left") {
    return phase === "from" ? "-translate-x-full" : "translate-x-0";
  }
  return phase === "from" ? "translate-x-full" : "translate-x-0";
}

function closeDrawer() {
  emit("close");
}

function handleEscape(event: KeyboardEvent) {
  const dialogs = document.querySelectorAll('[role="dialog"]');
  if (!props.show || !dialogs[dialogs.length - 1]?.contains(drawerRef.value))
    return;
  if (props.closeOnEscape && event.key === "Escape") {
    event.preventDefault();
    emit("close");
  }
  if (event.key === "Tab" && drawerRef.value) {
    const elements = [
      ...drawerRef.value.querySelectorAll<HTMLElement>(
        'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]',
      ),
    ].filter((element) => element.getClientRects().length > 0);
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (!first) {
      event.preventDefault();
      drawerRef.value.focus();
    } else if (!drawerRef.value.contains(document.activeElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first)?.focus();
    } else if (
      event.shiftKey &&
      (document.activeElement === first ||
        document.activeElement === drawerRef.value)
    ) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
}

watch(
  () => props.show,
  async (isOpen) => {
    if (typeof document === "undefined") {
      return;
    }

    if (isOpen) {
      previousActiveElement = document.activeElement as HTMLElement | null;
      document.body.classList.add("pw-dialog-open");
      await nextTick();
      drawerRef.value?.focus();
      return;
    }

    document.body.classList.remove("pw-dialog-open");
    previousActiveElement?.focus?.();
    previousActiveElement = null;
  },
  { immediate: true },
);

onMounted(() => {
  document.addEventListener("keydown", handleEscape);
});

onUnmounted(() => {
  document.removeEventListener("keydown", handleEscape);
  document.body.classList.remove("pw-dialog-open");
});
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
      @after-enter="drawerRef?.focus()"
    >
      <div
        v-if="show"
        class="fixed inset-0 z-[90] bg-slate-950/30 backdrop-blur-sm"
        role="dialog"
        :aria-label="title"
        aria-modal="true"
        @click.self="closeOnClickOutside ? closeDrawer() : undefined"
      >
        <Transition
          enter-active-class="transform transition duration-200 ease-out"
          :enter-from-class="panelTransitionClass(side, 'from')"
          :enter-to-class="panelTransitionClass(side, 'to')"
          leave-active-class="transform transition duration-150 ease-in"
          :leave-from-class="panelTransitionClass(side, 'to')"
          :leave-to-class="panelTransitionClass(side, 'from')"
          appear
        >
          <div
            ref="drawerRef"
            tabindex="-1"
            class="pw-dialog-panel absolute inset-y-0 flex h-full flex-col overflow-hidden shadow-2xl"
            :class="[
              panelPositionClass(side),
              !internalWidth ? widthClass(width) : '',
            ]"
            :style="panelStyle"
          >
            <!-- 可拖拽拉伸手柄 (仅当 resizable 且 side 为 right 时位于左侧) -->
            <div
              v-if="resizable && side === 'right'"
              class="absolute inset-y-0 left-0 w-3 -ml-1.5 cursor-col-resize z-50 group flex items-center justify-center select-none"
              title="按住左右拖拽调整抽屉宽度"
              @mousedown.prevent="startResize"
            >
              <div
                class="w-1 h-14 rounded-full bg-gray-300 dark:bg-dark-600 group-hover:bg-sky-500 group-hover:w-1.5 transition-all opacity-0 group-hover:opacity-100 group-active:opacity-100 group-active:bg-sky-600"
              />
            </div>
            <div
              class="flex shrink-0 items-center justify-between gap-4 border-b border-gray-100 px-6 py-4 dark:border-dark-800"
            >
              <div
                class="text-base font-semibold text-gray-900 dark:text-white flex-1 min-w-0"
              >
                <slot name="title">{{ title }}</slot>
              </div>
              <div class="flex items-center gap-2">
                <slot name="header-actions" />
                <button
                  type="button"
                  class="rounded-xl p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-800 dark:hover:text-dark-200"
                  :aria-label="t('common.close')"
                  @click="closeDrawer"
                >
                  <BaseIcon name="x" size="sm" />
                </button>
              </div>
            </div>

            <div
              class="min-h-0 flex-1"
              :class="
                flush
                  ? 'flex flex-col overflow-hidden p-0'
                  : 'overflow-y-auto px-6 py-5'
              "
            >
              <slot />
            </div>

            <div
              v-if="$slots.footer"
              class="flex shrink-0 justify-end border-t border-gray-100 px-6 py-4 dark:border-dark-800"
            >
              <slot name="footer" />
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

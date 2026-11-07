<script setup lang="ts">
import { ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import BaseIcon from "@/components/base/BaseIcon.vue";
import { useNavigation } from "@/composables/useNavigation";
import { appMeta } from "@/config/app-meta";
import BrandMark from "@/components/layout/BrandMark.vue";
import { useThemeStore } from "@/stores/theme";
import { useUiStore } from "@/stores/ui";

const route = useRoute();
const { t } = useI18n();
const uiStore = useUiStore();
const themeStore = useThemeStore();

const groups = useNavigation();

const activeTooltip = ref<{
  text: string;
  top: number;
  visible: boolean;
}>({
  text: "",
  top: 0,
  visible: false,
});

function showTooltip(text: string, event: MouseEvent) {
  if (!uiStore.sidebarCollapsed) return;
  const el = event.currentTarget as HTMLElement | null;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  activeTooltip.value = {
    text,
    top: rect.top + rect.height / 2,
    visible: true,
  };
}

function hideTooltip() {
  activeTooltip.value.visible = false;
}

function isActive(path: string, exact = false): boolean {
  if (exact) {
    return route.path === path;
  }

  return route.path === path || route.path.startsWith(`${path}/`);
}

function isGroupExpanded(groupId: string): boolean {
  if (uiStore.sidebarCollapsed) {
    return true;
  }

  return uiStore.isSidebarGroupExpanded(groupId);
}

function isGroupActive(group: (typeof groups.value)[number]): boolean {
  return group.items.some((item) => isActive(item.to, item.exact));
}

function toggleGroup(groupId: string) {
  if (uiStore.sidebarCollapsed) {
    return;
  }

  uiStore.toggleSidebarGroup(groupId);
}

watch(
  groups,
  (nextGroups) => {
    uiStore.ensureSidebarExpandedGroups(nextGroups.map((group) => group.id));
  },
  { immediate: true },
);
</script>

<template>
  <aside
    class="pw-sidebar transition-[width] duration-300"
    :class="uiStore.sidebarCollapsed ? 'w-[72px]' : 'w-64'"
  >
    <div
      class="pw-sidebar-header"
      :class="uiStore.sidebarCollapsed ? 'justify-center px-0' : ''"
    >
      <div
        class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl shadow-glow"
      >
        <BrandMark alt="Agent Platform mark" class="scale-[1.08]" />
      </div>
      <div v-if="!uiStore.sidebarCollapsed" class="flex min-w-0 flex-col">
        <div
          class="truncate text-[17px] font-semibold tracking-[-0.01em] text-gray-900 dark:text-white"
        >
          {{ appMeta.name }}
        </div>
        <div
          class="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400 dark:text-dark-500"
        >
          {{ appMeta.versionLabel }}
        </div>
      </div>
    </div>

    <nav class="pw-sidebar-nav">
      <section v-for="group in groups" :key="group.id" class="mb-6">
        <button
          v-if="!uiStore.sidebarCollapsed"
          type="button"
          class="mb-2 flex w-full items-center px-3 pb-1 pt-0.5 text-left transition-colors duration-150 hover:text-gray-700 dark:hover:text-dark-200"
          :class="
            isGroupActive(group)
              ? 'text-gray-700 dark:text-dark-100'
              : 'text-gray-400 dark:text-dark-500'
          "
          :aria-expanded="isGroupExpanded(group.id)"
          @click="toggleGroup(group.id)"
        >
          <span class="pw-sidebar-section-title mb-0 px-0">
            {{ group.label }}
          </span>
        </button>
        <div v-else class="mx-4 my-3 h-px bg-gray-200 dark:bg-dark-800" />
        <div v-show="isGroupExpanded(group.id)" class="space-y-1">
          <template v-for="item in group.items" :key="item.to">
            <div
              v-if="!uiStore.sidebarCollapsed && item.sectionTitle"
              class="pw-sidebar-subsection-title"
            >
              {{ item.sectionTitle }}
            </div>
            <router-link
              :to="item.to"
              class="pw-sidebar-link"
              :class="
                isActive(item.to, item.exact) ? 'pw-sidebar-link-active' : ''
              "
              :aria-label="item.label"
              @mouseenter="showTooltip(item.label, $event)"
              @mouseleave="hideTooltip"
              @click="hideTooltip"
            >
              <BaseIcon :name="item.icon as never" size="md" class="shrink-0" />
              <span v-if="!uiStore.sidebarCollapsed">{{ item.label }}</span>
            </router-link>
          </template>
        </div>
      </section>
    </nav>

    <div class="mt-auto border-t border-gray-100 p-3 dark:border-dark-800">
      <button
        type="button"
        class="pw-sidebar-link mb-2 w-full"
        :aria-label="
          themeStore.mode === 'dark'
            ? t('common.lightMode')
            : t('common.darkMode')
        "
        @mouseenter="
          showTooltip(
            themeStore.mode === 'dark'
              ? t('common.lightMode')
              : t('common.darkMode'),
            $event,
          )
        "
        @mouseleave="hideTooltip"
        @click="
          themeStore.toggleMode();
          hideTooltip();
        "
      >
        <BaseIcon
          :name="themeStore.mode === 'dark' ? 'sun' : 'moon'"
          size="md"
          class="shrink-0"
          :class="themeStore.mode === 'dark' ? 'text-amber-500' : ''"
        />
        <span v-if="!uiStore.sidebarCollapsed">
          {{
            themeStore.mode === "dark"
              ? t("common.lightMode")
              : t("common.darkMode")
          }}
        </span>
      </button>

      <button
        type="button"
        class="pw-sidebar-link w-full"
        :aria-label="uiStore.sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
        @mouseenter="
          showTooltip(
            uiStore.sidebarCollapsed ? '展开侧边栏' : '收起侧边栏',
            $event,
          )
        "
        @mouseleave="hideTooltip"
        @click="
          uiStore.toggleSidebar();
          hideTooltip();
        "
      >
        <BaseIcon
          :name="uiStore.sidebarCollapsed ? 'chevron-right' : 'chevron-left'"
          size="md"
          class="shrink-0"
        />
        <span v-if="!uiStore.sidebarCollapsed"> 收起 </span>
      </button>
    </div>

    <!-- Mini 态右侧浮动气泡 (单例，Teleport 至 body，绝不被侧边栏裁剪) -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="opacity-0 translate-x-1"
        enter-to-class="opacity-100 translate-x-0"
        leave-active-class="transition duration-100 ease-in"
        leave-from-class="opacity-100 translate-x-0"
        leave-to-class="opacity-0 translate-x-1"
      >
        <div
          v-if="uiStore.sidebarCollapsed && activeTooltip.visible"
          role="tooltip"
          class="pointer-events-none fixed z-50 flex items-center"
          :style="{
            left: '80px',
            top: `${activeTooltip.top}px`,
            transform: 'translateY(-50%)',
          }"
        >
          <!-- 小三角指向图标 -->
          <div
            class="h-0 w-0 border-y-[5px] border-r-[6px] border-y-transparent border-r-gray-900/90 dark:border-r-dark-800"
          />
          <!-- 气泡主体 -->
          <div
            class="whitespace-nowrap rounded-lg bg-gray-900/90 px-2.5 py-1 text-xs font-medium text-white shadow-lg backdrop-blur-sm dark:border dark:border-dark-700/80 dark:bg-dark-800 dark:text-gray-100"
          >
            {{ activeTooltip.text }}
          </div>
        </div>
      </Transition>
    </Teleport>
  </aside>
</template>

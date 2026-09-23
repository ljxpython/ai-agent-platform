<script setup lang="ts">
import { ref, computed, watch, onMounted, onScopeDispose } from "vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import {
  getDearSkills,
  getDearSkillDetail,
  getDearSkillContent,
  createCustomSkill,
  updateCustomSkill,
  toggleCustomSkill,
  deleteCustomSkill,
  type SkillItem,
  type PublicSkillItem,
  type CustomSkillItem,
  type SkillDetail,
  type DearSkillsCapabilities,
  type DearSkillsLimits,
} from "@/services/dear-agent/skills.service";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";
import ConfirmDialog from "@/components/base/ConfirmDialog.vue";
import SkillDetailDrawer from "../components/SkillDetailDrawer.vue";
import SkillUploadModals from "../components/SkillUploadModals.vue";

const { activeProject, activeProjectId } = useWorkspaceProjectContext();
const { can } = useAuthorization();
const canWrite = computed(() => can("project.runtime.execute", activeProjectId.value));

// 专区切换
const activeTab = ref<"public" | "custom">("public");

// 技能数据与状态
const skillsList = ref<SkillItem[]>([]);
const capabilities = ref<DearSkillsCapabilities>({
  can_read: true,
  can_write: true,
  custom_management_enabled: true,
});
const limits = ref<DearSkillsLimits | null>(null);
const loading = ref(false);
const errorMsg = ref("");
const successMsg = ref("");
const searchQuery = ref("");

// 权限与管理综合判断
const canWriteSkill = computed(
  () => canWrite.value && capabilities.value.can_write && capabilities.value.custom_management_enabled,
);

// 启停防抖 Set
const togglingSlugs = ref<Set<string>>(new Set());

// 导入弹窗状态
const isUploadModalOpen = ref(false);
const selectedFile = ref<File | null>(null);
const fileError = ref("");
const isUploading = ref(false);
const conflictSlug = ref<string | null>(null);

// 显式更新弹窗状态
const isUpdateModalOpen = ref(false);
const updateTargetSkill = ref<CustomSkillItem | null>(null);
const updateSelectedFile = ref<File | null>(null);
const updateFileError = ref("");
const isUpdating = ref(false);

// 删除确认弹窗
const isDeleteModalOpen = ref(false);
const deleteTargetSkill = ref<CustomSkillItem | null>(null);
const isDeleting = ref(false);

// 详情抽屉状态
const isDrawerOpen = ref(false);
const drawerSkill = ref<SkillDetail | null>(null);
const drawerLoading = ref(false);
const selectedPath = ref<string>("");
const selectedContent = ref<string>("");
const contentLoading = ref(false);
const contentError = ref("");
const copySuccess = ref(false);

// 分组计算
const publicSkills = computed(() =>
  skillsList.value.filter((s): s is PublicSkillItem => s.source === "public"),
);
const customSkills = computed(() =>
  skillsList.value.filter((s): s is CustomSkillItem => s.source === "custom"),
);

// 过滤后的公共技能
const filteredPublicSkills = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return publicSkills.value;
  return publicSkills.value.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.slug.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q),
  );
});

// 过滤后的自定义技能
const filteredCustomSkills = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return customSkills.value;
  return customSkills.value.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.slug.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.digest.toLowerCase().includes(q),
  );
});

// 加载技能全量列表
async function fetchSkills() {
  if (!activeProjectId.value) {
    skillsList.value = [];
    return;
  }
  loading.value = true;
  errorMsg.value = "";
  try {
    const resp = await getDearSkills(activeProjectId.value);
    skillsList.value = [...(resp.items || [])];
    capabilities.value = resp.capabilities || {
      can_read: true,
      can_write: false,
      custom_management_enabled: false,
    };
    limits.value = resp.limits || null;
  } catch (err: any) {
    const code = err.response?.data?.error?.code || err.response?.data?.code || err.code;
    if (code === "dear_skills_disabled") {
      errorMsg.value = "自定义技能管理未开启（RUNTIME_DEAR_GOVERNANCE_ENABLED=1）";
    } else if (code === "dear_skills_scope_denied") {
      errorMsg.value = "无权访问此项目的技能数据";
    } else {
      errorMsg.value = err.message || "读取技能列表失败";
    }
  } finally {
    loading.value = false;
  }
}

// 启停自定义技能
async function handleToggleSkill(skill: CustomSkillItem, nextEnabled: boolean) {
  if (!canWriteSkill.value || togglingSlugs.value.has(skill.slug) || !activeProjectId.value) return;
  togglingSlugs.value.add(skill.slug);
  errorMsg.value = "";
  try {
    const updated = await toggleCustomSkill(
      activeProjectId.value,
      skill.slug,
      nextEnabled,
      skill.revision,
    );
    const idx = skillsList.value.findIndex(
      (s) => s.source === "custom" && s.slug === skill.slug,
    );
    if (idx !== -1) {
      skillsList.value[idx] = updated;
    }
    if (drawerSkill.value && drawerSkill.value.slug === skill.slug) {
      drawerSkill.value = updated;
    }
    showSuccess(`技能 ${skill.name || skill.slug} 已${nextEnabled ? "启用" : "停用"}`);
  } catch (err: any) {
    const code = err.response?.data?.error?.code || err.code;
    if (code === "skill_revision_conflict") {
      errorMsg.value = "⚠️ 版本状态已被其他并发操作更新，已自动刷新，请重新核对";
      await fetchSkills();
    } else {
      errorMsg.value = err.response?.data?.message || err.message || "启停操作失败";
    }
  } finally {
    togglingSlugs.value.delete(skill.slug);
  }
}

// 打开详情抽屉
async function openDetailDrawer(skill: SkillItem) {
  if (!activeProjectId.value) return;
  isDrawerOpen.value = true;
  drawerLoading.value = true;
  drawerSkill.value = null;
  selectedPath.value = "";
  selectedContent.value = "";
  contentError.value = "";
  copySuccess.value = false;
  try {
    const detail = await getDearSkillDetail(activeProjectId.value, skill.source, skill.slug);
    drawerSkill.value = detail;
    const defaultFile =
      detail.manifest?.find((m) => m.path === "SKILL.md") || detail.manifest?.[0];
    if (defaultFile) {
      await loadFileContent(defaultFile.path);
    }
  } catch (err: any) {
    contentError.value = err.response?.data?.message || err.message || "加载技能详情失败";
  } finally {
    drawerLoading.value = false;
  }
}

// 加载单个文件内容
async function loadFileContent(path: string, retryOnConflict = true) {
  if (!drawerSkill.value || !activeProjectId.value) return;
  selectedPath.value = path;
  selectedContent.value = "";
  contentError.value = "";
  copySuccess.value = false;

  const item = drawerSkill.value.manifest?.find((m) => m.path === path);
  if (item && !item.readable) {
    contentError.value =
      item.reason === "file_too_large"
        ? "文件体积超过 256 KiB 限制，不支持在线预览"
        : item.reason === "not_utf8_text"
        ? "非 UTF-8 文本文件（可能为二进制资产），不支持在线预览"
        : "此文件不支持在线阅读";
    return;
  }

  contentLoading.value = true;
  try {
    const resp = await getDearSkillContent(
      activeProjectId.value,
      drawerSkill.value.source,
      drawerSkill.value.slug,
      path,
      drawerSkill.value.revision,
    );
    selectedContent.value = resp.content;
  } catch (err: any) {
    const code = err.response?.data?.error?.code || err.code;
    if (code === "skill_revision_conflict" && retryOnConflict) {
      try {
        const fresh = await getDearSkillDetail(
          activeProjectId.value,
          drawerSkill.value.source,
          drawerSkill.value.slug,
        );
        drawerSkill.value = fresh;
        await loadFileContent(path, false);
        return;
      } catch {
        // ignore
      }
    }
    contentError.value = err.response?.data?.message || err.message || "读取文件内容失败";
  } finally {
    contentLoading.value = false;
  }
}

// 导入文件选择
function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  fileError.value = "";
  conflictSlug.value = null;
  if (!input.files || input.files.length === 0) {
    selectedFile.value = null;
    return;
  }
  const file = input.files[0];
  if (!file.name.endsWith(".zip")) {
    fileError.value = "仅支持上传 .zip 格式的技能压缩包";
    selectedFile.value = null;
    return;
  }
  if (file.size > 1024 * 1024) {
    fileError.value = "技能包体积不能超过 1 MiB (1,048,576 字节)";
    selectedFile.value = null;
    return;
  }
  selectedFile.value = file;
}

// 提交导入新技能
async function handleUpload() {
  if (!activeProjectId.value || !selectedFile.value || isUploading.value) return;
  isUploading.value = true;
  fileError.value = "";
  conflictSlug.value = null;
  try {
    const base64 = await fileToBase64(selectedFile.value);
    await createCustomSkill(activeProjectId.value, base64);
    isUploadModalOpen.value = false;
    selectedFile.value = null;
    showSuccess("自定义技能导入成功！");
    await fetchSkills();
    activeTab.value = "custom";
  } catch (err: any) {
    const code = err.response?.data?.error?.code || err.response?.data?.code || err.code;
    if (code === "skill_name_conflict") {
      fileError.value = "检测到同名自定义技能已存在。";
      // 从文件名尝试解析 slug 或提示用户可覆盖更新
      conflictSlug.value = selectedFile.value
        ? selectedFile.value.name.replace(/\.zip$/i, "")
        : null;
    } else if (code === "skill_package_size") {
      fileError.value = "压缩包体积超出限制 (≤1 MiB)";
    } else if (code === "unsafe_skill_package") {
      fileError.value = "技能包包含不安全文件（如软链接、跨目录路径、隐藏文件或未受控扩展名）";
    } else if (code === "skill_frontmatter_required") {
      fileError.value = "根目录下 SKILL.md 缺少有效的 YAML frontmatter 元数据";
    } else if (code === "reserved_public_skill_name") {
      fileError.value = "该技能名称与平台公共技能重名，禁止覆盖官方保留名称";
    } else if (code === "skill_security_blocked") {
      fileError.value = "检测到技能包含高风险指令或凭据，已被安全规则阻断";
    } else if (code === "skill_capacity") {
      fileError.value = "该项目自定义技能已达到 50 个容量上限，请先删除无用技能";
    } else {
      fileError.value = err.response?.data?.message || err.message || "导入失败";
    }
  } finally {
    isUploading.value = false;
  }
}

// 从导入冲突一键转为覆盖更新
async function handleSwitchToUpdate() {
  if (!selectedFile.value || !activeProjectId.value) return;
  // 查找已有技能获取 revision
  const existing = customSkills.value.find(
    (s) => s.slug === conflictSlug.value || s.name === conflictSlug.value,
  );
  if (!existing) {
    fileError.value = "未找到同名技能记录，请在列表中直接点击对应技能的“更新”按钮";
    return;
  }
  openUpdateModal(existing);
  isUploadModalOpen.value = false;
  selectedFile.value = null;
  conflictSlug.value = null;
}

// 打开显式更新弹窗
function openUpdateModal(skill: CustomSkillItem) {
  if (!canWriteSkill.value) return;
  updateTargetSkill.value = skill;
  updateSelectedFile.value = null;
  updateFileError.value = "";
  isUpdateModalOpen.value = true;
}

// 更新文件选择
function handleUpdateFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  updateFileError.value = "";
  if (!input.files || input.files.length === 0) {
    updateSelectedFile.value = null;
    return;
  }
  const file = input.files[0];
  if (!file.name.endsWith(".zip")) {
    updateFileError.value = "仅支持上传 .zip 格式的技能压缩包";
    updateSelectedFile.value = null;
    return;
  }
  if (file.size > 1024 * 1024) {
    updateFileError.value = "技能包体积不能超过 1 MiB (1,048,576 字节)";
    updateSelectedFile.value = null;
    return;
  }
  updateSelectedFile.value = file;
}

// 提交覆盖更新
async function handleUpdateSkill() {
  if (
    !activeProjectId.value ||
    !updateTargetSkill.value ||
    !updateSelectedFile.value ||
    isUpdating.value
  )
    return;
  isUpdating.value = true;
  updateFileError.value = "";
  try {
    const base64 = await fileToBase64(updateSelectedFile.value);
    const updated = await updateCustomSkill(
      activeProjectId.value,
      updateTargetSkill.value.slug,
      base64,
      updateTargetSkill.value.revision,
    );
    showSuccess(`技能 ${updateTargetSkill.value.slug} 覆盖更新成功！原启用状态已保留`);
    isUpdateModalOpen.value = false;
    updateSelectedFile.value = null;
    updateTargetSkill.value = null;

    // 更新列表
    const idx = skillsList.value.findIndex(
      (s) => s.source === "custom" && s.slug === updated.slug,
    );
    if (idx !== -1) {
      skillsList.value[idx] = updated;
    }
    // 若抽屉打开，更新抽屉
    if (drawerSkill.value?.slug === updated.slug) {
      drawerSkill.value = updated;
      const defaultFile =
        updated.manifest?.find((m) => m.path === "SKILL.md") || updated.manifest?.[0];
      if (defaultFile) {
        await loadFileContent(defaultFile.path);
      }
    }
  } catch (err: any) {
    const code = err.response?.data?.error?.code || err.code;
    if (code === "skill_name_mismatch") {
      updateFileError.value = `ZIP 内部 SKILL.md 的 name 与目标技能 (${updateTargetSkill.value?.slug || ""}) 不一致，禁止更新`;
    } else if (code === "skill_revision_conflict") {
      updateFileError.value = "该技能已被其他并发操作更新，请刷新后重新选择更新";
      await fetchSkills();
    } else {
      updateFileError.value = err.response?.data?.message || err.message || "更新失败";
    }
  } finally {
    isUpdating.value = false;
  }
}

// 打开删除确认弹窗
function openDeleteModal(skill: CustomSkillItem) {
  if (!canWriteSkill.value) return;
  deleteTargetSkill.value = skill;
  isDeleteModalOpen.value = true;
}

// 执行删除
async function handleDeleteSkill() {
  if (!activeProjectId.value || !deleteTargetSkill.value || isDeleting.value) return;
  isDeleting.value = true;
  errorMsg.value = "";
  try {
    await deleteCustomSkill(
      activeProjectId.value,
      deleteTargetSkill.value.slug,
      deleteTargetSkill.value.revision,
    );
    showSuccess(`技能 ${deleteTargetSkill.value.slug} 已彻底删除`);
    if (drawerSkill.value?.slug === deleteTargetSkill.value.slug) {
      isDrawerOpen.value = false;
      drawerSkill.value = null;
    }
    isDeleteModalOpen.value = false;
    deleteTargetSkill.value = null;
    await fetchSkills();
  } catch (err: any) {
    const code = err.response?.data?.error?.code || err.code;
    if (code === "skill_revision_conflict") {
      errorMsg.value = "⚠️ 版本状态已被其他并发操作更新，请重新核对后再操作";
      await fetchSkills();
      isDeleteModalOpen.value = false;
    } else {
      errorMsg.value = err.response?.data?.message || err.message || "删除失败";
    }
  } finally {
    isDeleting.value = false;
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const res = reader.result as string;
      const base64 = res.split(",")[1] || "";
      resolve(base64);
    };
    reader.onerror = (e) => reject(e);
    reader.readAsDataURL(file);
  });
}

function showSuccess(msg: string) {
  successMsg.value = msg;
  setTimeout(() => {
    if (successMsg.value === msg) {
      successMsg.value = "";
    }
  }, 4000);
}

// 复制摘要指纹
function copyDigest(digest: string) {
  navigator.clipboard.writeText(digest);
  showSuccess("SHA256 指纹已复制到剪贴板");
}

// 监听项目切换，清理旧项目数据
watch(activeProjectId, (newId) => {
  skillsList.value = [];
  searchQuery.value = "";
  errorMsg.value = "";
  successMsg.value = "";
  isDrawerOpen.value = false;
  drawerSkill.value = null;
  if (newId) {
    fetchSkills();
  }
});

// ESC 键关闭抽屉与弹窗
function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") {
    isUploadModalOpen.value = false;
    isUpdateModalOpen.value = false;
    isDeleteModalOpen.value = false;
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("keydown", handleKeydown);
  onScopeDispose(() => {
    window.removeEventListener("keydown", handleKeydown);
  });
}

onMounted(() => {
  if (activeProjectId.value) {
    fetchSkills();
  }
});
</script>

<template>
  <div class="h-full overflow-y-auto p-6 md:p-8">
    <div class="mx-auto max-w-6xl space-y-6">
      <!-- 页面头部 -->
      <div class="flex flex-col gap-4 border-b border-zinc-200/80 pb-5 md:flex-row md:items-center md:justify-between dark:border-zinc-800">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 text-amber-600 shadow-sm dark:bg-amber-950/50 dark:text-amber-400">
              <BaseIcon name="sparkle" size="sm" />
            </span>
            <h1 class="text-xl font-bold text-zinc-900 dark:text-zinc-100">
              Skills 技能管理
            </h1>
          </div>
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            项目 {{ activeProject?.name || activeProjectId }} 的官方内置公共技能与隔离自定义技能管理
          </p>
        </div>

        <!-- 操作按钮组（无会话依赖） -->
        <div class="flex flex-wrap items-center gap-3">
          <BaseButton
            variant="secondary"
            size="sm"
            :loading="loading"
            @click="fetchSkills"
            title="重新从服务器加载技能列表"
          >
            <template #icon>
              <BaseIcon name="refresh" size="xs" />
            </template>
            刷新
          </BaseButton>

          <BaseButton
            variant="primary"
            size="sm"
            :disabled="!canWriteSkill"
            :title="!canWriteSkill ? '无项目写权限或自定义管理未开启' : undefined"
            @click="isUploadModalOpen = true"
          >
            <template #icon>
              <BaseIcon name="download" size="xs" />
            </template>
            导入技能包 (ZIP)
          </BaseButton>
        </div>
      </div>

      <!-- 功能禁用或只读横幅 -->
      <div
        v-if="!capabilities.custom_management_enabled"
        class="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-xs font-medium text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
      >
        <BaseIcon name="shield" size="xs" class="text-amber-600 dark:text-amber-400" />
        <span>自定义技能管理服务当前已关闭（RUNTIME_DEAR_GOVERNANCE_ENABLED=1），仅支持浏览公共技能。</span>
      </div>
      <div
        v-else-if="!canWrite"
        class="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-xs font-medium text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
      >
        <BaseIcon name="shield" size="xs" class="text-amber-600 dark:text-amber-400" />
        <span>当前项目仅允许查看。个人技能的导入、启停与删除需要项目执行权限，请联系项目管理员。</span>
      </div>

      <!-- 成功提示 -->
      <div
        v-if="successMsg"
        class="flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
      >
        <BaseIcon name="check" size="xs" class="text-emerald-600 dark:text-emerald-400" />
        <span>{{ successMsg }}</span>
      </div>

      <!-- 错误警告 -->
      <div
        v-if="errorMsg"
        class="flex items-center gap-2 rounded-xl bg-rose-50 px-4 py-3 text-xs font-medium text-rose-800 dark:bg-rose-950/40 dark:text-rose-300"
      >
        <BaseIcon name="alert" size="xs" class="text-rose-600 dark:text-rose-400" />
        <span class="flex-1">{{ errorMsg }}</span>
        <button @click="errorMsg = ''" class="text-rose-500 hover:text-rose-700">✕</button>
      </div>

      <!-- 专区切换与检索 -->
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-center gap-1 rounded-xl bg-zinc-100 p-1 dark:bg-zinc-800/80">
          <button
            type="button"
            @click="activeTab = 'public'"
            :class="[
              'flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition-all',
              activeTab === 'public'
                ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100'
                : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
            ]"
          >
            <BaseIcon name="sparkle" size="xs" />
            <span>平台公共技能</span>
            <span class="rounded-full bg-zinc-200 px-1.5 py-0.2 text-[10px] dark:bg-zinc-700">
              {{ publicSkills.length }}
            </span>
          </button>

          <button
            type="button"
            @click="activeTab = 'custom'"
            :class="[
              'flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-medium transition-all',
              activeTab === 'custom'
                ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-100'
                : 'text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200'
            ]"
          >
            <BaseIcon name="folder" size="xs" />
            <span>自定义技能管理</span>
            <span class="rounded-full bg-amber-100 px-1.5 py-0.2 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/60 dark:text-amber-400">
              {{ customSkills.length }}
            </span>
          </button>
        </div>

        <div class="relative w-48 sm:w-64">
          <span class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-zinc-400">
            <BaseIcon name="search" size="xs" />
          </span>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索技能名称或描述..."
            class="w-full rounded-lg border border-zinc-200 bg-white py-1.5 pl-8 pr-3 text-xs text-zinc-900 placeholder-zinc-400 shadow-sm focus:border-primary-500 focus:outline-none dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </div>
      </div>

      <!-- 专区一：平台公共技能 -->
      <div v-if="activeTab === 'public'" class="space-y-4">
        <div class="rounded-xl border border-blue-200/80 bg-blue-50/60 p-3.5 text-xs text-blue-900 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-300">
          <div class="flex items-center gap-1.5 font-medium">
            <BaseIcon name="shield" size="xs" />
            <span>平台内置公共技能目录</span>
          </div>
          <p class="mt-1 text-[11px] leading-relaxed text-blue-800 dark:text-blue-400">
            内置技能由沙箱容器全局托管，对所有任务即时可见且保持只读；点击卡片可查看技能文件树与文档正文。
          </p>
        </div>

        <div v-if="loading" class="py-12 text-center text-xs text-zinc-500">
          正在载入公共技能目录...
        </div>

        <div v-else-if="filteredPublicSkills.length === 0" class="rounded-2xl border border-dashed border-zinc-300 p-12 text-center dark:border-zinc-700">
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            {{ searchQuery ? "未找到匹配的公共技能" : "暂无公共技能" }}
          </p>
        </div>

        <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="skill in filteredPublicSkills"
            :key="skill.slug"
            class="flex flex-col justify-between rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm transition hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
          >
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <span class="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                  内置只读
                </span>
                <span
                  v-if="skill.backend_verified"
                  class="inline-flex items-center gap-0.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
                >
                  <BaseIcon name="check" size="xs" />
                  已通过验收
                </span>
              </div>

              <div>
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  {{ skill.name }}
                </h3>
                <div class="mt-0.5 font-mono text-[10px] text-zinc-400">
                  slug: {{ skill.slug }}
                </div>
              </div>

              <p class="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400 line-clamp-3">
                {{ skill.description }}
              </p>
            </div>

            <div class="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3 text-[10px] dark:border-zinc-800">
              <span class="font-mono text-zinc-400">rev.{{ skill.revision.slice(0, 8) }}</span>
              <BaseButton
                variant="secondary"
                size="xs"
                @click="openDetailDrawer(skill)"
              >
                <template #icon>
                  <BaseIcon name="file" size="xs" />
                </template>
                查看详情
              </BaseButton>
            </div>
          </div>
        </div>
      </div>

      <!-- 专区二：自定义技能管理 -->
      <div v-else class="space-y-4">
        <div class="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3.5 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300">
          <div class="flex items-center gap-1.5 font-medium">
            <BaseIcon name="shield" size="xs" />
            <span>执行生效规则</span>
          </div>
          <p class="mt-1 text-[11px] leading-relaxed text-amber-800 dark:text-amber-400">
            技能变更用于下一次新任务；正在执行或中断后恢复的任务保留原执行快照。同一技能仅保留单份当前内容，覆盖更新将保留原启用/停用状态。
          </p>
        </div>

        <div v-if="loading" class="py-12 text-center text-xs text-zinc-500">
          正在载入自定义技能列表...
        </div>

        <!-- 空态 -->
        <div v-else-if="filteredCustomSkills.length === 0" class="rounded-2xl border border-dashed border-zinc-300 p-12 text-center dark:border-zinc-700">
          <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500">
            <BaseIcon name="folder" size="md" />
          </div>
          <h3 class="mt-4 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {{ searchQuery ? "未找到匹配的自定义技能" : "暂无自定义技能" }}
          </h3>
          <p class="mx-auto mt-1 max-w-sm text-xs text-zinc-500 dark:text-zinc-400">
            您可以将包含根目录 SKILL.md 的标准 ZIP 压缩包（≤1MiB）上传，系统将自动校验并在下次新任务中生效。
          </p>
          <div class="mt-5">
            <BaseButton
              variant="primary"
              size="sm"
              :disabled="!canWriteSkill"
              @click="isUploadModalOpen = true"
            >
              <template #icon>
                <BaseIcon name="download" size="xs" />
              </template>
              立即导入技能 ZIP
            </BaseButton>
          </div>
        </div>

        <!-- 自定义技能列表 -->
        <div v-else class="space-y-4">
          <div
            v-for="skill in filteredCustomSkills"
            :key="skill.slug"
            class="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm transition dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div class="space-y-2 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <!-- 状态徽标 -->
                  <span
                    :class="[
                      'rounded-full px-2.5 py-0.5 text-[11px] font-semibold',
                      skill.enabled
                        ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20 dark:bg-emerald-950/50 dark:text-emerald-400'
                        : 'bg-zinc-100 text-zinc-600 ring-1 ring-zinc-500/20 dark:bg-zinc-800 dark:text-zinc-400'
                    ]"
                  >
                    {{ skill.enabled ? '● 启用中 (Active)' : '○ 已停用 (Disabled)' }}
                  </span>

                  <h3 class="text-base font-bold text-zinc-900 dark:text-zinc-100">
                    {{ skill.name || skill.slug }}
                  </h3>

                  <span class="font-mono text-xs text-zinc-400">rev.{{ skill.revision.slice(0, 8) }}</span>
                </div>

                <div class="text-[11px] font-mono text-zinc-400">
                  slug: {{ skill.slug }}
                </div>

                <p class="text-xs text-zinc-600 dark:text-zinc-400">
                  {{ skill.description }}
                </p>

                <!-- 指纹与时间 -->
                <div class="flex flex-wrap items-center gap-3 text-[11px] text-zinc-500">
                  <div class="flex items-center gap-1 font-mono">
                    <span>SHA256:</span>
                    <span class="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">
                      {{ skill.digest.slice(0, 12) }}...
                    </span>
                    <button
                      type="button"
                      @click="copyDigest(skill.digest)"
                      class="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                      title="复制完整指纹"
                    >
                      <BaseIcon name="copy" size="xs" />
                    </button>
                  </div>

                  <span v-if="skill.updated_at" class="text-zinc-400">
                    更新时间: {{ new Date(skill.updated_at).toLocaleString() }}
                  </span>
                </div>
              </div>

              <!-- 操作区 -->
              <div class="flex flex-wrap items-center gap-2 self-start">
                <!-- 启停 Switch 开关 -->
                <button
                  type="button"
                  role="switch"
                  :aria-checked="skill.enabled"
                  :disabled="!canWriteSkill || togglingSlugs.has(skill.slug)"
                  @click="handleToggleSkill(skill, !skill.enabled)"
                  :class="[
                    'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed',
                    skill.enabled ? 'bg-primary-600' : 'bg-zinc-200 dark:bg-zinc-700'
                  ]"
                  :title="skill.enabled ? '点击停用' : '点击启用'"
                >
                  <span
                    :class="[
                      'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                      skill.enabled ? 'translate-x-5' : 'translate-x-0'
                    ]"
                  />
                </button>

                <!-- 更新按钮 -->
                <BaseButton
                  variant="secondary"
                  size="xs"
                  :disabled="!canWriteSkill"
                  @click="openUpdateModal(skill)"
                >
                  <template #icon>
                    <BaseIcon name="refresh" size="xs" />
                  </template>
                  更新包
                </BaseButton>

                <!-- 查看详情按钮 -->
                <BaseButton
                  variant="secondary"
                  size="xs"
                  @click="openDetailDrawer(skill)"
                >
                  <template #icon>
                    <BaseIcon name="file" size="xs" />
                  </template>
                  查看详情
                </BaseButton>

                <!-- 删除按钮 -->
                <BaseButton
                  variant="danger"
                  size="xs"
                  :disabled="!canWriteSkill"
                  @click="openDeleteModal(skill)"
                >
                  删除
                </BaseButton>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 详情抽屉 -->
    <SkillDetailDrawer
      :show="isDrawerOpen"
      :loading="drawerLoading"
      :skill="drawerSkill"
      :selected-path="selectedPath"
      :selected-content="selectedContent"
      :content-loading="contentLoading"
      :content-error="contentError"
      @close="isDrawerOpen = false"
      @select-file="loadFileContent"
    />

    <!-- 导入与覆盖更新弹窗 -->
    <SkillUploadModals
      :is-upload-modal-open="isUploadModalOpen"
      :selected-file="selectedFile"
      :file-error="fileError"
      :conflict-slug="conflictSlug"
      :is-uploading="isUploading"
      :is-update-modal-open="isUpdateModalOpen"
      :update-target-skill="updateTargetSkill"
      :update-selected-file="updateSelectedFile"
      :update-file-error="updateFileError"
      :is-updating="isUpdating"
      @close-upload="isUploadModalOpen = false"
      @file-change="handleFileChange"
      @switch-to-update="handleSwitchToUpdate"
      @upload="handleUpload"
      @close-update="isUpdateModalOpen = false"
      @update-file-change="handleUpdateFileChange"
      @update-skill="handleUpdateSkill"
    />

    <!-- 删除危险操作确认弹窗 -->
    <ConfirmDialog
      v-if="isDeleteModalOpen"
      :show="isDeleteModalOpen"
      title="⚠️ 彻底删除自定义技能确认"
      :message="`确定要删除技能「${deleteTargetSkill?.name || deleteTargetSkill?.slug}」吗？删除后将物理移除该记录且不提供历史恢复；已在执行中的任务将继续沿用其历史快照。`"
      :danger="true"
      confirm-text="确认删除"
      cancel-text="取消"
      @confirm="handleDeleteSkill"
      @cancel="isDeleteModalOpen = false"
    />
  </div>
</template>

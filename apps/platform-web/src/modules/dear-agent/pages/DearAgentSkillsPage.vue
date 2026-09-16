<script setup lang="ts">
import { ref, computed, watch, onMounted, onScopeDispose } from "vue";
import { useAuthorization } from "@/composables/useAuthorization";
import { useDearGovernanceContext } from "../composables/useDearGovernanceContext";
import {
  listCustomSkills,
  uploadCandidateSkillPackage,
  activateSkillVersion,
  revokeSkillVersion,
  OFFICIAL_PUBLIC_SKILLS,
  type SkillVersion,
} from "@/services/dear-agent/skills.service";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseButton from "@/components/base/BaseButton.vue";

const {
  activeProject,
  activeProjectId,
  threads,
  activeThreadId,
  hasThreads,
  switchThread,
} = useDearGovernanceContext();

const { can } = useAuthorization();
const canWrite = computed(() => can("project.runtime.write", activeProjectId.value));

// 专区切换
const activeTab = ref<"public" | "custom">("public");

// 自定义技能版本数据与状态
const customSkills = ref<SkillVersion[]>([]);
const loading = ref(false);
const actionLoading = ref(false);
const errorMsg = ref("");
const successMsg = ref("");
const searchQuery = ref("");
const expandedManifestDigest = ref<string | null>(null);

// 导入弹窗状态
const isUploadModalOpen = ref(false);
const selectedFile = ref<File | null>(null);
const fileError = ref("");
const isUploading = ref(false);

// 激活/撤销确认弹窗
const isConfirmModalOpen = ref(false);
const confirmAction = ref<"activate" | "revoke">("activate");
const targetSkill = ref<SkillVersion | null>(null);

// 过滤后的公共技能
const filteredPublicSkills = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return OFFICIAL_PUBLIC_SKILLS;
  return OFFICIAL_PUBLIC_SKILLS.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      s.slug.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.category.toLowerCase().includes(q)
  );
});

// 过滤后的自定义技能版本
const filteredCustomSkills = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return customSkills.value;
  return customSkills.value.filter(
    (s) =>
      s.slug.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.digest.toLowerCase().includes(q)
  );
});

// 加载自定义技能列表
async function fetchCustomSkills() {
  if (!activeProjectId.value || !activeThreadId.value) {
    customSkills.value = [];
    return;
  }
  loading.value = true;
  errorMsg.value = "";
  try {
    const list = await listCustomSkills(activeProjectId.value, activeThreadId.value);
    customSkills.value = list;
  } catch (err: any) {
    const code = err.response?.data?.code || err.code;
    if (code === "dear_governance_disabled") {
      errorMsg.value = "治理存储未开启（RUNTIME_DEAR_GOVERNANCE_ENABLED=1）";
    } else if (code === "dear_governance_scope_denied") {
      errorMsg.value = "无权访问此会话的技能数据";
    } else {
      errorMsg.value = err.message || "读取技能列表失败";
    }
  } finally {
    loading.value = false;
  }
}

// 展开/收起 Manifest 文件清单
function toggleManifest(digest: string) {
  expandedManifestDigest.value = expandedManifestDigest.value === digest ? null : digest;
}

// 选择导入文件
function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  fileError.value = "";
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

// 提交导入候选包
async function handleUploadCandidate() {
  if (!activeProjectId.value || !activeThreadId.value || !selectedFile.value || isUploading.value) return;
  isUploading.value = true;
  fileError.value = "";
  errorMsg.value = "";
  try {
    const base64 = await fileToBase64(selectedFile.value);
    await uploadCandidateSkillPackage(activeProjectId.value, activeThreadId.value, base64);
    isUploadModalOpen.value = false;
    selectedFile.value = null;
    showSuccess("候选技能包导入成功！请通过聊天指令进行审查与评估后激活");
    await fetchCustomSkills();
    activeTab.value = "custom";
  } catch (err: any) {
    const code = err.response?.data?.code || err.code;
    if (code === "skill_package_size") {
      fileError.value = "压缩包大小超出限制";
    } else if (code === "unsafe_skill_package") {
      fileError.value = "技能包包含不安全文件（如软链接、跨目录路径、隐藏文件或未受控扩展名）";
    } else if (code === "skill_frontmatter_required" || code === "invalid_skill_frontmatter") {
      fileError.value = "根目录下 SKILL.md 缺少有效的 YAML frontmatter 元数据";
    } else if (code === "reserved_public_skill_name") {
      fileError.value = "该技能名称与平台公共技能重名，禁止覆盖官方保留名称";
    } else if (code === "skill_version_capacity") {
      fileError.value = "该项目自定义技能版本已达到 50 个容量上限";
    } else {
      fileError.value = err.response?.data?.message || err.message || "导入失败";
    }
  } finally {
    isUploading.value = false;
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

// 检查是否可激活
function canActivate(skill: SkillVersion): { allowed: boolean; reason?: string } {
  if (!canWrite.value) {
    return { allowed: false, reason: "只读模式：缺少项目写权限 (project.runtime.write)" };
  }
  if (skill.status === "revoked") {
    return { allowed: false, reason: "该版本已撤销，不可重新启用" };
  }
  if (skill.status === "active") {
    return { allowed: false, reason: "当前版本已处于启用状态" };
  }
  if (skill.warnings && skill.warnings.length > 0) {
    return { allowed: false, reason: "检测到安全警告，禁止启用" };
  }
  const reviewPassed = skill.review && skill.review.passed === true;
  const evalPassed = skill.evaluation && skill.evaluation.passed === true;
  if (!reviewPassed || !evalPassed) {
    return { allowed: false, reason: "必须通过静态审查 (Review) 与动态评估 (Evaluation) 后方可启用" };
  }
  return { allowed: true };
}

// 打开激活/撤销确认框
function openConfirmModal(skill: SkillVersion, action: "activate" | "revoke") {
  if (!canWrite.value) return;
  targetSkill.value = skill;
  confirmAction.value = action;
  isConfirmModalOpen.value = true;
}

// 执行激活或撤销
async function handleConfirmAction() {
  if (!activeProjectId.value || !activeThreadId.value || !targetSkill.value || actionLoading.value) return;
  actionLoading.value = true;
  errorMsg.value = "";
  try {
    if (confirmAction.value === "activate") {
      await activateSkillVersion(
        activeProjectId.value,
        activeThreadId.value,
        targetSkill.value.slug,
        targetSkill.value.digest,
        targetSkill.value.revision
      );
      showSuccess(`技能 ${targetSkill.value.slug} 已成功启用`);
    } else {
      await revokeSkillVersion(
        activeProjectId.value,
        activeThreadId.value,
        targetSkill.value.slug,
        targetSkill.value.digest,
        targetSkill.value.revision
      );
      showSuccess(`技能 ${targetSkill.value.slug} 已永久撤销`);
    }
    isConfirmModalOpen.value = false;
    await fetchCustomSkills();
  } catch (err: any) {
    const code = err.response?.data?.code || err.code;
    if (code === "skill_revision_conflict") {
      errorMsg.value = "⚠️ 版本状态已被其他并发操作更新，已自动刷新，请重新核对";
      fetchCustomSkills();
    } else if (code === "skill_not_approved") {
      errorMsg.value = "该技能包未完全通过审查或存在风险，无法激活";
    } else {
      errorMsg.value = err.response?.data?.message || err.message || "操作失败";
    }
  } finally {
    actionLoading.value = false;
  }
}

function showSuccess(msg: string) {
  successMsg.value = msg;
  setTimeout(() => {
    if (successMsg.value === msg) {
      successMsg.value = "";
    }
  }, 4000);
}

// 复制摘要
function copyDigest(digest: string) {
  navigator.clipboard.writeText(digest);
  showSuccess("SHA256 指纹已复制到剪贴板");
}

// 监听会话变更
watch(activeThreadId, (newId) => {
  if (newId) {
    fetchCustomSkills();
  }
});

// 监听项目切换，清理旧项目缓存
watch(activeProjectId, () => {
  customSkills.value = [];
  searchQuery.value = "";
  errorMsg.value = "";
  successMsg.value = "";
  expandedManifestDigest.value = null;
});

// 键盘无障碍支持（ESC 关闭弹窗）
function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") {
    isUploadModalOpen.value = false;
    isConfirmModalOpen.value = false;
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("keydown", handleKeydown);
  onScopeDispose(() => {
    window.removeEventListener("keydown", handleKeydown);
  });
}

onMounted(() => {
  if (activeThreadId.value) {
    fetchCustomSkills();
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
              Skills 技能版本治理
            </h1>
          </div>
          <p class="text-xs text-zinc-500 dark:text-zinc-400">
            项目 {{ activeProject?.name }} 的官方认证公共技能与隔离自定义技能版本管理（严格支持审查、评估、激活与撤销）
          </p>
        </div>

        <!-- 关联会话与操作按钮 -->
        <div class="flex flex-wrap items-center gap-3">
          <div v-if="hasThreads" class="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <span class="text-[11px] font-medium text-zinc-500">治理上下文:</span>
            <select
              :value="activeThreadId"
              @change="switchThread(($event.target as HTMLSelectElement).value)"
              class="max-w-[180px] truncate bg-transparent text-xs font-medium text-zinc-900 focus:outline-none dark:text-zinc-100"
            >
              <option v-for="t in threads" :key="t.thread_id" :value="t.thread_id">
                {{ t.metadata?.title || t.thread_id.slice(0, 8) }}
              </option>
            </select>
          </div>

          <BaseButton
            variant="secondary"
            size="sm"
            :loading="loading"
            @click="fetchCustomSkills"
            title="刷新列表"
          >
            <template #icon>
              <BaseIcon name="refresh" size="xs" />
            </template>
            刷新
          </BaseButton>

          <BaseButton
            variant="primary"
            size="sm"
            :disabled="!hasThreads || !canWrite"
            :title="!canWrite ? '缺少项目写权限' : undefined"
            @click="isUploadModalOpen = true"
          >
            <template #icon>
              <BaseIcon name="download" size="xs" />
            </template>
            导入候选 ZIP
          </BaseButton>
        </div>
      </div>

      <!-- 只读权限提示横幅 -->
      <div v-if="!canWrite" class="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-xs font-medium text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
        <BaseIcon name="shield" size="xs" class="text-amber-600 dark:text-amber-400" />
        <span>当前项目处于只读模式（缺少 project.runtime.write 权限），技能导入、激活与撤销操作已锁定。</span>
      </div>

      <!-- 成功提示 -->
      <div v-if="successMsg" class="flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
        <BaseIcon name="check" size="xs" class="text-emerald-600 dark:text-emerald-400" />
        <span>{{ successMsg }}</span>
      </div>

      <!-- 错误警告 -->
      <div v-if="errorMsg" class="flex items-center gap-2 rounded-xl bg-rose-50 px-4 py-3 text-xs font-medium text-rose-800 dark:bg-rose-950/40 dark:text-rose-300">
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
              {{ OFFICIAL_PUBLIC_SKILLS.length }}
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
            <span>自定义版本治理</span>
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
            <span>官方公共技能目录</span>
          </div>
          <p class="mt-1 text-[11px] leading-relaxed text-blue-800 dark:text-blue-400">
            公共技能由沙箱容器全局托管，已通过完整的后端测试验收（`backend_verified`）并支持 Agent 自动推荐（`recommendable`），所有会话可直接按需调用。
          </p>
        </div>

        <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="skill in filteredPublicSkills"
            :key="skill.slug"
            class="flex flex-col justify-between rounded-xl border border-zinc-200/80 bg-white p-4 shadow-sm transition hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
          >
            <div class="space-y-2">
              <div class="flex items-center justify-between">
                <span class="rounded-full bg-primary-50 px-2 py-0.5 text-[10px] font-medium text-primary-600 dark:bg-primary-950/40 dark:text-primary-400">
                  {{ skill.category }}
                </span>
                <div class="flex items-center gap-1">
                  <span class="inline-flex items-center gap-0.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                    <BaseIcon name="check" size="xs" />
                    已通过验收
                  </span>
                </div>
              </div>

              <div>
                <h3 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  {{ skill.name }}
                </h3>
                <div class="mt-0.5 font-mono text-[10px] text-zinc-400">
                  slug: {{ skill.slug }}
                </div>
              </div>

              <p class="text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
                {{ skill.description }}
              </p>
            </div>

            <div class="mt-4 border-t border-zinc-100 pt-2 text-[10px] text-zinc-400 dark:border-zinc-800">
              定义路径: {{ skill.path }}
            </div>
          </div>
        </div>
      </div>

      <!-- 专区二：自定义技能版本治理 -->
      <div v-else class="space-y-4">
        <!-- 冻结说明告示卡片 -->
        <div class="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3.5 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-300">
          <div class="flex items-center gap-1.5 font-medium">
            <BaseIcon name="shield" size="xs" />
            <span>会话版本冻结规则</span>
          </div>
          <p class="mt-1 text-[11px] leading-relaxed text-amber-800 dark:text-amber-400">
            DearFlow 会话在首次装配执行时，会冻结当时生效的技能版本。激活新版本后，请<strong>新建会话</strong>验证新特性；历史会话保持原有版本运行。若某版本被撤销，绑定该版本的历史会话将无法继续恢复，需新建会话。
          </p>
        </div>

        <div v-if="loading" class="py-12 text-center text-xs text-zinc-500">
          正在载入自定义技能版本...
        </div>

        <!-- 空态 -->
        <div v-else-if="filteredCustomSkills.length === 0" class="rounded-2xl border border-dashed border-zinc-300 p-12 text-center dark:border-zinc-700">
          <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500">
            <BaseIcon name="folder" size="md" />
          </div>
          <h3 class="mt-4 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {{ searchQuery ? "未找到匹配的自定义技能" : "暂无自定义技能版本" }}
          </h3>
          <p class="mx-auto mt-1 max-w-sm text-xs text-zinc-500 dark:text-zinc-400">
            您可以将包含根目录 SKILL.md 的标准 ZIP 压缩包（≤1MiB）上传为候选版本，经过审查评估后即可激活。
          </p>
          <div class="mt-5">
            <BaseButton
              variant="primary"
              size="sm"
              :disabled="!hasThreads"
              @click="isUploadModalOpen = true"
            >
              <template #icon>
                <BaseIcon name="download" size="xs" />
              </template>
              立即导入候选 ZIP
            </BaseButton>
          </div>
        </div>

        <!-- 自定义技能列表 -->
        <div v-else class="space-y-4">
          <div
            v-for="skill in filteredCustomSkills"
            :key="skill.digest"
            class="rounded-xl border border-zinc-200/80 bg-white p-5 shadow-sm transition dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div class="space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <!-- 状态徽标 -->
                  <span
                    :class="[
                      'rounded-full px-2.5 py-0.5 text-[11px] font-semibold',
                      skill.status === 'active'
                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400 ring-1 ring-emerald-600/20'
                        : skill.status === 'candidate'
                        ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 ring-1 ring-amber-600/20'
                        : skill.status === 'revoked'
                        ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-400 ring-1 ring-rose-600/20'
                        : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400'
                    ]"
                  >
                    {{
                      skill.status === 'active'
                        ? '● 生效中 (Active)'
                        : skill.status === 'candidate'
                        ? '待定候选 (Candidate)'
                        : skill.status === 'revoked'
                        ? '已撤销 (Revoked)'
                        : '未生效旧版 (Inactive)'
                    }}
                  </span>

                  <h3 class="text-base font-bold text-zinc-900 dark:text-zinc-100">
                    {{ skill.slug }}
                  </h3>

                  <span class="text-xs text-zinc-400">rev.{{ skill.revision }}</span>
                </div>

                <p class="text-xs text-zinc-600 dark:text-zinc-400">
                  {{ skill.description }}
                </p>

                <!-- 指纹与审查信息 -->
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

                  <!-- 审查结果 -->
                  <div class="flex items-center gap-1">
                    <span>代码审查:</span>
                    <span
                      v-if="skill.review?.passed === true"
                      class="font-medium text-emerald-600 dark:text-emerald-400"
                    >
                      ✓ 通过
                    </span>
                    <span
                      v-else-if="skill.review"
                      class="font-medium text-rose-600 dark:text-rose-400"
                    >
                      ✕ 未通过
                    </span>
                    <span v-else class="text-zinc-400">未进行</span>
                  </div>

                  <!-- 评估结果 -->
                  <div class="flex items-center gap-1">
                    <span>动态评估:</span>
                    <span
                      v-if="skill.evaluation?.passed === true"
                      class="font-medium text-emerald-600 dark:text-emerald-400"
                    >
                      ✓ 通过
                    </span>
                    <span
                      v-else-if="skill.evaluation"
                      class="font-medium text-rose-600 dark:text-rose-400"
                    >
                      ✕ 未通过
                    </span>
                    <span v-else class="text-zinc-400">未进行</span>
                  </div>
                </div>

                <!-- 安全告警 -->
                <div
                  v-if="skill.warnings && skill.warnings.length > 0"
                  class="flex items-center gap-1.5 rounded-lg bg-rose-50 px-3 py-1.5 text-[11px] font-medium text-rose-800 dark:bg-rose-950/40 dark:text-rose-300"
                >
                  <BaseIcon name="alert" size="xs" />
                  <span>检测到潜在安全风险模式，禁止激活：{{ skill.warnings.join(", ") }}</span>
                </div>
              </div>

              <!-- 操作区 -->
              <div class="flex flex-wrap items-center gap-2 self-start">
                <BaseButton
                  variant="secondary"
                  size="xs"
                  @click="toggleManifest(skill.digest)"
                >
                  <template #icon>
                    <BaseIcon
                      name="chevron-down"
                      size="xs"
                      :class="{ 'rotate-180': expandedManifestDigest === skill.digest }"
                      class="transition-transform"
                    />
                  </template>
                  {{ expandedManifestDigest === skill.digest ? "收起清单" : "文件清单" }}
                </BaseButton>

                <!-- 激活按钮 -->
                <div class="relative group">
                  <BaseButton
                    v-if="skill.status !== 'active'"
                    variant="primary"
                    size="xs"
                    :disabled="!canActivate(skill).allowed"
                    @click="openConfirmModal(skill, 'activate')"
                  >
                    启用版本
                  </BaseButton>
                  <div
                    v-if="!canActivate(skill).allowed && skill.status !== 'active'"
                    class="pointer-events-none absolute bottom-full left-1/2 mb-1.5 hidden -translate-x-1/2 whitespace-nowrap rounded bg-zinc-800 px-2 py-1 text-[10px] text-white opacity-0 transition group-hover:block group-hover:opacity-100 z-10"
                  >
                    {{ canActivate(skill).reason }}
                  </div>
                </div>

                <!-- 撤销按钮 -->
                <BaseButton
                  v-if="skill.status !== 'revoked'"
                  variant="danger"
                  size="xs"
                  :disabled="!canWrite"
                  :title="!canWrite ? '缺少项目写权限' : undefined"
                  @click="openConfirmModal(skill, 'revoke')"
                >
                  撤销
                </BaseButton>
              </div>
            </div>

            <!-- 文件清单展开面板 -->
            <div
              v-if="expandedManifestDigest === skill.digest"
              class="mt-4 rounded-lg border border-zinc-100 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-800/40"
            >
              <div class="text-[11px] font-semibold text-zinc-700 dark:text-zinc-300">
                Package Manifest 文件列表 ({{ skill.manifest?.length || 0 }} 个文件)
              </div>
              <div class="mt-2 space-y-1 font-mono text-[11px]">
                <div
                  v-for="item in skill.manifest"
                  :key="item.path"
                  class="flex items-center justify-between text-zinc-600 dark:text-zinc-400"
                >
                  <span class="font-medium text-zinc-900 dark:text-zinc-200">{{ item.path }}</span>
                  <span class="text-[10px] text-zinc-400">{{ item.sha256.slice(0, 16) }}...</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 导入候选 ZIP 弹窗 -->
    <div
      v-if="isUploadModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
    >
      <div class="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900">
        <div class="flex items-center justify-between border-b border-zinc-200 pb-3 dark:border-zinc-800">
          <h3 class="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            导入自定义技能候选包 (ZIP)
          </h3>
          <button @click="isUploadModalOpen = false" class="text-zinc-400 hover:text-zinc-600">✕</button>
        </div>

        <div class="mt-4 space-y-3">
          <div class="rounded-xl bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400 space-y-1">
            <div class="font-medium text-zinc-900 dark:text-zinc-200">包格式规范：</div>
            <div>• 必须包含根目录下的 <code>SKILL.md</code>，带 YAML frontmatter 元数据 (name & description)</div>
            <div>• 单个 ZIP 压缩包体积 ≤ 1 MiB，展开文件总数 ≤ 100</div>
            <div>• 严禁隐藏文件、跨目录路径与软链接</div>
            <div>• 导入仅作为 <strong>candidate 候选</strong>，须经会话评审测试后方可激活</div>
          </div>

          <div class="mt-3">
            <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">选择 .zip 文件</label>
            <input
              type="file"
              accept=".zip"
              @change="handleFileChange"
              class="mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
          </div>

          <div v-if="fileError" class="text-xs text-rose-600">
            {{ fileError }}
          </div>
        </div>

        <div class="mt-6 flex justify-end gap-2">
          <BaseButton variant="secondary" size="sm" @click="isUploadModalOpen = false">
            取消
          </BaseButton>
          <BaseButton
            variant="primary"
            size="sm"
            :disabled="!selectedFile"
            :loading="isUploading"
            @click="handleUploadCandidate"
          >
            确认上传
          </BaseButton>
        </div>
      </div>
    </div>

    <!-- 激活 / 撤销确认弹窗 -->
    <div
      v-if="isConfirmModalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-xs"
    >
      <div class="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl dark:bg-zinc-900">
        <div class="flex items-center gap-3" :class="confirmAction === 'activate' ? 'text-primary-600' : 'text-rose-600'">
          <BaseIcon :name="confirmAction === 'activate' ? 'sparkle' : 'alert'" size="md" />
          <h3 class="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            {{ confirmAction === 'activate' ? "启用技能版本确认" : "⚠️ 撤销技能版本严重警告" }}
          </h3>
        </div>

        <p class="mt-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
          <template v-if="confirmAction === 'activate'">
            确定要启用技能 <strong>{{ targetSkill?.slug }}</strong> (版本指纹: {{ targetSkill?.digest.slice(0, 12) }}...) 吗？
            启用后，该技能下的其他历史版本将自动切换为未生效状态。
          </template>
          <template v-else>
            确定要撤销技能 <strong>{{ targetSkill?.slug }}</strong> 吗？
            <span class="block mt-1 text-rose-600 font-medium">
              撤销为不可逆操作，该版本将被永久禁用且不可重新激活。任何已绑定该版本的历史会话将无法继续恢复运行！
            </span>
          </template>
        </p>

        <div class="mt-6 flex justify-end gap-2">
          <BaseButton variant="secondary" size="sm" @click="isConfirmModalOpen = false">
            取消
          </BaseButton>
          <BaseButton
            :variant="confirmAction === 'activate' ? 'primary' : 'danger'"
            size="sm"
            :loading="actionLoading"
            @click="handleConfirmAction"
          >
            {{ confirmAction === 'activate' ? "确认启用" : "确认永久撤销" }}
          </BaseButton>
        </div>
      </div>
    </div>
  </div>
</template>

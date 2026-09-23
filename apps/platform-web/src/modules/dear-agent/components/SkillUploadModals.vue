<script setup lang="ts">
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import type { CustomSkillItem } from "@/services/dear-agent/skills.service";

defineProps<{
  isUploadModalOpen: boolean;
  selectedFile: File | null;
  fileError: string | null;
  conflictSlug: string | null;
  isUploading: boolean;
  isUpdateModalOpen: boolean;
  updateTargetSkill: CustomSkillItem | null;
  updateSelectedFile: File | null;
  updateFileError: string | null;
  isUpdating: boolean;
}>();

const emit = defineEmits<{
  (e: "close-upload"): void;
  (e: "file-change", event: Event): void;
  (e: "switch-to-update"): void;
  (e: "upload"): void;
  (e: "close-update"): void;
  (e: "update-file-change", event: Event): void;
  (e: "update-skill"): void;
}>();
</script>

<template>
  <!-- 导入新技能弹窗 -->
  <BaseDialog
    :show="isUploadModalOpen"
    title="导入自定义技能 (ZIP)"
    width="normal"
    @close="emit('close-upload')"
  >
    <div class="space-y-3">
      <div class="rounded-xl bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400 space-y-1">
        <div class="font-medium text-zinc-900 dark:text-zinc-200">技能包规范：</div>
        <div>• 根目录必须包含 <code>SKILL.md</code> 并附带合法 YAML frontmatter (name & description)</div>
        <div>• 仅支持 <code>.zip</code> 格式，大小 ≤ 1 MiB，展开文件数 ≤ 100</div>
        <div>• 上传成功后将默认启用，并在下一次新任务执行中生效</div>
      </div>

      <div>
        <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">选择 .zip 文件</label>
        <input
          type="file"
          accept=".zip"
          @change="emit('file-change', $event)"
          class="mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
      </div>

      <div v-if="fileError" class="text-xs text-rose-600 dark:text-rose-400">
        {{ fileError }}
      </div>

      <!-- 同名冲突直接转更新提示 -->
      <div
        v-if="conflictSlug"
        class="flex items-center justify-between rounded-lg bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
      >
        <span>同名技能已存在，是否直接覆盖更新？</span>
        <BaseButton variant="secondary" size="xs" @click="emit('switch-to-update')">
          转为覆盖更新
        </BaseButton>
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <BaseButton variant="secondary" size="sm" @click="emit('close-upload')">
          取消
        </BaseButton>
        <BaseButton
          variant="primary"
          size="sm"
          :disabled="!selectedFile"
          :loading="isUploading"
          @click="emit('upload')"
        >
          确认导入
        </BaseButton>
      </div>
    </template>
  </BaseDialog>

  <!-- 显式覆盖更新弹窗 -->
  <BaseDialog
    :show="isUpdateModalOpen"
    :title="`更新技能包: ${updateTargetSkill?.name || updateTargetSkill?.slug}`"
    width="normal"
    @close="emit('close-update')"
  >
    <div class="space-y-3">
      <div class="rounded-xl bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-800/50 dark:text-zinc-400 space-y-1">
        <div class="font-medium text-zinc-900 dark:text-zinc-200">覆盖更新说明：</div>
        <div>• 包内 <code>SKILL.md</code> 中的 name 必须与当前技能 slug (<code>{{ updateTargetSkill?.slug }}</code>) 完全一致</div>
        <div>• 覆盖后保留原技能的启用/停用状态；新内容将在下一次新任务中生效</div>
      </div>

      <div>
        <label class="block text-xs font-medium text-zinc-700 dark:text-zinc-300">选择新 .zip 文件</label>
        <input
          type="file"
          accept=".zip"
          @change="emit('update-file-change', $event)"
          class="mt-1.5 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-xs text-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
        />
      </div>

      <div v-if="updateFileError" class="text-xs text-rose-600 dark:text-rose-400">
        {{ updateFileError }}
      </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <BaseButton variant="secondary" size="sm" @click="emit('close-update')">
          取消
        </BaseButton>
        <BaseButton
          variant="primary"
          size="sm"
          :disabled="!updateSelectedFile"
          :loading="isUpdating"
          @click="emit('update-skill')"
        >
          确认更新
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

<script setup lang="ts">
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDialog from "@/components/base/BaseDialog.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import type { ManagementServiceAccount } from "@/types/management";

defineProps<{
  createDialogOpen: boolean;
  createForm: { name: string; description: string; platform_roles: string[] };
  editDialogOpen: boolean;
  editForm: { description: string; platform_roles: string[] };
  tokenDialogOpen: boolean;
  tokenForm: { name: string; expires_in_days: string };
  tokenSecret: string;
  selectedAccount: ManagementServiceAccount | null;
  roleOptions: Array<{ value: string; label: string }>;
  submitting: boolean;
  savingAccount: boolean;
  canManageServiceAccounts: boolean;
  canManageSelectedAccount: boolean;
}>();

const emit = defineEmits<{
  (e: "close-create"): void;
  (e: "submit-create"): void;
  (e: "close-edit"): void;
  (e: "submit-edit"): void;
  (e: "close-token"): void;
  (e: "submit-token"): void;
  (e: "copy-token"): void;
}>();
</script>

<template>
  <BaseDialog
    :show="createDialogOpen"
    title="新建 Service Account"
    width="normal"
    @close="emit('close-create')"
  >
    <div class="space-y-4">
      <label class="block space-y-2">
        <span class="text-sm font-medium text-gray-700 dark:text-dark-100">名称</span>
        <BaseInput
          v-model="createForm.name"
          placeholder="例如 metrics-reader"
        />
      </label>
      <label class="block space-y-2">
        <span class="text-sm font-medium text-gray-700 dark:text-dark-100">描述</span>
        <BaseInput
          v-model="createForm.description"
          placeholder="说明这个账号给谁用、干什么"
        />
      </label>
      <label class="block space-y-2">
        <span class="text-sm font-medium text-gray-700 dark:text-dark-100">默认角色</span>
        <BaseSelect
          :model-value="createForm.platform_roles[0] || 'platform_viewer'"
          :options="roleOptions"
          @update:model-value="(value) => (createForm.platform_roles = [value])"
        />
      </label>
    </div>

    <template #footer>
      <div class="flex gap-3">
        <BaseButton
          variant="secondary"
          @click="emit('close-create')"
        >
          取消
        </BaseButton>
        <BaseButton
          :disabled="submitting || !createForm.name.trim() || !canManageServiceAccounts"
          @click="emit('submit-create')"
        >
          {{ submitting ? '创建中...' : '确认创建' }}
        </BaseButton>
      </div>
    </template>
  </BaseDialog>

  <BaseDialog
    :show="editDialogOpen"
    title="编辑 Service Account"
    width="normal"
    @close="emit('close-edit')"
  >
    <div class="space-y-4">
      <div
        v-if="selectedAccount"
        class="rounded-2xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-dark-800/80 dark:text-dark-200"
      >
        当前账号：{{ selectedAccount.name }}
      </div>
      <label class="block space-y-2">
        <span class="text-sm font-medium text-gray-700 dark:text-dark-100">描述</span>
        <BaseInput
          v-model="editForm.description"
          placeholder="描述账号用途、归属与责任人"
        />
      </label>
      <label class="block space-y-2">
        <span class="text-sm font-medium text-gray-700 dark:text-dark-100">平台角色</span>
        <BaseSelect
          :model-value="editForm.platform_roles[0] || 'platform_viewer'"
          :options="roleOptions"
          @update:model-value="(value) => (editForm.platform_roles = [value])"
        />
      </label>
    </div>

    <template #footer>
      <div class="flex gap-3">
        <BaseButton
          variant="secondary"
          @click="emit('close-edit')"
        >
          取消
        </BaseButton>
        <BaseButton
          :disabled="savingAccount || !canManageSelectedAccount"
          @click="emit('submit-edit')"
        >
          {{ savingAccount ? '保存中...' : '确认保存' }}
        </BaseButton>
      </div>
    </template>
  </BaseDialog>

  <BaseDialog
    :show="tokenDialogOpen"
    title="创建 Token"
    width="normal"
    @close="emit('close-token')"
  >
    <div class="space-y-4">
      <div
        v-if="selectedAccount"
        class="rounded-2xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-dark-800/80 dark:text-dark-200"
      >
        当前账号：{{ selectedAccount.name }}
      </div>
      <label class="block space-y-2">
        <span class="text-sm font-medium text-gray-700 dark:text-dark-100">Token 名称</span>
        <BaseInput
          v-model="tokenForm.name"
          placeholder="例如 default"
        />
      </label>
      <label class="block space-y-2">
        <span class="text-sm font-medium text-gray-700 dark:text-dark-100">过期天数</span>
        <BaseInput
          v-model="tokenForm.expires_in_days"
          type="number"
          placeholder="90"
        />
      </label>

      <div
        v-if="tokenSecret"
        class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 dark:border-emerald-900/40 dark:bg-emerald-950/20"
      >
        <div class="text-sm font-semibold text-emerald-700 dark:text-emerald-200">
          明文 Token 只展示这一次
        </div>
        <div class="mt-2 break-all text-sm text-emerald-700 dark:text-emerald-200">
          {{ tokenSecret }}
        </div>
        <div class="mt-3">
          <BaseButton
            variant="secondary"
            @click="emit('copy-token')"
          >
            复制 Token
          </BaseButton>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex gap-3">
        <BaseButton
          variant="secondary"
          @click="emit('close-token')"
        >
          关闭
        </BaseButton>
        <BaseButton
          :disabled="submitting || !tokenForm.name.trim() || !canManageSelectedAccount"
          @click="emit('submit-token')"
        >
          {{ submitting ? '创建中...' : '确认创建' }}
        </BaseButton>
      </div>
    </template>
  </BaseDialog>
</template>

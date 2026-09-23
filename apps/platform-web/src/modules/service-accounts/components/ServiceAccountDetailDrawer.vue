<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseDrawer from "@/components/base/BaseDrawer.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import { formatPlatformRoleLabel } from "@/services/auth/permissions";
import type {
  ManagementServiceAccount,
  ManagementServiceAccountToken,
} from "@/types/management";
import { formatDateTime } from "@/utils/format";

const props = defineProps<{
  show: boolean;
  account: ManagementServiceAccount | null;
  canManage: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "edit", account: ManagementServiceAccount): void;
  (e: "create-token", account: ManagementServiceAccount): void;
  (e: "revoke-token", account: ManagementServiceAccount, token: ManagementServiceAccountToken): void;
}>();

const tokenSearch = ref("");

watch(
  () => props.account?.id,
  () => {
    tokenSearch.value = "";
  }
);

const filteredSelectedTokens = computed<ManagementServiceAccountToken[]>(() => {
  const account = props.account;
  if (!account) {
    return [];
  }

  const keyword = tokenSearch.value.trim().toLowerCase();
  if (!keyword) {
    return account.tokens;
  }

  return account.tokens.filter((token) =>
    [token.name, token.token_prefix, token.status].join(" ").toLowerCase().includes(keyword)
  );
});
</script>

<template>
  <BaseDrawer
    :show="show"
    title="Service Account 详情"
    width="wide"
    @close="emit('close')"
  >
    <div
      v-if="account"
      class="space-y-5"
    >
      <div class="pw-card p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <div class="text-base font-semibold text-gray-900 dark:text-white">
                {{ account.name }}
              </div>
              <span
                class="rounded-full px-2.5 py-1 text-xs font-semibold"
                :class="account.status === 'active'
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-200'
                  : 'bg-gray-100 text-gray-600 dark:bg-dark-800 dark:text-dark-200'"
              >
                {{ account.status }}
              </span>
            </div>
            <div class="mt-3 text-sm text-gray-500 dark:text-dark-300">
              {{ account.description || '暂无描述' }}
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <BaseButton
              variant="secondary"
              :disabled="!canManage"
              @click="emit('edit', account)"
            >
              编辑
            </BaseButton>
            <BaseButton
              variant="secondary"
              :disabled="!canManage"
              @click="emit('create-token', account)"
            >
              发 Token
            </BaseButton>
          </div>
        </div>
        <div class="mt-4 grid gap-2 text-sm text-gray-600 dark:text-dark-200">
          <div>ID: {{ account.id }}</div>
          <div>Created by: {{ account.created_by || '--' }}</div>
          <div>Updated by: {{ account.updated_by || '--' }}</div>
          <div>Created at: {{ formatDateTime(account.created_at) }}</div>
          <div>Updated at: {{ formatDateTime(account.updated_at) }}</div>
          <div>Last used at: {{ formatDateTime(account.last_used_at) }}</div>
        </div>
      </div>

      <div>
        <div class="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
          Roles
        </div>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="role in account.platform_roles"
            :key="role"
            class="rounded-full bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 dark:bg-primary-950/30 dark:text-primary-200"
          >
            {{ formatPlatformRoleLabel(role) }}
          </span>
        </div>
      </div>

      <div class="space-y-3">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div class="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400 dark:text-dark-400">
              Tokens
            </div>
            <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
              {{ filteredSelectedTokens.length }} / {{ account.tokens.length }} 可见
            </div>
          </div>
          <div class="w-full sm:w-[260px]">
            <BaseInput
              v-model="tokenSearch"
              placeholder="搜索 token 名称或前缀"
            />
          </div>
        </div>

        <EmptyState
          v-if="!account.tokens.length"
          title="该账号暂无 token"
          description="还没有签发任何 token。"
          icon="lock"
          :action-label="canManage ? '发 Token' : ''"
          @action="emit('create-token', account)"
        />

        <EmptyState
          v-else-if="!filteredSelectedTokens.length"
          title="没有匹配的 token"
          description="换个名称或前缀关键字再试。"
          icon="search"
        />

        <template v-else>
          <article
            v-for="token in filteredSelectedTokens"
            :key="token.id"
            class="pw-card-subtle px-4 py-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="text-sm font-semibold text-gray-900 dark:text-white">
                  {{ token.name }}
                </div>
                <div class="mt-1 text-xs text-gray-500 dark:text-dark-300">
                  {{ token.token_prefix }} · {{ token.status }}
                </div>
                <div class="mt-3 grid gap-1 text-xs text-gray-500 dark:text-dark-300">
                  <span>created {{ formatDateTime(token.created_at) }}</span>
                  <span>expires {{ formatDateTime(token.expires_at) }}</span>
                  <span>last used {{ formatDateTime(token.last_used_at) }}</span>
                  <span>revoked {{ formatDateTime(token.revoked_at) }}</span>
                </div>
              </div>
              <BaseButton
                variant="secondary"
                :disabled="token.status !== 'active' || !canManage"
                @click="emit('revoke-token', account, token)"
              >
                撤销
              </BaseButton>
            </div>
          </article>
        </template>
      </div>
    </div>
  </BaseDrawer>
</template>

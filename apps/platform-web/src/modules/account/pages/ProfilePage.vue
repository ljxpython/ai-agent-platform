<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseInput from "@/components/base/BaseInput.vue";
import SurfaceCard from "@/components/base/SurfaceCard.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import { updateCurrentProfile } from "@/services/identity/identity.service";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const authStore = useAuthStore();
const workspaceStore = useWorkspaceStore();
const router = useRouter();

const loading = ref(false);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const username = ref("");
const email = ref("");

const presetAvatars = [
  { name: "极客少年 (默认)", url: "/avatars/user-avatar-1.png" },
  { name: "码农萌妹", url: "/avatars/user-avatar-2.png" },
  { name: "平台小精灵", url: "/avatars/user-avatar-3.gif" },
];

const selectedAvatar = ref(
  authStore.customAvatar || "/avatars/default-user.png",
);

function selectPreset(url: string) {
  selectedAvatar.value = url;
  authStore.setCustomAvatar(url);
  notice.value = "头像已即时生效！";
}

function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;

  if (file.size > 2 * 1024 * 1024) {
    error.value = "头像图片大小不能超过 2MB";
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const base64 = e.target?.result as string;
    if (base64) {
      selectedAvatar.value = base64;
      authStore.setCustomAvatar(base64);
      notice.value = "自定义头像上传成功并已生效！";
    }
  };
  reader.readAsDataURL(file);
}

function resetToDefaultAvatar() {
  selectedAvatar.value = "/avatars/default-user.png";
  authStore.setCustomAvatar("");
  notice.value = "已恢复为默认头像！";
}

async function loadProfile() {
  loading.value = true;
  error.value = "";

  try {
    const profile = await authStore.fetchCurrentUser();
    username.value = profile?.username || "";
    email.value = profile?.email || "";
  } catch (loadError) {
    error.value =
      loadError instanceof Error ? loadError.message : "个人资料加载失败";
  } finally {
    loading.value = false;
  }
}

async function saveProfile() {
  const nextUsername = username.value.trim();
  if (!nextUsername) {
    error.value = "用户名不能为空";
    return;
  }

  saving.value = true;
  error.value = "";
  notice.value = "";

  try {
    await updateCurrentProfile({
      username: nextUsername,
      email: email.value.trim(),
    });
    await authStore.fetchCurrentUser();
    notice.value = "个人资料已更新";
  } catch (saveError) {
    error.value =
      saveError instanceof Error ? saveError.message : "个人资料更新失败";
  } finally {
    saving.value = false;
  }
}

function signOut() {
  authStore.logout();
  workspaceStore.reset();
  void router.replace("/auth/login");
}

onMounted(() => {
  void loadProfile();
});

function handleSubmit(event: Event) {
  event.preventDefault();
  void saveProfile();
}
</script>

<template>
  <section class="pw-page-shell">
    <PageHeader
      eyebrow="Account"
      title="我的资料"
      description="查看并维护当前登录账号的基础个人信息。密码与敏感安全操作请前往安全设置。"
    >
      <template #actions>
        <BaseButton
          variant="secondary"
          @click="() => router.push('/workspace/security')"
        >
          <BaseIcon name="lock" size="sm" />
          安全设置
        </BaseButton>
      </template>
    </PageHeader>

    <StateBanner
      v-if="error"
      title="资料页出现问题"
      :description="error"
      variant="danger"
    />

    <StateBanner
      v-if="notice"
      title="操作成功"
      :description="notice"
      variant="success"
    />

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <SurfaceCard>
        <form class="space-y-5" @submit="handleSubmit">
          <div class="pw-card-glass flex items-center gap-4 p-4">
            <div
              class="relative flex h-16 w-16 items-center justify-center rounded-2xl overflow-hidden ring-2 ring-primary-400/50 shadow-glow bg-gray-100 dark:bg-dark-800 shrink-0"
            >
              <img
                :src="selectedAvatar || authStore.userAvatar"
                alt="头像"
                class="w-full h-full object-cover"
              />
            </div>
            <div>
              <div
                class="text-base font-semibold text-gray-900 dark:text-white"
              >
                {{ authStore.user?.username || "未加载" }}
              </div>
              <div class="mt-1 text-sm text-gray-500 dark:text-dark-300">
                {{ authStore.roleLabel }}
              </div>
            </div>
          </div>

          <!-- 个性化头像设置 -->
          <div
            class="space-y-3 p-4 rounded-xl border border-gray-200 dark:border-dark-800 bg-gray-50/50 dark:bg-dark-900/50"
          >
            <div class="flex items-center justify-between">
              <span class="pw-input-label">个性化头像设置</span>
              <button
                v-if="authStore.customAvatar"
                type="button"
                class="text-xs text-rose-500 hover:underline cursor-pointer"
                @click="resetToDefaultAvatar"
              >
                恢复默认
              </button>
            </div>

            <!-- 推荐预设头像列表 -->
            <div class="space-y-1.5">
              <span class="text-[11px] text-gray-500 dark:text-dark-400"
                >精美预设头像</span
              >
              <div class="flex items-center gap-3">
                <button
                  v-for="(av, idx) in presetAvatars"
                  :key="idx"
                  type="button"
                  class="w-14 h-14 shrink-0 rounded-2xl overflow-hidden border-2 transition-all p-0.5 cursor-pointer relative bg-white dark:bg-dark-800"
                  :class="
                    selectedAvatar === av.url
                      ? 'border-sky-500 scale-105 shadow-md'
                      : 'border-gray-200 dark:border-dark-700 hover:border-sky-300 opacity-80 hover:opacity-100'
                  "
                  :title="av.name"
                  @click="selectPreset(av.url)"
                >
                  <img
                    :src="av.url"
                    :alt="av.name"
                    class="w-full h-full object-cover rounded-xl"
                  />
                  <span
                    v-if="selectedAvatar === av.url"
                    class="absolute bottom-1 right-1 w-3.5 h-3.5 rounded-full bg-sky-500 flex items-center justify-center text-white text-[9px] font-bold shadow-xs"
                    >✓</span
                  >
                </button>

                <!-- 上传自定义头像按钮 -->
                <label
                  class="w-14 h-14 shrink-0 rounded-2xl border-2 border-dashed border-gray-300 dark:border-dark-700 hover:border-sky-400 flex flex-col items-center justify-center text-gray-400 hover:text-sky-500 cursor-pointer transition p-1 bg-white/50 dark:bg-dark-800/50"
                  title="上传本地图片作为头像 (最大 2MB)"
                >
                  <BaseIcon name="plus" size="sm" />
                  <span class="text-[9px] font-medium mt-0.5">上传</span>
                  <input
                    type="file"
                    accept="image/*"
                    class="hidden"
                    @change="handleFileUpload"
                  />
                </label>
              </div>
            </div>
          </div>

          <div class="grid gap-5">
            <label class="grid gap-2">
              <span class="pw-input-label">用户名</span>
              <BaseInput v-model="username" placeholder="请输入用户名" />
            </label>

            <label class="grid gap-2">
              <span class="pw-input-label">邮箱</span>
              <BaseInput v-model="email" placeholder="可选" />
            </label>
          </div>

          <div class="flex flex-wrap gap-3">
            <BaseButton type="submit" :disabled="loading || saving">
              {{ saving ? "保存中..." : "保存资料" }}
            </BaseButton>
            <BaseButton variant="ghost" @click="loadProfile">
              <BaseIcon name="refresh" size="sm" />
              重新加载
            </BaseButton>
          </div>
        </form>
      </SurfaceCard>

      <SurfaceCard class="space-y-4">
        <div class="pw-page-eyebrow">Session</div>
        <div class="text-sm leading-7 text-gray-500 dark:text-dark-300">
          当前登录账号：{{ authStore.user?.username || "未加载" }}
        </div>
        <div class="text-sm leading-7 text-gray-500 dark:text-dark-300">
          角色：{{ authStore.roleLabel }}
        </div>
        <BaseButton variant="secondary" @click="signOut">
          <BaseIcon name="logout" size="sm" />
          退出登录
        </BaseButton>
      </SurfaceCard>
    </div>
  </section>
</template>

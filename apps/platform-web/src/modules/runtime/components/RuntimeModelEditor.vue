<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import type { RuntimeModelItem } from "@/types/management";

export interface ModelRowDraft {
  id: string;
  name: string;
}

export interface ModelEditorSubmitPayload {
  isEdit: boolean;
  editingId?: string;
  provider: string;
  display_name: string;
  base_url: string;
  protocol: string;
  api_key: string;
  enabled: boolean;
  models: ModelRowDraft[];
}

const props = withDefaults(
  defineProps<{
    editingModel?: RuntimeModelItem | null;
    initialStation?: {
      provider: string;
      baseUrl: string;
      protocol: string;
    } | null;
    busy?: boolean;
  }>(),
  {
    editingModel: null,
    initialStation: null,
    busy: false,
  },
);

const emit = defineEmits<{
  close: [];
  submit: [payload: ModelEditorSubmitPayload];
}>();

interface ProviderPreset {
  id: string;
  name: string;
  defaultBaseUrl: string;
  defaultProtocol: string;
  placeholderKey: string;
  recommendedModels: ModelRowDraft[];
}

const PROVIDER_PRESETS: ProviderPreset[] = [
  {
    id: "deepseek",
    name: "DeepSeek",
    defaultBaseUrl: "https://api.deepseek.com/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "sk-... (DeepSeek 开放平台 API Key)",
    recommendedModels: [
      { id: "deepseek-chat", name: "DeepSeek V3" },
      { id: "deepseek-reasoner", name: "DeepSeek R1" },
    ],
  },
  {
    id: "openai",
    name: "OpenAI",
    defaultBaseUrl: "https://api.openai.com/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "sk-... (OpenAI API Key)",
    recommendedModels: [
      { id: "gpt-4o", name: "GPT-4o" },
      { id: "gpt-4o-mini", name: "GPT-4o Mini" },
      { id: "o3-mini", name: "o3-mini" },
    ],
  },
  {
    id: "ollama",
    name: "Ollama (本地/局域网)",
    defaultBaseUrl: "http://localhost:11434/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "ollama (本地无需或填任意值)",
    recommendedModels: [
      { id: "deepseek-r1:8b", name: "DeepSeek R1 8B" },
      { id: "llama3.3", name: "Llama 3.3" },
    ],
  },
  {
    id: "qwen",
    name: "通义千问 (DashScope)",
    defaultBaseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "sk-... (阿里云百炼 API Key)",
    recommendedModels: [
      { id: "qwen-max", name: "Qwen Max" },
      { id: "qwen-plus", name: "Qwen Plus" },
      { id: "qwen-turbo", name: "Qwen Turbo" },
    ],
  },
  {
    id: "glm",
    name: "智谱清言 (GLM)",
    defaultBaseUrl: "https://open.bigmodel.cn/api/paas/v4",
    defaultProtocol: "openai-compatible",
    placeholderKey: "智谱 BigModel API Key",
    recommendedModels: [
      { id: "glm-4-plus", name: "GLM-4 Plus" },
      { id: "glm-4-flash", name: "GLM-4 Flash" },
    ],
  },
  {
    id: "anthropic",
    name: "Anthropic Claude",
    defaultBaseUrl: "https://api.anthropic.com/v1",
    defaultProtocol: "anthropic",
    placeholderKey: "sk-ant-... (Anthropic API Key)",
    recommendedModels: [
      { id: "claude-3-7-sonnet-20250219", name: "Claude 3.7 Sonnet" },
      { id: "claude-3-5-haiku-20241022", name: "Claude 3.5 Haiku" },
    ],
  },
  {
    id: "custom",
    name: "自定义提供商 (Custom)",
    defaultBaseUrl: "",
    defaultProtocol: "openai-compatible",
    placeholderKey: "API Key",
    recommendedModels: [{ id: "", name: "" }],
  },
];

const providerOptions = PROVIDER_PRESETS.map((p) => ({
  value: p.id,
  label: p.name,
}));

const PROTOCOL_OPTIONS = [
  { value: "deepseek", label: "deepseek" },
  { value: "openai", label: "openai" },
  { value: "openai-compatible", label: "openai-compatible (主流兼容网关)" },
  { value: "anthropic", label: "anthropic (Claude 原生网关)" },
];

const selectedPreset = ref("deepseek");
const customProviderName = ref("");
const baseUrl = ref("https://api.deepseek.com/v1");
const protocol = ref("openai-compatible");
const apiKey = ref("");
const enabled = ref(true);
const showApiKey = ref(false);
const showAdvanced = ref(false);
const formError = ref("");

// 编辑模式下的单模型字段
const editSingleModelId = ref("");
const editSingleDisplayName = ref("");

// 新增模式下的多模型列表
const modelList = ref<ModelRowDraft[]>([
  { id: "deepseek-chat", name: "DeepSeek V3" },
  { id: "deepseek-reasoner", name: "DeepSeek R1" },
]);

const isEditMode = computed(() => Boolean(props.editingModel?.id));

const activeProviderKey = computed(() => {
  if (selectedPreset.value === "custom") {
    return customProviderName.value.trim() || "custom";
  }
  return selectedPreset.value;
});

const activePlaceholderKey = computed(() => {
  const preset = PROVIDER_PRESETS.find((p) => p.id === selectedPreset.value);
  return preset?.placeholderKey || "请输入 API Key";
});

function handlePresetChange(presetId: string) {
  selectedPreset.value = presetId;
  const found = PROVIDER_PRESETS.find((p) => p.id === presetId);
  if (!found) return;

  if (presetId !== "custom") {
    baseUrl.value = found.defaultBaseUrl;
    protocol.value = found.defaultProtocol;
    if (!isEditMode.value) {
      modelList.value = found.recommendedModels.map((m) => ({ ...m }));
    }
  } else {
    if (!baseUrl.value) {
      baseUrl.value = "https://";
    }
  }
}

function addModelRow() {
  modelList.value.push({ id: "", name: "" });
}

function removeModelRow(index: number) {
  if (modelList.value.length <= 1) return;
  modelList.value.splice(index, 1);
}

function initForm() {
  formError.value = "";
  showApiKey.value = false;
  showAdvanced.value = false;

  if (props.editingModel) {
    const m = props.editingModel;
    editSingleModelId.value = m.model;
    editSingleDisplayName.value = m.display_name || "";
    baseUrl.value = m.base_url || "";
    protocol.value = m.protocol;
    apiKey.value = "";
    enabled.value = m.enabled !== false;

    const matchedPreset = PROVIDER_PRESETS.find(
      (p) => p.id === m.provider?.toLowerCase(),
    );
    if (matchedPreset) {
      selectedPreset.value = matchedPreset.id;
      customProviderName.value = "";
    } else {
      selectedPreset.value = "custom";
      customProviderName.value = m.provider || "";
    }
  } else if (props.initialStation) {
    const s = props.initialStation;
    const matchedPreset = PROVIDER_PRESETS.find(
      (p) => p.id === s.provider?.toLowerCase(),
    );
    if (matchedPreset) {
      selectedPreset.value = matchedPreset.id;
      customProviderName.value = "";
    } else {
      selectedPreset.value = "custom";
      customProviderName.value = s.provider || "";
    }
    baseUrl.value = s.baseUrl || "";
    protocol.value =
      s.protocol === "anthropic" ? "anthropic" : "openai-compatible";
    apiKey.value = "";
    enabled.value = true;
    editSingleModelId.value = "";
    editSingleDisplayName.value = "";
    modelList.value = [{ id: "", name: "" }];
  } else {
    selectedPreset.value = "deepseek";
    customProviderName.value = "";
    baseUrl.value = "https://api.deepseek.com/v1";
    protocol.value = "openai-compatible";
    apiKey.value = "";
    enabled.value = true;
    editSingleModelId.value = "";
    editSingleDisplayName.value = "";
    modelList.value = [
      { id: "deepseek-chat", name: "DeepSeek V3" },
      { id: "deepseek-reasoner", name: "DeepSeek R1" },
    ];
  }
}

watch(
  [() => props.editingModel, () => props.initialStation],
  () => {
    initForm();
  },
  { immediate: true },
);

function handleSubmit() {
  if (props.busy) return;
  formError.value = "";
  const provider = activeProviderKey.value.trim();
  const trimmedBaseUrl = baseUrl.value.trim();

  if (!provider) {
    formError.value = "请提供有效的 Provider 标识";
    return;
  }
  if (!trimmedBaseUrl) {
    formError.value = "Base URL 不能为空";
    return;
  }

  if (isEditMode.value) {
    const singleId = editSingleModelId.value.trim();
    if (!singleId) {
      formError.value = "Model ID 不能为空";
      return;
    }

    emit("submit", {
      isEdit: true,
      editingId: props.editingModel?.id,
      provider,
      display_name: editSingleDisplayName.value.trim() || singleId,
      base_url: trimmedBaseUrl,
      protocol: protocol.value,
      api_key: apiKey.value.trim(),
      enabled: enabled.value,
      models: [{ id: singleId, name: editSingleDisplayName.value.trim() }],
    });
    return;
  }

  // 新增多模型模式
  const validModels = modelList.value
    .map((m) => ({ id: m.id.trim(), name: m.name.trim() }))
    .filter((m) => m.id.length > 0);

  if (validModels.length === 0) {
    formError.value = "请至少添加一个有效的模型（填写 Model ID）";
    return;
  }

  // 检查 API Key
  const trimmedKey = apiKey.value.trim();
  if (!trimmedKey && selectedPreset.value !== "ollama") {
    formError.value = "请输入该提供商的 API Key";
    return;
  }

  emit("submit", {
    isEdit: false,
    provider,
    display_name: validModels[0]?.name || validModels[0]?.id || provider,
    base_url: trimmedBaseUrl,
    protocol: protocol.value,
    api_key: trimmedKey,
    enabled: enabled.value,
    models: validModels,
  });
}
</script>

<template>
  <section
    class="pw-panel border border-gray-200 bg-white shadow-sm dark:border-dark-700 dark:bg-dark-900"
  >
    <!-- Header -->
    <div
      class="flex items-center justify-between border-b border-gray-100 px-6 py-4 dark:border-dark-800"
    >
      <div class="flex items-center gap-2.5">
        <div
          class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-400"
        >
          <BaseIcon
            name="sparkle"
            size="sm"
          />
        </div>
        <div>
          <h2 class="text-base font-semibold text-gray-900 dark:text-white">
            {{ isEditMode ? "编辑模型配置" : "添加提供商与模型" }}
          </h2>
          <p class="text-xs text-gray-500 dark:text-dark-400">
            {{
              isEditMode
                ? "修改已配置模型的接入地址、凭据或显示名称"
                : "配置提供商凭据，批量导入推荐模型或自定义模型清单"
            }}
          </p>
        </div>
      </div>
      <BaseButton
        variant="ghost"
        size="sm"
        :disabled="busy"
        @click="emit('close')"
      >
        <BaseIcon
          name="x"
          size="sm"
        />
        取消
      </BaseButton>
    </div>

    <!-- Body -->
    <div class="space-y-6 px-6 py-5">
      <!-- 错误提示 Banner -->
      <div
        v-if="formError"
        class="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300"
      >
        <BaseIcon
          name="alert"
          size="sm"
          class="shrink-0"
        />
        <span>{{ formError }}</span>
      </div>

      <!-- 第一行：提供方选择 (使用 BaseSelect 美化下拉框) 与 API Key -->
      <div class="grid gap-5 md:grid-cols-2">
        <div>
          <label
            class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
          >
            提供商 (Provider)
          </label>
          <BaseSelect
            :model-value="selectedPreset"
            :options="providerOptions"
            :disabled="busy || isEditMode"
            @update:model-value="handlePresetChange"
          />
          <div
            v-if="selectedPreset === 'custom'"
            class="mt-2"
          >
            <input
              v-model="customProviderName"
              class="pw-input text-xs"
              placeholder="自定义 Provider 标识，如 groq, siliconflow, vllm"
              :disabled="busy || isEditMode"
            >
          </div>
        </div>

        <div>
          <label
            class="mb-1.5 flex items-center justify-between text-xs font-semibold text-gray-700 dark:text-dark-200"
          >
            <span>API Key {{ isEditMode ? "(留空表示沿用现有凭据)" : "" }}</span>
            <button
              type="button"
              class="flex items-center gap-1 text-[11px] font-normal text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200"
              @click="showApiKey = !showApiKey"
            >
              <BaseIcon
                :name="showApiKey ? 'eye-off' : 'eye'"
                size="xs"
              />
              {{ showApiKey ? "隐藏" : "显示" }}
            </button>
          </label>
          <div class="relative">
            <input
              v-model="apiKey"
              :type="showApiKey ? 'text' : 'password'"
              class="pw-input pr-10 text-xs"
              :placeholder="activePlaceholderKey"
              autocomplete="new-password"
              :disabled="busy"
            >
            <button
              type="button"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
              tabindex="-1"
              @click="showApiKey = !showApiKey"
            >
              <BaseIcon
                :name="showApiKey ? 'eye-off' : 'eye'"
                size="sm"
              />
            </button>
          </div>
        </div>
      </div>

      <!-- 第二部分：编辑模式单模型 vs 新增模式多模型清单 (对标 deepseek-harness ModelListEditor) -->
      <div
        v-if="isEditMode"
        class="rounded-xl border border-gray-100 bg-gray-50/60 p-4 dark:border-dark-800 dark:bg-dark-950/30"
      >
        <h3 class="mb-3 text-xs font-semibold text-gray-800 dark:text-dark-200">
          模型标识与名称
        </h3>
        <div class="grid gap-4 md:grid-cols-2">
          <label class="block">
            <span class="pw-input-label">Model ID (必填)</span>
            <input
              v-model="editSingleModelId"
              class="pw-input text-xs"
              placeholder="例如 deepseek-chat, gpt-4o"
              :disabled="busy"
            >
          </label>
          <label class="block">
            <span class="pw-input-label">Display Name (显示别名)</span>
            <input
              v-model="editSingleDisplayName"
              class="pw-input text-xs"
              placeholder="例如 DeepSeek V3"
              :disabled="busy"
            >
          </label>
        </div>
      </div>

      <div
        v-else
        class="rounded-xl border border-gray-100 bg-gray-50/50 p-4 dark:border-dark-800 dark:bg-dark-950/30"
      >
        <div class="mb-3 flex items-center justify-between">
          <div>
            <h3 class="text-xs font-semibold text-gray-800 dark:text-dark-200">
              包含模型清单 (Model List)
            </h3>
            <p class="text-[11px] text-gray-500 dark:text-dark-400">
              同一个 Provider 下可批量录入多个模型，保存时将一并同步入库。
            </p>
          </div>
          <button
            type="button"
            class="flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 shadow-sm transition hover:border-gray-300 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200 dark:hover:bg-dark-700"
            :disabled="busy"
            @click="addModelRow"
          >
            <BaseIcon
              name="plus"
              size="xs"
            />
            <span>添加模型</span>
          </button>
        </div>

        <div class="space-y-2.5">
          <div
            v-for="(row, idx) in modelList"
            :key="idx"
            class="flex items-center gap-3 rounded-xl border border-gray-200/80 bg-white p-2.5 shadow-sm transition-all focus-within:border-primary-400 dark:border-dark-700 dark:bg-dark-900"
          >
            <div class="flex-1">
              <input
                v-model="row.id"
                class="pw-input h-9 text-xs"
                placeholder="Model ID，如 deepseek-chat"
                :disabled="busy"
              >
            </div>
            <div class="flex-1">
              <input
                v-model="row.name"
                class="pw-input h-9 text-xs"
                placeholder="Display Name，如 DeepSeek V3 (选填)"
                :disabled="busy"
              >
            </div>
            <button
              type="button"
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40 dark:hover:bg-rose-950/40 dark:hover:text-rose-400"
              :disabled="modelList.length <= 1 || busy"
              title="删除此模型"
              @click="removeModelRow(idx)"
            >
              <BaseIcon
                name="trash"
                size="sm"
              />
            </button>
          </div>
        </div>
      </div>

      <!-- 第三部分：高级设置 (折叠面板，收纳 Base URL, 协议 Protocol 美化下拉框) -->
      <div
        class="overflow-hidden rounded-xl border border-gray-200/70 bg-white dark:border-dark-800 dark:bg-dark-900"
      >
        <button
          type="button"
          class="flex w-full items-center justify-between px-4 py-3 text-left text-xs font-medium text-gray-700 transition hover:bg-gray-50 dark:text-dark-200 dark:hover:bg-dark-800"
          @click="showAdvanced = !showAdvanced"
        >
          <div class="flex items-center gap-2">
            <BaseIcon
              name="settings-2"
              size="sm"
              class="text-gray-400"
            />
            <span>高级设置 (Base URL、Protocol 协议与启用状态)</span>
          </div>
          <BaseIcon
            name="chevron-down"
            size="sm"
            class="text-gray-400 transition-transform duration-200"
            :class="showAdvanced ? 'rotate-180' : ''"
          />
        </button>

        <div
          v-show="showAdvanced"
          class="space-y-4 border-t border-gray-100 p-4 dark:border-dark-800"
        >
          <div class="grid gap-4 md:grid-cols-2">
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Base URL (API 接入端点)
              </label>
              <input
                v-model="baseUrl"
                class="pw-input text-xs"
                placeholder="https://api.example.com/v1"
                inputmode="url"
                :disabled="busy"
              >
            </div>

            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Protocol 协议
              </label>
              <BaseSelect
                v-model="protocol"
                :options="PROTOCOL_OPTIONS"
                :disabled="busy"
              />
            </div>
          </div>

          <div class="flex items-center gap-2 pt-1">
            <label
              class="flex cursor-pointer select-none items-center gap-2 text-xs text-gray-700 dark:text-dark-200"
            >
              <input
                v-model="enabled"
                type="checkbox"
                class="pw-table-checkbox rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                :disabled="busy"
              >
              <span>配置完成后默认启用该模型</span>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div
      class="flex items-center justify-end gap-3 border-t border-gray-100 bg-gray-50/50 px-6 py-3.5 dark:border-dark-800 dark:bg-dark-950/40"
    >
      <BaseButton
        variant="ghost"
        :disabled="busy"
        @click="emit('close')"
      >
        取消
      </BaseButton>
      <BaseButton
        :disabled="busy"
        @click="handleSubmit"
      >
        <BaseIcon
          v-if="busy"
          name="refresh"
          size="sm"
          class="animate-spin"
        />
        <span>{{
          busy ? "保存中..." : isEditMode ? "保存修改" : "批量添加并启用"
        }}</span>
      </BaseButton>
    </div>
  </section>
</template>

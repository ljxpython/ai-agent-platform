<script setup lang="ts">
import { computed, ref, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import BaseSelect from "@/components/base/BaseSelect.vue";
import type {
  RuntimeModelItem,
  RuntimeModelPricingInput,
  RuntimeModelPricingSnapshot,
} from "@/types/management";

export type ModelEditorMode = "standard" | "custom" | "edit";

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
  context_window_tokens?: number | null;
  pricing?: RuntimeModelPricingInput | null;
  pricingDirty?: boolean;
}

const CONTEXT_WINDOW_PRESETS = [
  { label: "32K", value: 32768 },
  { label: "64K", value: 65536 },
  { label: "128K", value: 131072 },
  { label: "200K", value: 200000 },
  { label: "1M", value: 1048576 },
];

const props = withDefaults(
  defineProps<{
    editingModel?: RuntimeModelItem | null;
    initialStation?: {
      provider: string;
      baseUrl: string;
      protocol: string;
      models?: RuntimeModelItem[];
    } | null;
    initialMode?: ModelEditorMode;
    busy?: boolean;
    scopeType?: "platform" | "project";
  }>(),
  {
    editingModel: null,
    initialStation: null,
    initialMode: "standard",
    busy: false,
    scopeType: "platform",
  },
);

const emit = defineEmits<{
  close: [];
  submit: [payload: ModelEditorSubmitPayload];
}>();

export interface ProviderPreset {
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
    id: "anthropic",
    name: "Anthropic (Claude)",
    defaultBaseUrl: "https://api.anthropic.com",
    defaultProtocol: "anthropic",
    placeholderKey: "sk-ant-... (Anthropic API Key)",
    recommendedModels: [
      { id: "claude-3-7-sonnet-20250219", name: "Claude 3.7 Sonnet" },
      { id: "claude-3-5-haiku-20241022", name: "Claude 3.5 Haiku" },
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
    id: "moonshot",
    name: "月之暗面 (Moonshot / Kimi)",
    defaultBaseUrl: "https://api.moonshot.cn/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "sk-... (Moonshot API Key)",
    recommendedModels: [
      { id: "moonshot-v1-8k", name: "Kimi 8K" },
      { id: "moonshot-v1-32k", name: "Kimi 32K" },
      { id: "moonshot-v1-128k", name: "Kimi 128K" },
    ],
  },
  {
    id: "siliconflow",
    name: "硅基流动 (SiliconFlow)",
    defaultBaseUrl: "https://api.siliconflow.cn/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "sk-... (SiliconFlow API Key)",
    recommendedModels: [
      { id: "deepseek-ai/DeepSeek-V3", name: "DeepSeek V3" },
      { id: "deepseek-ai/DeepSeek-R1", name: "DeepSeek R1" },
    ],
  },
  {
    id: "yi",
    name: "零一万物 (01.AI)",
    defaultBaseUrl: "https://api.lingyiwanwu.com/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "sk-... (零一万物 API Key)",
    recommendedModels: [
      { id: "yi-lightning", name: "Yi Lightning" },
      { id: "yi-large", name: "Yi Large" },
    ],
  },
  {
    id: "ollama",
    name: "Ollama (本地/局域网)",
    defaultBaseUrl: "http://localhost:11434/v1",
    defaultProtocol: "openai-compatible",
    placeholderKey: "ollama (本地免鉴权或填任意值)",
    recommendedModels: [
      { id: "deepseek-r1:8b", name: "DeepSeek R1 8B" },
      { id: "llama3.3", name: "Llama 3.3" },
    ],
  },
];

const providerOptions = PROVIDER_PRESETS.map((p) => ({
  value: p.id,
  label: p.name,
}));

const PROTOCOL_OPTIONS = [
  {
    value: "openai-compatible",
    label: "openai-compatible (主流兼容网关，如 vLLM / Ollama)",
  },
  { value: "anthropic", label: "anthropic (Anthropic Claude 原生网关)" },
  { value: "deepseek", label: "deepseek (DeepSeek 原生网关)" },
  { value: "openai", label: "openai (OpenAI 原生网关)" },
];

// 对标 deepseek-harness 的 Provider ID 正则校验：小写字母开头，小写字母、数字和中划线
const ROUTE_ID_PATTERN = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;

// 编辑器内部的当前模式
const activeMode = ref<ModelEditorMode>("standard");

// 通用字段
const apiKey = ref("");
const showApiKey = ref(false);
const enabled = ref(true);
const formError = ref("");

// 标准模式字段
const selectedPreset = ref("deepseek");
const standardBaseUrl = ref("https://api.deepseek.com/v1");
const standardProtocol = ref("openai-compatible");
const showAdvancedSettings = ref(false);
const standardModelList = ref<ModelRowDraft[]>([
  { id: "deepseek-chat", name: "DeepSeek V3" },
  { id: "deepseek-reasoner", name: "DeepSeek R1" },
]);

// 自定义模式字段
const customRoute = ref("");
const customDisplayName = ref("");
const customBaseUrl = ref("");
const customProtocol = ref("openai-compatible");
const customModelList = ref<ModelRowDraft[]>([{ id: "", name: "" }]);

// 编辑模式下的字段
const editModelId = ref("");
const editDisplayName = ref("");
const editBaseUrl = ref("");
const editProvider = ref("");
const editContextWindowTokensInput = ref("");
const editProtocol = ref("openai-compatible");

// 定价配置状态 (仅编辑模式生效)
interface PricingDraft {
  input: string;
  output: string;
  cache_read: string;
  cache_write: string;
  cache_write_5m: string;
  cache_write_1h: string;
}

const pricingDraft = ref<PricingDraft>({
  input: "",
  output: "",
  cache_read: "",
  cache_write: "",
  cache_write_5m: "",
  cache_write_1h: "",
});

const isPricingDirty = ref(false);
const isPricingCleared = ref(false);
const pricingSnapshot = ref<RuntimeModelPricingSnapshot | null>(null);
const DECIMAL_RATE_REGEX = /^\d{1,10}(\.\d{1,10})?$/;

function onPricingFieldInput() {
  isPricingDirty.value = true;
  isPricingCleared.value = false;
}

function onPricingFieldBlur(key: keyof PricingDraft) {
  let val = pricingDraft.value[key].trim();
  if (val.startsWith(".")) {
    val = "0" + val;
    pricingDraft.value[key] = val;
  } else if (val.endsWith(".") && !val.includes("..")) {
    val = val + "0";
    pricingDraft.value[key] = val;
  }
}

function handleClearPricing() {
  pricingDraft.value = {
    input: "",
    output: "",
    cache_read: "",
    cache_write: "",
    cache_write_5m: "",
    cache_write_1h: "",
  };
  isPricingDirty.value = true;
  isPricingCleared.value = true;
}

function handleRestorePricing() {
  if (!pricingSnapshot.value) return;
  const p = pricingSnapshot.value;
  pricingDraft.value = {
    input: p.input ?? "",
    output: p.output ?? "",
    cache_read: p.cache_read ?? "",
    cache_write: p.cache_write ?? "",
    cache_write_5m: p.cache_write_5m ?? "",
    cache_write_1h: p.cache_write_1h ?? "",
  };
  isPricingDirty.value = false;
  isPricingCleared.value = false;
}

const isEditMode = computed(() => activeMode.value === "edit");

const customRouteError = computed(() => {
  const val = customRoute.value.trim();
  if (!val) return "";
  if (!ROUTE_ID_PATTERN.test(val)) {
    return "Provider 标识必须以小写英文字母开头，仅可包含小写英文字母、数字和中划线（如 my-vllm）";
  }
  return "";
});

const activePlaceholderKey = computed(() => {
  if (activeMode.value === "standard") {
    const preset = PROVIDER_PRESETS.find((p) => p.id === selectedPreset.value);
    return preset?.placeholderKey || "请输入 API Key";
  }
  return "选填。若私有网关免鉴权可直接留空";
});

function handlePresetChange(presetId: string) {
  selectedPreset.value = presetId;
  const found = PROVIDER_PRESETS.find((p) => p.id === presetId);
  if (!found) return;

  standardBaseUrl.value = found.defaultBaseUrl;
  standardProtocol.value = found.defaultProtocol;
  standardModelList.value = found.recommendedModels.map((m) => ({ ...m }));
}

function addStandardModelRow() {
  standardModelList.value.push({ id: "", name: "" });
}

function removeStandardModelRow(index: number) {
  if (standardModelList.value.length <= 1) return;
  standardModelList.value.splice(index, 1);
}

function addCustomModelRow() {
  customModelList.value.push({ id: "", name: "" });
}

function removeCustomModelRow(index: number) {
  if (customModelList.value.length <= 1) return;
  customModelList.value.splice(index, 1);
}

function initForm() {
  formError.value = "";
  showApiKey.value = false;
  showAdvancedSettings.value = false;

  if (props.editingModel) {
    activeMode.value = "edit";
    const m = props.editingModel;
    editProvider.value = m.provider || "";
    editModelId.value = m.model;
    editDisplayName.value = m.display_name || "";
    editBaseUrl.value = m.base_url || "";
    editProtocol.value = m.protocol;
    apiKey.value = "";
    enabled.value = m.enabled !== false;
    editContextWindowTokensInput.value =
      typeof m.context_window_tokens === "number" && m.context_window_tokens > 0
        ? String(m.context_window_tokens)
        : "";

    // 初始化定价数据
    pricingSnapshot.value = m.pricing || null;
    const p = m.pricing;
    pricingDraft.value = {
      input: p?.input ?? "",
      output: p?.output ?? "",
      cache_read: p?.cache_read ?? "",
      cache_write: p?.cache_write ?? "",
      cache_write_5m: p?.cache_write_5m ?? "",
      cache_write_1h: p?.cache_write_1h ?? "",
    };
    isPricingDirty.value = false;
    isPricingCleared.value = false;
  } else {
    pricingSnapshot.value = null;
    pricingDraft.value = {
      input: "",
      output: "",
      cache_read: "",
      cache_write: "",
      cache_write_5m: "",
      cache_write_1h: "",
    };
    isPricingDirty.value = false;
    isPricingCleared.value = false;

    if (props.initialStation) {
      const s = props.initialStation;
      apiKey.value = "";
      enabled.value = true;
      editContextWindowTokensInput.value = "";

      // 判断是标准厂商还是自定义提供方
      const matchedPreset = PROVIDER_PRESETS.find(
        (p) => p.id === s.provider?.toLowerCase(),
      );
      if (matchedPreset && props.initialMode !== "custom") {
        activeMode.value = "standard";
        selectedPreset.value = matchedPreset.id;
        standardBaseUrl.value = s.baseUrl || matchedPreset.defaultBaseUrl;
        standardProtocol.value = s.protocol || matchedPreset.defaultProtocol;
        standardModelList.value = [{ id: "", name: "" }];
      } else {
        activeMode.value = "custom";
        customRoute.value = s.provider || "";
        customDisplayName.value = s.provider || "";
        customBaseUrl.value = s.baseUrl || "";
        customProtocol.value = s.protocol || "openai-compatible";
        customModelList.value = [{ id: "", name: "" }];
      }
    } else {
      activeMode.value = props.initialMode || "standard";
      apiKey.value = "";
      enabled.value = true;
      editContextWindowTokensInput.value = "";

      // 默认标准预设
      selectedPreset.value = "deepseek";
      standardBaseUrl.value = "https://api.deepseek.com/v1";
      standardProtocol.value = "openai-compatible";
      standardModelList.value = [
        { id: "deepseek-chat", name: "DeepSeek V3" },
        { id: "deepseek-reasoner", name: "DeepSeek R1" },
      ];

      // 默认自定义项
      customRoute.value = "";
      customDisplayName.value = "";
      customBaseUrl.value = "";
      customProtocol.value = "openai-compatible";
      customModelList.value = [{ id: "", name: "" }];
    }
  }
}

watch(
  [
    () => props.editingModel,
    () => props.initialStation,
    () => props.initialMode,
  ],
  () => {
    initForm();
  },
  { immediate: true },
);

function handleSubmit() {
  if (props.busy) return;
  formError.value = "";

  // 1. 编辑模式
  if (activeMode.value === "edit") {
    const trimmedId = editModelId.value.trim();
    const trimmedUrl = editBaseUrl.value.trim();
    if (!trimmedId) {
      formError.value = "Model ID 不能为空";
      return;
    }
    if (!trimmedUrl) {
      formError.value = "Base URL 不能为空";
      return;
    }

    if (props.initialStation?.models) {
      const isDuplicate = props.initialStation.models.some(
        (item: RuntimeModelItem) =>
          item.id !== props.editingModel?.id &&
          item.model.toLowerCase() === trimmedId.toLowerCase(),
      );
      if (isDuplicate) {
        formError.value = `Model ID "${trimmedId}" 在当前中转站已存在，请勿重复设置`;
        return;
      }
    }

    let parsedContextWindowTokens: number | null | undefined = undefined;
    const rawTokens = editContextWindowTokensInput.value.trim();
    if (rawTokens) {
      const parsed = Number(rawTokens);
      if (!Number.isInteger(parsed) || parsed <= 0) {
        formError.value = "上下文窗口容量必须为大于 0 的整数";
        return;
      }
      parsedContextWindowTokens = parsed;
    } else {
      parsedContextWindowTokens = null;
    }
    // 组装定价 payload (严格遵从 dirty 机制)
    let pricingPayload: RuntimeModelPricingInput | null | undefined = undefined;
    if (isPricingDirty.value) {
      if (isPricingCleared.value) {
        pricingPayload = null;
      } else {
        const rates: (keyof PricingDraft)[] = [
          "input",
          "output",
          "cache_read",
          "cache_write",
          "cache_write_5m",
          "cache_write_1h",
        ];
        for (const key of rates) {
          let val = pricingDraft.value[key].trim();
          if (val.startsWith(".")) {
            val = "0" + val;
            pricingDraft.value[key] = val;
          }
          if (val && !DECIMAL_RATE_REGEX.test(val)) {
            formError.value = `费率 ${key} 格式不合法：必须为不超过 10 位整数与 10 位小数的非负十进制数字`;
            return;
          }
        }
        const hasAnyRate = rates.some(
          (k) => pricingDraft.value[k].trim() !== "",
        );
        if (!hasAnyRate) {
          pricingPayload = null;
        } else {
          pricingPayload = {
            currency: "USD",
            basis: "per_million_tokens",
            input: pricingDraft.value.input.trim() || null,
            output: pricingDraft.value.output.trim() || null,
            cache_read: pricingDraft.value.cache_read.trim() || null,
            cache_write: pricingDraft.value.cache_write.trim() || null,
            cache_write_5m: pricingDraft.value.cache_write_5m.trim() || null,
            cache_write_1h: pricingDraft.value.cache_write_1h.trim() || null,
          };
        }
      }
    }

    emit("submit", {
      isEdit: true,
      editingId: props.editingModel?.id,
      provider: editProvider.value.trim(),
      display_name: editDisplayName.value.trim() || trimmedId,
      base_url: trimmedUrl,
      protocol: editProtocol.value,
      api_key: apiKey.value.trim(),
      enabled: enabled.value,
      models: [{ id: trimmedId, name: editDisplayName.value.trim() }],
      context_window_tokens: parsedContextWindowTokens,
      pricing: pricingPayload,
      pricingDirty: isPricingDirty.value,
    });
    return;
  }

  // 2. 标准提供方模式
  if (activeMode.value === "standard") {
    const provider = selectedPreset.value;
    const trimmedBaseUrl = standardBaseUrl.value.trim();
    const trimmedKey = apiKey.value.trim();

    if (!trimmedBaseUrl) {
      formError.value = "Base URL 不能为空";
      return;
    }

    if (!trimmedKey && provider !== "ollama") {
      formError.value = "请输入该提供商的 API Key";
      return;
    }

    const validModels = standardModelList.value
      .map((m) => ({ id: m.id.trim(), name: m.name.trim() }))
      .filter((m) => m.id.length > 0);

    if (validModels.length === 0) {
      formError.value = "请至少保留或添加一个有效的模型（填写 Model ID）";
      return;
    }

    const seenIds = new Set<string>();
    for (const m of validModels) {
      const lower = m.id.toLowerCase();
      if (seenIds.has(lower)) {
        formError.value = `模型列表中存在重复的 Model ID: "${m.id}"`;
        return;
      }
      seenIds.add(lower);
    }

    emit("submit", {
      isEdit: false,
      provider,
      display_name: validModels[0]?.name || validModels[0]?.id || provider,
      base_url: trimmedBaseUrl,
      protocol: standardProtocol.value,
      api_key: trimmedKey,
      enabled: enabled.value,
      models: validModels,
    });
    return;
  }

  // 3. 自定义提供方模式
  if (activeMode.value === "custom") {
    const route = customRoute.value.trim();
    const trimmedBaseUrl = customBaseUrl.value.trim();
    const dispName = customDisplayName.value.trim() || route;

    if (!route) {
      formError.value = "Provider 标识不能为空";
      return;
    }
    if (!ROUTE_ID_PATTERN.test(route)) {
      formError.value =
        "Provider 标识必须以小写字母开头，仅支持小写字母、数字和中划线（如 my-vllm）";
      return;
    }
    if (!trimmedBaseUrl) {
      formError.value = "Base URL (API 接入端点) 不能为空";
      return;
    }

    const validModels = customModelList.value
      .map((m) => ({ id: m.id.trim(), name: m.name.trim() }))
      .filter((m) => m.id.length > 0);

    if (validModels.length === 0) {
      formError.value = "自定义提供商必须至少添加一个模型（填写 Model ID）";
      return;
    }

    const seenIds = new Set<string>();
    for (const m of validModels) {
      const lower = m.id.toLowerCase();
      if (seenIds.has(lower)) {
        formError.value = `填写的模型列表中存在重复的 Model ID: "${m.id}"`;
        return;
      }
      seenIds.add(lower);
    }

    emit("submit", {
      isEdit: false,
      provider: route,
      display_name: dispName,
      base_url: trimmedBaseUrl,
      protocol: customProtocol.value,
      api_key: apiKey.value.trim(),
      enabled: enabled.value,
      models: validModels,
    });
  }
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
      <div class="flex items-center gap-3">
        <div
          class="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-400"
        >
          <BaseIcon name="sparkle" size="sm" />
        </div>
        <div>
          <h2 class="text-base font-semibold text-gray-900 dark:text-white">
            {{
              isEditMode
                ? "编辑模型配置"
                : activeMode === "standard"
                  ? scopeType === "project"
                    ? "添加标准提供方 (项目私有 BYOK)"
                    : "添加标准提供方 (全局平台模型)"
                  : scopeType === "project"
                    ? "添加自定义提供方 (项目私有 BYOK)"
                    : "添加自定义提供方 (全局平台模型)"
            }}
          </h2>
          <p class="text-xs text-gray-500 dark:text-dark-400">
            {{
              isEditMode
                ? "修改已配置模型的接入地址、凭据或显示名称"
                : activeMode === "standard"
                  ? "选择预置的公有云主流厂商，已自动配置官方端点与推荐模型，只需填写 API Key。"
                  : "面向私有网关、自建 vLLM、Ollama 或任意第三方 OpenAI 兼容端点，自定义路由标识与接入参数。"
            }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- 新增模式下的提供方类型切换 Segmented Control (对标 deepseek-harness) -->
        <div
          v-if="!isEditMode"
          class="flex items-center rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-xs dark:border-dark-700 dark:bg-dark-800"
        >
          <button
            type="button"
            class="rounded-md px-3 py-1 font-medium transition"
            :class="
              activeMode === 'standard'
                ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-900 dark:text-white'
                : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-dark-200'
            "
            :disabled="busy"
            @click="activeMode = 'standard'"
          >
            标准提供方
          </button>
          <button
            type="button"
            class="rounded-md px-3 py-1 font-medium transition"
            :class="
              activeMode === 'custom'
                ? 'bg-white text-gray-900 shadow-sm dark:bg-dark-900 dark:text-white'
                : 'text-gray-500 hover:text-gray-900 dark:text-dark-400 dark:hover:text-dark-200'
            "
            :disabled="busy"
            @click="activeMode = 'custom'"
          >
            自定义提供方
          </button>
        </div>

        <BaseButton
          variant="ghost"
          size="sm"
          :disabled="busy"
          @click="emit('close')"
        >
          <BaseIcon name="x" size="sm" />
          取消
        </BaseButton>
      </div>
    </div>

    <!-- Body -->
    <div class="space-y-6 px-6 py-5">
      <!-- 错误提示 Banner -->
      <div
        v-if="formError"
        class="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300"
      >
        <BaseIcon name="alert" size="sm" class="shrink-0" />
        <span>{{ formError }}</span>
      </div>

      <!-- ====================== 分支 1：标准提供方模式 (Standard) ====================== -->
      <template v-if="activeMode === 'standard'">
        <div class="grid gap-5 md:grid-cols-2">
          <!-- 提供商选择 -->
          <div>
            <label
              class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
            >
              公有云提供商 (Provider)
            </label>
            <BaseSelect
              :model-value="selectedPreset"
              :options="providerOptions"
              :disabled="busy"
              @update:model-value="handlePresetChange"
            />
          </div>

          <!-- API Key -->
          <div>
            <label
              class="mb-1.5 flex items-center justify-between text-xs font-semibold text-gray-700 dark:text-dark-200"
            >
              <span>API Key <span class="text-rose-500">*</span></span>
              <button
                type="button"
                class="flex items-center gap-1 text-[11px] font-normal text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200"
                @click="showApiKey = !showApiKey"
              >
                <BaseIcon :name="showApiKey ? 'eye-off' : 'eye'" size="xs" />
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
              />
              <button
                type="button"
                class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
                tabindex="-1"
                @click="showApiKey = !showApiKey"
              >
                <BaseIcon :name="showApiKey ? 'eye-off' : 'eye'" size="sm" />
              </button>
            </div>
          </div>
        </div>

        <!-- 推荐模型列表 -->
        <div
          class="rounded-xl border border-gray-100 bg-gray-50/50 p-4 dark:border-dark-800 dark:bg-dark-950/30"
        >
          <div class="mb-3 flex items-center justify-between">
            <div>
              <h3
                class="text-xs font-semibold text-gray-800 dark:text-dark-200"
              >
                包含模型清单 (Model List)
              </h3>
              <p class="text-[11px] text-gray-500 dark:text-dark-400">
                已为您预设该提供商推荐模型。您可自由调整显示别名或按需增删模型。
              </p>
            </div>
            <button
              type="button"
              class="flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 shadow-sm transition hover:border-gray-300 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200 dark:hover:bg-dark-700"
              :disabled="busy"
              @click="addStandardModelRow"
            >
              <BaseIcon name="plus" size="xs" />
              <span>添加模型</span>
            </button>
          </div>

          <div class="space-y-2.5">
            <div
              v-for="(row, idx) in standardModelList"
              :key="idx"
              class="flex items-center gap-3 rounded-xl border border-gray-200/80 bg-white p-2.5 shadow-sm transition-all focus-within:border-primary-400 dark:border-dark-700 dark:bg-dark-900"
            >
              <div class="flex-1">
                <input
                  v-model="row.id"
                  class="pw-input h-9 text-xs"
                  placeholder="Model ID，例如 deepseek-chat"
                  :disabled="busy"
                />
              </div>
              <div class="flex-1">
                <input
                  v-model="row.name"
                  class="pw-input h-9 text-xs"
                  placeholder="Display Name，例如 DeepSeek V3"
                  :disabled="busy"
                />
              </div>
              <button
                type="button"
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40 dark:hover:bg-rose-950/40 dark:hover:text-rose-400"
                :disabled="standardModelList.length <= 1 || busy"
                title="删除此模型"
                @click="removeStandardModelRow(idx)"
              >
                <BaseIcon name="trash" size="sm" />
              </button>
            </div>
          </div>
        </div>

        <!-- 折叠的高级设置 (Base URL, Protocol 协议) -->
        <div
          class="overflow-hidden rounded-xl border border-gray-200/70 bg-white dark:border-dark-800 dark:bg-dark-900"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between px-4 py-3 text-left text-xs font-medium text-gray-700 transition hover:bg-gray-50 dark:text-dark-200 dark:hover:bg-dark-800"
            @click="showAdvancedSettings = !showAdvancedSettings"
          >
            <div class="flex items-center gap-2">
              <BaseIcon name="settings-2" size="sm" class="text-gray-400" />
              <span>高级设置 (自定义 API 端点与启用状态)</span>
            </div>
            <BaseIcon
              name="chevron-down"
              size="sm"
              class="text-gray-400 transition-transform duration-200"
              :class="showAdvancedSettings ? 'rotate-180' : ''"
            />
          </button>

          <div
            v-show="showAdvancedSettings"
            class="space-y-4 border-t border-gray-100 p-4 dark:border-dark-800"
          >
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                API 地址 (Base URL)
              </label>
              <input
                v-model="standardBaseUrl"
                class="pw-input text-xs"
                placeholder="提供方默认，若内网反向代理可修改"
                inputmode="url"
                :disabled="busy"
              />
              <p class="mt-1 text-[11px] text-gray-500 dark:text-dark-400">
                已自动预设官方标准端点。如团队自建了反向代理网关，可展开修改。
              </p>
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
                />
                <span>配置完成后默认启用该模型</span>
              </label>
            </div>
          </div>
        </div>
      </template>

      <!-- ====================== 分支 2：自定义提供方模式 (Custom) ====================== -->
      <template v-else-if="activeMode === 'custom'">
        <div class="space-y-4">
          <div class="grid gap-4 md:grid-cols-2">
            <!-- Provider 标识 -->
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Provider 标识 (Route ID) <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="customRoute"
                class="pw-input text-xs"
                :class="
                  customRouteError
                    ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500'
                    : ''
                "
                placeholder="例如 my-vllm, company-gateway, ollama-local"
                :disabled="busy"
              />
              <p
                v-if="customRouteError"
                class="mt-1 text-[11px] text-rose-600 dark:text-rose-400"
              >
                {{ customRouteError }}
              </p>
              <p
                v-else
                class="mt-1 text-[11px] text-gray-500 dark:text-dark-400"
              >
                小写英文字母开头，仅含小写字母、数字和中划线，作为唯一路由代号。
              </p>
            </div>

            <!-- 显示名称 -->
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                显示名称 (Display Name)
              </label>
              <input
                v-model="customDisplayName"
                class="pw-input text-xs"
                :placeholder="
                  customRoute.trim() || '例如 公司自建 vLLM 集群 (选填)'
                "
                :disabled="busy"
              />
              <p class="mt-1 text-[11px] text-gray-500 dark:text-dark-400">
                面向界面展示的友好别名，留空将默认使用 Provider 标识。
              </p>
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <!-- Base URL (必填) -->
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Base URL (接入端点) <span class="text-rose-500">*</span>
              </label>
              <input
                v-model="customBaseUrl"
                class="pw-input text-xs"
                placeholder="例如 http://192.168.1.100:8000/v1 或 https://gateway.company.com/v1"
                inputmode="url"
                :disabled="busy"
              />
            </div>

            <!-- Protocol 协议 (必选) -->
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Protocol 协议
              </label>
              <BaseSelect
                v-model="customProtocol"
                :options="PROTOCOL_OPTIONS"
                :disabled="busy"
              />
            </div>
          </div>

          <!-- API Key (选填) -->
          <div>
            <label
              class="mb-1.5 flex items-center justify-between text-xs font-semibold text-gray-700 dark:text-dark-200"
            >
              <span>API Key (选填)</span>
              <button
                type="button"
                class="flex items-center gap-1 text-[11px] font-normal text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200"
                @click="showApiKey = !showApiKey"
              >
                <BaseIcon :name="showApiKey ? 'eye-off' : 'eye'" size="xs" />
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
              />
              <button
                type="button"
                class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
                tabindex="-1"
                @click="showApiKey = !showApiKey"
              >
                <BaseIcon :name="showApiKey ? 'eye-off' : 'eye'" size="sm" />
              </button>
            </div>
            <p class="mt-1 text-[11px] text-gray-500 dark:text-dark-400">
              若私有服务或内网集群免鉴权，可直接留空。
            </p>
          </div>

          <!-- 模型清单 -->
          <div
            class="rounded-xl border border-gray-100 bg-gray-50/50 p-4 dark:border-dark-800 dark:bg-dark-950/30"
          >
            <div class="mb-3 flex items-center justify-between">
              <div>
                <h3
                  class="text-xs font-semibold text-gray-800 dark:text-dark-200"
                >
                  包含模型清单 (Model List) <span class="text-rose-500">*</span>
                </h3>
                <p class="text-[11px] text-gray-500 dark:text-dark-400">
                  自定义提供商至少需录入 1 个模型，支持批量配置。
                </p>
              </div>
              <button
                type="button"
                class="flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 shadow-sm transition hover:border-gray-300 hover:bg-gray-50 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-200 dark:hover:bg-dark-700"
                :disabled="busy"
                @click="addCustomModelRow"
              >
                <BaseIcon name="plus" size="xs" />
                <span>添加模型</span>
              </button>
            </div>

            <div class="space-y-2.5">
              <div
                v-for="(row, idx) in customModelList"
                :key="idx"
                class="flex items-center gap-3 rounded-xl border border-gray-200/80 bg-white p-2.5 shadow-sm transition-all focus-within:border-primary-400 dark:border-dark-700 dark:bg-dark-900"
              >
                <div class="flex-1">
                  <input
                    v-model="row.id"
                    class="pw-input h-9 text-xs"
                    placeholder="Model ID (必填)，例如 qwen2.5-72b-instruct"
                    :disabled="busy"
                  />
                </div>
                <div class="flex-1">
                  <input
                    v-model="row.name"
                    class="pw-input h-9 text-xs"
                    placeholder="Display Name (选填)，例如 通义千问 72B 深度推理"
                    :disabled="busy"
                  />
                </div>
                <button
                  type="button"
                  class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40 dark:hover:bg-rose-950/40 dark:hover:text-rose-400"
                  :disabled="customModelList.length <= 1 || busy"
                  title="删除此模型"
                  @click="removeCustomModelRow(idx)"
                >
                  <BaseIcon name="trash" size="sm" />
                </button>
              </div>
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
              />
              <span>配置完成后默认启用该模型</span>
            </label>
          </div>
        </div>
      </template>

      <!-- ====================== 分支 3：单模型编辑模式 (Edit) ====================== -->
      <template v-else-if="activeMode === 'edit'">
        <div class="space-y-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                所属 Provider
              </label>
              <input
                :value="editProvider"
                class="pw-input bg-gray-50 text-xs text-gray-500 dark:bg-dark-800 dark:text-dark-400"
                disabled
              />
            </div>
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Protocol 协议
              </label>
              <BaseSelect
                v-model="editProtocol"
                :options="PROTOCOL_OPTIONS"
                :disabled="busy"
              />
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Model ID (必填)
              </label>
              <input
                v-model="editModelId"
                class="pw-input text-xs"
                placeholder="例如 deepseek-chat, gpt-4o"
                :disabled="busy"
              />
            </div>
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Display Name (显示别名)
              </label>
              <input
                v-model="editDisplayName"
                class="pw-input text-xs"
                placeholder="例如 DeepSeek V3"
                :disabled="busy"
              />
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <div>
              <label
                class="mb-1.5 block text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                Base URL (API 接入端点)
              </label>
              <input
                v-model="editBaseUrl"
                class="pw-input text-xs"
                placeholder="https://api.example.com/v1"
                inputmode="url"
                :disabled="busy"
              />
            </div>
            <div>
              <label
                class="mb-1.5 flex items-center justify-between text-xs font-semibold text-gray-700 dark:text-dark-200"
              >
                <span>更新 API Key (留空表示不修改已有凭据)</span>
                <button
                  type="button"
                  class="flex items-center gap-1 text-[11px] font-normal text-gray-500 hover:text-gray-700 dark:text-dark-400 dark:hover:text-dark-200"
                  @click="showApiKey = !showApiKey"
                >
                  <BaseIcon :name="showApiKey ? 'eye-off' : 'eye'" size="xs" />
                  {{ showApiKey ? "隐藏" : "显示" }}
                </button>
              </label>
              <div class="relative">
                <input
                  v-model="apiKey"
                  :type="showApiKey ? 'text' : 'password'"
                  class="pw-input pr-10 text-xs"
                  placeholder="留空则保持现有凭据不变"
                  autocomplete="new-password"
                  :disabled="busy"
                />
                <button
                  type="button"
                  class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-dark-200"
                  tabindex="-1"
                  @click="showApiKey = !showApiKey"
                >
                  <BaseIcon :name="showApiKey ? 'eye-off' : 'eye'" size="sm" />
                </button>
              </div>
            </div>
          </div>

          <!-- 上下文窗口容量 (Tokens) -->
          <div
            class="rounded-xl border border-gray-100 bg-gray-50/50 p-4 dark:border-dark-800 dark:bg-dark-950/30"
          >
            <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <label
                  class="block text-xs font-semibold text-gray-700 dark:text-dark-200"
                >
                  上下文窗口容量 (Context Window Tokens)
                </label>
                <p class="text-[11px] text-gray-500 dark:text-dark-400">
                  端点支持的最大输入与输出 Token 总量。留空或清除表示未设置。
                </p>
              </div>
              <button
                v-if="editContextWindowTokensInput"
                type="button"
                class="text-[11px] text-gray-500 hover:text-rose-600 dark:text-dark-400 dark:hover:text-rose-400"
                :disabled="busy"
                @click="editContextWindowTokensInput = ''"
              >
                清除设置
              </button>
            </div>

            <div class="space-y-2.5">
              <input
                v-model="editContextWindowTokensInput"
                class="pw-input text-xs font-mono"
                placeholder="例如 128000 (正整数)"
                inputmode="numeric"
                :disabled="busy"
              />

              <!-- 快捷预设药丸 -->
              <div class="flex flex-wrap items-center gap-1.5 pt-0.5">
                <span class="text-[11px] text-gray-400 dark:text-dark-500 mr-1"
                  >常用预设:</span
                >
                <button
                  v-for="preset in CONTEXT_WINDOW_PRESETS"
                  :key="preset.value"
                  type="button"
                  class="rounded-md border border-gray-200 bg-white px-2 py-0.5 text-[11px] text-gray-600 transition hover:border-primary-500 hover:bg-primary-50 hover:text-primary-600 dark:border-dark-700 dark:bg-dark-800 dark:text-dark-300 dark:hover:border-primary-500 dark:hover:bg-primary-950/40 dark:hover:text-primary-400"
                  :disabled="busy"
                  @click="editContextWindowTokensInput = String(preset.value)"
                >
                  {{ preset.label }} ({{ preset.value.toLocaleString() }})
                </button>
              </div>
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
              />
              <span>启用该模型</span>
            </label>
          </div>

          <!-- 模型费率配置卡片 (USD / 百万 Token) -->
          <div
            class="rounded-lg border border-gray-200 bg-gray-50/70 p-4 dark:border-dark-800 dark:bg-dark-900/60 space-y-3"
            data-testid="model-pricing-section"
          >
            <div
              class="flex items-center justify-between border-b pb-2.5 border-gray-200/80 dark:border-dark-800"
            >
              <div>
                <h4
                  class="text-xs font-semibold text-gray-900 dark:text-gray-100"
                >
                  模型费率配置 (USD / 百万 Token)
                </h4>
                <p class="text-[11px] text-gray-500 dark:text-dark-400 mt-0.5">
                  用于用量成本估算。留空表示未配置对应费率；清空或修改将触发版本快照归档。
                </p>
              </div>

              <button
                v-if="pricingSnapshot || isPricingDirty"
                type="button"
                data-testid="clear-pricing-btn"
                class="text-[11px] text-red-600 hover:text-red-700 dark:text-red-400 transition-colors"
                :disabled="busy"
                @click="handleClearPricing"
              >
                清空费率配置
              </button>
            </div>

            <!-- 服务端快照只读元数据 -->
            <div
              v-if="pricingSnapshot && !isPricingCleared"
              class="flex flex-wrap items-center gap-3 text-[10px] font-mono text-gray-500 dark:text-dark-400 bg-white/60 dark:bg-dark-950/40 px-2.5 py-1.5 rounded border border-gray-200/60 dark:border-dark-800"
            >
              <span>快照版本: {{ pricingSnapshot.version }}</span>
              <span>·</span>
              <span>来源: {{ pricingSnapshot.source }}</span>
              <span>·</span>
              <span
                >更新时间:
                {{
                  new Date(pricingSnapshot.updated_at).toLocaleString()
                }}</span
              >
            </div>

            <!-- 清空状态待生效提示及撤销按钮 -->
            <div
              v-else-if="isPricingCleared"
              data-testid="pricing-cleared-banner"
              class="flex items-center justify-between text-xs bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 px-3 py-2 rounded border border-amber-200 dark:border-amber-900"
            >
              <span>费率已标记待清空，保存后将移除该模型的价格配置。</span>
              <button
                v-if="pricingSnapshot"
                type="button"
                data-testid="restore-pricing-btn"
                class="text-xs font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 ml-2"
                @click="handleRestorePricing"
              >
                撤销恢复
              </button>
            </div>

            <!-- 六项费率表单输入网格 -->
            <div class="grid gap-3 sm:grid-cols-2 md:grid-cols-3 pt-1">
              <div>
                <label
                  class="mb-1 block text-[11px] font-medium text-gray-700 dark:text-dark-300"
                >
                  输入费率 (Input)
                </label>
                <input
                  v-model="pricingDraft.input"
                  type="text"
                  inputmode="decimal"
                  class="pw-input text-xs font-mono"
                  placeholder="如 2.0"
                  :disabled="busy"
                  @input="onPricingFieldInput"
                  @blur="onPricingFieldBlur('input')"
                />
              </div>

              <div>
                <label
                  class="mb-1 block text-[11px] font-medium text-gray-700 dark:text-dark-300"
                >
                  输出费率 (Output)
                </label>
                <input
                  v-model="pricingDraft.output"
                  type="text"
                  inputmode="decimal"
                  class="pw-input text-xs font-mono"
                  placeholder="如 8.0"
                  :disabled="busy"
                  @input="onPricingFieldInput"
                  @blur="onPricingFieldBlur('output')"
                />
              </div>

              <div>
                <label
                  class="mb-1 block text-[11px] font-medium text-gray-700 dark:text-dark-300"
                >
                  缓存读取 (Cache Read)
                </label>
                <input
                  v-model="pricingDraft.cache_read"
                  type="text"
                  inputmode="decimal"
                  class="pw-input text-xs font-mono"
                  placeholder="如 0.2"
                  :disabled="busy"
                  @input="onPricingFieldInput"
                  @blur="onPricingFieldBlur('cache_read')"
                />
              </div>

              <div>
                <label
                  class="mb-1 block text-[11px] font-medium text-gray-700 dark:text-dark-300"
                >
                  缓存写入 (Cache Write)
                </label>
                <input
                  v-model="pricingDraft.cache_write"
                  type="text"
                  inputmode="decimal"
                  class="pw-input text-xs font-mono"
                  placeholder="如 2.5"
                  :disabled="busy"
                  @input="onPricingFieldInput"
                  @blur="onPricingFieldBlur('cache_write')"
                />
              </div>

              <div>
                <label
                  class="mb-1 block text-[11px] font-medium text-gray-700 dark:text-dark-300"
                >
                  5分钟写入 (5m TTL)
                </label>
                <input
                  v-model="pricingDraft.cache_write_5m"
                  type="text"
                  inputmode="decimal"
                  class="pw-input text-xs font-mono"
                  placeholder="如 2.5"
                  :disabled="busy"
                  @input="onPricingFieldInput"
                  @blur="onPricingFieldBlur('cache_write_5m')"
                />
              </div>

              <div>
                <label
                  class="mb-1 block text-[11px] font-medium text-gray-700 dark:text-dark-300"
                >
                  1小时写入 (1h TTL)
                </label>
                <input
                  v-model="pricingDraft.cache_write_1h"
                  type="text"
                  inputmode="decimal"
                  class="pw-input text-xs font-mono"
                  placeholder="如 4.0"
                  :disabled="busy"
                  @input="onPricingFieldInput"
                  @blur="onPricingFieldBlur('cache_write_1h')"
                />
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Footer -->
    <div
      class="flex items-center justify-end gap-3 border-t border-gray-100 bg-gray-50/50 px-6 py-3.5 dark:border-dark-800 dark:bg-dark-950/40"
    >
      <BaseButton variant="ghost" :disabled="busy" @click="emit('close')">
        取消
      </BaseButton>
      <BaseButton :disabled="busy" @click="handleSubmit">
        <BaseIcon v-if="busy" name="refresh" size="sm" class="animate-spin" />
        <span>{{
          busy
            ? "保存中..."
            : isEditMode
              ? "保存修改"
              : activeMode === "standard"
                ? "批量添加标准模型"
                : "创建并接入自定义模型"
        }}</span>
      </BaseButton>
    </div>
  </section>
</template>

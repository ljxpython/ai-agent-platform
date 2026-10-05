import {
  computed,
  getCurrentScope,
  onScopeDispose,
  reactive,
  ref,
  type ComputedRef,
  type Ref,
} from "vue";
import type { AgentContext } from "@/services/agents/types";
import { parseAgentContext } from "@/services/agents/context";
import { listRuntimeModels } from "@/services/runtime/runtime.service";
import { listRuntimeModelPolicies } from "@/services/runtime-policies/runtime-policies.service";
import type { RuntimeModelItem } from "@/types/management";

export type ExecutionMode = "flash" | "standard" | "pro" | "ultra";

const projectModelBundleCache = new Map<
  string,
  {
    expiresAt: number;
    promise: Promise<
      [
        Awaited<ReturnType<typeof listRuntimeModels>>,
        Awaited<ReturnType<typeof listRuntimeModelPolicies>>,
      ]
    >;
  }
>();

export function loadProjectModelBundle(projectId: string) {
  const now = Date.now();
  const cached = projectModelBundleCache.get(projectId);
  if (cached && cached.expiresAt > now) {
    return cached.promise;
  }
  const promise = Promise.all([
    listRuntimeModels(projectId),
    listRuntimeModelPolicies(projectId),
  ]).catch((err) => {
    projectModelBundleCache.delete(projectId);
    throw err;
  });
  projectModelBundleCache.set(projectId, {
    expiresAt: now + 60_000,
    promise,
  });
  return promise;
}

export function clearProjectModelBundleCache(projectId?: string) {
  if (projectId) {
    projectModelBundleCache.delete(projectId);
  } else {
    projectModelBundleCache.clear();
  }
}

export interface UseChatRunConfigOptions {
  projectId: string;
  graphId: string;
  context: Ref<AgentContext>;
  initialContext?: AgentContext;
  recursionLimit: Ref<number>;
  enableExecutionMode?: boolean;
  isModeLocked: ComputedRef<boolean>;
  onLocalError?: (msg: string) => void;
}

export function useChatRunConfig(options: UseChatRunConfigOptions) {
  const models = ref<RuntimeModelItem[]>([]);
  const modelsLoading = ref(true);
  const defaultModelId = ref("");
  const defaultModelName = ref("");
  const optionsOpen = ref(false);
  const optionsError = ref("");

  const showExecutionMode = computed(
    () =>
      options.enableExecutionMode ??
      ["dear_agent", "dearflow_agent"].includes(options.graphId),
  );

  const draftRunOptions = reactive<{
    modelId: string;
    temperature: string;
    maxTokens: string;
    recursionLimit: string;
    executionMode: ExecutionMode;
  }>({
    modelId: "",
    temperature: "",
    maxTokens: "",
    recursionLimit: options.recursionLimit.value.toString(),
    executionMode:
      (options.context.value.execution_mode as ExecutionMode) ?? "standard",
  });

  const currentExecutionMode = computed<ExecutionMode>(
    () => (options.context.value.execution_mode as ExecutionMode) ?? "standard",
  );

  const initialContext = computed(() =>
    parseAgentContext(options.initialContext ?? {}),
  );

  function resetOptions(value: AgentContext = initialContext.value) {
    Object.assign(draftRunOptions, {
      modelId: value.model_id ?? "",
      temperature: value.temperature?.toString() ?? "",
      maxTokens: value.max_tokens?.toString() ?? "",
      recursionLimit: options.recursionLimit.value.toString(),
      executionMode: (value.execution_mode as ExecutionMode) ?? "standard",
    });
    optionsError.value = "";
  }

  function openOptions() {
    resetOptions(options.context.value);
    optionsOpen.value = true;
  }

  function applyOptions(): boolean {
    try {
      const nextMode = options.isModeLocked.value
        ? ((options.context.value.execution_mode as ExecutionMode) ??
          "standard")
        : draftRunOptions.executionMode || "standard";
      if (draftRunOptions.recursionLimit.trim()) {
        const limitNum = Number(draftRunOptions.recursionLimit);
        if (!Number.isInteger(limitNum) || limitNum < 1 || limitNum > 1000) {
          optionsError.value = "最大步数必须是 1 到 1000 之间的整数";
          return false;
        }
        options.recursionLimit.value = limitNum;
      }
      const updated = parseAgentContext({
        ...options.context.value,
        model_id: draftRunOptions.modelId || undefined,
        temperature: draftRunOptions.temperature.trim()
          ? Number(draftRunOptions.temperature)
          : undefined,
        max_tokens: draftRunOptions.maxTokens.trim()
          ? Number(draftRunOptions.maxTokens)
          : undefined,
        ...(showExecutionMode.value ? { execution_mode: nextMode } : {}),
      });
      options.context.value = updated;
      optionsOpen.value = false;
      return true;
    } catch (cause) {
      optionsError.value =
        cause instanceof Error ? cause.message : "运行参数无效";
      return false;
    }
  }

  let disposed = false;
  if (getCurrentScope()) {
    onScopeDispose(() => {
      disposed = true;
    });
  }

  void loadProjectModelBundle(options.projectId)
    .then(([value, policies]) => {
      if (disposed) return;
      models.value = value.models.filter(
        (model) =>
          model.enabled &&
          policies.items.find((item) => item.catalog_id === model.id)?.policy
            .is_enabled !== false,
      );
      const projectDefault = policies.items.find(
        (item) => item.policy.is_default_for_project,
      );
      const defaultModel =
        models.value.find((model) => model.id === projectDefault?.catalog_id) ??
        models.value[0];
      defaultModelId.value = defaultModel?.id ?? "";
      defaultModelName.value = defaultModel?.display_name ?? "";
      if (!options.context.value.model_id && defaultModel) {
        options.context.value = {
          ...options.context.value,
          model_id: defaultModel.id,
        };
      }
    })
    .catch(() => {
      if (!disposed) {
        options.onLocalError?.("模型列表读取失败，可恢复连接后重试");
      }
    })
    .finally(() => {
      if (!disposed) {
        modelsLoading.value = false;
      }
    });

  return {
    models,
    modelsLoading,
    defaultModelId,
    defaultModelName,
    optionsOpen,
    optionsError,
    draftRunOptions,
    currentExecutionMode,
    showExecutionMode,
    initialContext,
    resetOptions,
    openOptions,
    applyOptions,
  };
}

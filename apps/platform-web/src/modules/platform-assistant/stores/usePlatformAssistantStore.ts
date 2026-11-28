import { defineStore } from "pinia";
import type {
  AssistantAttachedContext,
  AssistantCapabilities,
  BootstrapConfig,
} from "../types";
import {
  bootstrapAssistant,
  getAssistantCapabilities,
} from "../services/client";
import { loadProjectModelBundle } from "@/modules/chat/composables/useChatRunConfig";
import type { RuntimeModelItem } from "@/types/management";

export const usePlatformAssistantStore = defineStore("platformAssistant", {
  state: () => ({
    isOpen: false,
    activeView: "chat" as "chat" | "history",
    bootstrapConfig: null as BootstrapConfig | null,
    capabilities: null as AssistantCapabilities | null,
    attachedContext: null as AssistantAttachedContext | null,
    activeThreadId: null as string | null,
    loading: false,
    error: null as string | null,
    selectedModelId:
      (typeof window !== "undefined"
        ? localStorage.getItem("pw_assistant_selected_model_id")
        : "") || "",
    availableModels: [] as RuntimeModelItem[],
    modelsLoading: false,
  }),

  getters: {
    boundProjectId(state): string {
      return state.bootstrapConfig?.project_id || "";
    },
    isPersonalProject(state): boolean {
      return Boolean(state.bootstrapConfig?.personal_project);
    },
    currentModelId(state): string {
      return state.selectedModelId || state.bootstrapConfig?.model_id || "";
    },
    defaultModelId(state): string {
      return state.bootstrapConfig?.model_id || "";
    },
    defaultModelName(state): string {
      const defaultId = state.bootstrapConfig?.model_id;
      if (!defaultId) return "";
      const match = state.availableModels.find((m) => m.id === defaultId);
      return match?.display_name || match?.model || "";
    },
    hasAttachedContext(state): boolean {
      return state.attachedContext !== null;
    },
  },

  actions: {
    setSelectedModelId(modelId: string) {
      this.selectedModelId = modelId;
      if (typeof window !== "undefined") {
        if (modelId) {
          localStorage.setItem("pw_assistant_selected_model_id", modelId);
        } else {
          localStorage.removeItem("pw_assistant_selected_model_id");
        }
      }
    },

    async loadAvailableModels(
      targetProjectId?: string,
    ): Promise<RuntimeModelItem[]> {
      const pid = targetProjectId || this.boundProjectId;
      if (!pid) return [];
      this.modelsLoading = true;
      try {
        const [value, policies] = await loadProjectModelBundle(pid);
        const list = (value?.models || []).filter(
          (model) =>
            model.enabled &&
            policies?.items?.find((item) => item.catalog_id === model.id)
              ?.policy?.is_enabled !== false,
        );
        this.availableModels = list;
        if (
          this.selectedModelId &&
          list.length > 0 &&
          !list.some((m) => m.id === this.selectedModelId)
        ) {
          this.setSelectedModelId("");
        }
        return list;
      } catch {
        this.availableModels = [];
        return [];
      } finally {
        this.modelsLoading = false;
      }
    },

    open(options?: { projectId?: string; threadId?: string }) {
      this.isOpen = true;
      if (options?.threadId) {
        this.activeThreadId = options.threadId;
      }
      this.activeView = "chat";
      void this.ensureBootstrap(options?.projectId).catch(() => {});
    },

    close() {
      this.isOpen = false;
    },

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    },

    /**
     * 全局错误现场一键唤起入口
     * 将诊断 Markdown 挂载为输入框顶部的上下文胶囊（Context Pill），自动滑出抽屉
     */
    openWithDiagnostic(context: AssistantAttachedContext) {
      this.attachedContext = context;
      this.isOpen = true;
      this.activeView = "chat";
      // 诊断目标不改变助手会话的项目绑定。
      void this.ensureBootstrap().catch(() => {});
    },

    setAttachedContext(context: AssistantAttachedContext | null) {
      this.attachedContext = context;
    },

    clearAttachedContext() {
      this.attachedContext = null;
    },

    switchView(view: "chat" | "history") {
      this.activeView = view;
    },

    setActiveThreadId(threadId: string | null) {
      this.activeThreadId = threadId;
      this.activeView = "chat";
    },

    /**
     * 确保已完成 Bootstrap 初始化
     */
    async ensureBootstrap(targetProjectId?: string): Promise<BootstrapConfig> {
      // 若已有配置且绑定的项目一致，直接复用
      if (
        this.bootstrapConfig &&
        (!targetProjectId ||
          this.bootstrapConfig.project_id === targetProjectId)
      ) {
        return this.bootstrapConfig;
      }

      this.loading = true;
      this.error = null;
      try {
        const config = await bootstrapAssistant(targetProjectId);
        if (
          this.bootstrapConfig &&
          this.bootstrapConfig.project_id !== config.project_id
        ) {
          this.activeThreadId = null;
        }
        this.bootstrapConfig = config;

        // 尝试加载能力声明，静默捕获不阻塞核心流程
        try {
          this.capabilities = await getAssistantCapabilities(config.project_id);
        } catch {
          // 能力声明仅作提示，失败不影响基础问答
        }

        // 异步并行加载可用模型列表
        void this.loadAvailableModels(config.project_id).catch(() => {});

        return config;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "平台助手初始化失败";
        this.error = msg;
        throw err;
      } finally {
        this.loading = false;
      }
    },

    /**
     * 开启新会话
     */
    newSession() {
      this.activeThreadId = null;
      this.activeView = "chat";
    },
  },
});

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
  }),

  getters: {
    boundProjectId(state): string {
      return state.bootstrapConfig?.project_id || "";
    },
    isPersonalProject(state): boolean {
      return Boolean(state.bootstrapConfig?.personal_project);
    },
    currentModelId(state): string {
      return state.bootstrapConfig?.model_id || "";
    },
    hasAttachedContext(state): boolean {
      return state.attachedContext !== null;
    },
  },

  actions: {
    open(options?: { projectId?: string; threadId?: string }) {
      this.isOpen = true;
      if (options?.threadId) {
        this.activeThreadId = options.threadId;
      }
      this.activeView = "chat";
      void this.ensureBootstrap(options?.projectId);
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
      void this.ensureBootstrap(context.projectId);
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
        this.bootstrapConfig = config;

        // 尝试加载能力声明，静默捕获不阻塞核心流程
        try {
          this.capabilities = await getAssistantCapabilities(config.project_id);
        } catch {
          // 能力声明仅作提示，失败不影响基础问答
        }

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

import { defineStore } from "pinia";
import { extractPlatformHttpError } from "@/utils/http-error";
import { getSessionGeneration } from "@/services/auth/token";
import {
  getProjectAccess,
  listProjects,
} from "@/services/projects/projects.service";
import type { ManagementProject, ProjectAccess } from "@/types/management";

const accessRequests = new WeakMap<
  object,
  { epoch: number; promise: Promise<void> }
>();
const contextRequests = new WeakMap<object, Promise<void>>();

const PROJECT_STORAGE_KEY = "pw:workspace:project-id";

function readProjectPreference(storageKey: string) {
  if (typeof window === "undefined") {
    return "";
  }

  return window.localStorage.getItem(storageKey)?.trim() || "";
}

function writeProjectPreference(storageKey: string, projectId: string) {
  if (typeof window === "undefined") {
    return;
  }

  if (projectId) {
    window.localStorage.setItem(storageKey, projectId);
    return;
  }

  window.localStorage.removeItem(storageKey);
}

export const useWorkspaceStore = defineStore("workspace", {
  state: () => ({
    currentProjectId: "",
    projects: [] as ManagementProject[],
    currentProjectAccess: null as ProjectAccess | null,
    loading: false,
    accessLoading: false,
    accessStatus: "unknown" as "unknown" | "ready" | "denied" | "unavailable",
    accessCheckedAt: 0,
    contextLoaded: false,
    error: "",
    accessEpoch: 0,
    contextEpoch: 0,
  }),
  getters: {
    currentProject(state) {
      return (
        state.projects.find(
          (project) => project.id === state.currentProjectId,
        ) ?? null
      );
    },
  },
  actions: {
    hydrateProjectPreference() {
      this.currentProjectId = readProjectPreference(PROJECT_STORAGE_KEY);
    },
    async setProjectId(projectId: string) {
      const id = projectId.trim();
      if (id !== this.currentProjectId || !id) {
        this.accessEpoch += 1;
        this.currentProjectAccess = null;
        this.accessStatus = "unknown";
        this.accessCheckedAt = 0;
      }
      this.currentProjectId = id;
      writeProjectPreference(PROJECT_STORAGE_KEY, id);
      await this.refreshCurrentProjectAccess(true);
    },
    async refreshCurrentProjectAccess(force = true): Promise<void> {
      const projectId = this.currentProjectId;
      if (!projectId) {
        this.currentProjectAccess = null;
        this.accessLoading = false;
        return;
      }
      const active = accessRequests.get(this);
      if (active?.epoch === this.accessEpoch) return active.promise;
      // 合并切屏、聚焦和拒绝事件的短时间突发；显式重试不受冷却限制。
      if (
        !force &&
        this.accessCheckedAt &&
        Date.now() - this.accessCheckedAt < 10_000
      )
        return;
      const epoch = this.accessEpoch;
      const generation = getSessionGeneration();
      const isCurrent = () =>
        epoch === this.accessEpoch &&
        projectId === this.currentProjectId &&
        generation === getSessionGeneration();
      this.accessLoading = true;
      const pending = (async () => {
        try {
          const access = await getProjectAccess(projectId);
          if (!isCurrent()) return;
          this.currentProjectAccess = access;
          this.accessStatus = access.permissions.length ? "ready" : "denied";
          this.error = "";
        } catch (cause) {
          if (isCurrent()) {
            const { status, code } = extractPlatformHttpError(cause);
            if (
              status === 403 ||
              (status === 404 && code === "project_not_found")
            ) {
              this.currentProjectAccess = null;
              this.accessStatus = "denied";
              this.error = "当前账号无法访问此项目";
            } else {
              this.accessStatus = "unavailable";
              this.error = "暂时无法确认项目权限，请检查连接后重试";
            }
          }
          throw cause;
        } finally {
          if (isCurrent()) {
            this.accessLoading = false;
            this.accessCheckedAt = Date.now();
          }
        }
      })();
      accessRequests.set(this, { epoch, promise: pending });
      try {
        await pending;
      } finally {
        if (accessRequests.get(this)?.promise === pending)
          accessRequests.delete(this);
      }
    },
    async hydrateContext(): Promise<void> {
      const active = contextRequests.get(this);
      if (active) return active;
      const epoch = ++this.contextEpoch;
      const generation = getSessionGeneration();
      const isCurrent = () =>
        epoch === this.contextEpoch && generation === getSessionGeneration();
      this.loading = true;
      this.error = "";
      const pending = (async () => {
        try {
          if (!this.currentProjectId) this.hydrateProjectPreference();
          const rows = await listProjects();
          if (!isCurrent()) return;
          this.projects = rows;
          // 当前路由/用户选择优先。列表更新不能悄悄切换工作区。
          const nextProjectId = this.currentProjectId || rows[0]?.id || "";
          await this.setProjectId(nextProjectId);
          if (isCurrent()) this.contextLoaded = true;
        } catch {
          if (isCurrent()) this.error ||= "项目列表暂时无法加载，请重试";
        } finally {
          if (isCurrent()) this.loading = false;
        }
      })();
      contextRequests.set(this, pending);
      try {
        await pending;
      } finally {
        if (contextRequests.get(this) === pending) contextRequests.delete(this);
      }
    },
    reset() {
      this.contextEpoch += 1;
      contextRequests.delete(this);
      this.error = "";
      this.projects = [];
      void this.setProjectId("");
      this.loading = false;
      this.contextLoaded = false;
    },
  },
});

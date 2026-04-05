"use client";

import type { ReactNode } from "react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryState } from "nuqs";

import { hasOidcSession } from "@/lib/oidc-storage";
import {
  listProjects,
  type ManagementProject,
} from "@/lib/management-api/projects";
import {
  getMe,
  type ManagementUser,
  type ManagementUserProject,
} from "@/lib/management-api/users";
import {
  clearStoredWorkspaceProjectId,
  getStoredWorkspaceProjectId,
  setStoredWorkspaceProjectId,
} from "@/lib/workspace-project-preference";

type WorkspaceContextValue = {
  projectId: string;
  setProjectId: (value: string) => void;
  assistantId: string;
  setAssistantId: (value: string) => void;
  projects: ManagementProject[];
  currentProject: ManagementProject | null;
  currentUser: ManagementUser | null;
  currentProjectRole: ManagementUserProject["role"] | null;
  currentRoleLabel: string;
  canAccessAudit: boolean;
  loading: boolean;
  refreshProjects: () => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(
  undefined,
);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [projectId, setProjectIdQuery] = useQueryState("projectId", {
    defaultValue: "",
  });
  const [assistantId, setAssistantIdQuery] = useQueryState("assistantId", {
    defaultValue: "",
  });
  const [, setThreadId] = useQueryState("threadId", { defaultValue: "" });
  const [projects, setProjects] = useState<ManagementProject[]>([]);
  const [currentUser, setCurrentUser] = useState<ManagementUser | null>(null);
  const [loading, setLoading] = useState(true);

  const loadProjects = useCallback(async () => {
    const currentProjectId = (projectId ?? "").trim();
    if (!hasOidcSession()) {
      setProjects([]);
      setProjectIdQuery("");
      setCurrentUser(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const [rows, me] = await Promise.all([
        listProjects({ limit: 100, offset: 0 }),
        getMe().catch(() => null),
      ]);
      setProjects(rows);
      setCurrentUser(me);

      const storedProjectId = getStoredWorkspaceProjectId();
      const nextProjectId =
        rows.find((item) => item.id === currentProjectId)?.id ||
        rows.find((item) => item.id === storedProjectId)?.id ||
        rows[0]?.id ||
        "";

      setProjectIdQuery(nextProjectId);
      if (nextProjectId) {
        setStoredWorkspaceProjectId(nextProjectId);
      } else {
        clearStoredWorkspaceProjectId();
      }
    } catch {
      setProjects([]);
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  }, [projectId, setProjectIdQuery]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const value = useMemo<WorkspaceContextValue>(() => {
    const normalizedProjectId = projectId ?? "";
    const currentProjectRole = null;
    const currentRoleLabel = currentUser?.is_super_admin
      ? "super admin"
      : currentUser
        ? "member"
        : loading
          ? "loading..."
          : "guest";
    const canAccessAudit = Boolean(currentUser?.is_super_admin);

    return {
      projectId: normalizedProjectId,
      setProjectId: (value: string) => {
        const normalizedValue = value.trim();
        setProjectIdQuery(normalizedValue);
        if (normalizedValue) {
          setStoredWorkspaceProjectId(normalizedValue);
        } else {
          clearStoredWorkspaceProjectId();
        }
        setThreadId(null);
        setAssistantIdQuery("");
      },
      assistantId: assistantId ?? "",
      setAssistantId: (value: string) => {
        setAssistantIdQuery(value.trim());
      },
      projects,
      currentProject:
        projects.find((item) => item.id === normalizedProjectId) ?? null,
      currentUser,
      currentProjectRole,
      currentRoleLabel,
      canAccessAudit,
      loading,
      refreshProjects: loadProjects,
    };
  }, [
    assistantId,
    currentUser,
    loadProjects,
    loading,
    projectId,
    projects,
    setAssistantIdQuery,
    setProjectIdQuery,
    setThreadId,
  ]);

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaceContext() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error(
      "useWorkspaceContext must be used within WorkspaceProvider",
    );
  }
  return context;
}

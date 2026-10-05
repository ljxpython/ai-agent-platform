import type { Router } from "vue-router";
import { defaultWorkspacePath } from "@/services/auth/permissions";
import { getAccessToken, hasStoredAuthSession } from "@/services/auth/token";
import { useAuthStore } from "@/stores/auth";
import { useUiStore } from "@/stores/ui";
import { useWorkspaceStore } from "@/stores/workspace";
import { resolveRouteAccess } from "@/services/auth/route-access";
import type { PermissionCode } from "@/types/management";

function resolveRoutePermissionProjectId(
  params: Record<string, unknown>,
  workspaceStore: ReturnType<typeof useWorkspaceStore>,
  source?: "workspace" | "route",
): string {
  if (source === "route") {
    if (typeof params.projectId === "string") {
      return params.projectId.trim();
    }
    return "";
  }

  return workspaceStore.currentProjectId;
}

export function registerRouterGuards(router: Router) {
  router.beforeEach(async (to) => {
    const authStore = useAuthStore();
    const workspaceStore = useWorkspaceStore();
    const uiStore = useUiStore();

    await authStore.hydrate();
    if (hasStoredAuthSession() && (!authStore.user || !getAccessToken())) {
      await authStore.fetchCurrentUser();
    }

    const isAuthenticated = hasStoredAuthSession() && Boolean(authStore.user);

    if (to.path.startsWith("/workspace") && !hasStoredAuthSession()) {
      return {
        path: "/auth/login",
        query: { redirect: to.fullPath },
      };
    }

    if (
      to.path.startsWith("/workspace") &&
      !isAuthenticated &&
      to.name !== "workspace-access-unavailable"
    ) {
      return {
        name: "workspace-access-unavailable",
        query: { returnTo: to.fullPath, reason: "unavailable" },
      };
    }

    if (to.path.startsWith("/auth") && isAuthenticated) {
      if (
        typeof to.query.redirect === "string" &&
        to.query.redirect.startsWith("/workspace")
      ) {
        return to.query.redirect;
      }

      return defaultWorkspacePath(authStore.user);
    }

    if (
      to.path.startsWith("/workspace") &&
      isAuthenticated &&
      !workspaceStore.contextLoaded
    ) {
      await workspaceStore.hydrateContext();
    }

    if (to.path.startsWith("/workspace")) {
      const requiredPermissions = Array.isArray(to.meta.requiredPermissions)
        ? (to.meta.requiredPermissions as PermissionCode[])
        : [];

      if (requiredPermissions.length > 0) {
        const projectId = resolveRoutePermissionProjectId(
          to.params as Record<string, unknown>,
          workspaceStore,
          to.meta.permissionProjectSource,
        );
        if (
          to.meta.permissionProjectSource === "route" &&
          projectId &&
          workspaceStore.currentProjectAccess?.project_id !== projectId
        ) {
          try {
            await workspaceStore.setProjectId(projectId);
          } catch {
            return {
              name: "workspace-access-unavailable",
              query: {
                returnTo: to.fullPath,
                reason:
                  workspaceStore.accessStatus === "denied"
                    ? "denied"
                    : "unavailable",
              },
            };
          }
        }
        const access = resolveRouteAccess(to, authStore.user, workspaceStore);
        if (access !== "allowed") {
          if (access === "denied")
            uiStore.pushToast({
              type: "warning",
              title: "无访问权限",
              message: "当前账号没有访问该页面所需的权限。",
            });
          return {
            name: "workspace-access-unavailable",
            query: {
              returnTo: to.fullPath,
              reason: access === "denied" ? "denied" : "unavailable",
            },
          };
        }
      }
    }

    return true;
  });
}

import type { RouteMeta } from "vue-router";
import type { ManagementUser, ProjectAccess } from "@/types/management";
import { hasPermission, isProjectPermission } from "./permissions";

export type RouteAccess = "allowed" | "denied" | "loading" | "unavailable";

// 路由入口和驻留页面共用同一判定；快照缺失不等于已被撤权。
export function resolveRouteAccess(
  route: { meta: RouteMeta; params?: Record<string, unknown> },
  user: ManagementUser | null,
  workspace: {
    currentProjectId: string;
    currentProjectAccess: ProjectAccess | null;
    accessStatus?: string;
    accessLoading?: boolean;
    error?: string;
  },
): RouteAccess {
  const permissions = route.meta.requiredPermissions ?? [];
  if (!permissions.length) return "allowed";
  const projectId =
    route.meta.permissionProjectSource === "route"
      ? String(route.params?.projectId ?? "").trim()
      : workspace.currentProjectId;
  const states = permissions.map((permission): RouteAccess => {
    if (!isProjectPermission(permission)) {
      if (!user) return "unavailable";
      return hasPermission(user, permission) ? "allowed" : "denied";
    }
    if (projectId && workspace.currentProjectAccess?.project_id === projectId) {
      return workspace.currentProjectAccess.permissions.includes(permission)
        ? "allowed"
        : "denied";
    }
    if (
      projectId === workspace.currentProjectId &&
      workspace.accessStatus === "denied"
    )
      return "denied";
    if (workspace.accessLoading) return "loading";
    if (workspace.error || workspace.accessStatus === "unavailable")
      return "unavailable";
    return projectId ? "loading" : "denied";
  });
  if (route.meta.permissionMode === "any") {
    if (states.includes("allowed")) return "allowed";
  } else if (states.includes("denied")) return "denied";
  if (states.includes("unavailable")) return "unavailable";
  if (states.includes("loading")) return "loading";
  return states.every((state) => state === "allowed") ? "allowed" : "denied";
}

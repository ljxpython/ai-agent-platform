export const ACCESS_DENIED_EVENT = "platform-access-denied";

export interface AccessDeniedDetail {
  scope: "platform" | "project" | "thread" | "resource";
  projectId?: string;
  threadId?: string;
  method: string;
  code?: string;
}

export function notifyAccessDenied(
  url: string,
  method: string,
  projectHeader?: string | null,
  code?: string,
) {
  const path = new URL(url, window.location.origin).pathname;
  // 权限快照查询由 Store 自己处理，禁止查询失败再次广播并形成反馈循环。
  if (/\/api\/projects\/[^/]+\/access\/?$/.test(path)) return;
  const projectId =
    projectHeader || path.match(/\/api\/projects\/([^/]+)/)?.[1];
  const threadId = path.match(/\/threads\/([^/]+)/)?.[1];
  const scope =
    code === "platform_role_missing"
      ? "platform"
      : code === "project_role_missing" && projectId
        ? "project"
        : threadId && projectId
          ? "thread"
          : "resource";
  window.dispatchEvent(
    new CustomEvent<AccessDeniedDetail>(ACCESS_DENIED_EVENT, {
      detail: {
        scope,
        projectId,
        threadId,
        method: method.toUpperCase(),
        code,
      },
    }),
  );
}

export function accessDeniedDetail(
  event: Event,
): AccessDeniedDetail | undefined {
  return (event as CustomEvent<AccessDeniedDetail>).detail;
}

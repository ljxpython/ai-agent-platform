import type { RouteRecordRaw } from "vue-router";

const workspaceChildren: RouteRecordRaw[] = [
  {
    path: ":pathMatch(.*)*",
    name: "workspace-not-found",
    component: () => import("@/views/workspace/AccessUnavailableView.vue"),
    meta: { title: "页面不存在" },
  },
  {
    path: "projects/:projectId/agents",
    name: "workspace-agents",
    component: () => import("@/modules/agents/pages/AgentsPage.vue"),
    meta: {
      title: "Agents",
      requiredPermissions: ["project.assistant.read"],
      permissionProjectSource: "route",
    },
  },
  {
    path: "projects/:projectId/agents/:agentId",
    name: "workspace-agent-detail",
    component: () => import("@/modules/agents/pages/AgentEditorPage.vue"),
    meta: {
      title: "Agent 详情",
      requiredPermissions: ["project.assistant.read"],
      permissionProjectSource: "route",
    },
  },
  {
    path: "projects/:projectId/models",
    name: "workspace-models",
    component: () => import("@/modules/runtime/pages/RuntimeModelsPage.vue"),
    meta: {
      title: "Models",
      requiredPermissions: ["project.runtime.read"],
      permissionProjectSource: "route",
    },
  },
  {
    path: "projects/:projectId/graphs",
    name: "workspace-graphs",
    component: () => import("@/modules/graphs/pages/GraphsPage.vue"),
    meta: {
      title: "Graphs",
      requiredPermissions: ["project.runtime.read"],
      permissionProjectSource: "route",
    },
  },
  {
    path: "projects/:projectId/chat/:threadId?",
    name: "workspace-chat",
    component: () => import("@/modules/chat/pages/ChatPage.vue"),
    meta: {
      title: "Chat",
      requiredPermissions: ["project.runtime.read"],
      permissionProjectSource: "route",
    },
  },
  {
    path: "access-unavailable",
    name: "workspace-access-unavailable",
    component: () => import("@/views/workspace/AccessUnavailableView.vue"),
    meta: { title: "无法访问" },
  },
  {
    path: "",
    redirect: "/workspace/overview",
  },
  {
    path: "overview",
    name: "workspace-overview",
    component: () => import("@/modules/overview/pages/OverviewPage.vue"),
    meta: { title: "总览", eyebrow: "Overview" },
  },
  {
    path: "projects",
    name: "workspace-projects",
    component: () => import("@/modules/projects/pages/ProjectsPage.vue"),
    meta: { title: "项目", eyebrow: "Projects" },
  },
  {
    path: "projects/new",
    name: "workspace-project-create",
    component: () => import("@/modules/projects/pages/ProjectCreatePage.vue"),
    meta: {
      title: "新建项目",
      eyebrow: "Projects",
      requiredPermissions: ["platform.project.create"],
    },
  },
  {
    path: "projects/:projectId",
    name: "workspace-project-detail",
    component: () => import("@/modules/projects/pages/ProjectDetailPage.vue"),
    meta: {
      title: "项目详情",
      eyebrow: "Projects",
      requiredPermissions: ["platform.project.read", "project.member.read"],
      permissionMode: "any",
      permissionProjectSource: "route",
    },
  },
  {
    path: "projects/:projectId/members",
    name: "workspace-project-members",
    component: () => import("@/modules/projects/pages/ProjectMembersPage.vue"),
    meta: {
      title: "项目成员",
      eyebrow: "Projects",
      requiredPermissions: ["project.member.read"],
      permissionProjectSource: "route",
    },
  },
  {
    path: "users",
    name: "workspace-users",
    component: () => import("@/modules/users/pages/UsersPage.vue"),
    meta: {
      title: "用户",
      eyebrow: "Users",
      requiredPermissions: ["platform.user.read"],
    },
  },
  {
    path: "users/new",
    name: "workspace-user-create",
    component: () => import("@/modules/users/pages/UserCreatePage.vue"),
    meta: {
      title: "新建用户",
      eyebrow: "Users",
      requiredPermissions: ["platform.user.create"],
    },
  },
  {
    path: "users/:userId",
    name: "workspace-user-detail",
    component: () => import("@/modules/users/pages/UserDetailPage.vue"),
    meta: {
      title: "用户详情",
      eyebrow: "Users",
      requiredPermissions: ["platform.user.read"],
    },
  },

  {
    path: "control-plane",
    name: "workspace-control-plane",
    component: () =>
      import("@/modules/control-plane/pages/ControlPlanePage.vue"),
    meta: {
      title: "Control Plane",
      eyebrow: "Governance",
      requiredPermissions: ["platform.config.read"],
      permissionMode: "any",
    },
  },

  {
    path: "announcements",
    name: "workspace-announcements",
    component: () =>
      import("@/modules/announcements/pages/AnnouncementsPage.vue"),
    meta: {
      title: "公告管理",
      eyebrow: "Announcements",
      requiredPermissions: [
        "platform.announcement.write",
        "project.announcement.write",
      ],
      permissionMode: "any",
      permissionProjectSource: "workspace",
      allowWithoutProject: true,
    },
  },
  {
    path: "me",
    name: "workspace-me",
    component: () => import("@/modules/account/pages/ProfilePage.vue"),
    meta: { title: "我的信息", eyebrow: "Account" },
  },
  {
    path: "security",
    name: "workspace-security",
    component: () => import("@/modules/account/pages/SecurityPage.vue"),
    meta: { title: "安全设置", eyebrow: "Account" },
  },
  {
    path: "audit",
    name: "workspace-audit",
    component: () => import("@/modules/audit/pages/AuditPage.vue"),
    meta: {
      title: "审计日志",
      eyebrow: "Audit",
      requiredPermissions: ["platform.audit.read", "project.audit.read"],
      permissionMode: "any",
      permissionProjectSource: "workspace",
      allowWithoutProject: true,
    },
  },
  {
    path: "platform-config",
    name: "workspace-platform-config",
    component: () =>
      import("@/modules/platform-config/pages/PlatformConfigPage.vue"),
    meta: {
      title: "平台配置",
      eyebrow: "Governance",
      requiredPermissions: ["platform.config.read"],
    },
  },
  {
    path: "service-accounts",
    name: "workspace-service-accounts",
    component: () =>
      import("@/modules/service-accounts/pages/ServiceAccountsPage.vue"),
    meta: {
      title: "Service Accounts",
      eyebrow: "Governance",
      requiredPermissions: ["platform.service_account.read"],
    },
  },
  {
    path: "system-governance",
    name: "workspace-system-governance",
    component: () =>
      import("@/modules/system-governance/pages/SystemGovernancePage.vue"),
    meta: {
      title: "System Probes",
      eyebrow: "Governance",
      requiredPermissions: ["platform.config.read"],
    },
  },
];

const navigation: Record<
  string,
  { group: string; label: string; icon: string }
> = {
  "workspace-overview": { group: "工作区", label: "总览", icon: "overview" },
  "workspace-projects": { group: "工作区", label: "项目", icon: "folder" },
  "workspace-agents": { group: "项目管理", label: "Agents", icon: "assistant" },
  "workspace-chat": { group: "项目管理", label: "Chat", icon: "chat" },
  "workspace-models": {
    group: "项目管理",
    label: "模型与工具",
    icon: "runtime",
  },
  "workspace-graphs": { group: "项目管理", label: "Graphs", icon: "graph" },
  "workspace-users": { group: "平台管理", label: "用户", icon: "users" },
  "workspace-control-plane": {
    group: "平台管理",
    label: "控制面",
    icon: "overview",
  },
  "workspace-announcements": { group: "平台管理", label: "公告", icon: "bell" },
  "workspace-platform-config": {
    group: "平台管理",
    label: "平台配置",
    icon: "lock",
  },
  "workspace-service-accounts": {
    group: "平台管理",
    label: "服务账号",
    icon: "users",
  },
  "workspace-system-governance": {
    group: "平台管理",
    label: "系统探测",
    icon: "shield",
  },
  "workspace-audit": { group: "平台管理", label: "审计", icon: "audit" },
};
for (const route of workspaceChildren) {
  const item = navigation[String(route.name)];
  if (item) route.meta = { ...route.meta, navigation: item };
}

export const routes: RouteRecordRaw[] = [
  {
    path: "/:pathMatch(.*)*",
    redirect: "/workspace/not-found",
  },
  {
    path: "/",
    redirect: "/workspace",
  },
  {
    path: "/auth",
    component: () => import("@/layouts/AuthLayout.vue"),
    children: [
      {
        path: "login",
        name: "auth-login",
        component: () => import("@/views/auth/LoginView.vue"),
      },
      {
        path: "callback",
        name: "auth-callback",
        component: () => import("@/views/auth/AuthCallbackView.vue"),
      },
    ],
  },
  {
    path: "/workspace",
    component: () => import("@/layouts/WorkspaceLayout.vue"),
    children: workspaceChildren,
  },
];

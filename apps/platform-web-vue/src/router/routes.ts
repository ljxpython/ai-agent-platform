import type { RouteRecordRaw } from 'vue-router'
import { h } from 'vue'
import { RouterView } from 'vue-router'
import AuthLayout from '@/layouts/AuthLayout.vue'
import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import ProfilePage from '@/modules/account/pages/ProfilePage.vue'
import SecurityPage from '@/modules/account/pages/SecurityPage.vue'
import AssistantsPage from '@/modules/assistants/pages/AssistantsPage.vue'
import AuditPage from '@/modules/audit/pages/AuditPage.vue'
import OverviewPage from '@/modules/overview/pages/OverviewPage.vue'
import ProjectsPage from '@/modules/projects/pages/ProjectsPage.vue'
import UsersPage from '@/modules/users/pages/UsersPage.vue'
import LoginView from '@/views/auth/LoginView.vue'
import PlaceholderView from '@/views/workspace/PlaceholderView.vue'

const workspaceChildren: RouteRecordRaw[] = [
  {
    path: '',
    redirect: '/workspace/overview'
  },
  {
    path: 'overview',
    name: 'workspace-overview',
    component: OverviewPage,
    meta: { title: '总览', eyebrow: 'Overview' }
  },
  {
    path: 'projects',
    name: 'workspace-projects',
    component: ProjectsPage,
    meta: { title: '项目', eyebrow: 'Projects' }
  },
  {
    path: 'users',
    name: 'workspace-users',
    component: UsersPage,
    meta: { title: '用户', eyebrow: 'Users' }
  },
  {
    path: 'assistants',
    name: 'workspace-assistants',
    component: AssistantsPage,
    meta: { title: '助手', eyebrow: 'Assistants' }
  },
  {
    path: 'runtime',
    name: 'workspace-runtime',
    component: PlaceholderView,
    meta: { title: 'Runtime', eyebrow: 'Runtime' }
  },
  {
    path: 'graphs',
    name: 'workspace-graphs',
    component: PlaceholderView,
    meta: { title: 'Graphs', eyebrow: 'Graphs' }
  },
  {
    path: 'sql-agent',
    name: 'workspace-sql-agent',
    component: PlaceholderView,
    meta: { title: 'SQL Agent', eyebrow: 'Agent' }
  },
  {
    path: 'threads',
    name: 'workspace-threads',
    component: PlaceholderView,
    meta: { title: 'Threads', eyebrow: 'Threads' }
  },
  {
    path: 'chat',
    name: 'workspace-chat',
    component: PlaceholderView,
    meta: { title: 'Chat', eyebrow: 'Chat' }
  },
  {
    path: 'testcase',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-testcase',
        component: PlaceholderView,
        meta: { title: 'Testcase', eyebrow: 'Testcase' }
      },
      {
        path: 'generate',
        name: 'workspace-testcase-generate',
        component: PlaceholderView,
        meta: { title: '用例生成', eyebrow: 'Testcase' }
      },
      {
        path: 'cases',
        name: 'workspace-testcase-cases',
        component: PlaceholderView,
        meta: { title: '用例管理', eyebrow: 'Testcase' }
      },
      {
        path: 'documents',
        name: 'workspace-testcase-documents',
        component: PlaceholderView,
        meta: { title: '文档管理', eyebrow: 'Testcase' }
      }
    ]
  },
  {
    path: 'me',
    name: 'workspace-me',
    component: ProfilePage,
    meta: { title: '我的信息', eyebrow: 'Account' }
  },
  {
    path: 'security',
    name: 'workspace-security',
    component: SecurityPage,
    meta: { title: '安全设置', eyebrow: 'Account' }
  },
  {
    path: 'audit',
    name: 'workspace-audit',
    component: AuditPage,
    meta: { title: '审计日志', eyebrow: 'Audit' }
  }
]

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workspace'
  },
  {
    path: '/auth',
    component: AuthLayout,
    children: [
      {
        path: 'login',
        name: 'auth-login',
        component: LoginView
      }
    ]
  },
  {
    path: '/workspace',
    component: WorkspaceLayout,
    children: workspaceChildren
  }
]

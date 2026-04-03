import type { RouteRecordRaw } from 'vue-router'
import { h } from 'vue'
import { RouterView } from 'vue-router'
import AuthLayout from '@/layouts/AuthLayout.vue'
import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import ProfilePage from '@/modules/account/pages/ProfilePage.vue'
import SecurityPage from '@/modules/account/pages/SecurityPage.vue'
import AssistantsPage from '@/modules/assistants/pages/AssistantsPage.vue'
import AuditPage from '@/modules/audit/pages/AuditPage.vue'
import ChatPage from '@/modules/chat/pages/ChatPage.vue'
import GraphsPage from '@/modules/graphs/pages/GraphsPage.vue'
import OverviewPage from '@/modules/overview/pages/OverviewPage.vue'
import ProjectsPage from '@/modules/projects/pages/ProjectsPage.vue'
import RuntimeModelsPage from '@/modules/runtime/pages/RuntimeModelsPage.vue'
import RuntimePage from '@/modules/runtime/pages/RuntimePage.vue'
import RuntimeToolsPage from '@/modules/runtime/pages/RuntimeToolsPage.vue'
import SqlAgentPage from '@/modules/sql-agent/pages/SqlAgentPage.vue'
import TestcaseCasesPage from '@/modules/testcase/pages/TestcaseCasesPage.vue'
import TestcaseDocumentsPage from '@/modules/testcase/pages/TestcaseDocumentsPage.vue'
import TestcaseGeneratePage from '@/modules/testcase/pages/TestcaseGeneratePage.vue'
import ThreadsPage from '@/modules/threads/pages/ThreadsPage.vue'
import UsersPage from '@/modules/users/pages/UsersPage.vue'
import LoginView from '@/views/auth/LoginView.vue'

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
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-runtime',
        component: RuntimePage,
        meta: { title: 'Runtime', eyebrow: 'Runtime' }
      },
      {
        path: 'models',
        name: 'workspace-runtime-models',
        component: RuntimeModelsPage,
        meta: { title: 'Runtime Models', eyebrow: 'Runtime' }
      },
      {
        path: 'tools',
        name: 'workspace-runtime-tools',
        component: RuntimeToolsPage,
        meta: { title: 'Runtime Tools', eyebrow: 'Runtime' }
      }
    ]
  },
  {
    path: 'graphs',
    name: 'workspace-graphs',
    component: GraphsPage,
    meta: { title: 'Graphs', eyebrow: 'Graphs' }
  },
  {
    path: 'sql-agent',
    name: 'workspace-sql-agent',
    component: SqlAgentPage,
    meta: { title: 'SQL Agent', eyebrow: 'Agent' }
  },
  {
    path: 'threads',
    name: 'workspace-threads',
    component: ThreadsPage,
    meta: { title: 'Threads', eyebrow: 'Threads' }
  },
  {
    path: 'chat',
    name: 'workspace-chat',
    component: ChatPage,
    meta: { title: 'Chat', eyebrow: 'Chat' }
  },
  {
    path: 'resources',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-resources-overview',
        component: () => import('@/modules/examples/pages/UiAssetsPage.vue'),
        meta: { title: '资源总览', eyebrow: 'Resources' }
      },
      {
        path: 'pages',
        name: 'workspace-resources-pages',
        component: () => import('@/modules/examples/pages/ResourcePageTemplatesPage.vue'),
        meta: { title: '页面模板', eyebrow: 'Resources' }
      },
      {
        path: 'components',
        name: 'workspace-resources-components',
        component: () => import('@/modules/examples/pages/ResourceComponentTemplatesPage.vue'),
        meta: { title: '组件模板', eyebrow: 'Resources' }
      },
      {
        path: 'engineering',
        name: 'workspace-resources-engineering',
        component: () => import('@/modules/examples/pages/ResourceEngineeringTemplatesPage.vue'),
        meta: { title: '工程模板', eyebrow: 'Resources' }
      },
      {
        path: 'top-picks',
        name: 'workspace-resources-top-picks',
        component: () => import('@/modules/examples/pages/ResourceTopPicksPage.vue'),
        meta: { title: '团队推荐 Top 10', eyebrow: 'Resources' }
      }
    ]
  },
  {
    path: 'ui-assets',
    redirect: '/workspace/resources',
    meta: { title: '资源总览', eyebrow: 'Resources' }
  },
  {
    path: 'testcase',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-testcase',
        redirect: '/workspace/testcase/generate',
        meta: { title: 'Testcase', eyebrow: 'Testcase' }
      },
      {
        path: 'generate',
        name: 'workspace-testcase-generate',
        component: TestcaseGeneratePage,
        meta: { title: '用例生成', eyebrow: 'Testcase' }
      },
      {
        path: 'cases',
        name: 'workspace-testcase-cases',
        component: TestcaseCasesPage,
        meta: { title: '用例管理', eyebrow: 'Testcase' }
      },
      {
        path: 'documents',
        name: 'workspace-testcase-documents',
        component: TestcaseDocumentsPage,
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

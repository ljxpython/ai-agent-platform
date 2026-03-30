# Platform Web

`apps/platform-web` 是当前平台工作台前端。

它不再是通用 LangGraph 示例前端，而是一个基于 Next.js App Router 的平台控制面 UI，主要负责：

- 登录与工作区导航
- 项目、用户、成员、审计等管理页面
- Assistant / graph / runtime capability 管理入口
- Chat / thread 视图
- 调用 `platform-api` 的 `/_management/*` 与 `/api/langgraph/*`

## 当前职责边界

### 负责

- 平台工作台界面与交互
- 认证态保持（浏览器 token）
- 工作区 query-state（`projectId` / `assistantId` / `threadId` 等）
- 管理面 API 调用
- 聊天 UI 与 LangGraph SDK 前端集成

### 不负责

- 平台数据库与权限判定（由 `apps/platform-api` 负责）
- Graph 真正执行（由 `apps/runtime-service` 负责）

## 当前入口与主要路由

- `/`：根据登录态跳转到 `/workspace/projects` 或 `/auth/login`
- `/auth/login`：用户名/密码登录
- `/workspace/chat`
- `/workspace/testcase`
- `/workspace/testcase/generate`
- `/workspace/testcase/cases`
- `/workspace/testcase/documents`
- `/workspace/sql-agent`
- `/workspace/threads`
- `/workspace/graphs`
- `/workspace/assistants`
- `/workspace/runtime/*`
- `/workspace/projects`
- `/workspace/users`
- `/workspace/me`
- `/workspace/security`
- `/workspace/audit`

## 快速启动

1. 安装依赖

```bash
pnpm install
```

2. 准备环境文件

```bash
cp .env.example .env
```

3. 启动开发服务器

```bash
pnpm dev
```

默认访问：`http://localhost:3000`

## 最重要的环境变量

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_PLATFORM_API_URL`（可选，优先于 `NEXT_PUBLIC_API_URL`）
- `NEXT_PUBLIC_ASSISTANT_ID`（仅保留给 chat fallback / direct runtime 场景）
- `LANGGRAPH_API_URL`（仅 Next passthrough route 使用）
- `LANGSMITH_API_KEY`（仅 server passthrough 使用）
- `FRONTEND_LOGS_DIR`
- `FRONTEND_SERVER_LOG_FILE`
- `FRONTEND_CLIENT_LOG_FILE`

当前管理面真实连接口径以 `src/lib/management-api/client.ts` 为准。

## 推荐阅读顺序

1. `README.md`
2. `docs/README.md`
3. `docs/onboarding.md`
4. `docs/current-architecture.md`
5. `docs/local-dev.md`
6. `docs/testing.md`
7. `docs/agent-chat-template.md`
8. `docs/testcase-workspace.md`

## 当前代码入口

- `src/app/layout.tsx`：根布局与全局 auth guard
- `src/app/workspace/layout.tsx`：工作区布局
- `src/app/workspace/sql-agent/page.tsx`：基于 Base Chat Template 的 agent 专属页面示例
- `src/components/platform/workspace-shell.tsx`：主导航与 shell
- `src/components/chat-template/base-chat-template.tsx`：内部复用的 chat 模板基座
- `src/providers/WorkspaceContext.tsx`：工作区 query-state
- `src/providers/Stream.tsx`：chat/runtime stream provider
- `src/providers/Thread.tsx`：thread list/query provider
- `src/lib/management-api/*`：管理面 API 封装

## 与其他应用的关系

```text
platform-web
  -> /_management/*
  -> /api/langgraph/*
       platform-api
         -> postgres
         -> runtime-service
```

## 文档目录

- `docs/README.md`：文档导航
- `docs/onboarding.md`：开发者上手路径
- `docs/current-architecture.md`：当前前端结构与集成边界
- `docs/local-dev.md`：本地开发说明
- `docs/testing.md`：构建与 Playwright 验证
- `docs/agent-chat-template.md`：Agent 专属 chat 页面模板开发约定

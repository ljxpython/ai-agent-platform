# 当前架构说明

这份文档只描述 `apps/platform-web` 当前真实实现，不再沿用旧的通用 demo 产品叙事。

## 1. 产品定位

当前 `platform-web` 是平台工作台前端，负责：

- 登录与鉴权态跳转
- 工作区导航
- 平台管理页面
- Chat / thread 体验
- 与 `platform-api` 的管理面和 LangGraph 网关联动

## 2. 根布局与入口

### 2.1 根布局

`src/app/layout.tsx` 当前负责：

- 注入 `NuqsAdapter`
- 包裹 `GlobalAuthGuard`
- 设置全局 metadata

### 2.2 根路由

`src/app/page.tsx` 当前不展示 setup form，而是：

- 已登录 -> `/workspace/projects`
- 未登录 -> `/auth/login`

### 2.3 登录页

`src/app/auth/login/page.tsx` 通过 `/_management/auth/login` 登录，并把 token 存入本地存储。

## 3. 工作区结构

`src/app/workspace/layout.tsx` 当前组合：

- `WorkspaceAuthGuard`
- `WorkspaceProvider`
- `LogBootstrap`
- `WorkspaceShell`

`WorkspaceShell` 暴露的主导航包括：

- Chat
- Threads
- Graphs
- Assistants
- Runtime
- Projects
- Users
- My Profile
- Security
- Audit

## 4. 当前状态管理模型

### 4.1 工作区状态

`src/providers/WorkspaceContext.tsx` 是当前共享状态入口。

它依赖 URL query state（`nuqs`）维护：

- `projectId`
- `assistantId`
- `threadId`

切换项目时会清理 thread / assistant 相关状态。

### 4.2 Chat / thread 状态

- `src/providers/Thread.tsx`：thread 查询与列表
- `src/providers/Stream.tsx`：运行时 stream、assistant/graph 选择、消息与 UI event 合并

## 5. API 集成边界

### 5.1 管理面 API

`src/lib/management-api/client.ts` 当前优先从以下来源解析 base URL：

1. `NEXT_PUBLIC_PLATFORM_API_URL`
2. `NEXT_PUBLIC_API_URL`
3. `localStorage("lg:platform:apiUrl")`
4. `http://localhost:2024`

典型调用：

- `/_management/auth/*`
- `/_management/projects/*`
- `/_management/assistants/*`
- `/_management/catalog/*`
- `/_management/runtime/*`

### 5.2 LangGraph 运行时交互

当前 chat/thread 交互主要走：

- `/api/langgraph/*`（平台后端网关）

前端仍保留 `src/app/api/[..._path]/route.ts` 的 Next passthrough route，但这不是当前平台工作台的主叙事，只是可选兼容能力。

## 6. 当前页面实现模式

管理页当前普遍采用：

- client component
- `useEffect + useState + useCallback`
- 手写 API wrapper
- 平台共用组件：
  - `ListSearch`
  - `PaginationControls`
  - `PageState*`
  - `ConfirmDialog`
  - `useResizableColumns`

## 7. 与其他应用的关系

```text
platform-web
  -> /_management/*
  -> /api/langgraph/*
       platform-api
         -> postgres
         -> runtime-service
```

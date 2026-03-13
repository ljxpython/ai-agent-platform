# 开发者上手路径

## 1. 先建立正确心智模型

当前 `platform-web` 不是单纯的 LangGraph demo chat UI，而是平台工作台前端：

- 登录入口
- 工作区导航
- 管理面页面
- Chat / Threads
- 通过 `platform-api` 访问 `/_management/*` 与 `/api/langgraph/*`

## 2. 建议阅读顺序

### 第一天必读

1. `../README.md`
2. `docs/current-architecture.md`
3. `docs/local-dev.md`
4. `docs/testing.md`

### 按需深读

- 改工作区导航：`src/components/platform/workspace-shell.tsx`
- 改工作区 query-state：`src/providers/WorkspaceContext.tsx`
- 改 chat/runtime 行为：`src/providers/Stream.tsx`、`src/providers/Thread.tsx`
- 改管理面接口：`src/lib/management-api/*`

## 3. 当前模块地图

```text
src/
  app/
    auth/              # 登录页
    workspace/         # 工作区页面
    api/[..._path]/    # 可选 Next passthrough route
  components/platform/ # 工作台组件、导航、guards、表格工具
  components/thread/   # Chat / thread UI
  providers/           # Workspace / Stream / Thread providers
  lib/management-api/  # 平台管理面 API 客户端
  lib/oidc-storage.ts  # token 与 API URL 本地存储
```

## 4. 你要改什么，就去哪里

### 新增工作区页面

- 路由：`src/app/workspace/<feature>/page.tsx`
- 共用导航：`src/components/platform/workspace-shell.tsx`

### 新增/修改管理面接口调用

- `src/lib/management-api/<feature>.ts`
- 底层 client：`src/lib/management-api/client.ts`

### 修改聊天与 runtime 交互

- `src/providers/Stream.tsx`
- `src/providers/Thread.tsx`
- `src/components/thread/*`

### 修改工作区上下文

- `src/providers/WorkspaceContext.tsx`
- 当前共享状态优先走 URL query state（`nuqs`），不是另起全局 store

## 5. 当前最重要的约定

- 工作区状态以 query params 为准：`projectId` / `assistantId` / `threadId` / `targetType`
- 管理面调用统一走 `src/lib/management-api/*`
- 项目边界通过 `x-project-id` 传给后端
- 管理页主要是 client component + `useEffect/useState/useCallback`
- Chat 页通过 provider 组合运行，不要直接绕开 `WorkspaceProvider` / `ThreadProvider` / `StreamProvider`

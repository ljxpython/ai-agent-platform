# 03. 目标前端架构与编码规范

## 目标技术栈

正式迁移如果确定切到 Vue，建议目标栈如下：

- `Vue 3`
- `Vite`
- `TypeScript`
- `Vue Router`
- `Pinia`
- `Axios`
- `Tailwind CSS 3`
- `Vitest`

## 为什么先保持 Tailwind 3

虽然我们现有 React 方案里用过 Tailwind 4，但当前这次迁移不建议一上来就升级。

原因：

- `sub2api` 当前样式系统就是基于 Tailwind 3
- 一上来升级 Tailwind 4 会引入额外兼容成本
- 老板要的是“先看见好结果”，不是先看你升级工具链

结论：

- 第一阶段保持 Tailwind 3
- 等 UI 与业务稳定后，再评估是否升级 Tailwind 4

## 目标目录结构

正式 app 不建议继续沿用上游扁平目录。

建议结构如下：

```text
apps/platform-web-vue/
  package.json
  vite.config.ts
  tsconfig.json
  public/
  src/
    main.ts
    App.vue
    router/
      index.ts
      guards.ts
      routes/
        auth.ts
        workspace.ts
    layouts/
      AuthLayout.vue
      WorkspaceLayout.vue
    stores/
      auth.ts
      workspace.ts
      ui.ts
      theme.ts
    services/
      http/
        client.ts
      auth/
        auth.service.ts
      projects/
        projects.service.ts
      users/
        users.service.ts
      assistants/
        assistants.service.ts
      graphs/
        graphs.service.ts
      runtime/
        runtime.service.ts
      audit/
        audit.service.ts
      threads/
        threads.service.ts
      testcase/
        testcase.service.ts
    modules/
      overview/
      projects/
      users/
      assistants/
      graphs/
      runtime/
      sql-agent/
      threads/
      chat/
      testcase/
      account/
      audit/
    components/
      base/
      layout/
      platform/
    composables/
    styles/
    types/
    utils/
```

## 路由规范

### 1. 用嵌套路由管理 layout

不能继续用：

- 每个页面自己包一层 `AppLayout`

建议统一成：

- 路由级 layout

例如：

```ts
{
  path: "/workspace",
  component: WorkspaceLayout,
  children: [...]
}
```

这样好处很直接：

- layout 职责清晰
- 页面文件更干净
- 后续权限守卫和上下文注入更统一

### 2. 路由按业务域拆文件

不要把所有路由继续堆在一个 `router/index.ts` 里。

建议拆为：

- `routes/auth.ts`
- `routes/workspace.ts`

后面如果模块变大，再继续拆分：

- `routes/testcase.ts`
- `routes/runtime.ts`

## 状态规范

### 1. Pinia 只管全局状态

Pinia 只应该放这些：

- 当前用户
- token / refresh token
- 当前项目上下文
- 全局 theme
- 全局 UI 状态

不要把所有页面数据都塞进 store。

### 2. 页面数据优先放 composable

例如：

- `useProjectsList`
- `useAssistantDetail`
- `useThreadHistory`
- `useTestcaseDocuments`

这样比“巨型 store”更适合我们这种工作台型页面。

## API 规范

### 1. API 模块按域拆分

不能延续“一个 `api/admin/*` 包天下”的组织方式。

建议按我们自己的业务拆：

- `services/projects`
- `services/users`
- `services/assistants`
- `services/graphs`
- `services/runtime`
- `services/audit`
- `services/threads`
- `services/testcase`

### 2. 页面禁止直接写裸请求

页面里不允许出现：

- 直接 `axios.get(...)`
- 直接拼 URL
- 直接写 token header

页面只能调：

- `service`
- `composable`

### 3. API 类型必须收口

每个业务域都要有自己的返回类型和入参类型。

不能让 `any` 在迁移期乱飞。

## 组件规范

### 1. 基础组件与业务组件分层

组件分成三层：

1. `components/base`
   - button
   - input
   - select
   - modal
   - table
   - badge
2. `components/layout`
   - sidebar
   - topbar
   - page container
3. `components/platform`
   - 项目切换器
   - thread 列表面板
   - testcase 文档预览卡
   - assistant 详情块

### 2. 不允许继续堆巨型页面组件

建议约束：

- 单文件页面尽量控制在 `200` 行上下
- 超过 `300` 行的页面默认要拆

这不是教条，是为了防止把 `sub2api` 现有那种“大而全页面”问题原样搬进来。

## 文案与国际化规范

当前阶段建议：

- 保留 `vue-i18n` 能力
- 但迁移第一阶段只维护 `zh-CN`

原因：

- 减少迁移工作量
- 保留后续扩展空间
- 不让页面文案散落硬编码

## 测试与质量门禁

正式迁移后，最低门禁建议如下：

- `pnpm lint`
- `pnpm typecheck`
- `pnpm build`

复杂模块增加：

- `Vitest` 单测
- 页面烟测

重点烟测页面：

- 登录
- 项目切换
- assistants
- chat
- threads
- testcase 三个子页

## 结论

如果正式切 Vue，这次必须顺手把工程规范也一起切对。

不然最后只会得到一个结果：

- 页面变好看了
- 代码结构比原来还乱

这事不能干。

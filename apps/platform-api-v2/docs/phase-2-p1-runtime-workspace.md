# Phase 2 / P1 运行工作台稳定化

这份文档记录第二阶段 `P1 运行工作台稳定化` 的收敛结果。

## 1. 目标

把 `platform-web-vue` 中和运行工作台直接相关的四块入口拉到同一条轨道：

- `chat`
- `threads`
- `sql-agent`
- `testcase generate`

目标不是重写页面壳，而是把 runtime 细节收回服务层，统一状态语义和验收口径。

## 2. 本轮发现的核心问题

改造前主要有 3 个明显问题：

1. `thread / run / stream / cancel / history / state` 能力散在页面和 composable 里
2. `ThreadsPage` 自己维护了一套详情、历史和错误态，和 `BaseChatTemplate + useChatWorkspace` 脱节
3. 部分失败场景只有一条笼统报错，用户分不清是：
   - 线程列表失败
   - 当前 thread 详情失败
   - 只有 `state/history` 局部失败
   - 登录态失效或权限被拒

## 3. 已落地改造

### 3.1 runtime gateway 工作台服务收敛

新增：

- `apps/platform-web-vue/src/services/runtime-gateway/workspace.service.ts`

现在由这层统一承接：

- thread 列表
- thread 详情
- thread state
- thread history
- create thread
- stream run
- cancel run
- update thread state
- delete thread
- 运行时错误归一化
- 权限拒绝文案归一化

兼容出口：

- `apps/platform-web-vue/src/services/threads/threads.service.ts`

保留原导出名，避免旧调用点瞬间炸掉。

### 3.2 Chat 工作台状态语义统一

改造文件：

- `apps/platform-web-vue/src/modules/chat/composables/useChatWorkspace.ts`
- `apps/platform-web-vue/src/modules/chat/components/BaseChatTemplate.vue`

补齐内容：

- `detailWarning`
  - 当 thread 基础信息成功，但 `state/history` 局部失败时，不再直接黑盒报错
- `accessDeniedMessage`
  - 把 `401 / 403` 归一成清晰的无权限提示
- `create / stream / cancel / updateState / delete`
  - 页面层不再直接碰 LangGraph SDK
- 空态 / 加载态 / 中断态 / 重试态 / 无权限态
  - 统一在同一套 chat 基座内处理

### 3.3 Threads 页面与 Chat 基座对齐

改造文件：

- `apps/platform-web-vue/src/modules/threads/pages/ThreadsPage.vue`

现在 `ThreadsPage` 也共用同一套 runtime snapshot 装载逻辑：

- 列表错误单独处理
- 详情错误单独处理
- `state/history` 局部失败单独提示
- 无权限时直接进入明确 empty state

### 3.4 SQL Agent / Testcase Generate 验收口径统一

页面仍继续复用：

- `BaseChatTemplate`

含义是：

- `sql-agent`
  - 查询、上下文、结果、异常展示遵守 chat 基座同一套规则
- `testcase generate`
  - thread / history / 运行参数 / 中断 / 重试也遵守同一套规则

本轮没有再造第二套工作台 UI。

## 4. 验证

已完成：

```bash
pnpm --dir apps/platform-web-vue build
```

验证结论：

- 前端类型检查通过
- `chat / threads / sql-agent / testcase generate` 的共享运行服务收敛完成
- 运行工作台不再继续散落 runtime 细节到页面层

## 5. 当前边界

P1 已经把“工作台稳定化”这件事做成了正式基座，但还没做：

- operation 驱动的真正异步长任务 UI
- project 级 policy overlay 真正写库接入
- runtime refresh 走 operation 的前端编排

这些都留到 phase-2 后续条目处理。

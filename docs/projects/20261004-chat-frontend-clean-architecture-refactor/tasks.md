# Chat 前端对话架构治理与 Clean Architecture 重构 - 任务拆分

## Phase 1: 视口与运行时参数逻辑剥离

### Task 1.1: 抽离 `useChatRunConfig.ts`
- **改动内容：** 将 `ChatSession.vue` 中模型列表加载、缓存、运行参数草稿（Temperature、MaxTokens、ExecutionMode）、弹窗状态等从组件 setup 中剥离为独立 Composable。
- **代码位置：** 新建 `apps/platform-web/src/modules/chat/composables/useChatRunConfig.ts`
- **预期结果：** 暴露 `models`, `modelsLoading`, `draftRunOptions`, `openOptions`, `applyOptions` 等干净接口，组件内无需处理异步模型加载与草稿赋值。
- **验证项：** 编写 `useChatRunConfig.spec.ts` 并验证参数重置与提交行为正确。
- **状态：** `[x]` 已完成

### Task 1.2: 抽离 `useChatViewport.ts`
- **改动内容：** 将 `ChatSession.vue` 中 300+ 行关于滚动触底判断、用户向上滚动打断跟随、流式打字持续跟随、最新轮次锚定（Anchor）、动态 Spacer 高度计算等 DOM 计算与生命周期监听抽离为独立 Composable。
- **代码位置：** 新建 `apps/platform-web/src/modules/chat/composables/useChatViewport.ts`
- **预期结果：** 提供统一的 `follow()`, `anchorLatestUserTurn()`, `handleScroll()`, `bottomSpacerHeight` 响应式对象与方法，消除组件中的 DOM 杂质。
- **验证项：** 编写 `useChatViewport.spec.ts` 验证滚动计算逻辑无误。
- **状态：** `[x]` 已完成

---

## Phase 2: 动作编排与分支逻辑解耦

### Task 2.1: 抽离 `useChatActions.ts`
- **改动内容：** 将 `ChatSession.vue` 中消息重试（retryMessage）、会话分支分叉（forkToNewThread）、历史快照按需拉取（loadHistory）、历史消息编辑（edit/submitEditedBranch）等纯动作编排抽离。
- **代码位置：** 新建 `apps/platform-web/src/modules/chat/composables/useChatActions.ts`
- **预期结果：** `ChatSession.vue` setup 代码量削减，动作执行失败统一走标准错误出口。
- **验证项：** 运行 `ChatSession.spec.ts` 确保分支分叉、重试、历史加载逻辑无退化。
- **状态：** `[x]` 已完成

---

## Phase 3: 消息转录流水线（Message Pipeline）重构

### Task 3.1: 规范化 `useTranscriptMessages.ts` 纯函数归约管道
- **改动内容：** 重构 `useTranscriptMessages.ts`，建立基于事件溯源的单向纯函数 Pipeline：
  1. 快照基准层（Snapshot Base）；
  2. 实时增量层（Delta Chunks & Live Reasoning 纯函数注入）；
  3. 本地乐观暂存层（Optimistic Echoes）；
  消除随意就地突变与复杂难以理解的防洪 ad-hoc 判断。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- **预期结果：** 消息时序 100% 正序稳定，思维链实时推流无卡顿，流式结束无闪烁。
- **验证项：** 运行 `useTranscriptMessages.spec.ts` 10 项全绿通过。
- **状态：** `[x]` 已完成

---

## Phase 4: 会话连接与状态机拆解收敛

### Task 4.1: 拆解 `useSessionConnection.ts`
- **改动内容：** 从 `useChatSession.ts` 中抽取 SSE 流生命周期管理、连接状态订阅、410 游标过期自愈、SWR 乐观权限护栏等纯传输与网络逻辑。
- **代码位置：** 新建 `apps/platform-web/src/modules/chat/composables/useSessionConnection.ts`
- **预期结果：** 纯粹处理网络连接与流恢复，对业务层只抛出连接状态与标准错误。
- **验证项：** 运行 `useSessionConnection.spec.ts` 验证通过。
- **状态：** `[x]` 已完成

### Task 4.2: 精简 `useChatSession.ts` 门面与状态收敛
- **改动内容：** 接入 `useSessionConnection`，清理悬空引用与重复的 ACL 监听，收敛会话连接、状态管理与操作逻辑，保持对外导出的完整契约兼容。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- **预期结果：** 外部调用签名保持 100% 契约不变，内部完全解耦。
- **验证项：** 运行 `useChatSession.spec.ts` 27 项全部通过。
- **状态：** `[x]` 已完成

---

## Phase 5: 全量回归与项目闭环

### Task 5.1: 静态检查与全量单测回归
- **改动内容：** 执行 `vue-tsc --noEmit` 及全仓 429 套前端单测全量回归。
- **验证项：** 0 errors，429 passed。
- **状态：** `[x]` 已完成

### Task 5.2: 生产构建验证与文档同步
- **改动内容：** 执行 `pnpm build` 确认打包无警告无报错，同步更新 `docs/CONTEXT.md`。
- **验证项：** 生产构建 14.89s 成功完成。
- **状态：** `[x]` 已完成

---

## Phase 6: 中断状态治理与消息队列时序修复

### Task 6.1: 修复手动停止/取消与虚假中断状态
- **改动内容：**
  - `ChatAgentStatusBar.vue` 移除对手动终止任务弹出的无意义“继续生成”和空 resume 请求，避免触发后端 `Resume requires interrupt IDs` 400 报错；
  - `ChatSession.vue` 中仅当真正存在 `hasPendingInterrupts` 或 `reviews` 时才将会话标记为中断等待状态；
  - 精简 `ChatAgentStatusBar.vue`，明确当且仅当存在人工确认/审批时才展示“查看审批”；
  - 编写 `ChatAgentStatusBar.spec.ts` 锁定该行为。
- **状态：** `[x]` 已完成

### Task 6.2: 修复消息队列出队与乐观消息时序倒挂
- **改动内容：**
  - 根治 `ChatSession.vue` 中新消息插入时倒退搜索导致倒挂在上一轮 Human 之后、AI 之前的严重时序 BUG；
  - 将消息对齐算法抽离为纯函数模块 `apps/platform-web/src/modules/chat/message-alignment.ts`；
  - 基于历史基线切片锚定法保证新出队/发送消息绝对紧随上一轮 Agent 之后，AI 流式响应时严格保持一问一答时序；
  - 编写 `message-alignment.test.ts`（7 套场景）全面覆盖出队定位、并发防重、连续用户消息隔离。
- **状态：** `[x]` 已完成

---

## Phase 7: 多轮会话视口平滑锚定与流式滚动保护修复

### Task 7.1: 修复多轮对话下用户最新消息 DOM 匹配与垫片 Clamp 截停
- **改动内容：**
  - 重写 `useChatViewport.ts` 中 `getLatestUserElement`：使用 `querySelectorAll('article[data-author="user"]')` 数组末尾元素，彻底消除 `:last-of-type` 在多 author 混合 article 下无法匹配最后一个 user 的 BUG；
  - 在 `anchorLatestUserTurn` 中，计算并修改 `bottomSpacerHeightPx.value` 之后增加 `await nextTick()`，确保 DOM 垫片尺寸真实撑开 `scrollHeight` 后再调用 `vp.scrollTo`，彻底解决浏览器将平滑滚动直接限制（clamp）在旧内容底部导致新消息滚不到位的致命缺陷。
- **状态：** `[x]` 已完成

### Task 7.2: 消除平滑滚动期间流式跟随竞态截杀与误判上滑
- **改动内容：**
  - 在 `requestSmartStreamingFollow` 内部增加 `Date.now() < programmaticScrollUntil` 互斥保护，禁止在锚定平滑滚动进行中强行截停并改写 `scrollTop`；
  - 在 `handleViewportScroll` 内部对于 `isProgrammatic` 期间纯粹同步当前滚动位置并立即 return，绝不把平滑动画的插值帧误判为用户手动上滑打断跟随；
  - 简化 `options.displayedMessages` watcher，只要检测到新用户回合（`nextHumanCount > prevHumanCount`），强制恢复跟随并执行平滑锚定，消除此前因提前给 `lastAnchoredTurnCount` 赋值导致新回合被短路遗漏的隐患；
  - 清理未使用的 `lastAnchoredTurnCount` 变量。
- **状态：** `[x]` 已完成

### Task 7.3: 自动化测试与全量回归
- **改动内容：**
  - 在 `useChatViewport.spec.ts` 中增加针对程序平滑滚动保护、新回合自动恢复跟随的自动化用例；
  - 执行 `pnpm typecheck`（0 errors）；
  - 执行前端全量单测 `pnpm test:run`（102 passed, 444 passed）；
  - 执行生产构建 `pnpm build`（成功）。
- **状态：** `[x]` 已完成

## 进度追踪
- [x] Phase 1 视口与运行时参数逻辑剥离
- [x] Phase 2 动作编排与分支逻辑解耦
- [x] Phase 3 消息转录流水线重构
- [x] Phase 4 会话连接与状态机拆解收敛
- [x] Phase 5 全量回归与项目闭环
- [x] Phase 6 中断状态治理与消息队列时序修复
- [x] Phase 7 多轮会话视口平滑锚定与流式滚动保护修复

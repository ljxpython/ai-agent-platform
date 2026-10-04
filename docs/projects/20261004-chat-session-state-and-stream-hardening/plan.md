# Chat 会话状态机加固与流式体验优化 - 整体方案

## 背景
在 Thread `ce88ceb8-8907-4c4b-af94-3d489df7167f` 的 Dear Agent 对话中，暴露出以下几类严重的交互与状态机缺陷：
1. **排队消息 Banner 误报**：界面底部突然弹出黄色横条：“排队补充消息 0 ... ⓘ 投递状态读取失败，请刷新”，即使队列中毫无消息；
2. **页面权限误判失效**：切出前台或失焦唤醒时，界面突然跳出“当前页面权限已失效”，把合法用户踢出当前工作区；
3. **状态指示器冲突**：模型已触发 `request_information` 中断等待用户填表澄清，但底部依然显示“Agent 正在处理当前回合”；
4. **首轮思考流式缺失**：DeepSeek 等思维链模型首先输出数百 token 的 `reasoning-delta`，前端在思考期间呈现白板停滞，思考结束和工具调用生成后突兀一次性弹出全部内容。

## 目标
1. 彻底消灭 `QueuedMessagesBanner` 在空队列场景下的异常渲染，空队列轮询失败静默重试。
2. 加固 `workspaceStore.refreshCurrentProjectAccess` 的容错机制，避免网络抖动或 Token 并发刷新时把现有项目权限置空。
3. 修正 `ChatMessageList.vue` 的 `shouldShowLiveStep` 计算逻辑，确保在会话挂起/中断/澄清期间立即隐藏“Agent 正在处理当前回合”。
4. 优化思维链（Reasoning）在流式期间的渐进反馈，确保用户能清晰感知到模型正在思考。

## 方案设计

### 1. `QueuedMessagesBanner.vue` 显隐条件加固
- **改动文件：** `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue`
- **方案：**
  - 修改 `v-if` 条件：仅在 `totalCount > 0`（即 `queueItems.length > 0 || receipts.length > 0 || pendingMessage`）时展示该横条；
  - 如果 `totalCount === 0`，即使后台有 `receiptError`，绝不在前台渲染任何横条。轮询错误由 composable 内部定时器按指数退避或静默重试即可。

### 2. `workspaceStore.ts` 权限刷新容错（防误踢）
- **改动文件：** `apps/platform-web/src/stores/workspace.ts`
- **方案：**
  - 在 `refreshCurrentProjectAccess` 的 `catch` 分支中，除非明确判定是 403 Forbidden（确实无权），否则对于网络异常、401（Token 刷新中）或 5xx，保留现有的 `this.currentProjectAccess`，不将其踩空设为 `null`；
  - 避免 `WorkspaceLayout.vue` 的计算属性 `routeAccessAllowed` 误判为 `false`。

### 3. `ChatMessageList.vue` 的 `shouldShowLiveStep` 状态判定修复
- **改动文件：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- **方案：**
  - 如果 `props.isInterrupted` 为 `true`，直接返回 `false`；
  - 检查最后一个回合中的工具调用：若包含 `request_information` 等需要人工补充信息的澄清工具，或者工具处于等待用户交互状态（而非单纯的后台代码执行中），不计入 `hasRunningTools`，立即让位于澄清表单/等待补充信息提示。

### 4. 流式思考与正文渲染优化
- **改动文件：** `apps/platform-web/src/modules/chat/transcript.ts` / `ChatMessageList.vue`
- **方案：**
  - 梳理正在流式过程中的消息块判定：当首轮输出以思维链为主且尚未有普通 text 产生时，确保占位状态或思维链气泡能够处于活跃流动状态，消除长时间卡顿假死的视觉错觉。

## 风险和依赖
- **兼容性：** 改动全在 `platform-web` 内部，不涉及后端契约变更。
- **回归测试：** 需确保既有 ChatPage、DearAgentPage、审批流、排队补充消息发送等测试用例全部通过。

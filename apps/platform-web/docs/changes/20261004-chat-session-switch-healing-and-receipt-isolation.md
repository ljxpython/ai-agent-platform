# 修复多会话切换切回假死死锁、空白消息水合缺失与投递报错误伤

## 背景

用户在会话连续追问后切到其他新会话，切回原会话时出现三项严重缺陷：

1. **状态机假死与队列死锁**：后端 3 个 Run 均早已执行成功，但前端切回后 `isSessionRunning` 与 `busy` 依然卡死为 `true`，用户新输入的内容被强行推入待执行队列且永远发不出去，输入框悬挂【补充要求】和【停止生成】；
2. **AI 回复空白**：切走导致流式中断后，切回时未主动水合最新落盘检查点，且 `displayedMessages` 中 `missingSuffix` 因 `isSessionRunning` 为 `true` 被判空裁剪，导致最新已落盘回复只剩头像与空白气泡；
3. **投递状态报错误伤**：后台轮询 `listThreadMessages` 时因网络瞬态波动抛错，直接在本地纯前端待执行队列上方粗暴抛出红字“投递状态读取失败，请刷新”。

## 改动内容

1. **`useChatSession.ts`**：
   - 在 `verify()` 终态处理中（`!active(run.value)`），强制将 `stream.isLoading.value = false`、`streamInFlight.value = false`，并调用 `actions.acknowledge()` 归位提交态，彻底打破状态机假死闭环；
   - 在 `refreshReceipts()` 中增加对 Axios 取消（`ERR_CANCELED` / `CanceledError` / `AbortError`）的识别与过滤，并限定仅在存在待投递的 `pendingMessage` 或已有 `receipts` 时才记录错误，后台空队列轮询静默容错；
   - 补充终态 Run 状态收敛单测用例。

2. **`ChatSession.vue`**：
   - 优化 `watch(() => props.visible)`：当切回会话且当前 Run 已终态时，立即触发轻量历史水合（`loadHistory(true, 10)`），并自动唤醒 `drainNextQueuedItem()` 消费滞留的排队消息；
   - 优化 `displayedMessages`：在末尾 AI 消息内容为空且后续已落盘历史存在时放行水合并替换空占位符，杜绝空头像问题；
   - 严防用户问题倒挂：重构 `hasOptimisticEchoed` 支持复杂数组/对象 Content 文本比对与 `isHumanMessage` 类型识别，并在 `displayedMessages` 中将运行期乐观消息前置到当前运行轮次的最开端，彻底杜绝用户提问排在模型思考/回复下方的时序倒挂；
   - 彻底解放后台队列自动消费：移除 `drainNextQueuedItem` 和 `watch(queueLen)` 中人为限制的 `props.visible === false` 阻断，让切到后台的会话能自主顺延消费队列并发起执行。

3. **`useTranscriptMessages.ts`**：
   - 彻底重构 snapshot 权威检查点与增量流式消息的合并机制：严格以 snapshot 为正序时序基底，融入增量实时 live reasoning，并将未落盘的新增量追加在末尾，彻底根除切回重连时把 snapshot 历史前序消息 `push` 到末尾导致的时间线彻底颠倒顽疾；
   - 补充时序保护定向单元测试。

4. **`WorkspaceLayout.vue` & `workspace.ts`**：
   - 将 `refreshingAccess` 声明为真正的响应式 `ref(false)`，并在 `refreshCurrentProjectAccess` 期间严谨维护 `accessLoading` 生命周期；
   - 实装 Google 工业级 Stale-While-Revalidate 乐观权限护栏：在窗口切回失焦唤醒刷新期间，只要本地已有当前项目的有效授权，坚决保持现有权限，彻底消灭因网络瞬态抖动误判导致的“当前页面权限已失效”全屏拦截与会话池自毁误杀。

5. **`QueuedMessagesBanner.vue`**：
   - 隔离 `receiptError` 警告与错误横幅判定，仅在存在真实投递（`pendingMessage` 或 `receipts`）时才展示投递错误，避免污染本地纯前端 `promptQueue`。

## 涉及文件

- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.spec.ts`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue`
- `apps/platform-web/src/layouts/WorkspaceLayout.vue`
- `apps/platform-web/src/stores/workspace.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`

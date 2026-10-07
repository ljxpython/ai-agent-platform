# 修复消息排队提交未决死锁、会话切换幽灵锁与双重自愈容错

## 背景

用户在会话连续追问或消息排队期间切换到其他会话，切回原会话时界面顶部挂起警告横幅：
`排队提交结果待确认；请用原消息和原幂等键重试。 核实并重试`，且输入框无法继续发送新消息。

根本原因分析：

1. **会话切换 Key 漂移导致幽灵锁无法清理**：`useServerPromptQueue` 中 `remember(null)` 清除本地持久化锁时动态依赖了响应式 `options.storageKey.value`。当请求在后台未完成或响应延迟时，若用户切走会话，`storageKey` 变更为新会话 Key，导致原会话在 `localStorage` 中的待确认锁（`submitted_queue:...`）未被正确删除，切回原会话时被重新反序列化挂载；
2. **自愈逻辑过于严苛**：`refresh()` 原先仅在 `queuedRuns`（即当前处于 `status=pending` 的排队列表）中匹配 `client_queue_id`。若该任务在切走期间已被 Worker 取出执行（状态流转为 `running`/`success`/`error`/`interrupted`），或接口异常，`queuedRuns` 中永远查不到它，导致自愈判定死锁；
3. **缺少主动放弃/恢复逃生通道**：原横幅仅提供【核实并重试】按钮，在网络波动或多次核实失败时，用户无法主动丢弃锁并拿回草稿，被 `if (pending.value) throw ...` 彻底卡死。

## 改动内容

1. **`useServerPromptQueue.ts`**：
   - 彻底解耦 `submitting`（正在提交）与 `unconfirmed`（未决待确认）状态机：入队时记录 `status: "submitting"`，只有真正发生未决网络异常、超时或从 Storage 恢复时才转为 `unconfirmed`，彻底根除正常入队网络传输期间（约数十毫秒至数百毫秒）误弹黄色待确认横幅的闪现 Bug；
   - 增强连击防重：当有上一个请求正在提交时，内部平滑等待串行化入队，杜绝用户手速快连续排队第二条消息被误拒；
   - 增强 `PendingPromptSubmission` 结构，强绑定创建时的 `threadId`、`storageKey` 与 `createdAt`；
   - 提取 `clearPending(item)`：优先按待确认实体自带的 `storageKey` 进行定向清除，彻底杜绝切换会话时 `removeItem` 误伤或遗留幽灵锁；
   - 在 `watch(options.threadId)` 中加入防串会话与超过 30 分钟远古脏记录的自动清除逻辑；
   - 增强 `refresh()` 双重自愈：不仅匹配排队队列 `queuedRuns`，当排队队列无匹配时自动向下探测最近执行记录 `runs(threadId)`，一旦检测到任务已落地执行即自动解除待确认锁；
   - 导出 `dismiss()` 方法，支持主动释放待确认锁并返回待入队消息内容。

2. **`ChatSession.vue`**：
   - 待确认横幅增加【放弃并恢复草稿】逃生按钮；
   - 实现 `handleDismissPendingQueue`：释放锁并将消息原样恢复至输入框（调用 `restoreQueuedDraft`），确保用户草稿零丢失且随时可脱困。

3. **`useServerPromptQueue.spec.ts`**：
   - 补充 6 项高覆盖率针对性单元测试，覆盖正常入队清理、跨会话 Key 漂移清除、排队列表自愈、历史运行记录自愈、手动 dismiss 恢复草稿、以及远古过期记录丢弃场景。

## 涉及文件

- `apps/platform-web/src/modules/chat/composables/useServerPromptQueue.ts`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/composables/useServerPromptQueue.spec.ts`

# 会话历史关键节点过滤、时间旅行多步长加载与消息编辑分叉修复

## 背景与问题
1. **关键节点与全部 steps 数量一模一样**：
   在会话详情抽屉的历史标签中，关键节点计数和全部 steps 数量完全相同（如 181/181）。根因在于 `history-view-model.ts` 的 `isKeyMilestoneEntry` 之前采用了缺陷性的黑名单机制，大量无 tasks 或空任务的中间系统检查点由于 `tasks.length === 0` 逃逸并被误判为关键节点。
2. **时间旅行底部只能单次拉取 20 条，长对话浏览翻页极其低效**：
   在会话产生上百个 Step 时，`session.service.ts` 的 `history` 接口写死 `limit: 20`，用户必须重复点击十余次“加载更多”。
3. **点击消息下方的“编辑”后无法进入编辑，全场按钮变成只剩“复制”**：
   用户点击特定消息（如“现在请再次准备修改 report.py，将错误的统计逻辑修复。”）下方的【编辑】按钮后，界面没有弹出文本输入框，所有消息的【编辑】/【重试】全部消失只剩【复制】，无法进行时间旅行分支创建。根因：
   - `edit` 内部使用串行发起最多 200 次 HTTP 状态请求的循环，耗时极长且容易因结构不匹配中途退出；
   - 匹配函数只比对单一的 `asObject(message).id === messageId`，忽略了嵌套消息、key 标识及文本内容复合判定；
   - 在请求期间 `editLoading` 被绑定到 `canEdit` 计算属性上，导致全局所有消息的编辑按钮全部被隐藏；
   - 失败时仅静默设置 `localError`，UI 停留在只读态，无法恢复。

## 变更内容
1. **重构 `history-view-model.ts` 关键节点判定算法**：
   - 废除黑名单机制，转为严格的**业务里程碑白名单**判定：
     - 保留最新快照 (`isLatest`)；
     - 保留人工审批与中断节点 (`hasInterrupts`)；
     - 保留具有分叉或分支组的节点 (`childCount > 0 || siblingCount > 1`)；
     - 业务动作消息白名单：新产生的用户输入 (`human`)、AI 工具调用发起 (`tool_calls`)、工具执行完成返回 (`tool`) 以及非空 Agent 答复文本；
     - 精准剔除纯系统中间件 (`Middleware`/`__pregel`) 以及与父节点相比消息完全未变且无业务任务的纯状态流转帧。
2. **时间旅行多步长快速加载与快照交互醒目化**：
   - `session.service.ts`：`history` 方法支持可选 `limit` 参数（默认 20，支持 50/100 等自定义步长）。
   - `ChatContextDrawer.vue`：
     - 历史列表底部扩展为多步长快速翻页按钮组：【加载更多 (+20)】、【+50 条】、【+100 条 (快速翻页)】，并清晰提示“已加载全部历史记录”；
     - 抽屉顶部横幅区与展开卡片内直接提供【从此快照重新执行】与【关闭抽屉查看】醒目操作按钮，告别滑到底部才找得到按钮的反人类体验。
   - `ChatSession.vue`：
     - 主界面顶部横幅新增【从此快照重新执行】与【返回最新对话】操作按钮，并带快照 ID 视觉标签，无论是否关闭抽屉均能秒级直观操作。
3. **彻底重构 `ChatSession.vue` 消息编辑与分支创建 (`edit`)**：
   - **秒级响应**：用户点击【编辑】立即设置 `editingMessageId` 与 `editDraft`，在原消息卡片原地展开编辑框，消除 UI 停顿卡死；
   - **内存反查**：优先通过 `messageMetadata` 与本地 `history` 链条倒序查找父检查点，0 毫秒完成定位，杜绝 200 次串行网络请求；
   - **复合匹配增强**：支持通过 `id`、`key` 以及角色与文本内容匹配定位消息；
   - **解耦按钮锁死**：将 `ChatMessageList` 的 `:can-edit` 与 `editLoading` 解耦，确保在编辑或回溯期间不会导致全场所有编辑按钮意外隐藏成只剩“复制”；
   - **完善取消机制**：新增 `cancelEdit`，用户点击【取消编辑】安全复位状态。

4. **快照模式解锁输入框与全链路流式分叉执行 (Fork)**：
   - **解锁快照模式输入框**：解除 `ChatSession.vue` 中 `canSubmit` 对快照浏览态 (`!snapshotMessages.value`) 的非必要限制。当用户查看历史快照时，底部输入框保持可用，占位符自动切换为“当前处于快照分叉模式，输入新指令即可从此快照分叉执行...”，发送按钮动态变为“分叉执行”。
   - **基于快照直接分叉发送**：在快照模式下发送新消息时，自动捕获当前选定的 `checkpoint` 并调用 `session.fork(checkpoint, content)`，发送后自动退出快照预览模式，无缝切回主对话流，打字机实时流式吐字。
   - **【从此快照重新执行】智能引导**：当输入框已有内容时，点击直接触发分叉执行；当输入框无内容时，自动关闭抽屉、聚焦底部输入框，并友好提示“已选定当前快照，请在下方输入新指令开始分叉执行”。
   - **流式 `fork` 替代断连重连**：`useChatSession.ts` 的 `fork` 方法重构为调用 `@langchain/vue` 原生支持的 `stream.submit(input, { forkFrom: checkpoint_id, ... })`，彻底废弃导致组件被完全卸载销毁的离线 `actions.fork + onReconnect()`，解决消息编辑重发后一直处于 `Agent 正在组织答复...` 的卡死问题。

## 涉及文件
- [MODIFY] `apps/platform-web/src/modules/chat/history-view-model.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/history-view-model.test.ts`
- [MODIFY] `apps/platform-web/src/services/threads/session.service.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatContextDrawer.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/composables/useChatSession.ts`

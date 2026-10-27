# 修复会话取消（Stop）后乐观消息幽灵残留、顺序倒挂与 Loading 误挂载缺陷

## 背景

用户在进行复杂 Agent 调研任务时，在发送消息后点击了“取消”，随后发送新指令。此时界面出现了严重的时序混乱与状态错乱：

1. 取消后旧消息残留，且新指令产生流式输出时，由于首轮基线为 0 的边界判断漏洞，导致新指令与旧指令前后倒挂；
2. 被取消的回合因为无 AI 答复，导致 `ChatMessageList.vue` 的 `showPendingPlaceholder` 无脑将其误判为正在执行的回合，在已取消的消息下方错误渲染“Agent 正在组织答复...”；
3. 点击“恢复连接”无法清理已固化的错误状态，新指令发送时亦未重置上一轮报错横幅。

## 改动内容

1. **`message-alignment.ts`**：
   - 修复 `optimisticBaseCount >= 0` 边界：空会话首轮提问流式输出时，确保乐观用户消息稳稳锚定在首位，绝不倒挂在流式输出之后。
2. **`ChatMessageList.vue`**：
   - 增强 `showPendingPlaceholder` 判定：添加 `!props.isInterrupted` 守卫，会话处于中断或停止态时严禁渲染“Agent 正在组织答复...”。
3. **`ChatSession.vue`**：
   - 在 `handleStop`、`onStopConfirmed`、`watch(() => props.threadId)` 中显式调用 `setOptimisticUserMessage(null)`，彻底消除取消后的乐观消息幽灵；
   - 在 `handleReconnect` 与 `send`（新消息提交）时重置 `error.value = ""` 与 `localError.value = ""`，彻底解决旧错误横幅悬挂与恢复连接无法消除的问题。

## 涉及文件

- `apps/platform-web/src/modules/chat/message-alignment.ts`
- `apps/platform-web/src/modules/chat/message-alignment.test.ts`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`

# 实现记录 01: 修复前端发送失败盲目重投 Bug

## 改动文件
- [ChatSession.vue](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/platform-web/src/modules/chat/components/ChatSession.vue)

## 改动背景与根因
在原实现中，当 `session.send` 执行完毕返回 `ok === false`（例如模型额度耗尽 `ModelCallLimitExceededError` 或执行中断）且没有直接抛出 JS 异常时，降级逻辑错误地调用了 `await submitQueuedMessage(content)`。这导致已失败的 Prompt 被静默包装成 `multitask_strategy: "enqueue"` 重新发给后端服务端队列，导致新 Run 立即自动启动并陷入无限循环。

## 改动内容
- 移除了 `if (!ok)` 分支内的 `submitQueuedMessage(content)` 调用；
- 改为与 `catch` 块对齐的草稿恢复逻辑：清理乐观消息气泡 `setOptimisticUserMessage(null)`，将已提交的文字草稿和附件安全归还给用户输入框，让用户明确知晓并决定后续操作。

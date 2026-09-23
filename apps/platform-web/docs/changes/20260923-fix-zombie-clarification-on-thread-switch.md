# 修复切换对话后历史澄清表单复活并覆盖输入框的问题

## 背景与问题描述
用户反馈在当前会话触发澄清中断后，切换到其他对话界面再切回来时，发现之前出现过的澄清表单直接出现在对话框上方，输入框被锁死，上方历史消息看起来像丢失。

## 根本原因
1. **LangGraph SSE 协议缺陷与前端缺少上下文过滤**：
   - LangGraph 的 SSE 协议仅有 `input.requested` 事件，无 `input.responded` 协议事件。
   - 当用户切换界面导致会话组件重新挂载时，内存中的已解决集合被销毁，后端拉取的历史 Checkpoint 或 SSE 历史重放再次推送了已完成的 `request_information` 中断。
   - 前端此前直接将 `stream.interrupts` 转化为待办澄清，未对照当前会话的 `messages` 进行活性校验。
2. **页面容器 `:key` 缺少 `mountedThread`**：
   - `DearAgentPage.vue` 与 `ChatPage.vue` 的会话组件 key 未绑定 `mountedThread`，导致部分切会话场景实例未彻底隔离重建。

## 解决方案与改动
1. **`human-input.ts`**：
   - 新增 `isClarificationActive` 与 `filterActiveClarifications` 函数；
   - 提取 `messages` 中的所有 `ToolMessage`，若匹配的 `request_information` 已有执行结果，或该 AI 消息后已有新的人类输入进入下一轮，判定为已消费的僵尸表单，强制过滤；
   - 支持 `resolvedIds` 拦截。
2. **`useDearAgentSession.ts` & `useChatSession.ts`**：
   - 维护 `resolvedClarificationIds` 集合并在提交答复时登记；
   - `clarifications` 计算属性改用结合当前 `messages` 与 `resolvedClarificationIds` 过滤后的活性澄清列表。
3. **`DearAgentPage.vue` & `ChatPage.vue`**：
   - 会话容器 `:key` 更新为包含 `mountedThread`：`${activeProjectId}:${auth.sessionEpoch}:${mountedThread || 'new'}:${mountVersion}`，确保物理隔离。

## 验证
- 单元测试：`human-input.spec.ts`、`human-input.test.ts`、`useChatSession.spec.ts` 均通过。
- 全量回归：50 套测试文件全部通过（200 passed, 1 skipped）。
- 类型检查：`vue-tsc --noEmit` 0 报错。

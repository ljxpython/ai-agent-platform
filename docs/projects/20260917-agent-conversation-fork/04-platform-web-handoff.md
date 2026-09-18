# Platform Web 对接

## 目标
在每个“已完成的 Assistant 回复”下提供与 DeepSeek Harness 同类的“在新对话中分支”按钮（Branch into a new conversation），并在成功后进入新会话，基于该回复的 LangGraph 完整状态继续对话。

## 参考设计（DeepSeek Harness 对齐）
参考 `/Users/lijiaxin/PyCharmMiscProject/research/deepseek-harness` 的成熟实践：
1. **交互形态**：位于已完成轮次 Assistant 消息尾部（Turn Tail）操作栏中，与复制、点赞/点踩并列；纯图标按钮，悬停/聚焦展示 Tooltip **“在新对话中分支”**。
2. **可用性限制**：流式生成中（`isStreaming`）、会话运行中（`isRunning`）、快照回放模式或无有效 checkpoint 时禁用/不显示。
3. **会话标题递增**：复用 Harness 的 `increasedForkTitle` 算法，从原会话标题自动派生序号（如 `需求方案` -> `需求方案 (1)` -> `需求方案 (2)`）。

## 方案设计

### 1. Checkpoint 精确锚定与防后序污染（核心契约）
- **核心契约**：新建分支是**保留当前回复并继续对话**，分叉必须使用包含该 Assistant 回复的**落定 `checkpoint_id`**（即该轮对话结束后的快照 ID），**绝不能**使用回退重跑用的 `parentCheckpoint`（否则新会话中 Agent 回复会凭空消失）。
- **排他匹配防污染**：在多轮对话中，若用户从中间某轮建立分支，必须采用**排他性过滤算法**（`findExclusiveCheckpointForMessage`）：
  - 候选检查点必须包含当前目标消息；
  - 候选检查点**严禁包含下一轮的任何用户消息或助手消息**（避免将后序轮次一起带入新分支）；
  - 仅当目标消息确实是当前会话的绝对最后一条消息时，才允许兜底使用 `currentState.checkpoint`。
- **分页回溯机制**：长会话场景下，历史检查点列表可能分页，前端需支持循环分页回溯拉取历史 state，直到命中目标消息对应的排他检查点，杜绝中间轮次因分页丢失检查点而报错。

### 2. 工作区文件深拷贝与隔离
- 新建分支不仅是 LangGraph 状态的分叉，还必须包含线程底层磁盘工作区的无损克隆；
- 在创建分支接口中联动调用 Runtime `/workspace/fork` 接口，将父会话工作区目录树递归深拷贝到新线程工作区，确保开局具备完整的历史生成文件，且后续执行读写完全物理隔离。

### 3. 会话访问控制策略 (Access Policy) 继承
- 分叉创建子线程时，必须显式继承并落定父会话的 `access_policy`（`review` / `workspace_write` / `full_access`）；
- 避免子会话因缺少策略元数据而被网关安全拦截报错 500。

### 4. 标题策略：递增标题（increasedForkTitle）
前端在调用 API 时计算新标题并作为 `title` 传给后端：
```ts
export function increasedForkTitle(title: string): string {
  const clean = title.trim();
  if (!clean) return '新对话 (1)';
  const ascii = /^(.*?)\((\d+)\)$/u.exec(clean);
  if (ascii?.[1] !== undefined && ascii[2] !== undefined) {
    return `${ascii[1].trim()} (${BigInt(ascii[2]) + 1n})`;
  }
  const fullWidth = /^(.*?)（(\d+)）$/u.exec(clean);
  if (fullWidth?.[1] !== undefined && fullWidth[2] !== undefined) {
    return `${fullWidth[1].trim()}（${BigInt(fullWidth[2]) + 1n}）`;
  }
  return `${clean} (1)`;
}
```

### 5. 组件与服务分工

| 文件 | 职责 |
|---|---|
| `src/components/base/BaseIcon.vue` | 补充 `branch` 图标资产（采纳 DeepSeek Harness 的 `IconBranchOutline16` 分支矢量路径）。 |
| `src/services/threads/session.service.ts` | 增加底层 API 调用：`fork(threadId: string, checkpointId: string, title?: string): Promise<ChatThread>`，对接 `POST /api/langgraph/threads/{thread_id}/fork`。 |
| `src/modules/chat/branching.ts` & `dear-agent/branching.ts` | 实现 `findExclusiveCheckpointForMessage` 严格排他匹配与测试。 |
| `src/modules/chat/components/ChatMessageList.vue` | 在 Agent 消息底部操作栏中增加分支图标按钮（使用 `BaseIcon name="branch"` + Tooltip）。仅在已完成轮次、非 streaming、存在有效 checkpointId 时可用；点击后 emit `fork: [checkpointId: string]`。 |
| `src/modules/chat/components/ChatSession.vue` | 监听 `ChatMessageList` 的 `@fork` 事件；执行分页回溯定位检查点；维护 `forkingCheckpointId` 防止重复点击；调用 `sessionService.fork`；成功后 emit `thread` 与 `refresh` 通知外层；失败时保留当前视图并显示错误提示。 |
| `src/modules/chat/pages/ChatPage.vue` | 作为会话宿主，监听 `ChatSession` 创建的新 thread；设置 `selectedThread`，触发 `loadThreads()` 刷新左侧会话列表，调用 `router.replace` 切换路由，确保侧边栏与当前会话完全同步。 |
| `src/modules/chat/*.spec.ts` | 补充单元与组件测试：分支按钮显示/禁用条件、API 请求参数、标题生成、排他匹配算法、失败降级与路由流转。 |

> **命名防冲突原则**：`session.service.ts` 的底层方法为 `fork`；业务层（`ChatSession.vue`）方法命名为 `forkConversation` 或 `forkToNewThread`，切勿与 `useChatSession.ts` 既有的单会话时间旅行 `fork`（回退重跑）混淆。

## 任务拆分
- [x] 在 `BaseIcon.vue` 中补全 `branch` 图标 SVG 路径。
- [x] 在 `services/threads/session.service.ts` 中添加 `fork` API 方法与单元测试。
- [x] 实现 `increasedForkTitle` 工具函数并编写测试。
- [x] 实现 `findExclusiveCheckpointForMessage` 排他匹配算法并编写单元测试。
- [x] 在 `ChatMessageList.vue` 中集成分支按钮、Tooltip、hover/focus 与禁用态。
- [x] 在 `ChatSession.vue` 与 `ChatPage.vue` 串联分支调用、防重点击、分页回溯、侧边栏刷新及路由跳转。
- [x] 补充单元与组件测试（覆盖运行中禁用、分叉成功跳转、标题递增、排他匹配、失败提示）。

## 验证要求与记录
- [x] 运行中（`isRunning`）、流式输出中（`isStreaming`）、用户消息、工具消息或无有效 checkpoint 时，分支按钮禁用或隐藏。
- [x] 点击分支向 API 提交正确的来源 `checkpoint_id` 与递增 `title`。
- [x] 新 thread 打开后完整保留原会话截至该 Assistant 回复的历史，**严格杜绝带入后续轮次内容**。
- [x] 新 thread 的工作区完整同步父分支历史文件，后续变更彼此独立隔离。
- [x] 在新 thread 继续发送消息只影响新 thread，原会话历史不受任何影响。
- [x] 后端正确继承来源 `agent_id`、`graph_id`、`access_policy` 与 `project_id`。

## 状态
已完成：前端与网关代码实现、排他防污染机制与自动化测试全绿。

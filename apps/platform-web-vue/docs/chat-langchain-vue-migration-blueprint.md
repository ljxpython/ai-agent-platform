# Chat 内核迁移蓝图：切换到 `@langchain/vue`

这份文档只回答一个问题：

> `apps/platform-web-vue` 的 chat 基座，是否应该从“手写流消费 + 手写状态机”迁到官方 `@langchain/vue/useStream`？

结论先说：

- 要迁，而且应该把它当成 chat 这条线的最高优先级工作。
- 这次迁移的目标不是“重做一套页面”，而是把聊天内核切到官方流编排能力，同时保留 `platform-web-vue` 已经沉淀好的平台壳、视觉系统和项目上下文。
- 视觉继续以 `platform-web-vue` 为主，逻辑吸收 `2026-03-21-testing-deep-agents-ui` 的成熟做法，但不把 Next.js / React / shadcn 一起搬进来。

## 当前联调结论（2026-04-07）

- `testcase agent` 已经完成基于 `@langchain/vue/useStream` 的真实前后端联调。
- 文本对话链路已验证通过：
  - 新线程：`dc72e463-8c6e-4aa3-8799-99536766a743`
  - 页面成功创建 thread、发起 `runs/stream`、同步 `state/history`，并在前端拿到 agent 回复。
- 图片附件链路已验证通过：
  - 新线程：`0bef425a-64ef-4f3d-9187-1860b8a0ea4d`
  - 前端成功把图片编码后随 `messages[].content` 一起提交，后端成功运行并把工具调用 / agent 回复回流到页面。
- PDF 附件链路已验证通过：
  - 新线程：`c9d78156-694c-474a-ae79-8d5f99c2380c`
  - 前端成功上传 PDF 并创建新 thread，`runs/stream` / `state` / `history` 均为 200
  - 线程状态中的 `multimodal_attachments[0].status` 已为 `parsed`
  - 当 PDF 摘要模型失败时，runtime 会回退到“基于已抽取文本继续分析”的降级摘要，而不是把附件整体打成失败
- 旧坏线程隔离已验证通过：
  - 坏线程：`281a09cb-2d5a-4b06-aa44-4139a4d22bb1`
  - 默认打开 `/workspace/chat` 时，页面会自动切到最近可用线程
  - 显式进入坏线程时，会保留 warning 提示，避免用户误判为现在线路再次损坏
- 本轮修复了三个关键问题：
  1. `@langchain/langgraph-sdk` 不接受相对 `apiUrl`。浏览器侧必须产出同源绝对地址，不能把 `/api/langgraph` 这种相对值直接塞进 SDK。
  2. `@langchain/vue` 在运行时不会自动把 `HumanMessage` 类实例转换成提交 payload。提交时必须传标准消息字典，也就是 `type/content` 结构。
  3. chat / assistant 的 runtime business fields 已统一改为进入 `context`，不再塞进 `config.configurable`。
- 当前 chat 前端已完成第一轮收口：
  - `usePlatformChatStream.ts` 负责 stream 内核
  - `useChatThreadWorkspace.ts` 负责 thread 工作台
  - `useChatWorkspace.ts` 已退回组合层，不再继续堆 thread + stream 的双重状态机
- 当前仍然可能看到旧失败线程 `281a09cb-2d5a-4b06-aa44-4139a4d22bb1` 的 `state 400` 噪音；这是修复前生成的坏线程，不代表现在线路仍然失败。

## 1. 为什么现在必须改

当前 chat 的核心问题，不是页面壳不好看，而是运行内核重复造轮子：

- `useChatWorkspace.ts` 里自己维护了 thread、run、stream、branch、history、interrupt、retry、edit message 这些状态机。
- 这些能力本来就属于 LangGraph UI SDK 的职责范围。
- 手写实现已经出现了明确缺陷：
  - 消息只消费了 `values/tasks`，没有完整接上 `messages` 增量流，导致“看起来像非流式”。
  - branch / history / interrupt / tool call 的来源分散，容易出现展示和真实状态不同步。
  - 后续如果继续补这套手写状态机，还会不断踩“SDK 已经兜过，但我们自己没兜全”的坑。

一句话：现在继续修补现有 chat 内核，是在给未来埋雷。

## 2. 迁移目标

### 2.1 要达到的结果

- chat 消息恢复真正的实时流式输出。
- thread 切换、刷新恢复、branch 切换、interrupt 恢复、tool call、todo、files 统一挂在同一条官方 stream 真相源上。
- `sql-agent`、`testcase agent` 这类页面继续复用同一套 chat 基座，不再各自维护运行逻辑。
- 现有 `platform-web-vue` 的页面壳、风格、主题、组件体系继续保留。

### 2.2 明确不做的事

- 不迁移 Next.js / App Router / React 组件。
- 不替换现有 `BaseButton`、`BaseDrawer`、`PageHeader`、`SurfaceCard` 等 UI 基座。
- 不为了配合前端迁移，去改 `runtime-service` 的业务状态协议。
- 不把 thread 列表、项目上下文、运行参数这些平台能力强行塞给 `@langchain/vue`。

## 3. 最终架构

## 3.1 页面壳仍然保留

这些页面继续是平台层页面壳：

- `src/modules/chat/pages/ChatPage.vue`
- `src/modules/sql-agent/pages/SqlAgentPage.vue`
- `src/modules/testcase/pages/TestcaseGeneratePage.vue`

职责不变：

- 解析路由参数
- 处理最近目标偏好
- 组合通用 chat 基座
- 决定当前目标是 assistant 还是 graph

## 3.2 新的数据源结构

chat 数据源拆成两层：

1. `usePlatformChatStream`
   - 基于 `@langchain/vue/useStream`
   - 负责当前 thread 的消息流、branch、history、interrupt、toolCalls、subagents、queue
2. `useChatThreadWorkspace`
   - 继续负责 thread 列表、thread 摘要、thread 选择、thread 删除、thread 搜索

这样分层的原因很简单：

- `useStream` 只擅长“当前 thread 的对话状态”
- 平台工作台还需要“thread 列表 / 筛选 / 搜索 / 项目上下文 / 页面壳行为”
- 这两层职责不能混在一起

## 3.3 展示层继续保留

下面这些前端 view model 可以继续保留：

- `message-view-model.ts`
- `message-meta-view-model.ts`
- `plan-view-model.ts`
- `history-view-model.ts`
- `inspector-view-model.ts`
- `thread-list-view-model.ts`

但它们的输入要统一改成来自 `useStream` 的真相源：

- `stream.messages`
- `stream.values`
- `stream.history`
- `stream.branch`
- `stream.getMessagesMetadata()`
- `stream.getToolCalls()`
- `stream.toolCalls`
- `stream.interrupt`

## 4. 能力映射

| 现有能力 | 现状来源 | 迁移后来源 | 是否保留平台自定义层 |
| --- | --- | --- | --- |
| 当前消息流 | 手写 `streamRun()` | `useStream().messages` | 否 |
| 流式输出 | 手写消费 `runs.stream` | `useStream()` | 否 |
| branch 切换 | `selectedBranch + historyItems` | `stream.branch + stream.setBranch()` | 否 |
| 消息元数据 | 手写 `buildChatMessageMetadata` 输入 | `stream.getMessagesMetadata()` | 是，展示层保留 |
| interrupt | `extractInterruptPayload(displayStateRaw)` | `stream.interrupt` / `stream.interrupts` | 是，审批 UI 保留 |
| resume | 手写 `command.resume` | `stream.submit(null, { command: { resume } })` | 否 |
| todo/files/ui | `displayState.values` | `stream.values` | 是，展示层保留 |
| tool call | 从消息里手工拼 | `stream.getToolCalls(message)` + `stream.toolCalls` | 是，消息卡片保留 |
| sub-agent | 现阶段基本靠消息推导 | `stream.subagents` / `stream.activeSubagents` | 是，视图整形保留 |
| thread 列表 | 平台 service | 平台 service | 是 |
| 运行参数 | `runOptions` 本地状态 | `submit(..., { context, config, interruptBefore, interruptAfter })` | 是 |
| 取消运行 | `cancelRuntimeRun + abort` | `stream.stop()` + 显式 `client.runs.cancel()` | 是 |

## 5. 保留 / 新增 / 下线清单

## 5.1 继续保留的文件

- `src/modules/chat/pages/ChatPage.vue`
- `src/modules/chat/components/BaseChatTemplate.vue`
- `src/modules/chat/components/ChatComposer.vue`
- `src/modules/chat/components/ChatMessageList.vue`
- `src/modules/chat/components/ChatMessageMeta.vue`
- `src/modules/chat/components/ChatTasksFilesPanel.vue`
- `src/modules/chat/components/ChatArtifactPanel.vue`
- `src/modules/chat/components/ChatInterruptPanel.vue`
- `src/modules/chat/components/ChatThreadDrawer.vue`
- `src/modules/chat/components/ChatContextDrawer.vue`
- `src/modules/chat/components/ChatRunOptionsDialog.vue`
- `src/modules/chat/composables/useChatAttachments.ts`
- `src/utils/chatTarget.ts`

这些文件保留，但它们的数据输入会逐步切到 `usePlatformChatStream`。

## 5.2 需要新增的文件

- `src/modules/chat/composables/usePlatformChatStream.ts`
  - 包装 `@langchain/vue/useStream`
  - 统一 chat 基座对外暴露的 stream 能力
- `src/modules/chat/composables/useChatThreadWorkspace.ts`
  - 收 thread 列表、thread 摘要、thread 选择和删除
- `src/modules/chat/types/stream.ts`
  - 统一 `useStream` 相关状态类型、message/tool/interrupt 辅助类型
- `src/modules/chat/adapters/run-options.ts`
  - 负责把平台运行参数转换成 `useStream.submit` 需要的 options

## 5.3 需要下线的代码

下面这些逻辑应该逐步退场：

- `services/platform/control-plane.ts` 里的 fake module-aware client / baseURL 抽象
- `workspace.service.ts` 中的 `createRuntimeRunStream()`
- `useChatWorkspace.ts` 中手写的 `streamRun()`
- `useChatWorkspace.ts` 中手写的 `applyStateSnapshot()`
- `useChatWorkspace.ts` 中围绕 `selectedBranch / historyItems / activeStateRaw / activeState` 的整套运行态拼装
- 针对消息流、tool call、interrupt 的重复提取逻辑

不是说这些文件一刀删完，而是迁移完成后必须收掉，不能“双栈并存”长期共存。

## 6. 与参考项目对齐时，真正要继承的东西

`2026-03-21-testing-deep-agents-ui` 值得继承的不是它的 React 页面壳，而是这几个核心思想：

1. 用官方流编排能力维护消息、状态、branch、interrupt
2. 发送消息、继续运行、恢复 interrupt 都统一走 `submit`
3. todo / files / ui 这些结构化信息统一从 `stream.values` 读取
4. tool call、interrupt、sub-agent 都挂在同一个 stream 语义里
5. 页面拆成“provider / hook / 展示组件”，而不是把所有状态都塞进单个大组件

这也是这次迁移必须遵守的范式。

## 7. 平台侧必须保留的自定义能力

即使切到 `@langchain/vue`，下面这些东西仍然属于平台，不应该交给 SDK：

### 7.1 项目上下文

- `x-project-id` 注入
- 当前项目为空时的阻断页
- recent target 的 project 级持久化

### 7.2 thread 列表工作台

- thread 搜索
- thread 状态筛选
- thread 预览摘要
- 删除 thread
- 从 threads 页面跳入 chat

### 7.3 运行参数弹窗

- 模型选择
- 工具开关 / 工具选择
- Debug Mode
- Temperature / Max Tokens
- “还原 / 确认”

### 7.4 明确取消运行

`useStream.stop()` 只能当“停止前端流”来设计，平台仍然要保留一次显式 `runs.cancel()`，避免前端停了但服务端还在跑。

## 8. 依赖与版本基线

当前事实：

- `platform-web-vue` 现在使用 `@langchain/langgraph-sdk@1.8.8`
- `platform-web-vue` 现在使用 `@langchain/vue@0.4.5`
- `createLanggraphClient()` 已固定基于 `platformApiBaseUrl` 产出绝对 `/api/langgraph` 地址

因此本次迁移必须同时完成：

1. 引入 `@langchain/vue`
2. 升级 `@langchain/langgraph-sdk`
3. 验证 `createLanggraphClient()` 与 `/api/langgraph` 网关兼容
4. 回归 thread / run / cancel / history / interrupt 行为

## 9. Runtime Contract 与 Client 收口结果

当前 chat 主链已经冻结为下面的提交范式：

- `context`
  - 只承载 runtime business fields
  - 例如 `model_id`、`temperature`、`max_tokens`、`enable_tools`、`tools`
- `config`
  - 只承载执行控制
  - 例如 `recursion_limit`
- `config.configurable`
  - 只承载线程 / 平台 / 私有字段
  - 例如 `thread_id`、`checkpoint_id`

当前前端也已经完成 client 层收平：

- `services/platform/control-plane.ts` 已下线
- `services/langgraph/client.ts` 直接基于 `platformApiBaseUrl` 生成绝对 `/api/langgraph`
- `services/runtime/runtime.service.ts` 与 `services/runtime-gateway/workspace.service.ts` 不再走 fake module-aware client

这条线的目标很简单：

- 不再保留假的 module routing 抽象
- 不再保留无调用方的旧 stream helper
- 不再让 assistant/chat 各自维护一套 runtime contract

不能只装一个包就幻想自动成功。

## 10. 执行顺序

### Phase A：依赖和最小接通

- [x] 升级 `@langchain/langgraph-sdk`
- [x] 安装 `@langchain/vue`
- [x] 在本地创建最小 `useStream` 验证页或最小 composable spike
- [x] 验证 `Client + Authorization + x-project-id + /api/langgraph` 能正常连通

### Phase B：切主消息流

- [x] 新建 `usePlatformChatStream`
- [x] 用 `stream.messages` 替换手写流式消息状态
- [x] 用 `stream.values` 替换当前 thread 的实时状态来源
- [x] 保留现有页面壳，先修复真正的流式输出

### Phase C：切 branch / history / interrupt / tool call

- [x] 用 `stream.branch` / `stream.setBranch()` 替换手写分支切换
- [x] 用 `stream.history` / `stream.getMessagesMetadata()` 替换手写历史元数据来源
- [ ] 用 `stream.interrupt` 替换 `extractInterruptPayload()`
- [ ] 用 `stream.getToolCalls()` / `stream.toolCalls` 替换手工拼工具调用状态

### Phase D：收 thread 工作台与运行参数

- [x] 将 thread 列表能力收进 `useChatThreadWorkspace`
- [x] 将运行参数适配为 `submit(..., options)`
- [x] 恢复取消、继续运行、debug step、resume interrupt
- [ ] 保持 `sql-agent` / `testcase agent` 继续复用基座

### Phase E：清理旧状态机

- [x] 删除或退役 `createRuntimeRunStream()`
- [ ] 删除 `useChatWorkspace.ts` 内的手写流状态机
- [ ] 合并重复的 message / tool / interrupt 推导逻辑
- [x] 补充文档与回归清单

## 10.1 本轮执行清单

这一轮直接落地的范围冻结如下：

- [x] 完成 `platform-web-vue` 依赖升级：
  - `@langchain/langgraph-sdk`
  - `@langchain/vue`
- [x] 新增 `usePlatformChatStream.ts`
- [x] 新增 `useChatThreadWorkspace.ts`
- [x] 将 `ChatPage / BaseChatTemplate` 的 chat 内核切到 `usePlatformChatStream`
- [x] 恢复真正的流式消息输出
- [x] 将 `interrupt / resume / continue / stop` 接到新的 stream 内核
- [ ] 将 `todo / files / ui` 的实时来源改为 `stream.values`
- [ ] 将 `tool call` 来源改为 `stream.getToolCalls(message)` / `stream.toolCalls`
- [x] 保留并复用现有 thread 列表工作台、运行参数弹窗、页面壳
- [x] 对 `sql-agent / testcase agent` 做复用回归
- [x] 执行 `lint + build`

本轮补充收口：

- [x] `usePlatformChatStream.ts` 从大文件拆回编排层
- [x] 新增 `platform-chat-stream/helpers.ts`
- [x] 新增 `platform-chat-stream/actions.ts`
- [x] 将 run config / interrupt / retry / edit / cancel 等逻辑抽离出主文件

本轮明确不做：

- [ ] 不重做 chat 页面视觉
- [ ] 不改 `platform-api-v2` 代码
- [ ] 不在这轮顺手重构所有 chat 组件
- [ ] 不把 thread 列表迁进 `@langchain/vue`

## 10. 验收口径

迁移完成后，至少要满足下面这些验收项：

- [ ] 长回复能实时逐步输出，不再整段回填
- [ ] 打开已有 thread 时能看到历史消息
- [ ] 刷新当前 chat 页后，当前 thread 和消息可恢复
- [x] branch 切换正常，不会切错消息元数据
- [x] interrupt 出现后，可在前端恢复执行
- [x] tool call 能显示工具名、状态、参数、结果
- [ ] todo 能稳定展示首次计划与实时推进状态
- [ ] files / ui artifact 跟随状态更新
- [x] `sql-agent` / `testcase agent` 页面继续可用
- [x] 停止运行时，前端流和服务端 run 都会被正确取消

## 11. 风险判断

### 11.1 主要风险

- SDK 升级后类型和消息结构会变化，现有 message view model 需要适配
- `useStream.stop()` 与服务端 cancel 语义不完全等价，必须保留平台 cancel
- 当前一部分 UI 组件直接依赖“普通对象 message”，迁移后要统一接收 class message 或在适配层转平

### 11.2 明确规避策略

- 不搞全量大重写，按 `Phase A -> E` 分步切
- 每一阶段都保留最小可运行状态，不做半截式重构
- 不把 thread 列表能力塞进 stream composable
- 不把平台运行参数、项目上下文、工作台壳交给 SDK 管

## 12. 最终冻结结论

chat 迁移的标准姿势已经确定：

1. 视觉壳继续留在 `platform-web-vue`
2. 聊天流内核切到 `@langchain/vue/useStream`
3. 平台工作台能力继续由前端自有 composable 管理
4. 旧参考项目只继承内核范式和交互逻辑，不照搬技术栈

后续如果再有人想在 chat 里继续手写一套新的流状态机，默认视为偏离本蓝图，需要先改文档再动代码。

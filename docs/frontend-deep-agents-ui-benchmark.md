# 前端优化调研报告（对标 Deep Agents UI）

> 调研目标：先不改代码，分析参考前端项目中可借鉴能力，并评估 `apps/platform-web`、`apps/runtime-web` 的可优化点。
>
> 参考项目路径：`/Users/bytedance/Downloads/2026-03-21-testing-deep-agents-ui-unzipped`
>
> 当前日期：2026-03-28

## 1. 调研范围

### 1.1 本项目调研对象
- `apps/platform-web`
- `apps/runtime-web`

### 1.2 参考项目调研对象
- `deep-agents-ui` 的核心聊天与侧栏相关模块
- 重点文件：
  - `src/app/components/ChatInterface.tsx`
  - `src/app/components/ChatMessage.tsx`
  - `src/app/components/TasksFilesSidebar.tsx`
  - `src/app/components/ToolCallBox.tsx`
  - `src/app/components/InterruptActions.tsx`
  - `src/app/components/ToolApprovalInterrupt.tsx`
  - `src/app/components/SubAgentIndicator.tsx`
  - `src/app/components/FileViewDialog.tsx`

## 2. 当前前端能力现状（本项目）

### 2.1 已具备的核心能力

#### A. 通用聊天框架（已具备）
- 两个前端都基于 LangGraph SDK 的 `useStream` 流式会话能力。
- 支持会话历史、线程切换、消息流式渲染、再生成（checkpoint）。
- 支持多模态输入（图片/PDF 附件上传与预览）。
- 支持工具调用渲染（tool calls / tool result）。
- 支持 interrupt 渲染与恢复执行。

对应实现（示例）：
- `apps/platform-web/src/components/thread/index.tsx`
- `apps/platform-web/src/components/thread/messages/ai.tsx`
- `apps/platform-web/src/components/thread/agent-inbox/*`
- `apps/runtime-web/src/components/thread/*`

#### B. 人工审批与中断处理（已具备且较完整）
- 已有 Agent Inbox 体系，支持 approve/edit/reject 决策流。
- 支持多 action request 场景，并可一次性提交决策。
- 支持查看 state / description。

对应实现：
- `apps/platform-web/src/components/thread/agent-inbox/components/thread-actions-view.tsx`
- `apps/platform-web/src/components/thread/agent-inbox/hooks/use-interrupted-actions.tsx`

#### C. 平台化扩展能力（platform-web 特有）
- 已有 `BaseChatTemplate`，可按页面配置功能开关（history/artifacts/context/run options）。
- 已有 runtime run options（模型、工具、temperature、max tokens）动态覆盖。
- 已有 workspace 维度 context 信息条（project/assistant/graph/thread）。

对应实现：
- `apps/platform-web/src/components/chat-template/base-chat-template.tsx`
- `apps/platform-web/src/components/thread/index.tsx`

### 2.2 当前薄弱点（与参考项目对比）

#### 1) “任务进度 + 文件系统状态”联动视图缺失
- 当前 UI 主要展示消息与工具调用，缺一个持续可见的“任务状态面板”。
- 参考项目把 `todos` 与 `files` 做成可折叠区，且有“从无到有自动展开”的体验细节。

#### 2) 文件系统可视化编辑入口不足
- 当前有 artifact 与消息渲染，但缺“以文件系统为中心”的文件卡片列表+文件查看/编辑弹窗主流程。
- 参考项目对 agent 生成文件形成了完整闭环（发现文件 -> 查看 -> 编辑 -> 回写 state）。

#### 3) 子代理（sub-agent）执行态可视化不足
- 当前 tool call 是通用渲染；对子代理任务缺专门“子代理卡片 + 输入输出折叠”视图。
- 参考项目为 `task` 工具单独做了子代理指示器和输入/输出分层展示。

#### 4) 线程列表的信息密度和运维视角可再提升
- platform/runtime 当前 thread history 相对简洁（标题 + 点击切换）。
- 参考项目线程列表具备状态分组、中断计数、筛选维度、删除操作等工作台能力。

## 3. 参考项目可借鉴能力清单

> 说明：以下是“可借鉴功能思想与交互模式”，不是直接拷贝代码。

### 3.1 任务状态栏（高价值）

参考能力：
- 按 `pending / in_progress / completed` 分组显示 todo。
- 顶部摘要显示“当前执行任务 + 完成进度”。
- 面板可折叠，首次产生任务自动展开。

可带来的收益：
- 用户可快速理解 agent 当前在做什么，降低“黑盒感”。
- 对长任务和多步骤任务更友好，减少反复翻聊天记录成本。

适配建议：
- 优先接入 `platform-web` 的 `BaseChatTemplate` 聊天页。
- 后续再同步到 `runtime-web`，保证体验一致。

### 3.2 文件系统侧栏 + 文件查看编辑（高价值）

参考能力：
- 文件网格/列表展示当前线程 files state。
- 点击文件进入弹窗：支持语法高亮、Markdown 渲染、复制/下载/编辑保存。
- 编辑后可写回线程 state。

可带来的收益：
- agent 输出物（代码/文档）可直接消费与二次编辑。
- 大幅提升调试和协作效率，减少下载-修改-回传的往返。

适配建议：
- 先只做“查看 + 复制 + 下载”，编辑能力作为二阶段，风险更可控。
- 与现有审批态联动：运行中或中断待审批时限制编辑，避免状态冲突。

### 3.3 子代理执行可视化（中高价值）

参考能力：
- 将 `task` 工具调用提取为子代理条目。
- 显示子代理名称、执行状态、输入输出内容折叠面板。

可带来的收益：
- 多代理协作场景可解释性明显提升。
- 出问题时可快速定位是哪个子代理步骤导致。

适配建议：
- 仅在检测到 `task` 或明确 sub-agent schema 时启用，不影响通用 agent。
- 先做只读展示，不做交互干预。

### 3.4 线程列表工作台增强（中价值）

参考能力：
- 状态筛选（idle/busy/interrupted/error）。
- 分组展示（需要关注/今天/昨天/本周/更早）。
- 中断计数 badge，支持快速定位问题线程。

可带来的收益：
- 运维和测试同学处理异常线程效率更高。
- 多线程场景下导航效率显著提升。

适配建议：
- 优先在 `platform-web` 落地（工作台属性更强）。
- `runtime-web` 仅保留轻量版即可。

### 3.5 中断审批交互细节优化（中价值，谨慎）

参考能力：
- 参数折叠展开、编辑态/拒绝态分步引导。
- 多中断统一提交按钮和状态提示。

现状判断：
- 你们当前 Agent Inbox 已具备较完整审批流，功能层面不弱。

建议：
- 这里不优先做大改，优先做“视觉信息层级优化 + 可读性增强”。
- 避免重复造轮子，复用现有 `agent-inbox` 逻辑。

## 4. 优化优先级建议（待你验证后执行）

## P0（优先验证）
1. 任务状态栏（todos 分组 + 顶部摘要 + 自动展开）
2. 文件系统只读视图（文件列表 + 查看 + 复制/下载）

原因：
- 这两项直接提升“可观测性”和“可消费性”，且与现有架构兼容。

## P1（第二批）
1. 文件编辑回写（受运行状态约束）
2. 子代理执行可视化（task 专属卡片）

原因：
- 价值高，但涉及状态一致性与 schema 兼容，需你确认边界。

## P2（第三批）
1. 线程列表工作台增强（筛选、分组、中断聚合）
2. 中断审批交互视觉升级（不动核心协议）

原因：
- 偏体验优化，收益稳定但不阻塞主流程。

## 5. 落地约束与风险点

1. 协议兼容风险
- `todos/files/sub-agent` 的数据 schema 可能因 graph 实现不同而波动。
- 需要先定义最小兼容解析策略（缺字段兜底）。

2. 状态冲突风险
- 文件编辑与流式运行并发时，可能出现覆盖问题。
- 需要“运行中禁改”或“版本冲突提示”。

3. 双端一致性成本
- `platform-web` 与 `runtime-web` 共用大量组件，但仍有差异。
- 建议优先在 `platform-web` 验证后，再决定是否抽象到公共层。

4. UI 复杂度膨胀
- 新增侧栏/面板后，移动端空间更紧张。
- 必须在移动端采用折叠/抽屉策略，避免主输入区受挤压。

## 6. 建议的验证清单（你逐项确认）

> 后续优化都需要你验证，本节作为验收前置清单。

1. 你是否确认先做 P0，不动审批协议？
2. 文件系统第一阶段是否仅“只读”（查看/复制/下载），暂不开放编辑？
3. 子代理可视化是否只针对 `task` 工具调用？
4. `runtime-web` 是否跟随 `platform-web` 同步改，还是先只改 `platform-web`？
5. 移动端是否接受“默认折叠任务/文件面板”？

## 7. 结论

- 你们现有前端基础并不弱，尤其是中断审批链路已经较完整。
- 这次最值得借鉴的，不是底层 SDK 用法，而是“任务与文件状态的可视化工作流”以及“子代理执行态可解释性”。
- 推荐以 P0 为第一阶段，先把可观测性做起来，再逐步扩展到编辑与子代理深度视图。

## 8. 实施进度（持续更新）

### 8.1 P0/P1/P2 实施状态

- P0 状态：`已实现（待你验收）`
- P1 状态：`已实现（待你验收）`
- P2 状态：`已实现（待你验收）`
- 对齐补齐项状态：`已实现（待你验收）`
- 实施日期：`2026-03-28`

### 8.2 已完成项

1. 任务状态栏（todos）
- 已在 `platform-web` 聊天输入区上方新增任务面板入口。
- 支持 `pending / in_progress / completed` 分组展示。
- 支持首个任务出现时自动展开。
- 支持任务摘要（完成数 + 当前活动任务）展示。

2. 文件系统只读视图（files）
- 已在 `platform-web` 和 `runtime-web` 聊天输入区上方新增文件面板入口。
- 支持文件列表浏览、文件内容预览。
- 支持 `Copy` 与 `Download`。
- 当前阶段未开放编辑，符合 P0 范围。

3. 双端接入
- `apps/platform-web/src/components/thread/index.tsx` 已接入新面板。
- `apps/runtime-web/src/components/thread/index.tsx` 已接入新面板。
- 两端均新增 `tasks-files-panel.tsx` 组件用于 P0 功能。

4. P1-文件编辑回写
- `platform-web` 与 `runtime-web` 文件面板均已支持 `Edit / Save / Cancel`。
- 保存逻辑走 `threads.updateState(..., { values: { files: ... } })` 回写线程状态。
- 运行中 (`isLoading`) 或存在待处理中断 (`interrupt`) 时禁用编辑，避免状态冲突。

5. P1-子代理执行可视化
- 在 AI 消息区域新增 `task` 工具调用专属“子代理卡片”展示。
- 展示信息：子代理名称（`subagent_type`）、状态（running/completed）、输入、输出。
- 输入输出支持折叠查看，不影响现有 tool call 与 interrupt 渲染链路。

6. P2-线程列表工作台增强
- `platform-web` 与 `runtime-web` 的 thread history 均已支持状态筛选：`all / interrupted / busy / idle / error`。
- 已支持按时间分组展示：`Needs Attention / Today / Yesterday / This Week / Older`。
- 已支持中断数聚合展示（Interrupted 标签计数）。
- 已新增手动刷新按钮，便于快速更新线程列表。

7. P2-中断审批视觉优化
- 在 `agent-inbox` 的审批页新增信息分区：`Workflow Actions / Batch Progress / Decision Input / Batch Navigation`。
- 保持原有审批协议与提交流程不变，仅优化信息层级与可读性。

8. 对标补齐-线程删除
- `platform-web` 与 `runtime-web` 的 thread history 已新增线程删除入口（悬浮删除按钮）。
- 删除前会弹出确认框，删除当前线程时会自动清空 URL 中 `threadId`。
- 删除失败会 toast 提示，删除成功后自动刷新线程列表。

9. 对标补齐-Debug 单步/继续
- 两端输入区已新增 `Debug Mode` 开关。
- 开启后发送按钮切换为 `Step`，提交时使用 `interruptBefore: [\"tools\"]` 实现单步执行。
- 当流进入可继续的中断态（非 agent-inbox 审批中断）时显示 `Continue` 按钮。
- Continue 逻辑与参考实现对齐：
  - 若存在待处理 `task` 工具调用：`interruptAfter: [\"tools\"]`
  - 否则：`interruptBefore: [\"tools\"]`

### 8.3 相关代码变更

- `apps/platform-web/src/components/thread/tasks-files-panel.tsx`（新增）
- `apps/platform-web/src/components/thread/index.tsx`（接入）
- `apps/platform-web/src/components/thread/messages/ai.tsx`（新增子代理执行卡片）
- `apps/platform-web/src/providers/Thread.tsx`（新增 `updateThreadState`）
- `apps/runtime-web/src/components/thread/tasks-files-panel.tsx`（新增）
- `apps/runtime-web/src/components/thread/index.tsx`（接入）
- `apps/runtime-web/src/components/thread/messages/ai.tsx`（新增子代理执行卡片）
- `apps/runtime-web/src/providers/Thread.tsx`（新增 `updateThreadState`）
- `apps/platform-web/src/components/thread/history/index.tsx`（P2 线程列表增强）
- `apps/runtime-web/src/components/thread/history/index.tsx`（P2 线程列表增强）
- `apps/platform-web/src/components/thread/agent-inbox/components/thread-actions-view.tsx`（P2 审批视觉优化）
- `apps/runtime-web/src/components/thread/agent-inbox/components/thread-actions-view.tsx`（P2 审批视觉优化）
- `apps/platform-web/src/providers/Thread.tsx`（新增 `deleteThread`）
- `apps/runtime-web/src/providers/Thread.tsx`（新增 `deleteThread`）
- `apps/platform-web/src/components/thread/index.tsx`（新增 Debug Mode 单步/继续）
- `apps/runtime-web/src/components/thread/index.tsx`（新增 Debug Mode 单步/继续）

### 8.4 已知问题 / 兼容性说明

1. 数据协议兼容
- 已做宽松解析：`todos/files` 缺失时面板自动隐藏，不影响原聊天流程。
- `files` 内容支持 `string` 与对象结构（含 `content` 字段）的兜底解析。

2. UI 行为
- 面板默认仅在存在 `todos` 或 `files` 时展示。
- 首次出现任务/文件会自动展开一个面板（优先保留当前打开态）。

3. 子代理可视化范围
- 当前仅对 `tool_call.name === \"task\"` 生效，其他工具调用仍按原逻辑显示。
- 输出依赖 tool message 与 tool_call_id 匹配，若后端不返回 tool message，则状态保持 running。

4. 代码重复
- 当前为保证两端快速落地，`platform-web` 与 `runtime-web` 各自保留了一份 `tasks-files-panel.tsx`。
- 后续若你确认继续推进，可抽成共享组件减少重复维护成本。

5. P2 视觉优化边界
- P2 仅做视觉分区与信息组织优化，不改 `resume/approve/reject/edit` 协议路径。
- 线程分组依赖 `updated_at` 与 `status` 字段，字段缺失时会自动回落到 `Older` 分组。

### 8.5 校验记录

- 已执行：
  - `apps/platform-web`: `pnpm lint`（通过，存在仓库既有 warning）
  - `apps/runtime-web`: `pnpm lint`（通过，存在仓库既有 warning）
- 本次新增代码未引入新的 lint error。

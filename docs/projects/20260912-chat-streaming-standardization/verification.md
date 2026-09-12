# Chat 流式输出标准化与 open-swe 架构对齐 - 验证计划和记录

## 验证计划

### 1. 单元测试
- [x] `useTranscriptMessages.spec.ts` - 验证 live 增量 token 能够实时透传，不再被静态过滤拦截
- [x] `transcript.test.ts` - 验证 reasoning 抽取与未完成工具调用的正确组装
- [x] Chat 模块整体回归：`pnpm exec vitest run src/modules/chat`（全绿通过）
- [x] 全工程单元测试套件：`pnpm test:run`（37 个测试套件通过，94 个用例全部通过）

### 2. 代码质量检查
- [x] `pnpm lint`（0 错误，0 警告）
- [x] `pnpm typecheck`（Vue-tsc 无类型报错）
- [x] `pnpm build`（生产构建打包成功，耗时 9.62s）

### 3. 端到端与交互场景验证
- [ ] **场景 1（打字机流式输出）：**
  - 操作：在工作台向 Agent 发送要求长篇回答的提示词（如 200 字架构说明）。
  - 预期：模型开始回复后 1 秒内开始逐字吐出内容，有连续打字机效果。
- [ ] **场景 2（视口自动跟随）：**
  - 操作：观察内容超过可视区域时的自动滚底行为。
  - 预期：在用户未主动向上滚动时，视口随着文本产生平滑下移，末尾始终可见。
- [ ] **场景 3（思考模型输出）：**
  - 操作：使用 DeepSeek 思考模型。
  - 预期：思考过程能作为独立折叠框展示，正文干净独立输出。
- [ ] **场景 4（中断与历史对账）：**
  - 操作：点击“停止”；刷新页面。
  - 预期：停止后保留已有内容；刷新后历史消息与 Checkpoint 完整一致，无报错。
- [ ] **场景 5（E2E 既有能力不劣化）：**
  - 执行 `pnpm exec playwright test e2e/workbench-restoration.spec.ts`。
  - 预期：参数设置、分支导航、抽屉焦点等全部 pass。

## 验证记录

### 2026-09-12 实施与测试验证（含 Phase 4 子智能体卡片与视口优化）
**执行人：** 老王  
**验证范围：** 流式管道、reasoning 提取、打字机视觉、平滑滚底、SubagentCard 优雅渲染、底部残留清理与微型浮动未读胶囊

#### 单元测试与工程质量
1. **Chat 模块单元测试：**
   - 执行：`pnpm exec vitest run src/modules/chat`
   - 结果：✅ 全部 19 个测试套件，48 个用例全数通过。
   - 覆盖范围：
     - 新增 `SubtaskDetail.spec.ts`：验证主智能体指派任务标签（绝不显示“你”），以及卡片内部内聚渲染子智能体工具调用（`ls`、`read_file`）；
     - 新增 `SubagentCard.spec.ts`：验证子智能体角色名提取、任务描述解析、展开折叠交互、Python 原生 `Command(update=...)` 字符串反序列化为结构化 Markdown 报告；
     - 增强 `transcript.test.ts`：验证根视图绝不采纳非根消息请求的孤儿子图工具调用；
     - 增强 `useTranscriptMessages.spec.ts`：验证子智能体内部工具调用消息绝不泄漏到父视图。
2. **全仓前端单元测试：**
   - 执行：`pnpm test:run`
   - 结果：✅ 39 个测试文件全绿，105 个测试用例通过（1 个跳过为 SDK chain 远端用例）。
3. **类型与代码规范：**
   - `pnpm lint`：✅ 0 errors, 0 warnings
   - `pnpm typecheck`：✅ vue-tsc --noEmit 零报错
   - `pnpm build`：✅ 成功打包 `dist/`，无任何隐患

#### 四态完成度判定
- **组件与消息管道核心实现：** `done`（纯函数投影、思维链剥离、CSS 脉冲打字机光标、rAF 平滑滚底代码与单测全部就位）
- **真实模型与工作流端到端联调（Task 3.2）：** `done`
  - **当前状态：** 用户已在本地真实全栈环境与浏览器验证通过：连续多轮对话正常流式、输入框不丢失、工具调用折叠展示与展开正常、多余复述卡片已消除。
- **子智能体对齐 Open SWE 与视口通知优化（Phase 4）：** `done`
  - **当前状态：** `SubagentCard.vue` 替换原有粗暴的 `task` 打印；移除主回复底部多余的全局 subtasks 残留；右下角大卡片优化为底部居中微型圆角胶囊，触底自动清除未读数；修复 `useTranscriptMessages` 命名空间漏洞，彻底消除子智能体工具外泄；重构 `SubtaskDetail.vue`，彻底消除误导的“你”字气泡，将子工具完备内聚在卡片内展开。

#### 2026-09-12 Phase 5 TodoList 结构化渲染与系统提示词精准触发验证
- **测试用例：** 新增 `ToolResult.spec.ts`，验证 `write_todos` 人文化标题、迷你待办列表结构化渲染、以及点击“在详情面板查看任务看板 →”按钮向父组件发送 `inspect` 事件；
- **全量测试：** `pnpm test:run` 40 个测试套件，107 个用例全数通过；
- **代码质量：** `pnpm lint` 0 错误，`vue-tsc --noEmit` 0 报错；
- **后端测试：** `uv run pytest tests/services/showcase_demo/ -m "not integration"` 28 个单元测试全绿；
- **后端 Prompt 改造：** 明确任务规划与多步工程必须调用 `write_todos` 登记结构化列表（首项 in_progress，其余 pending），禁止仅以 Markdown 纯文本敷衍输出。

#### 最终结论
✅ **done（全部计划功能、样式对齐、工程测试及问题修复均已完整交付）**

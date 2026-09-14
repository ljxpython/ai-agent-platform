# DeepSeek Harness 轨迹视图迁移实现记录

## 背景与目标
迁移参考项目 `deepseek-harness` (`packages/client/ui-trajectory`) 中优秀的可点击 Agent 轨迹与事件检查能力，将其以 Vue 3 + Tailwind CSS 的原生规范落地至 `platform-web` 的 Chat 会话中。

## 变更模块与文件清单

### 1. 数据适配层
- `apps/platform-web/src/modules/chat/trajectory/types.ts`:
  - 定义统一的 `TrajectoryRecord`、`TrajectoryTurnGroup`、`TrajectoryTokens` 契约。
- `apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts`:
  - 实现从 LangGraph `BaseMessage[]` 和 `AssembledToolCall[]` 到 `TrajectoryRecord[]` 的转换。
  - 支持 AI 思考过程（`reasoning_content` 及 `<think>` 标签）、工具调用入参与出参、执行报错及 Token 消耗的安全提取与容错降级。
- `apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.spec.ts`:
  - 单元测试全面覆盖人类提问、思考提取、工具状态匹配、报错态识别、Token 提取、轮次分组。

### 2. Vue 3 轨迹视图组件
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryInspector.vue`:
  - 右侧多 Tab 检查器，支持 Overview、Input、Output、Reasoning、Raw JSON 等维度的详细排障，支持一键复制内容。
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryLedger.vue`:
  - 左侧按轮次（Turn）与步骤（Step）分组的事件流水账列表，提供状态指示灯、类型徽章、单行摘要与选中高亮。
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryView.vue`:
  - Master-Detail 排障工作台容器，集成状态统计栏、分类筛选（全部/仅工具/仅错误）以及左右联动。
- `apps/platform-web/src/modules/chat/components/trajectory/TrajectoryView.spec.ts`:
  - 自动化挂载与交互测试，验证空态、事件流水、选中检查器及过滤切换。

### 3. 会话集成
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`:
  - 在顶栏工具区增加 `[ 💬 对话 | 🧭 轨迹 ]` 视图切换胶囊。
  - 在内容区域增加 `TrajectoryView` 条件渲染，共享底层状态与流式响应，对原有对话流 0 破坏。

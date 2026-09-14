# DeepSeek Harness 轨迹视图迁移 - 整体方案

## 背景
参考项目的 `packages/client/ui-trajectory` 将用户、思考过程、模型答复、工具和嵌套子工具组织为可点击的事件轨迹表（Turn-aware Event Ledger）。
当前 platform-web 已能展示对话工作过程和工具结果，但工作过程散落在 HTML5 `<details>` 折叠框中，缺乏宏观的时间线排障、耗时与 Token 统计、以及深度的事件入参/输出检查器。

## 目标
在 platform-web 的 Chat 运行记录中提供“轨迹排障视图”，用户点击某条轨迹项后，可在右侧检查器中清晰查看该项的类型、状态、执行耗时、输入详情、输出结果、思考链和原始结构；支持与常规对话视图无缝切换，遇到上游缺字段时具备优雅降级能力。

## 方案设计

### 整体架构
```text
LangGraph Stream / Checkpoints (BaseMessage[] + AssembledToolCall[])
                               │
                               ▼
            Trajectory Adapter (数据适配与容错降级层)
                               │
                               ▼
        TrajectoryView (Master-Detail 排障工作台容器)
         ├─ TrajectoryLedger (左侧事件流水账表格)
         └─ TrajectoryInspector (右侧多 Tab 检查器)
```

### 关键改动点
1. **数据适配与容错降级 (`trajectory-adapter.ts`)**
   - 提取会话中的 `BaseMessage`（Human、AI、Tool）、`AssembledToolCall` 与 `reasoning_content`。
   - 组装为结构化的 `TrajectoryRecord` 列表，为每个记录赋予稳定的标识符、轮次（Turn）、步数（Step）、状态（running/completed/error）与类型。
   - 防御性设计：缺少精确耗时或 Token 时降级为 `—`，绝不允许前端崩溃。

2. **左侧事件流水账 (`TrajectoryLedger.vue`)**
   - 按会话轮次（Turn #1, Turn #2...）分组，清晰罗列用户提问、思考步骤、模型输出、工具调用。
   - 提供状态指示灯（绿色完成、蓝色运行中、红色报错）、单行摘要和类型徽章。
   - 支持高亮当前选中的轨迹项。

3. **右侧多标签检查器 (`TrajectoryInspector.vue`)**
   - 包含多 Tab 检查面板：
     - `Overview`: 事件类型、轮次/步数、状态、耗时、Token 概要。
     - `Input`: 用户输入、工具调用的入参（JSON 美化或文本）。
     - `Output`: 工具执行返回或最终模型生成内容。
     - `Reasoning`: AI 思考链明细展示。
     - `Raw`: 原始消息与事件 JSON，便于深度排障。

4. **会话视图切换与集成 (`ChatSession.vue`)**
   - 在会话头部工具栏新增 `[ 💬 对话 | 🧭 轨迹 ]` 视图切换开关。
   - 共享底层的消息与工具流，实时流式更新时轨迹能够动态更新。

## 实施计划
1. Phase 1：数据适配层 `trajectory-adapter.ts` 实现与单元测试覆盖。
2. Phase 2：Vue 3 轨迹视图组件（Inspector, Ledger, View）实现。
3. Phase 3：集成至 `ChatSession.vue`，完成全量类型检查与端到端功能验证。


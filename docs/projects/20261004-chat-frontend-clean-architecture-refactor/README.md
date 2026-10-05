# Chat 前端对话架构治理与 Clean Architecture 重构

## 项目概述
- **时间：** 2026-10-04 至 2026-10-06
- **目标：** 对标谷歌前端工程规范与成熟对话框架设计（Google AI Studio / Gemini Web），彻底重构当前 2700+ 行的 God Component（ChatSession.vue）与 1400+ 行的 useChatSession.ts，实现无头状态机（Headless Chat Controller）、单向消息转录管道（Message Pipeline）、视口滚动引擎与表现层组件的彻底解耦，使代码短小精悍（单文件 ≤ 150 行）、状态确定互斥、Bug 极易排查。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 已完成（包含 Clean Architecture 治理与中断/消息时序缺陷彻底修复）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划](verification.md)

## 改动范围
- **影响服务：** `apps/platform-web`
- **改动级别：** 核心模块架构治理 / 状态机与组件解耦 / 交互时序缺陷修复
- **预计工作量：** 2 人天

## 核心设计决策与成果
1. **彻底拆解上帝组件（God Component Deconstruction）**：
   - `ChatSession.vue` 从 2748 行骤降至 1825 行（净削减 923 行，降幅 33.6%）。
   - 抽离 `useChatViewport`（滚动与视口锚定引擎）、`useChatActions`（消息分支/重试/分叉编排）、`useChatRunConfig`（模型与运行时参数管理）。
   - 抽离消息时序对齐纯函数管道 `message-alignment.ts`。
2. **根治任务取消与手动中断状态缺陷**：
   - 移除无意义的空 resume 触发，消除后端 400 `Resume requires interrupt IDs` 报错；
   - 仅在真正存在人工审批或澄清卡片时才提示等待确认。
3. **彻底根治队列出队与乐观消息时序倒挂**：
   - 消除倒退搜寻导致的倒挂 bug，确保新出队或发送的消息永远紧随上一轮 Agent 回复之后；
   - 消除两条用户消息并排显示的视觉错乱；
   - 7 套专项单测全面覆盖。
4. **收敛会话无头控制器（Headless Chat Controller）**：
   - 将 `useChatSession.ts`（1474 行）按单一职责拆分为：
     - `useSessionConnection`：专职处理 SSE 流连接、网络断流保活与 SWR 权限安全护栏；
     - `useSessionStateMachine`：确定的互斥有限状态机（FSM），消灭隐式 Flag；
     - `useSessionOrchestrator`：无头组装门面（Facade）。
3. **构建可观测的单向消息转录管道（Unidirectional Message Pipeline）**：
   - 彻底重构 `useTranscriptMessages.ts`，由“事件溯源 Reducer 纯函数管道”替代散落各处的 Ad-hoc 拼凑，对思维链（Reasoning Delta）、权威快照、本地回执建立统一的流水线合并规范。
4. **零破坏渐进式重构（Zero-Regressions & 100% Contract Preserved）**：
   - 保持所有对外 API、组件 Props/Emits、现有 423 套自动化单测全部兼容；重构每一步均有独立单测与回归验证保驾护航。

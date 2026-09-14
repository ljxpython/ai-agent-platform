# DeepSeek Harness 轨迹视图迁移

## 项目概述
- **时间：** 2026-09-14 至待定
- **目标：** 将 deepseek-harness 的可点击 Agent 轨迹与事件检查能力迁移到 platform-web 的运行工作台。
- **负责人：** @team
- **状态：** 已完成

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** platform-web、platform-api、runtime-service
- **改动级别：** 链路改动
- **预计工作量：** 6-10 人天（首期）

## 关键决策
1. 首期复用现有 Runtime SSE、`Transcript`、`ToolResult` 和 `SubtaskDetail` 数据，不直接搬 React/Cordis 组件。
2. 先做按事件展开的检查器和时间线；虚拟滚动、缩放时间轴等复杂能力后置。
3. 只有当前端缺少事件字段时才扩展 platform-api/runtime-service 事件投影。

# 有界调研委派与子智能体上下文隔离

## 项目概述
- **时间：** 2026-10-28 起；完成时间在基线测量后确定
- **目标：** 对长篇、可拆分的调研任务启用受限 Subagent 委派，让主 Agent 只接收带证据的短摘要；在现有上下文治理基础上验证主上下文、总 Token 预算和答案质量。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 方案已修订，待实施评审；实施未开始，并发预算边界和 GitHub 来源证据隔离是启用委派前置门禁

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划与记录](verification.md)

## 改动范围
- **影响服务：** apps/runtime-service
- **改动级别：** 单服务内部改动，不改变对外契约
- **主要位置：**
  - dearflow_agent/modes.py：为 Pro 模式开放受限委派
  - dearflow_agent/agent.py、subagents/：工具可见性和受限代码探索角色
  - runtime-service/tests/services/dearflow_agent/：模式、权限、并发、隔离与预算测试
- **不涉及：** Platform API/Web 功能、前端并发树、Artifact 新协议、独立 Subagent 调度引擎

## 已有能力与前置条件
- 当前 Agent 已使用 DeepAgents task 工具、researcher 子 Agent 和每父图 3 路并发限制；本项目复用这些能力。
- 上下文溢出落盘和 ToolOutputPruning 已在本地工作区实现并记录验证；相关文件尚有未提交改动。实现前先确认这些改动进入目标分支并运行现有测试。
- RuntimeUsageCallback 已采集主/子 Agent 命名空间用量及缓存 Token 字段；但并发在途调用是否纳入同一 Run 硬额度尚未证明，Phase 2 必须先验证，不能重复建设采集链路或提前开放委派。
- 产物发布工具和预览/下载页面已存在；本项目不增加新的交付 UI。
- 真实模型验收只使用公开仓库内容；执行付费或外部模型调用前需另行取得明确授权。

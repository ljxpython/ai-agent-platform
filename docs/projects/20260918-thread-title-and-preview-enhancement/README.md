# 会话标题识别与消息预览优化

> 2026-10-09源码复核：本项目交付规则命名、手动改名与侧栏AI提炼，Task2.4曾撤回自动完成回调。F07现已获批准并补齐后端/Runtime/引擎候选，前端和正式CAS发布未完成，见[F07实施](../20261009-agent-thread-auto-title/README.md)；本旧项目不证明自动标题已上线。

## 项目概述
- **时间：** 2026-09-18 至 2026-09-20
- **目标：** 解决会话列表标题千篇一律、副标题永久显示“(无内容)”的交互缺陷，提供手动重命名与智能标题生成能力。
- **负责人：** @laowang
- **状态：** 已完成（Phase 1 手动能力 + Phase 2 LLM 智能提炼全部交付完毕）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-web`, `platform-api`, `runtime-service`
- **改动级别：** 链路改动
- **预计工作量：** 2 人天

## 关键决策
1. **分阶段实施**：Phase 1 优先落地“手动重命名 + 预览内容修复 + 模板词清洗”（不改动 runtime-service 即可解除燃眉之急）；Phase 2 接入 runtime-service 智能 LLM 标题生成。
2. **职责边界清晰**：`platform-api` 负责会话元数据修改的网关透传与权限校验（`project.runtime.write`）；`runtime-service` 负责利用 LangChain 模型与底层会话历史生成精炼总结；`platform-web` 负责侧边栏内联编辑、手动 AI 提炼与标题同步。此处权限名称是原方案描述，当前授权事实及后续治理评审见 F07 规划，不据此绕过当前 ACL。

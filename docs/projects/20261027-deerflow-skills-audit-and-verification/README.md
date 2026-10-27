# DeerFlow Skills 全量迁移对齐、触发验证与缺陷治理工程

## 项目概述
- **时间：** 2026-10-27 至 2026-10-28
- **目标：** 系统性梳理参考项目 `deer-flow` 的全部 23 项 Skills 与本平台 `dearflow_agent` 现有 20 项 Skills 的迁移对齐度；建立详尽的触发指引与验证基准，逐个验证运行状态，彻底排查并根除潜在的契约退化、环境依赖缺失和执行故障。
- **负责人：** @老王
- **模板类型：** 标准模板
- **状态：** 已完成

## 快速导航
- [整体方案与技能全景图](plan.md)
- [任务拆分与执行追踪](tasks.md)
- [验证计划与实测记录](verification.md)

## 改动范围
- **影响服务：** `runtime-service`（`dearflow_agent` 核心服务、工具链、沙箱脚本与能力声明）
- **改动级别：** 链路改动（涉及 Skills 装配、底层工具链调用、沙箱执行与结果返回契约）
- **预计工作量：** 1.5 人天

## 核心阶段划分
1. **全景盘点与状态矩阵**：对照 `deer-flow` 建立 5 大类 25 项技能清单，逐一标明迁移状态、底层依赖与触发机制。
2. **Phase 1: 学术与深度调研类技能验证与排查**（`deep-research`, `github-deep-research`, `academic-paper-review`, `systematic-literature-review`, `consulting-analysis`, `code-documentation`, `newsletter-generation`）
3. **Phase 2: 数据分析与商业图表类技能验证与排查**（`data-analysis`, `chart-visualization`）
4. **Phase 3: 前端设计、规范与部署类技能验证与排查**（`frontend-design`, `web-design-guidelines`, `vercel-deploy-claimable`）
5. **Phase 4: 多模态生成与平台元技能验证与排查**（`image-generation`, `ppt-generation`, `skill-creator`, `skill-reviewer`, `find-skills`, `bootstrap`, `surprise-me`）
6. **未开放能力边界收口**（`music-generation`, `podcast-generation`, `video-generation`, `claude-to-deerflow`）

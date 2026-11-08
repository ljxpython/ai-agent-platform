# Runtime Agent 开发指南与入口纠偏

## 项目概述

- **启动日期：** 2026-11-08。
- **目标：** 让开发者明确如何在 runtime-service 中设计、实现和验证符合当前规范的 Agent。
- **模板类型：** 标准模板。
- **状态：** 已完成（done，仅文档范围）；首轮指南和追加的 45 篇 docs + 7 篇案例 README 全文审查、必要修订与静态验证均完成。
- **人工验收：** 2026-11-08 用户明确验收通过，并授权提交/推送、合并主工作区与清理本 Worktree 及所属测试资源。
- **范围：** 现有实现与规则的文档说明；不改变运行时架构、权限规则或公开契约。
- **范围调整：** 原 CI 接入与文档检查器扩展提案移出本期，不作为未完成任务。

## 快速导航

- [整体方案](plan.md)
- [任务与验收条件](tasks.md)
- [验证记录](verification.md)
- [52 篇逐篇审查清单](document-review.md)
- [追加实施记录](implementation/02-full-document-review.md)

## 本期交付

- [Agent 设计与开发指南](../../../apps/runtime-service/docs/standards/runtime-agent-development-guide.md)
- [案例与官方资料导航](../../../apps/runtime-service/docs/standards/runtime-service-reading-guide.md)
- [本地运行与验证](../../../apps/runtime-service/docs/standards/runtime-service-onboarding-and-verification.md)

1. 当前开发入口：应用 README → 文档导航 → Agent 开发指南。
2. 一条完整开发路径：需求设计 → 类型选择 → 模块职责 → 接入步骤 → 验证与交付。
3. 案例使用表：说明每个案例能学什么、不能证明什么，以及对应源码与测试。
4. 资料查询表：区分必读规范、按需专题、历史设计和官方 API 文档。
5. 追加轮 45 篇修订、7 篇保留；案例直接纠偏，历史资料逐篇说明有效边界、后续实现与缺失归档，不以统一标签代替审查。

## 边界

本轮按用户纠偏后的需求执行文档工作，原先提出的仓库 CI 治理不获本轮授权，也不继续实施。现有根 AGENTS、项目 Skills 和专题约束继续有效；遇到安全、权限、契约冲突，标记差异而不自行裁决业务实现。

规划与修改均位于当前关联 Worktree。主工作区的其他未提交改动不纳入本项目。保留原项目目录名称以便接续，不额外迁移目录。

## 验收后收尾

本次纯文档开发未初始化本 Worktree 本地栈，未创建服务或测试数据库。收尾已检查环境登记、进程真实目录和本机 PostgreSQL 名称/归属元数据，没有发现本需求所属的待停服务或待删数据库；其他专项的资源不在清理范围。

Git 合并与清理结果见 [verification.md](verification.md) 的“人工验收与交付收尾”。合并要求保留主工作区已完成的知识库、模型计价、看板与控制面功能，以合并后非 Markdown 文件和主干原版本完全一致作为静态保护检查。

# LangGraph v3 默认消费与 DeltaChannel 评估

## 项目概述

- **时间：** 2026-10-04 至待定
- **目标：** 将后端所有默认 Run 入口统一为 LangGraph v3，交付前端消费验收交接文档，并完成 DeltaChannel 的离线可行性验证和真实 checkpoint 体积测量。
- **负责人：** @lijiaxin
- **模板类型：** 标准模板
- **状态：** 部分完成：后端默认 v3、前端交接、离线 Spike 和本地 PostgreSQL 测量已完成；回滚门禁和前端浏览器验收待执行

## 快速导航

- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围

- **影响服务：** platform-api、runtime-service、GraphHarbor 运行时验证；platform-web 仅交付交接文档
- **改动级别：** 治理改动（跨服务事件契约、前端消费默认值、持久化格式评估）
- **预计工作量：** 4—7 人天，取决于真实持久化环境和浏览器验收可用性

## 范围边界

- **纳入：** P0 后端默认 v3、前端 v3 消费验收交接、v2 兼容、DeltaChannel 离线 Spike、真实 checkpoint 体积和恢复性能测量。
- **不纳入：** 节点级 timeout、节点级 error_handler、RunControl/request_drain；本项目只记录后续候选，不实施。

## 关键决策

1. 后端新 Run、stream 和 resume 的默认版本统一为 v3；显式 v2 和已保存 v2 Run 继续兼容。
2. 前端源码由同事实施，本分支只提供入口清单、事件映射、验收项和切换注意事项。
2. DeltaChannel 先做只读测量和隔离 Spike；没有 reducer 批处理不变性、恢复、回滚证据，不进入生产线程。
3. 生产 Agent Server/GraphHarbor 仍是 checkpoint 的所有者，Runtime 不新增自建 Checkpointer。
4. 未经用户明确批准，不执行数据库迁移、生产发布或 git commit/push。

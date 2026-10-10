# Agent 通用后台非阻塞任务能力

## 项目概述

- **立项/实施日期：** 2026-10-09；D01-D06 已获用户批准。
- **目标：** 让具备 Workspace 执行权限的 Agent 显式启动长命令后继续工作，并通过受管查询、取消和完成通知取得真实结果。
- **负责人：** 本轮 Codex 实施非前端范围；前端由用户同事负责；方案评审已由用户完成。
- **模板类型：** 标准模板。执行、授权、通知和停止互相依赖，按一个专项分阶段验收。
- **改动级别：** 治理改动。涉及跨服务契约、Runtime 应用表迁移、脱离原 Run 的资源生命周期和自动创建有费用的后续 Run。
- **状态：** `partial`。[B01](engine-handoff.md) 已解除：正式 post45 双包、服务锁与部署断言已接入，lost-ACK notify/Stop/撤权联合验收通过。T02/T03/T04/T06/T07 与 T09/F01-F11 已完成；T01/T05/T08 保留全范围验证和新镜像门禁，T10/F12 待全栈联合 Final。非 Docker 兼容 AB01-AB03 与 ABF01-ABF03 前后端独立验收已完成。
- **基础交付：** 后台 Docker 执行、持久租约对账、有界日志、三工具、四个公开接口、平台完成续接/开始前授权及 Stop 摘要已实施。原 post43 Linux 镜像、旧源码回退、K轮审批/固定Stop证据保留；新增 post45 固定接受回执与平台迁移 0007，发送前落盘最终 bytes/key/digest，未知接受只 GET 原回执、不二次 POST。正式源 notify/Stop/撤权三场景通过；新提交默认关闭，全范围故障/竞态矩阵和后端/全栈 Final 尚未完成，现役未部署。
- **2026-10-10 A/B 交付：** 指定 99f7 Worktree 完成模型能力门禁、旧 checkpoint 原回执和精确未启动兜底；91项 Runtime、12项真实PG、2项平台能力及两图真实 local API/Worker 通过。前端 ABF01-ABF03 独立验收已完成，专属栈保留联调。安装、服务锁与 Dockerfile 现均为 post45；B01 由独立接受回执专项的正式源联合证据解除。

## 阅读顺序

1. [源码对照与方案评估](reference-analysis.md)：open-swe 怎么实现、本项目已有能力及缺口、同事建议逐条判断。
2. [整体方案](plan.md)：三层职责、通用接入方式、状态与交付协议、代码位置、生产边界。
3. [任务拆分](tasks.md)：规划完成项、实施任务、先后依赖和逐项验收条件。
4. [验证计划和记录](verification.md)：单元、真实 PG/Docker/API/Worker 阶段证据、失败记录和未完成门禁。
5. [前端交接](frontend-handoff.md)：已实现的 v1 接口与 DTO、实际样本、交互状态、接续 Run 发现机制及 F01-F12 验收清单。
6. [引擎接续](engine-handoff.md)：B01 触发窗口、现有降级、所需只读契约和正式发行/复验清单。
7. [运维手册](../../runbooks/runtime-background-tasks.md)与 [Agent 接入规范](../../../apps/runtime-service/docs/standards/background-task-integration.md)：部署、drain/回退及新 Agent 四个接入点。
8. [A/B 非 Docker 兼容前端交接](local-compatibility-frontend-handoff.md)：本轮同事接续入口，含能力/探针门禁、恢复提示、浏览器验收、专属环境与可转发话术；既有 F01-F11 不重做。

`implementation/` 保存实际改动与验证细节；进度只看 tasks.md。

## 改动范围

| 层 | 必要性 | 实施状态 |
|---|---|---|
| runtime-service | 必须 | 持久任务/runner/对账/三工具/Stop 与 A/B 后端已实施；post45 固定只读回查及 suppressed/撤权链路已验，剩余全范围 Final 另验 |
| platform-api | 必须 | 当前授权、三精确 operation、四入口/安全 DTO/审计已验；最终 bytes 落盘与正式 acceptance adapter 已接入，B01 解除 |
| platform-web | 建议随产品交付 | F01-F11与ABF01-ABF03已完成；B01已解除，F12待T10全范围联合Final |
| GraphHarbor | 复用并需接续 | 原 post43 验收与只读回查缺口保留；新接受回执/正式依赖接线由 `20261010-run-acceptance-receipts` 专项实施，本轮不解除 B01 |
| 部署/工具链 | 必须检查 | Dockerfile 已对齐 uv.lock；默认关闭的单主机 overlay、运行/回退手册已交付，阶段结果见 verification |

本期只补后台 Workspace shell 命令。MCP Tasks、媒体供应商任务、持久 DAG、自动 Goal 续跑、GitHub/Slack/Linear、环境刷新、网络部署和预览端口发布不纳入。

## 关键建议

1. 保留普通 `execute` 的等待结果与 60 秒限制，新增显式后台工具，默认关闭新任务提交。
2. 首期支持单主机、同一 Docker daemon 和持久 Workspace 的受管拓扑；LocalShell 不提供本能力。
3. 借鉴 open-swe 的非阻塞工具、无模型监控、有界日志和完成后 enqueue；任务事实放 Runtime 应用表，执行证据来自可信 Docker 管理接口。
4. 采用已有 lifespan 对账模式处理到期任务，不为每个 Thread 建 cron 或复制 scheduler。原生 cron 继续服务已有定时 Agent 任务。
5. 完成交付只走平台授权的原生新 Run，明确 `multitask_strategy="enqueue"`；不同时投 inbox，也不打断正在执行的 Run。
6. 自然后台延续与用户停止分开：原 Run 正常成功后任务可继续；会话 Stop 固定捕获已有后台任务并抑制它们的未接受通知。
7. 后续 Run 是新增执行和费用，必须在开始前复核权限，保留 HITL；完成通知 Run 不得再次创建后台任务。

上述已由用户在 2026-10-09 批准为本专项设计；代码完成与验证状态以 tasks.md 为准。

## 人工评审清单

| 决策 | 需要批准的内容 | 推荐 |
|---|---|---|
| D01 | 首发执行拓扑和 Docker 控制权限 | 单主机/同 daemon；明确服务进程管理权限及宿主 Workspace 挂载；不给命令容器 Docker socket |
| D02 | 监控方式和延迟 | Runtime 有租约的轻量对账；轮询不调用模型；不使用每 Thread cron |
| D03 | 自动完成交付和费用 | 同 Thread enqueue 新 Run；每任务最多一个接受的通知 Run；开始前重授权；禁止自动后台任务链 |
| D04 | 生命周期和停止行为 | 正常成功可延续；父 Run error/timeout/用户 Stop 触发清理及抑制；HITL 不自动恢复 |
| D05 | 限额、日志权限和保留期 | 采用 plan.md 的首发有界值与日志总额；日志独立授权；去重回执随可重放来源保留，未知资源占用容量直到确认 |
| D06 | 对外契约与迁移/回退 | 三个精确 operation、新增 DTO/接口、Stop 加法字段、先迁移后启用、关闭提交后清空受管资源再回退 |

评审记录见 tasks.md。锁定依赖的实际缺口与解除条件已记入 engine-handoff.md；未执行 Git 提交/推送或生产发布。JWT/SSE 整体仍为 draft，不随本专项阶段通过而毕业。

## 工作量估计

后端与部署验证约 9-13 人天，前端约 2-3 人天，联合验收约 1-2 人天；T01 若发现必须跨仓库补引擎能力或调整部署拓扑，重新估算。估计不是排期承诺。

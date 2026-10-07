# Agent 运行生命周期超时治理

## 项目概述

- **启动日期：** 2026-10-06
- **目标：** 借鉴 open-swe 的模型收尾提醒，按 LangGraph Server Worker 的每次执行尝试语义补齐受信预算、终态和恢复验证。
- **负责人：** @lijiaxin；前端实现和浏览器验收由同事承接。
- **模板类型：** 标准模板。超时、收尾、恢复和展示属于一条耦合链路，不拆成多个独立专题。
- **改动级别：** 治理改动，涉及执行终止、Worker 重试、受信参数与持久运行语义。
- **状态：** 已完成（done，2026-10-08）。正式 post42 发布/平台锁定、12 组 HTTP、真实 Worker 接管与匹配版本回退均通过；前端超时治理实装（T11）及用户真实浏览器全链路验收（T12，含排队死锁自愈）100% 验收通过；本地开发服务已安全停止。
- **本轮边界：** 完成 GraphHarbor、Runtime、Platform API、Platform Web 前端实装及端到端联调闭环。准备向主线分支安全合并。

## 快速导航

1. [open-swe 源码对照与同事方案评估](open-swe-comparison.md)：参考实现、当前事实、差距和不采纳的设计。
2. [整体方案](plan.md)：时间语义、分层职责、代码补充位置、契约、安全和回退。
3. [任务拆分](tasks.md)：评审、GraphHarbor 依赖、Runtime、平台、前端和最终门禁。
4. [验证计划与记录](verification.md)：可执行用例、已有基线、Phase 与 Final 分离。
5. [前端交接](frontend-handoff.md)：接口、状态与F01-F10；第7节是可直接执行的UI/停止时序/开发顺序/联调条件/回执模板。
6. [LangGraph Worker 对照](langgraph-worker-parity.md)：官方 0.13.0 源码、配置和本次对齐边界；取代原跨 attempt 总截止点。

实施按实际改动创建 `implementation/` 记录；实施进度只看 `tasks.md`。

## 本轮实施结果与剩余门禁

GraphHarbor取消专项已发布 `graphharbor=graphharbor-runtime=0.13.0.post42`。本会话核对PyPI四产物哈希并复用正式版本，没有重复上传。当前Runtime依赖声明、锁文件和本机虚拟环境均为post42；独立冻结依赖环境完成冷安装。证据保存在 [evidence](evidence/README.md)，历史高负载、404及用户暂停轮次仍保留在verification的Phase区。

- GraphHarbor 每次 claim 生成当前 attempt 预算；同 Run 的故障重试或重启接管重新计时。工厂、执行及 drain 共用当前 attempt 的剩余时间，私有预算不进入公开 Run/事件。
- 模型/provider 超时最终为 error，不因此自动重跑整图；受支持的数据库故障才由 Worker 有界重试并从当前 Run checkpoint 继续。正常 checkpoint handoff 不消耗故障 attempt，租约代次始终递增。
- Runtime 已实现受信 `RunBudget`、通用软收尾、四正式图与主/子 Agent 共享预算、模型超时来源区分，以及 local shell 取消后的进程组清理。
- Platform API 已补客户端预算注入拒绝与递归脱敏，保持原生 `status/reason`；未增加接口或 SSE 事件。
- 官方Worker探针4项、真实PG/Redis116项及checkpoint补验通过；正式包完整12组平台HTTP覆盖软收尾/硬超时/模型error/HITL/三Thread/SSE/取消竞态/排队/G=0/防注入，包含真实SIGTERM与新PID接管。旧10-06 deadline结果仅作历史。
- **回退完成：** 当前Runtime/post42先drain并暂停提交，再切换到匹配旧Runtime源码/post41；同Run从checkpoint继续、pending/历史/工作区保留，回退后普通运行/取消/HITL通过，无Schema迁移。新Runtime不得只把依赖降为post41。
- **回归边界：** Runtime全量617 passed/2 failed，API全量326 passed/2 failed/654 subtests；四项失败在旧源码对照同样复现，分别为PTY回显时序和既有HTML预览断言，未改无关实现。API自身锁定SDK0.4.2的85项定向unittest通过；没有宣称全仓全绿。
- **前端与端到端闭环：** 前端 T11 完成 F01-F10 规范对齐（胶囊展示、停止双通道确认防死锁、单测 108/108、vue-tsc 零错误、build 成功）；用户在浏览器交互中进一步排查并治本解决了排队提交未决死锁与切换自愈（T12 Final），端到端验收通过。服务已停止，准备合入主工作区。

当前 worktree 为 detached HEAD，基点 `0bc15df1840c83750d821c93fb65600d0d483fa4`；没有创建开发分支、提交或推送。

## 核心结论

| 问题 | 核对结论 |
| --- | --- |
| 当前是否没有整体运行超时？ | 不准确。GraphHarbor post41 已有执行尝试硬限；官方 Server 同样按每次 attempt 计时，本次保持该语义。 |
| 是否直接加一个 2700 秒 middleware 就够了？ | 不够。现有开发模板硬限为 1800 秒，容器模板为 300 秒；2700 秒提醒可能永远不会触发。 |
| open-swe 如何收尾？ | 默认首次模型调用开始计时，超过 45 分钟后在后续模型请求追加收尾提示；没有强制结束或保存进度的保证。 |
| 前端是否必须开发？ | 运行保障不依赖前端；现有 Chat 已识别 timeout。同事负责必要的展示适配和回归，本轮仅交接。 |
| platform-api 是否需要调度器？ | 不需要。复用 Run 查询、授权、脱敏、幂等和终态透传，不建运行状态镜像或强杀定时器。 |
| Runtime 是否需要补代码？ | 需要：消费 Worker 时间预算、显式装配收尾 middleware、保证主/子 Agent 共享截止点，并区分单次模型超时。 |
| GraphHarbor 是否需要补代码？ | 需要：提供私有attempt预算，纠正模型错误重试分类，分离handoff与故障次数；正式post42已发布并接入验收。 |

## 建议验收范围

1. 按单个 Worker attempt 计算：领取后开始计时；同 Run 重试/接管创建新 attempt，采用接管 Worker 的 H，退避和停机不累计到下一 attempt。
2. 首次排队不计入运行预算；HITL 使原 Run interrupted，审批恢复产生新 Run，重新计算预算。
3. 复用 `GRAPHHARBOR_RUN_TIMEOUT_SECONDS` 作为硬限唯一来源；新增收尾预留时间，而非第二个同义总超时变量。
4. 收尾是模型调用边界上的软提醒；硬超时由 Worker 取消执行、释放资源并持久化原生 timeout 终态。
5. 不迁入 open-swe 的 GitHub/PR/Linear/Slack、仓库身份、桌面或业务 completion webhook。

10-06 用户批准实施；10-07 明确要求按官方 Worker 实现，取代原跨 attempt 截止点。累计 Run/Thread/任务总预算不在本期范围。

## 影响范围与依赖

- **runtime-service：** 公共 middleware、四个正式图组合根、配置校验和相关测试。
- **platform-api：** 私有字段拒绝/脱敏、Run 结果和错误语义回归；不增加产品调度模块。
- **platform-web：** 前端交接；同事实施必要适配、SDK/多会话和浏览器验收。
- **GraphHarbor：** 独立依赖的通用 Worker attempt 预算与重试/交接对齐，见方案中的准确包路径；从正式源码构建候选包并隔离安装，不修改 `site-packages`。
- **预计工作量：** 约 5-7 人天，包含 GraphHarbor、隔离联调和前端回归；人工评审及依赖发布等待不计入。

## 与其他专项的边界

- SSE 心跳、410 恢复、缓存治理沿用现有专项，不在本次重建传输层。
- [Chat 持久消息队列](../20261005-durable-chat-prompt-queue/README.md)保有 FIFO、取消及审批阻塞职责；本次只验证 timeout 后不重复提交和不吞补充消息。
- [DearFlow 可靠性重审](../20260913-dearflow-agent/14-effect-parity-and-reliability.md)保有响应终止、循环、Todo 与证据验收任务；时间预算不替代这些能力。
- `docs/knowledge/open-swe-vs-runtime-gap.md` 第 4 节是本次待核对的参考，关于“没有整体超时”的判断以本项目源码核对结论为准。

## 评审记录

| 项目 | 当前记录 |
| --- | --- |
| 评审对象 | `plan.md`、`tasks.md`、`verification.md`、`frontend-handoff.md` |
| 评审人 / 日期 | 用户 @lijiaxin / 2026-10-06 |
| 预算范围、默认值、GraphHarbor 契约 | 当前 plan.md：每 attempt、现有平台 H、G=120（0 关闭）、排队/退避不计、HITL resume 新 Run、协作取消；通用底座支持官方 BG_JOB 配置 |
| 批准结论 | 用户明确：“我已经评审完成，可以开始实施了，任务推进到只剩下前端的相关事项，除非遇到 block 的事项。”已核对 GraphHarbor 独立正式 checkout；保留其现有 cron 改动。 |
| 10-07 修订指令 | 用户明确：“langgraph server 的 worker 的能力也是这样的吗？graphharbor 要按照 langgraph server 的能力实现。”按官方 0.13.0 核对并实施 T13；不含发布/现役部署授权。 |
| 10-07 发布与暂停指令 | 用户授权本机使用 `~/.my_best/.env` 发布；随后确认另一会话仍在实施取消传播专项，明确要求“我们先停一下，等他结束后我们再开始”。发布授权保留，本会话暂停，等待用户恢复。 |
| 10-07 恢复与交付 | 用户明确“一个专项已经结束了，你可以继续了”。复用该专项已发布的post42，完成平台锁定/冷安装/正式包HTTP与匹配回退；前端及联合Final交同事。 |

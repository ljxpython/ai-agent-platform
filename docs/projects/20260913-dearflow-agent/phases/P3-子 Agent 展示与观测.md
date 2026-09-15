# P3 子 Agent 展示与观测：阶段执行包

> 本文件是 P3 实施时的唯一执行入口。先看需求清单了解做什么、交付标准和当前状态，再按专题链接查实现细节。需求清单与专题任务一起更新；已有代码不等于验收完成。用户本轮再次确认：只做后端，F3 前端保留交接；后端完成与整阶段完成分开标记。

## 阶段目标

普通子 Agent 详情、稳定关联、父 Run 取消反馈、已有 usage 展示

## 需求清单

优先复用现有普通子 Agent 能力，并修复实际缺陷；普通 task 已存在不代表以下需求已验收。

| 需求点 | 要交付什么／怎样算完成 | 对应专题 | 当前状态 |
|---|---|---|---|
| 普通子 Agent 执行 | 复用官方同步子图，传入必要任务和证据，不传递凭据或全部父状态 | 05/S-A | done：并发与父输入隔离组合通过；未新建执行器 |
| 稳定任务关联 | 用调用 ID 和 namespace 关联消息、审批、文件及结果；同角色并发任务不串线 | 05/S-B；08/W04 | 后端 done：native／GraphHarbor debug关联回归及来源隔离通过；前端适配 deferred，当前只读角色不验子审批／写文件 |
| 子任务工作区边界 | 验证文件归属和隔离，明确哪些引用可共享，不依赖角色名称区分目录 | 04；05 | done：只读共享线程资料；禁止写入、执行、再委派；同内部调用 ID 的来源由 namespace 区分 |
| 结果与状态核验 | 区分成功、失败、中断和取消；结果引用可读取，无证据不能声称产物完成 | 05；03 证据 | partial：组合成功／权限拒绝／父取消验证通过；真实完整成功链路仍需补齐，未新增结构化结果验收框架 |
| 断线和父 Run 取消 | 刷新、缺失 discovery、断流后从引擎恢复事实；父取消不能把未完成任务显示成功 | 05/S-C | partial：真实父取消至 interrupted 通过；浏览器断流／刷新 deferred |
| 已有 tracing 与用量 | 复用现有字段，保留父子关联；未知用量显示未知，不估造子任务费用 | 05/S-D | partial：受信字段丢失已修复，callback 与消息 usage 组合通过；外部导出 blocked，展示 deferred |

明确后置：独立 child Run、单子任务取消、独立调度恢复与完整子任务用量归属。现有能力无法提供的部分记录限制，不在本阶段另建执行系统。专题内 S-A/P1 等为原切片标签，本项目施工阶段以此 P3 执行包为准。

## 必读上下文

- 总纲：[README.md](../README.md)
- 主专题：[05-subagents-and-lifecycle.md](../05-subagents-and-lifecycle.md)
- 任务切片：`05/S-A—S-D；04 子任务工作区；08/F3、W04`

## 本阶段任务

### 从 P2 接续的实际基础

P2 后端功能和一次真实研究闭环已通过，但整阶段仍 partial：重复运行出现 Redis／Worker 超时，外部观测导出未验收，前端本轮后置。P3 可以先做下面第1步核查与确定性测试；最终平台取消／断线／观测验收需要先收口这些环境问题，不能直接宣称 P2 全部完成。

已经存在的代码：

- Runtime：`apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`、`subagents/researcher.py`、`middleware/delegation.py`、`tools/search.py`。Ultra 使用普通同步研究子图，最多3个并发 task、累计调用限额、只读研究权限；P3 不再建第二个执行器。
- 前端：`apps/platform-web/src/modules/dear-agent/components/SubagentCard.vue`、`components/SubtaskDetail.vue`、`composables/useTranscriptMessages.ts`、`transcript.ts`、`trajectory/trajectory-adapter.ts`。这些是已有展示基础，不等于 F3 全部验收。
- 观测：`apps/runtime-service/src/runtime_service/observability/langfuse.py` 及官方消息／回调；只消费确实存在的关联与 usage 字段。

### 推荐施工顺序与交付内容

| 步骤 | 具体开发／验证内容 | 代码落点与对接 | 验收证据（实施后回填） |
|---|---|---|---|
| 1. 核查实际事件 | 用两个同角色并发研究任务采集父 Run、task 调用 ID、真实 namespace、子工具消息与最终结果；写清字段来源 | `apps/runtime-service/tests/services/dearflow_agent/test_subagents.py` | 已完成采集：native lifecycle 与 GraphHarbor debug 字段不同，真实结构和兼容限制见07；根/子消息隔离通过 |
| 2. 稳定任务归属 | 修复按名字兜底及猜测 namespace；缺失关联显示未知／恢复中，禁止串接另一任务 | 现有 Dear `SubagentCard.vue`、`SubtaskDetail.vue`、transcript／轨迹适配器；先核对官方 SDK 数据 | 同名并发、缺失 discovery、重连后不串线；前端待安排 |
| 3. 只读工作区和结果 | 验证当前子图只能读取获准资料／检索，不能写入、执行或再次委派；来源按 namespace＋调用 ID 归属；父 Agent 核对真实引用 | Runtime `subagents/researcher.py`、`tools/search.py` 及现有工作区；仅发现缺陷时修复 | 只读权限3种拒绝与来源隔离通过；不新建每子任务目录，未实现通用结果验证器 |
| 4. 父取消与恢复 | 沿用现有父 Run 取消；验证取消竞态、断流、刷新与超时，不把 ACK／流结束视为子任务成功 | `apps/runtime-service/tests/services/dearflow_agent/test_platform.py`；官方 Run／子图状态 | 真实父取消1项通过、组合传播通过；双子任务成功链路超时记录见07；浏览器恢复后置 |
| 5. 已有观测与用量 | 核对 parent span／namespace／调用 ID；仅在现有信息足够时展示输入／输出用量，缺失标未知，避免父级总量与子级重复相加 | `apps/runtime-service/src/runtime_service/observability/langfuse.py` 与对应测试 | 4个受信字段保留已修复；callback父关联和消息usage通过；外部Langfuse导出超时，未声称已验收 |
| 6. 收口 | 后端并发／权限／取消回归；前端落实后从 Dear 路由做刷新、同名任务及失败状态验收 | 本执行包与07实施记录，每项列完整修改路径和实际命令 | 39 passed、1 skipped；真实父取消通过；完整成功运行仍超时，事件积压约80秒的排查证据见07；F3 deferred |

以上不要求新增一批 analyst／writer／chart 角色。P3 先用现有 research 角色证明稳定关联，后续 Skills 出现真实需要时才加角色。当前研究子图未开放提问／写文件审批工具，因此不为展示验收额外给子图增加这些权限；新增这类角色时再验证多中断归属。

### P3 完成后用户能看到什么

Ultra 委派后可以区分两个同名研究任务，查看各自真实步骤与结果；失败、未完成和父任务取消反馈准确；刷新后能恢复已知事实；已有用量有来源，无数据明确未知。独立取消、独立恢复、完整用量归属和结构化结果验收框架继续 deferred。

### 范围状态

- [x] P3 范围与已有代码落点已细化到本执行包。
- [x] 后端并发／来源隔离／只读权限与取消传播测试；兼容事件证据见07。
- [x] 修复追踪受信字段丢失并增加回归；无新增执行框架。
- [ ] F3 前端接入：deferred，用户本轮明确只做后端，需单独安排；交接见 frontend-handoff.md。
- [ ] 真实平台稳定性门禁与联合验收。

- [x] 按上方任务编号读取对应专题的“工作上下文／任务拆分／验证要求”。
- [x] 只创建本阶段实际需要的测试和实施记录，无未来目录脚手架。
- [x] 实施记录写入07，代码路径逐文件列出，前端需求写入交接。

## 前置条件

- [x] 前一阶段已明确记录 partial／blocked。
- [x] 本阶段涉及的契约生产方与消费方已在08及前端交接登记。

## 验收

- [ ] 使用专题文档列出的确定性测试和实际受影响链路验证。
- [x] 未实现能力标记 deferred／partial，不用模拟结果勾选完成。

## 状态

partial：后端复用与必要修复已落地，组合及真实父取消已有通过证据；真实双子任务完整成功与外部观测仍需收口。F3 前端经用户明确确认 deferred。逐项代码、命令、成功与失败证据见 [07 实施记录](../implementation/07-p3-subagents-and-observability.md)；未宣称 P3 全部验收完成。

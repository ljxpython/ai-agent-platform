# open-swe 源码对照与方案评估

> 本文保留2026-10-06实施前的源码对照基线，表内“当前”指规划时post41。后续T02-T09实现与候选post42隔离验收见[实施记录](implementation/01-budget-and-wrapup.md)和[验证记录](verification.md)；正式锁仍post41，发布门禁未完成。

> 2026-10-07 修订：下表“本次需要补什么”已按[官方 Worker 对照](langgraph-worker-parity.md)更新。此前跨 attempt 固定总 deadline 的建议被用户要求取代；open-swe 源码基线不变。

## 证据范围

核对日期为 2026-10-06。本文中的 `open-swe/` 指用户提供的本地参考 checkout；参考路径均相对其根目录，不要求其他开发者拥有相同本机路径。

- 当前平台基线：`0bc15df1840c83750d821c93fb65600d0d483fa4`，开始规划时工作树干净。
- open-swe HEAD：`ad417d64d91cc349d63d832c7b643637dc1774cf`，存在大量本地修改及未解决合并冲突。因此本文比较**实际读取的工作树**，不将其等同上游发布版本。
- `agent/middleware/timeout_wrapup.py`、`agent/server.py`、`tests/agent/test_timeout_wrapup.py` 均有本地修改；prompt 是本地新增资源。
- 当前安装并核对的依赖：GraphHarbor `0.13.0.post41`、LangGraph `1.2.11`、LangChain `1.3.17`、Deep Agents `0.7.8`。
- `apps/runtime-service/pyproject.toml` 锁定 GraphHarbor post41 与 LangGraph 1.2.11；其余依赖以锁文件和实际安装版本为准。

关键证据 SHA256：

| 文件 | SHA256 |
| --- | --- |
| open-swe `agent/middleware/timeout_wrapup.py` | `ef9e4d6e7d0362d512dc5774e3f2144f57b2bc8644c142ac2470c3ef567e26e1` |
| open-swe `agent/resources/prompts/timeout-wrapup.md` | `f1a2b1922a63b9bda8fce46b3007855cd9c999855a09902eec9e3174e7cfb61e` |
| 已安装 GraphHarbor `langgraph_runtime_pg/production_worker.py` | `d3a8b46f0ad73685d35e489c9bb6c56b1f69b89e3466efd921a72da7bd6220fd` |

源码存在、实际装配、部署启用、测试通过和生产效果是不同的证据层级。规划阶段没有读取现役私密 `.env`，也没有启动或重启服务；实施阶段只启动隔离验收实例，不能据模板断言现役超时值。

## 1. open-swe 实际怎么做

| 位置 | 实际设计 | 可借鉴内容 |
| --- | --- | --- |
| `agent/middleware/timeout_wrapup.py:15` | 默认提醒阈值为 `45 * 60`，由 `OPEN_SWE_WRAPUP_TIMEOUT_SECONDS` 覆盖；非法配置回退默认值 | 将收尾提醒与单次模型超时区分，避免无界模型循环 |
| 同文件 `TimeoutWrapupMiddleware.__init__/_should_wrapup` | `_start=None`；首次检查时才取 `time.monotonic()`，不是构造时或 `abefore_agent` 计时 | 避免图发现/缓存让运行时钟提前老化；单进程用 monotonic |
| 同文件 `_content_with_instruction/_apply` | 处理无 system message、字符串和结构化块；检测重复提醒，再通过 `request.override()` 生成新请求 | 保留结构、缓存标记及原请求，重复调用不叠加提示 |
| `agent/resources/prompts/timeout-wrapup.md` | 要求完成当前步骤、保存或报告有用状态、停止新调查并给出当前最佳结果 | 使用通用收尾语义，不携带 PR、仓库或渠道业务属性 |
| `agent/server.py:1321` | 主 Agent 的 `create_deep_agent(..., middleware=[...])` 显式装配，模型超时位于更内层 | 在组合根声明顺序，并验证模型实际收到提示 |
| `agent/reviewer.py`、`agent/analyzer.py` | 对相关根 Agent 单独装配 | 不能仅看导出文件就认为所有 graph/子 Agent 都已覆盖 |
| `tests/agent/test_timeout_wrapup.py` | 测惰性启动、重复提醒去重、结构化 system content 保留 | 复用测试思路，增加我们自己的并发、重建与恢复验证 |

该 middleware 没有强制停止工具、控制外部进程、写 checkpoint、生成可靠最终报告或持久化 timeout 终态。正在执行的模型/工具不会因达到提醒阈值被它打断；只有**之后再发模型请求**时才可能收到提醒。

计时从首个模型请求开始，也就不覆盖此前的鉴权兑换、沙箱准备和工具初始化。它依赖“每次 Run 构建一个实例”的假设；按子 Agent 单独构造新实例会再起一个时钟，跨 Worker 重建也没有持久预算。

## 2. 规划时平台基线能力

下表中的 Runtime 路径相对 `apps/runtime-service/`，平台路径从仓库根开始。

| 能力 | 当前源码事实 | 本次需要补什么 |
| --- | --- | --- |
| 单次模型硬超时 | `src/runtime_service/middlewares/model_call_timeout.py:ModelCallTimeoutMiddleware.awrap_model_call` 使用 `asyncio.timeout`，默认 600 秒；环境变量 `AGENT_MODEL_CALL_TIMEOUT_SECONDS` | 保留；增加可识别的本中间件超时类型，避免与 provider 自身 TimeoutError 或整体 run timeout 混淆 |
| 整体执行尝试硬超时 | GraphHarbor `langgraph_runtime_pg/production_worker.py:ProductionWorker.run_once` 使用 `asyncio.wait(..., timeout=self.run_timeout_seconds)`；包含图工厂和 invocation | 复用此 Worker，不在平台再建强杀定时器 |
| 硬超时配置 | `.env.example:22` 为 1800 秒；`deploy/.env.runtime-service.example:70` 与 host-infra 示例为 300 秒 | 检查环境值与收尾预留关系；不照搬 2700 秒 |
| 硬超时终态 | 同一 Worker 对 `RunTimedOut` 调用 `RunRepository.finish(..., RunStatus.TIMEOUT, reason=TIMEOUT)` | 验证 timeout 唯一落库、取消竞态及资源清理；普通模型 TimeoutError 不是这个分支 |
| 普通超时的重试 | `production_worker.py:_is_infrastructure_error` 把 `TimeoutError` 归为基础设施错误，`RunRepository.fail` 可按现有次数上限重试 | 这是与官方 Worker 的差异；普通模型/provider TimeoutError 应落 error，不触发整图重试，数据库瞬时故障保留有界重试 |
| 用户取消与 HITL | `ProductionWorker.run_once` 均结束为 interrupted，分别 reason=cancel_requested/hitl_interrupt；`run_state.py` 约束合法转换 | 前端核实 reason/state，不要求新 cancelled 状态；HITL resume 新 Run，保持审批职责 |
| 同一 Run 的多次尝试 | `run_store.py:claim_next/fail/requeue_expired` 持有租约和有界重试；每次 `run_once` 重新等待完整 timeout | 保持官方每 attempt 计时，提供当前 attempt 私有预算给 Runtime；checkpoint handoff 与故障次数分开 |
| Worker 优雅停机 | `ProductionWorker.run_once` 的 shutdown 分支改用独立 `drain_grace_seconds` 等待，没有按原 H 剩余时间缩短 | drain 必须受原截止点约束，不能在接近 H 时又获得完整 grace |
| 可用执行身份 | LangGraph `Runtime.execution_info` 有 run/thread/node 标识，没有整体运行开始时间或 deadline；`node_first_attempt_time` 是节点时间 | Worker 显式提供受信 Run 预算，不能拿节点时间或客户端创建时间冒充 |
| 图构建 | `services/dearflow_agent/agent.py`、`services/demo/showcase_demo/agent.py` 等工厂按请求组合；GraphHarbor `GraphRegistry.open` 每次打开工厂 | 在 graph factory 消费同一个预算，不用全局 `_start` 或按 Thread 计时 |
| 子 Agent | DearFlow 与 Showcase 显式装配主/子 middleware；现有父取消和 namespace 测试 | 子 Agent 共享根 Run 截止点，不在启动子任务时重置 |
| 模型/工具次数限制 | 四个正式图已有 `ModelCallLimitMiddleware`，复杂 Agent 有 `ToolCallLimitMiddleware` | 沿用；次数限制、token 限制、超时是不同机制，不因本项目顺带重构预算体系 |
| 中断与历史修复 | `RuntimeConfigMiddleware` 验权限、过滤工具、修复 tool-call 历史；官方 HITL 与 checkpoint 恢复 | 收尾不得绕过审批或授权；取消时保留最后完整 checkpoint |
| 工具执行清理 | `src/runtime_service/workspace/execution.py:execute_in_workspace` 已处理取消/超时后的 Docker 清理；各服务 backend 另有 local/Docker 路径 | 故障注入验证清理真正生效，不能承诺外部供应商请求也被取消 |
| 平台执行网关 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:_execution_config` 限制公开 config；平台负责权限、幂等、快照及转发 | 拒绝客户端注入新内部预算；继续透传原生终态，不保存第二套 Run 表 |
| 事件/结果区别 | 同文件 `_normalize_protocol_lifecycle_frame` 适配 SDK event label，同时保留 status；Run JSON 查询保持执行状态 | 验证 Protocol 的 completed 不被解释为业务任务全部成功 |
| 前端 | `apps/platform-web/src/modules/chat/composables/useChatSession.ts` 已在 busy/status 中识别 timeout，stop 调 cancel 后核实；恢复单独在 `useSessionConnection.ts` | 不再造运行状态机；同事补必要说明与回归，不能用浏览器计时决定终态 |

## 3. 对同事五点方案逐条评估

| 原建议 | 判断 | 落地修正 |
| --- | --- | --- |
| “当前没有整体 run wall-clock 超时” | 需要纠正 | 已有执行尝试硬限，官方 Worker 同样按 attempt；缺口是软收尾、受信共享预算、错误分类/交接次数对齐及完整生命周期验证 |
| 在 `abefore_agent` 赋开始时间 | 可用于局部演示，不足以治理整个 Run | graph factory 在该 hook 之前；子图或 invocation 重建也会重置。整体开始时间由 Worker 持有 |
| 每次 `awrap_model_call` 判断并追加提示 | 采纳 | 使用 Worker 提供的截止点，保留结构化 SystemMessage、去重、原请求不变与显式 middleware 顺序 |
| 独立 `AGENT_RUN_TIMEOUT_SECONDS=2700` | 不采纳同义配置与固定默认 | 硬限复用 `GRAPHHARBOR_RUN_TIMEOUT_SECONDS`；新增 `AGENT_RUN_WRAPUP_RESERVE_SECONDS` 表示硬限前的预留窗口 |
| “platform 层强杀，这里优雅退出” | 需要纠正分层 | GraphHarbor Worker 负责取消与 durable 终态；platform-api 的 HTTP 超时、SDK 断流和浏览器停止不是整体执行硬限 |
| 单独放 Markdown prompt 文件 | 非必要 | 首期短通用指令用模块常量即可；若选择资源文件，必须增加 wheel package-data 及冷安装验证，不能只在源码目录读得到 |

“快到超时”必须定义为 `elapsed >= H - G`，而不是已经超过硬限 H 再提醒。提醒仍是 best effort；不能在没有后续模型调用时承诺有最终总结。

## 4. 三层如何融入当前范式

| 层 | open-swe 参考方式 | 当前平台对应方式 | 是否需要开发 |
| --- | --- | --- | --- |
| 前端 | `ui/src/features/agents/lib/stream/AgentStreamProvider.tsx`、`provider/useSubmitAgentMessage.ts` 消费 SDK、区分提交与观察；timeout middleware 本身不在前端 | Vue 的官方 SDK controller、Chat composable、服务层和现有状态条 | 不承担计时终止；必须做交接与回归，必要展示小改由同事完成 |
| 平台后端 | `agent/dashboard/threads/{proxy,runs}.py` 代理命令/事件，`dispatch.py` 创建 durable run，部分 completion 路径混有业务通知 | platform-api 网关与 run_requests；身份/项目/模型/工具授权在平台，执行事实在 GraphHarbor | 需要参数保护和契约回归，通常无新 CRUD/调度器/表 |
| Agent Runtime | `agent/server.py` 显式组合 Deep Agents 和 middleware，按 graph 权限裁剪；收尾通过模型请求注入 | `services/<service>/agent.py` 唯一组合根，公共原子 middleware、官方 backend/子 Agent/HITL | 需要补软收尾及共享预算装配 |
| Runtime Worker | open-swe 依赖其 LangGraph Agent Server 执行基础设施，所读 wrap-up 代码不实现硬限 | GraphHarbor 独立 API/Worker、PG 状态/租约/checkpoint、Redis 唤醒 | 复用每 attempt 硬限，补私有预算桥接并对齐官方重试/停机能力 |

## 5. 借鉴边界

保留有代码依据的思想：组合根显式装配、单进程 monotonic、请求不可变覆盖、结构化 prompt 保留、调用预算与 Run 预算分离、官方 SDK 的提交/观察分离。

本期不迁入：GitHub login/token/repository、PR review/check/branch、Linear/Slack 路由与通知、桌面 worktree、sandbox provider 名单、coding 专属完成判定。也不顺带复制 fallback/熔断/自动重试框架、金额计费、Token 预算、动态工具发现和通用 completion webhook。

它们有各自需求和验收范围；本次的验收对象仅为时间预算、收尾提醒、终态与恢复链路。不能因为 open-swe 有某个文件，就认定当前缺失或必须复制。

## 6. 官方 API 核对

已查询 `langchain-docs` 与 `langchain-reference` MCP，并核对锁定安装源码：

- [自定义 middleware / Dynamic prompt](https://docs.langchain.com/oss/python/langchain/middleware/custom#dynamic-prompt)：使用 `system_message`、结构化 content blocks 和不可变 override。
- [ModelRequest.override](https://reference.langchain.com/python/langchain/agents/middleware/types/ModelRequest/override)：明确支持 `system_message`，不修改原请求。
- [AgentMiddleware.abefore_agent](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/abefore_agent)：是 Agent 开始 hook，不是 Worker Run 生命周期总入口。
- [LangGraph 节点超时](https://docs.langchain.com/oss/python/langgraph/use-graph-api#configure-node-timeouts)：`TimeoutPolicy(run_timeout=...)` 针对单个异步节点尝试，不是整张图或 durable Run 的总限。
- [Agent Server BG_JOB_TIMEOUT_SECS](https://docs.langchain.com/langsmith/env-var-self-hosted#bg_job_timeout_secs)：官方每attempt配置；post41未直接支持同名变量，本次post42已源码对齐、正式发布并在使用方锁定验收。

# 前端交付报告：Agent 执行预算提示

交付日期：2026-10-07。Runtime/Platform API 的非前端开发与验证已全部完成；前端已在当前工作树落地 F01-F03 初版草稿实现，但经技术审查，代码中存在响应式订阅断裂、Zod 重复解析性能黑洞、SafetyError 降级误判（Thread 耗尽误给草稿重发）、复读机式重复文案与预警状态下取消按钮丢失等严重缺陷。当前任务是在现有工作树改动基础上进行架构与契约重构纠偏，并完成 F04 联合验收。详细类型、文案、权限动作与 H01-H16 验收见[前端交接](frontend-handoff.md)，真实公共事件见[安全证据 JSON](implementation/budget-http-evidence.json)。

## 开发工作树与交接入口

- 本机开发工作树：`~/.codex/worktrees/ce00/ai-agent-platform`。本轮 Runtime/API 源码、测试和项目文档均在该工作树；前端接续目录为其中的 `apps/platform-web/`。
- 当前 Git 状态：detached HEAD，改动尚未提交或推送。**前端工作树中已有部分代码改动（包含 `budget/` 模块、`useRunBudget.ts` 及 4 个相关 Vue 组件）**；接手必须基于当前文件进行重构与纠偏，严禁直接 `git checkout` 覆盖冲掉已有骨架。
- **前端依赖环境准备**：当前 worktree 下若未创建 `node_modules` 软链或依赖，开工前需在仓库根目录确认依赖就绪（如 `pnpm install`），避免本地测试或门禁因缺失依赖直接报错。
- 主交接报告：本文件，仓库相对路径为 `docs/projects/20261007-agent-execution-budget/frontend-delivery-report.md`，用于确认范围、任务、联调入口和回执。
- 详细实施契约：[frontend-handoff.md](frontend-handoff.md)，用于确定字段校验、SDK 消费、状态文案、用户动作和 H01-H16 验收要求。

本机可先确认位置及状态（以下命令只读取）：

```bash
cd "$HOME/.codex/worktrees/ce00/ai-agent-platform"
git rev-parse --show-toplevel
git status --short --branch
```

## 如何熟悉需求

先理解本项要解决的用户问题：Agent 接近额度时没有预警，因限制停止时缺少准确解释。后端已产生可信执行事实，前端需要在现有聊天流程中展示预警、收尾和停止原因，并保留已经生成的消息与成果。本期前端工作为 F01-F04 重构纠偏和 T08B 浏览器联合验收。

| 顺序 | 阅读入口 | 看完需要掌握什么 |
| --- | --- | --- |
| 1 | [项目状态快照](../../CONTEXT.md)、[本项目概览](README.md) | 三服务分工、本期范围、后端已完成与前端待办；整体项目仍为 partial |
| 2 | [整体方案](plan.md)的目标、预算口径与三层职责 | 模型调用数和图 superstep 的区别；Run 与 Thread 限额；软收尾与 Worker 硬超时的区别 |
| 3 | [详细交接](frontend-handoff.md)的通知契约、SDK 订阅、硬错误与历史回退、状态文案、用户操作 | 哪个字段可信、如何关联当前 Run/namespace、如何通过增量事件与 LRU 去重、安全错误未知 scope 降级、哪些用户动作允许 |
| 4 | [真实事件样例](implementation/budget-http-evidence.json) | 对照 model_end、graph_low、soft_finish、parallel_child_limit，看 custom、lifecycle 和历史标记的实际形状；注意 seconds 为高精度浮点且 remaining 为 null；这些 ID 只用于取证 |
| 5 | [任务清单](tasks.md)的 F01-F04/T08B、本报告下方代码入口 | 沿 useSessionConnection → useChatSession → ChatAgentStatusBar/ChatSession/SubagentCard/SubtaskDetail 追踪现有链路；确认预算数据在哪里接入、页面在哪里展示 |
| 6 | [前端开发规范](../../../apps/platform-web/docs/frontend-development-playbook.md)、详细交接 H01-H16、[验证记录](verification.md) Final-B | 按现有开发范式重构实现，补测试和真实浏览器证据，完成验收回执 |

需要理解参考方案的取舍时，再读 [open-swe 源码对照](open-swe-comparison.md)。本项目采用结构化通知和原生错误分类；前端根据服务端字段判断停止原因，不能扫描消息中的英语限制短语。

开始写前端前，应能解释三个具体场景：model_end 虽为 success 仍要说明额度停止；soft_finish 的 wrapup_started 保持运行语义；并行子图通知按 namespace 归属，父图结果服从真实 Run 终态。然后按 F01 增量解析投影 → F02 消除文案复读并保留取消 → F03 严格动作分流（Thread 禁用当前会话重发） → F04 门禁及浏览器验收推进。

## 已可使用的能力

| 后端能力 | 前端接入要点 |
| --- | --- |
| 模型额度预警/触限 | custom v1 的 model_call_limit_approaching / model_call_limit_reached；区分 run 与 thread |
| 图步骤预警 | graph_step_limit_approaching，单位 graph_supersteps，不是工具次数 |
| 可选时间软收尾 | wrapup_started，仍在 running；数值为浮点秒数，remaining为null；AGENT_WRAPUP_AFTER_SECONDS 缺省关闭 |
| 四类硬停止安全码 | runtime_graph_step_limit_reached / runtime_model_call_limit_reached / runtime_tool_call_limit_reached / runtime_run_timeout |
| end 历史标记 | AIMessage.additional_kwargs.runtime_budget_notice；与 live custom 用同一 notice_id 去重 |
| 子图/重放/权限 | 原生 namespace、SSE 游标和终态不变；已有 Thread ACL、410 与恢复链路继续生效 |

没有新增接口或前端必填参数。普通默认 stream modes 已包含 custom；客户端显式提供 modes 时仍需包含 custom。普通 Run 的子图事件需要创建时 `stream_subgraphs=true`，对应 SDK `streamSubgraphs: true`；Protocol scoped 订阅使用已有 namespace/depth。

## 前端需要完成

| 任务 | 现有代码入口 | 交付结果 |
| --- | --- | --- |
| F01 解析与投影重构 | useSessionConnection.ts、useChatSession.ts；budget/types.ts、view-model.ts、useRunBudget.ts | Zod 白名单（区分整型与浮点秒数）；`safeExtractBudgetNotice` 弹性解包（支持多层 payload 嵌套）；弃用 computed 内反复全量跑 Zod，改为增量处理与真正 200 条 LRU 有界去重；采用响应式 target 订阅机制（`useChannelEffect`）避免 namespace 响应式断裂；禁止在子组件三元表达式中违规条件调用 Composable |
| F02 展示与文案纠偏 | ChatAgentStatusBar.vue、ChatSession.vue、SubagentCard.vue、SubtaskDetail.vue | 彻底拆解复读机拼接文案（title 与 description 语义解耦）；状态栏 `v-if` 支持原生 success 停机，但在 running + approaching 预警时**必须保留取消按钮**；子任务卡片头部与详情展示归属 namespace 预算提示；保留已有消息与成果 |
| F03 动作与契约修正 | useChatActions.ts、run-actions.ts、branching.ts、view-model.ts | 严格动作分流：Run 限额提供“调整请求”；Thread 限额**严禁引导重发当前会话**，分流为“新建会话”与“在新分支继续”，输入框置灰禁用；当只有 safetyError 且未知 scope 时严格安全降级，**绝不冒进提供调整草稿重发**；草稿回填处理多模态内容并规避原生 `window.confirm` |
| F04 验收 | 本项单测与项目 verification.md | H01-H16、pnpm test:run、pnpm check、真实浏览器证据和订阅数量对照 |

不新增页面或 Agent 配置表单；不增加第二个 useStream、EventSource 或独立 SSE；预算投影不能创建第二套运行状态机。当前 Web 锁定 `@langchain/vue 1.0.35` / SDK `1.10.2`，本项不升级 SDK。

## 必须保持的语义

1. `success` 只代表原生执行结果。Reference/Workflow 因模型 end 限额正常退出时仍显示“因额度限制停止，任务可能尚未完成”，打破现有组件隐藏门槛，不能显示任务完整成功或就绪。
2. Thread 模型额度是 checkpoint 累计。发下一条请求不自动清零，禁止引导重发当前会话；提供新建会话或合法分支，输入框置灰，不提供提高配额、自动继续或 resume 绕过限制的动作。**当仅有原生 safetyError 且 scope 未知时，严禁假定为 run 级而向用户提供重发草稿**。
3. 子图 notice 放在对应任务范围。DearFlow/Showcase 保留 child=error，异常可沿父图传播，真实并行案例父 Run 为 error；不能承诺父图必继续。child=end 可继续的情形也要以真实父终态为准。
4. `wrapup_started` 是软提示，不是 timeout。Workflow 起点为内层模型 Agent invocation；不包含外图准备、模型准备或人工等待。不显示 Worker 剩余秒数；其数值为浮点秒数，Zod 严禁误用 `.int()` 校验。
5. 低 recursion 可能没有 custom，使用当前 Run 的安全 lifecycle/error。原生 Run GET 没有 error，最新 Thread.error 不能归因任意历史 Run。事件/人工标记都过期时按原生状态安全降级。
6. outer params.run_id/seq 在部分入口缺省；用官方 controller 核实的 Run 和 notice.run_id 关联，保留 namespace 与 SSE id，勿用临时 UUID。
7. null 表示未知；非法版本、枚举、ID或数值整条忽略。当前 custom unit 只有 model_calls、graph_supersteps、seconds，工具限额仅有硬错误码。
8. 预警不抢占 HITL、取消、权限处理；取消 ACK 仍需终态核实，不自动重发消息、批准工具或追加总结调用。**在 Agent 处于 running 且出现接近上限预警时，必须保留界面显式停止/取消按钮**。

## 真实样例索引

以下是 JSON 的实际 `samples` 键。`transport[]` 包含公共 SSE event/id/payload；notice 不含凭据、提示词或宿主路径。ID 仅供测试比对，不能复制成真实业务请求。

| JSON 键 | 可验证内容 |
| --- | --- |
| model_end、end_marker | Reference run=10/end，7/10 预警、10/10 reached、原生 success；人工标记与通知一致 |
| v2_model_end | 普通 v2 custom 是直接数据，而 v3 是 method/params/data |
| model_error、thread_exhausted | Showcase 测试额度 run=4/thread=5；error 安全码，Worker 重建后 Thread 累计保留 |
| parallel_child_limit | 同时委派两个 task；一个正常完成，一个 4 次调用后触限，subagent namespace 与父 Run error |
| graph_low、graph_warning | 极低 recursion 无预警也有安全错误；有机会时 graph approaching |
| tool_limit、hard_timeout | 工具额度与 Worker timeout 各自固定安全码 |
| soft_finish | 一次 wrapup_started 后自然成功，remaining=null |
| normal_reference_agent、normal_workflow_demo、normal_showcase_demo、normal_dearflow_agent、real_model_normal | 正常请求无误告警，四 graph 均可运行 |

Protocol custom 重放、历史人工标记、410、取消、HITL、ACL、输入防伪和回退结果在 JSON `cases`；Workflow primary root writer 的 compiled graph 证据在 `apps/runtime-service/tests/services/test_execution_budget_composition.py`。后端取证不替代浏览器验收。

## 联调方法

1. 在独立联调栈启动本工作树 Runtime API、Worker 和 Platform API，前端代理指向该 API。不要将故障注入接到现役数据。
2. 使用真实项目/Agent/模型目录，通过 `/api/langgraph` 现有受管入口提交。确定性限额边界复用 `scripts/verify_execution_budget.py` 的本地 OpenAI 兼容 provider；`loop-end`、`loop-error`、`loop-thread`、`parallel-budget`、`loop-graph`、`soft-finish`、`slow` 仅是该测试 provider 的指令，不是任意真实 LLM 的协议。
3. 真服务自动化复验入口（Runtime 工作目录）：

   ```bash
   BUDGET_RUNTIME_INTEGRATION=1 \
   BUDGET_MODEL_ENV_FILE="<私有模型配置文件>" \
   uv run pytest -q tests/durable/test_execution_budget.py -m durable
   ```

   要求本机 PG/Redis 和可建测试库的用户；可用 `BUDGET_POSTGRES_ADMIN_DSN` / `BUDGET_REDIS_URI` 指向独立环境。脚本使用临时 API 数据库、随机 PG 库/Redis prefix 和空闲端口，退出后关闭测试服务并保留运行库证据。前端浏览器联调需另起持续运行的隔离栈。
4. 对照详细交接 H01-H16 执行：正常/告警/硬停/end/Thread/子图、旧 Run 迟到、重连/刷新/410、HITL/cancel/撤权、草稿冲突与幂等；在 360/390/768/1440 视口保留截图、trace 和物理订阅数量。

## 验收回执

| 项 | 同事填写 |
| --- | --- |
| 实现版本/变更文件 | 待填写 |
| F01-F04 与 H01-H16 结果 | 待填写，失败项逐条说明 |
| Web 单测、lint/typecheck/build | 待填写 |
| 四 graph 浏览器截图/trace/环境 | 待填写，不含凭据 |
| SDK 订阅数量前后对照及卸载释放 | 待填写 |
| 剩余问题/负责人 | 待填写 |

后端验收：Runtime 253 passed；API 81 passed、1 skipped、423 subtests passed；durable 23/23 场景通过。当前非前端范围 done，无非前端 Block；整体项目 partial，待同事完成前端和 T08B 浏览器联合验收后收口。完整验证见 [verification.md](verification.md)。

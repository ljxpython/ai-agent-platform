# 05 子 Agent 生命周期与观测

## 目标

当前阶段先复用普通子 Agent 能力并修复现有展示缺陷：身份、namespace、进度／历史和父 Run 取消反馈。独立 child Run、单任务取消、完整结果验收和用量归属在现有基础不足时后置。所有角色仍使用 Deep Agents／LangGraph；不搬 DeerFlow 执行器。

## 工作上下文

- **总入口：** [项目总纲与交接规则](README.md)。独立开发本章时先读总纲，不以聊天历史代替依赖证据。
- **实施阶段：** P1/P2 普通子图复用与缺陷修复；独立 child 能力后置。
- **必读前置：** [01 底座证据](01-architecture-and-boundaries.md)、[02 模式／权限](02-agent-composition-and-modes.md)、[04 子任务资源](04-workspace-sandbox-and-artifacts.md)、[08 C05／C06／F3](08-web-and-platform-contracts.md)。
- **输入 → 输出／对接：** 父 Run／有效角色／作用域／预算 → 普通子图或独立 child Run、归属／取消／结果／用量；UI 只能消费真实引擎状态。
- **当前切片／最近证据：** 2026-09-14 规划第二版；业务未实施，无实施验证记录；本文末尾只记录文档调研情况。
- **下一任务：** 先完成 S-A/S-B 的普通子图复用与稳定关联；不能把暂不具备的独立控制能力伪装成交付。
- **结束回填：** 更新本章任务／验证／状态及此处游标，按总纲登记最近 implementation 记录、契约变化和下一精确任务；部分切片通过不勾选整章完成。

## 方案设计

### 1. 逐点参考与实现

DeerFlow 源码根为 `backend/packages/harness/deerflow/`，下列路径相对该根。

| 能力点 | 源码／符号 | 目标实现 |
|---|---|---|
| 角色定义 | `subagents/config.py:SubagentConfig`、`subagents/registry.py` | `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents.py:build_subagents`（拟新增）；声明式官方 SubAgent，不建全局 Registry |
| 委派与返回 | `tools/builtins/task_tool.py:task_tool`、`subagents/executor.py:SubagentExecutor` | 常规任务用官方 `task`，可独立控制任务走官方 SDK Thread／Run；不搬后台线程池和隔离事件循环 |
| 父上下文快照 | `subagents/context_snapshot.py:ParentContextSnapshot.from_state` | 默认只传任务、必要证据／文件引用；明确需要时传受控快照，不传系统权限、凭据、全部状态或同级消息 |
| 并发与总量 | `subagents/capacity.py`、`agents/middlewares/subagent_limit_middleware.py:SubagentLimitMiddleware` | 服务声明预算＋工具调用边界限制；进程内 semaphore 仅限制单进程，跨 worker 容量由实际任务存储／执行资源原子裁决 |
| 状态与取消 | `subagents/status_contract.py`、`tools/builtins/task_tool.py:_finalize_interrupted_subagent` | 普通子图跟随父 Run；独立任务用 SDK cancel 并查询真实终态，取消 ACK 不是完成 |
| 流式步骤与历史 | `subagents/step_events.py`、`runtime/runs/worker.py` 中子任务事件保存 | 沿用官方 namespace／discovery／messages／updates，独立子 Run 单独订阅；不复制 task_started/task_running 协议 |
| 结果契约与证据 | `subagents/report_contract.py`、`subagents/acceptance_checks.py`、`agents/middlewares/receipt_verification.py` | `schemas.py:SubtaskResult` 和 `evidence.py`（拟新增）；结构化总结＋工具证据，主 Agent 验证后交付 |
| Token 与费用归属 | `subagents/token_collector.py`、`tools/builtins/task_tool.py:_report_subagent_usage` | 现有 `observability/langfuse.py`＋官方消息 usage／callback，按实际调用去重，不写全局 provider tool ID 缓存 |

### 2. 两种执行模型必须区分

| 情形 | 采用方式 | 真实语义 |
|---|---|---|
| 父 Agent 等待短／中任务汇总 | 官方 `SubAgent`／必要时 `CompiledSubAgent` | 可并行但父工具等待；独立 namespace；随父 Run 生命周期，不承诺单独取消 |
| 用户需中途单独取消／追加指示，或任务需独立恢复 | 后置：官方 `AsyncSubAgent`／SDK Run | 需要独立 child Thread／Run、持久归属和授权基础；当前不作为首发能力 |

当前只实现第一行。父 Run 取消沿用现有语义，不新增子任务独立取消按钮；第二行及其持久化、恢复和用量聚合列为 deferred，待真实长任务和独立控制需求出现后再做 Spike。

独立子任务需要额外 worker Graph 入口是官方协议要求。它们的代码仍在同一 `services/dearflow_agent/`，`graphs/dearflow_research_worker.py` 等仅在对应角色真实需要时创建重导出入口。Platform 将其标为内部 worker、不能由普通用户当作独立产品 Agent 直接启动；所有独立子 Run 重新验证角色与有效授权。

### 3. P0 必须完成的 SDK 接入检查

本地 Deep Agents 0.7.8 `middleware/async_subagents.py` 中：`_build_start_tool` 先 `threads.create` 再 `runs.create`，spec headers 是静态的；`_build_cancel_tool` 收到 ACK 即把本地 task 标记 cancelled。因此不直接以默认 AsyncTask state 作为本平台完成事实。

需要验证：

1. child Thread 创建时能绑定当前项目、允许角色、父 Thread／Run 和资源 scope；客户端不能任意选择内部 worker。
2. 每次创建／读／取消／恢复使用正确 operation 的短期委托，长任务后续请求能重新授权；不复用父 thread 专属 token，更不能把平台用户 bearer 固定进 checkpoint。
3. child Run 提交携带获准模型、完整 Context 和幂等键。远端成功而父 checkpoint 未写入时，可以查询原提交恢复，不能新建重复付费任务。
4. 官方结果读取实际字段与 GraphHarbor 一致；终态、interrupted、timeout 不被误读为空成功。
5. 不同角色／用户共享进程时 SDK client 缓存不会共享凭据。

若官方 Middleware 没有公开的逐请求注入点，推荐服务私有 `delegation.py` 用官方 `langgraph_sdk` 显式实现 launch／get／cancel 所需业务调用，返回标准 ToolMessage／Command。它只处理授权、归属和幂等，不自己运行 Agent、建线程池、轮询模型或模拟官方 API。该分支须在 S2 结果中写明，不能伪称直接使用 AsyncSubAgent 就已满足全部条件。

### 4. 标识、持久化和资源

- 展示／调用关联键使用 `(parent_run_id, namespace, tool_call_id)`；provider tool_call_id 单独不全局唯一。
- 独立 child Thread／Run ID 由引擎产生；服务端 task ID 是业务归属键，不能由模型自选 owner。
- 拟新增服务私有 `task_links.py` 保存最小 `parent_thread_id,parent_run_id,delegation_key,child_thread_id,child_run_id,role,scope_hash,request_digest,created_at`。唯一键为授权域＋delegation_key；执行状态从 child Run 读取，不重复写第二份终态。
- 表归 Runtime 业务所有，数据库迁移和 repository 在 `services/dearflow_agent/` 下，只操作自己的表；不直接修改 GraphHarbor runs/checkpoints。
- 父 Run 取消默认请求取消本轮未结束 child Runs；独立继续执行必须是用户明确选定的后台行为。父取消与子完成竞态保留实际结果，不把已完成文件删掉。
- child Run 持久读取只读输入引用及独立写目录，工作区发布经父侧核验；授权被撤销后停止新模型／工具操作。

### 5. 角色与最小权限

初期角色只围绕真实消费者声明：research（搜索、网页／文件只读）、analyst（受限数据处理、专属输出）、writer（基于证据生成报告）、chart（图表工具）。是否增加 coder／media 角色由对应 Skill 委派收益决定，不因上游有 Bash Agent 就开放通用宿主命令角色。

显式约束默认 `general-purpose`，避免框架隐式新增全工具角色。子 Agent 不默认拥有再次委派；需要层级委派时必须评审总深度、预算和父子取消，不自动放开。

### 6. 进度、结果、用量

- 普通子图按官方 namespace 订阅；根 transcript 只展示根消息。同名角色同时执行按调用 ID 区分，禁止“找不到 ID 就按名字归并”。
- 独立 Run 的详情由父子归属校验后读取其官方流；刷新先读当前状态再重连，不依赖进程内事件列表。
- `SubtaskResult` 拟含 `summary, evidence_refs, artifact_refs, unmet_requirements, stop_reason`；结构化输出只验证形状，真实性另由 evidence 校验。
- 超预算／超时返回部分结果和明确 stop_reason；主 Agent 必须识别未完成，不能把“停止”当作“验收通过”。
- 用量按实际模型调用 ID／trace span 记一次，再聚合 parent 与 child。输入、输出、缓存字段按 provider 定义记录；缺失显示未知，不用 0 代替，不把父级聚合与子级累加重复收费。
- 总预算覆盖所有 child；未提供 usage 的模型以调用次数／时长硬限额，不能声称 Token 硬预算可精确执行。

## 任务拆分

- [ ] S-A/P1：复用普通官方子图及现有 `SubagentCard`／`SubtaskDetail` 展示。
- [ ] S-B/P1：按稳定调用 ID／namespace 关联，移除名称 fallback，修复同角色并发串线。
- [ ] S-C/P2：修复断线、刷新、缺失 discovery、父 Run 取消时的状态展示误判。
- [ ] S-D/P2：复用现有 tracing／usage 字段；缺失 usage 显示未知，不伪造费用。
- [ ] S-E/deferred：独立 child Run、单任务取消／恢复、完整 usage 归属和结果验收框架。
- 人机交互切片与 `02/C04-d`、`08/W05` 联合验收：普通子图／独立 child 的提问卡片、答案校验、多 ID、取消／撤权和恢复归属，细节以 02 §6／08 §11 为准；不能只测工具批准而漏掉动态澄清。

## 验证要求与记录

- [ ] 两个同角色同时间执行，ID、消息、文件、审批、用量完全分开。
- [ ] UI 不显示当前不存在的子任务独立取消按钮；父 Run 取消反馈准确。
- [ ] 父取消、子刚完成、网络超时、worker 崩溃、父 checkpoint 前后崩溃不重复建任务。
- [ ] 刷新／断线后按官方数据恢复展示；缺失 discovery 显示未知或恢复中。
- [ ] 主／子审批均可恢复，未批准副作用不发生；子角色不能再次委派越权。
- [ ] 部分失败与全部失败时，主结果准确标注；缺失 usage 保持未知。
- 独立取消、独立 usage、独立恢复及完整结果验收均为 deferred，不作为当前阶段失败。
- 2026-09-13：确认官方同步与异步能力差异；未运行协议 Spike。

## 状态

规划中。当前交付普通子图复用与展示缺陷修复；独立取消、独立 child Run、完整 usage 和结果验收后置。

# Runtime Service 开发范式与规则

## 以 Showcase Demo 为模板

- `agent.py` 是唯一组合根：校验身份和 Context，获取模型，显式装配 Middleware、工具和子 Agent。
- `prompts.py` 只放提示词和纯渲染函数；不读环境变量、不发网络请求。
- `tools.py` 只放本服务真实业务动作；不返回模拟成功。
- `backend.py` 只处理工作区、资源边界和执行隔离；优先复用官方 Backend。
- `subagents.py` 用声明式角色和最小权限；禁止无边界通用子 Agent。
- `skills/` 是按需读取的资源，不授予权限。
- Graph 入口通过 `langgraph*.json -> graphs -> services/<name>/agent.py` 注册。

## 必须遵守

1. 先查本导航、相关 knowledge、官方 MCP 文档和现有调用者，再改代码。
2. 优先使用 LangChain/LangGraph/Deep Agents 官方能力，不自建 Agent 循环、Tool Registry、Builder 或审批 State。
3. 信任边界必须校验：身份、Context 哈希、tenant/project/thread scope、工具 allowlist 和审批动作。
4. 正式环境文件和命令执行必须限制在当前线程工作区；禁止回退到宿主机 shell，禁止把凭据或绝对路径放进 Prompt/Context。Showcase 经评审允许受信任本地开发显式选择 LocalShellBackend（本地栈默认 local），该模式不提供 shell 隔离，不用于生产或多租户环境；独立 Runtime 默认仍为 Docker。
5. 新增能力必须有单元或组合测试；跨边界改动补集成测试和至少一条 E2E 链路。
6. 变更保持最小：不为未来需求预留抽象，不复制旧 Runtime，不新增兼容 Adapter。
7. 影响功能现状时同步 `docs/FEATURES.md`；治理或跨服务改动更新 `docs/projects/` 记录。

## 新功能最短流程

阅读资料 → 复制 Showcase 的边界模式 → 在所属 Service 显式装配 → 编写最小测试 → 本地运行 → 更新文档和变更记录 → 提交评审。

## 通用文档读取

复用 `DocumentWorkspace`、六字段 `FileRef v1` 与公共 `tools/documents.py:build_document_tools()`；DOCX/PPTX 上传只存原字节，不自动转换或持久派生 Markdown。`DocumentToolsMiddleware.tools` 沿官方 Agent 装配同一工具，消息已有附件引用，不逐轮枚举 uploads 注入 SystemMessage。

Office 异步读取固定 Docker reader，要求组合根绑定现有 workspace image；即使受信开发 shell 选择 local，Office 也没有宿主 parser 回退。单次 20 section/slide、12,000 字符，DOCX section 为正文段落/表格而非打印页码，续读使用返回的 `next_read` / `char_offset`。结构/哈希/输出边界由共享模块校验；取消和 execution unknown 保留控制流。

仅 Showcase/DearFlow 普通主图授权读取，Plan/子图不因格式扩展获得权限；Excel 保持 data-analysis，OCR/旧 DOC/PPT/复杂版面后置。锁、镜像、资源与前端契约见 [F10 专项](../../../../docs/projects/20261010-agent-document-reading/README.md)。

## 上下文窗口管理

DearFlow/Showcase 根图与声明式子图在 agent.py 显式替换官方摘要，公共能力位于 `middlewares/conversation_offloading.py`。使用受信模型容量/输出预算；摘要副本 nostream，最终模型请求 guard 计入动态 system/tools。大批历史裁剪保留初始目标或上一轮摘要，归档继续由 checkpoint/StateBackend 保存。

schema-only 与执行图必须声明相同 OffloadingState，保留 DeepAgentState 的 DeltaChannel；整理状态使用 PrivateStateAttr 防父子复制/合并，API 再按白名单公开，不以此注解替代网关脱敏。手动维护只运行根摘要，通过 before hook/end 结束；不得准备执行 MCP/Workspace、claim 队列或执行 Memory/Skills 后处理。

开启受管上下文治理时，历史 write/edit 大参数复用官方 request-only 压缩（输入预算85%触发、保留最近10% token、字符串上限2000）；不按后续成功覆盖判定删除历史。现有 Filesystem 使用 `resolve_tool_output_limit`，取主/备最小输入预算B并设 `max(1,min(20000,B//16))`，实际外置门槛为4T字符，仍由完整请求guard兜底。`ResultFilesystemMiddleware` 以官方同名替换，只为新外置路径增加正文SHA256，避免父子/并行同call ID覆盖原文；保留官方文件工具、预览、失败处理与旧路径读取。正文仍在checkpoint files，不承诺PG/HTTP体积减少；超长单行的行分页仍可能无法取到中部。薄扩展依赖锁版本内部方法，升级需重验。见[F04](../../../../docs/projects/20260913-dearflow-agent/15-tool-output-budget-review.md)。

`AGENT_CONTEXT_MANAGEMENT_ENABLED` 默认 0，目录容量、输出预算、迁移和双端 Context（当前 v6）就绪后才能开启。关闭时沿用官方摘要并保留历史/私有事件，不清数据。reference/其他教学图未接入，不宣称支持。依赖升级需复跑隐藏流、预算、归档、父子隔离、真实 PG/Worker 恢复测试，证据见 [上下文专项](../../../../docs/projects/20261006-agent-context-window-governance/verification.md)。

## 通用 Plan Mode 接入

`runtime/planning.py`、`middlewares/plan_mode.py`、`tools/plan_mode.py` 是公共实现。组合根在 `RuntimeConfigMiddleware` 后装配 `PlanModeMiddleware`，传入经过审查的真实只读工具实例；middleware 提供 enter/save/submit 三工具，图 defaults/catalog 同步声明。工具列表裁剪和 ToolCall 执行门禁同时生效，三个控制工具必须独占批次；MCP、task、shell、普通写文件默认不放行。

execution_mode/access_policy/plan_mode 正交；批准只解除规划限制，原工具授权和 HITL 继续。人工审批复用 submit 的原生 interrupt 与 API input.respond，不提供模型 approve 工具。Markdown 只写 checkpoint，正文64 KiB、反馈2000字符；计划状态和执行 ID 服务端持有，不允许客户端注入。

DearFlow/Showcase 子图用 `child=True` 且绑定自己的只读工具实例，不拥有计划控制工具；自定义 Workflow 显式传递 runtime_plan 并保留嵌套 checkpointer。新增图还须同步 Runtime `runtime/planning.py:PLAN_GRAPHS`、API `application/planning.py:PLAN_GRAPHS`、capability、graph_tools 与测试；仅加 middleware 不能宣称完成平台接入。审查自动记忆、技能、受控证据缓存等隐式副作用，规划时不能写业务目录。

双端 Context 使用 v6，服务端执行 ID 跨审批恢复保持、新 Run/fork/含计划历史建立新周期。发布与回退须成对处理，旧 Runtime 无法保护计划 Thread 时拒绝降版，保留当前约束。可执行契约与前端边界见 [专项](../../../../docs/projects/20261008-agent-plan-mode-governance/README.md)。

## Run 时间预算与收尾

正式执行按 LangGraph Server Worker attempt 计时：每次 claim 生成 `GRAPHHARBOR_RUN_TIMEOUT_SECONDS`（官方别名 `BG_JOB_TIMEOUT_SECS`）预算。Runtime 组合根通过 `read_run_budget` 消费快照，主/子 Agent 和 workflow 内部重建共享本 attempt 不可变值；不得按构图、模型重试或子 Agent 重新计时。DB故障/Worker接管从checkpoint继续并获得新attempt H；跨attempt累计总限不在本期。私有预算不绑定公开 invocation/state/checkpoint，schema/probe可无预算，正式执行缺预算明确失败。

`TimeoutWrapupMiddleware` 在硬限前 `AGENT_RUN_WRAPUP_RESERVE_SECONDS` 秒（默认120，0关闭，正值须小于H）向后续模型请求追加通用收尾指令；软提醒不代表总结已生成、文件全量保存或审批豁免。Worker硬限落timeout；`ModelCallTimeoutError`只标识模型scope，provider超时和外部取消保留原异常。模型/provider错误由图内policy恢复，未恢复则error，不自动触发Worker整图重试。

该能力需要GraphHarbor post42；当前正式双包已发布并锁定/安装，API-Worker隔离HTTP及匹配源码回退通过。新Runtime不可只降依赖为post41，回退须同时恢复已验证旧Runtime源码并先暂停提交/drain。现役服务没有被本轮升级；发布、取消清理及回退证据见[运行超时专项](../../../../docs/projects/20261006-agent-run-timeout-governance/README.md)。

## 执行预算接入

复用 `middlewares.ExecutionBudgetMiddleware`，替换组合根里的官方模型限制器实例，保留已批准的
run/thread/exit_behavior；主子图分别声明 scope，禁止合并为未实现的全局额度。默认余量为 3 次调用、
8 个 supersteps。不要通过扫描模型消息或 after_agent 判断异常退出。

可选 `TimeoutWrapupMiddleware` 只接主模型 Agent；单调时钟/latch 为 invocation 私有状态，不能持久化
或接受客户端覆盖。阈值缺省关闭，Worker 独立持有 hard timeout；自定义 Workflow 的模型时间从内层
Agent invocation 起算。通知沿现有 custom writer，不接 Slack 或新事件存储；公开数据由平台白名单投影。
接入/自定义 StateGraph 样例见 [Showcase](../../src/runtime_service/services/demo/showcase_demo/README.md)。

## Run Token 额度保护

`RUNTIME_TOKEN_BUDGET_ENABLED` 默认 false；启用要求 `RUNTIME_USAGE_ENABLED=true`、Runtime 应用迁移 `0003_token_budget` 和完整受信 native Run 身份。`RUNTIME_TOKEN_BUDGET_MAX_TOKENS` 默认 100000，范围为正 JS safe integer；固定 80% 向后续模型追加已有 system 收尾指令。API/Worker 使用一致部署配置，客户端 Context 不能指定或提升此额度，schema/probe 不访问账本。

复用唯一 `RuntimeUsageCallback` 与 `runtime_usage_calls`，按 model_call_id 增量去重；`RunTokenBudget` 是 Run 绑定、可恢复投影，不扫描 Thread 消息、不新增全局缓存。策略在 `runtime_usage_runs` 首写冻结，Worker 接管同 Run 时恢复消耗与停止原因，旧 attempt 未确认 started 或持久化故障按不可验证处理。四图主子、Workflow 内层及可信摘要/vision/memory 共享额度。同步派发守卫只检查，不另采集或计价；启用时 SDK max_retries=0，防止单次 callback 内发生隐藏物理重试。

额度耗尽或不可验证时，拒绝新增模型/工具工作，分别传播 `TokenBudgetExceededError` / `TokenBudgetUnverifiableError`；既有取消、HITL、retry/fallback 与 Worker 基础设施恢复语义保留。自然最终回答达到/超过 cap 仍可成功，只有实际拒绝新增工作才持久记录 stop_code；可选 memory 后处理在不足时跳过并保留主回答。已在途请求可完成并超额，这是已观测 Token 保护，不是供应商账单严格封顶。

通知复用 custom `runtime_budget_notice`；历史原因由现有 Run Usage 的可选 `token_budget` 读取。扩展列与历史用量保留，回退先暂停/drain、统一关闭开关，再恢复已验证旧源码，不做删除式 downgrade。实现和验证见 [F01](../../../../docs/projects/20260913-dearflow-agent/15-token-budget-governance.md)，前端接入见 [交接](../../../../docs/projects/20260913-dearflow-agent/16-token-budget-frontend-handoff.md)。

## 准备与重试装配

`middlewares/run_prepare.py` 的 `RunPrepareMiddleware` 供可幂等的资源准备继承：实现 `_validate()`、`_is_prepared()`、`_prepare()`，传入固定 component/revision 与 resolved config_hash。授权/路径检查每次执行，成功后提交私有 `runtime_prepare`；标记不保护 checkpoint 提交前的副作用，操作仍需幂等。不缓存模型、凭据或 MCP 连接。

`middlewares/retry.py` 复用官方模型/工具 retry，总尝试最多 2 次；主/写子图的 SDK max_retries=0，由模型 middleware 负责。只读子图由父 `DelegatedTaskRetryMiddleware` 负责，其模型 middleware 使用 delegated=True。只读角色集合由本图组合根固定声明并核对工具闭包，不能根据另一个图的同名角色授权。任何 content/reasoning/tool delta 后禁止重放，取消/中断/权限/未知缺陷继续传播。

provider 最终失败用安全 RuntimeExecutionError，真实 PG/checkpoint/lease 故障保留 Worker 恢复。Reference 沿用现有接线；其他 graph 显式选择接入。诊断只记录安全 preparations/retries，不增加 SSE 运行控制。接线与故障证据见 [专项](../../../../docs/projects/20261007-agent-production-capabilities/README.md)。

## 通用会话停止与资源适配

`run_control/`持有平台控制动作、恢复租约、inbox屏障、资源回执和确定性报告；GraphHarbor持有Run/lease/checkpoint执行事实。Runtime使用正式引擎cancel-active与固定回执接口，不直接改引擎runs/lease表、不新增Agent循环或停止工具。该源码已隔离验证，正式配套版本/锁接入与真实Docker仍blocked；本期不代表现役可用。

- 新Agent沿当前组合根/图注册即可接入会话停止；`webapp.py`统一挂internal Stop路由和受管lifespan reconciler，无需每图加middleware。业务工具要传播 `CancelledError`，不要改成普通ToolMessage成功/失败。
- 长命令资源复用 `workspace/execution.py::execute_in_workspace()` 与 `run_control/resources.py::{register_resource,finish_resource,wait_cleanup}`。资源登记只保存thread/run/kind/status，不保存命令、宿主路径或凭据；重复取消也要等待已拥有的清理任务并持久记录confirmed/unconfirmed。
- LocalShellBackend仅用于受信本地开发；Python同步线程不能强杀，取消等待有界命令结束，超出确认等待保留unconfirmed。不得回退宿主shell提供生产隔离；真实Docker证据不能用local或mock替代。
- inbox enqueue/claim与Stop准备共用Thread advisory lock，屏障绑定固定旧run_id；执行退出后复用 `reconcile_run()` 按committed checkpoint对账。保留consumed，旧未消费项标user_stopped；新Run和已有run_ended/run_cancelled原因不被覆盖。
- 报告从固定目标取已保存计划/真实工具回执/合法成果，最多20 checkpoints、30 progress、20 artifacts，脱敏label/JWT/宿主路径；无证据明确unknown。业务工具可以沿现有Todo/ToolMessage/artifact引用提供证据，不为此自建业务摘要schema或自动summary Run。
- Stop不抹掉HITL，不自动resume；显式恢复绑定当前interrupt ID，不携新input/config/context。媒体/部署已接受但丢响应的unknown回执必须保留，同key重试不能再次购买或发布；独立Terminal/detached任务不冒充已取消。

职责、函数、迁移/回退与真实四图证据见[取消专项](../../../../docs/projects/20261007-agent-run-cancellation/README.md)；前端只消费安全DTO，未接入前不改变Run/SSE原契约。

## 新增代码粒度规范

后台 Workspace 长命令通过公共 `build_background_tools()` 显式接入根 Agent，使用持久任务/受管容器/无模型对账与开始前完成 guard；不新增 Agent 循环、每 Thread cron 或宿主 shell 回退。普通 execute/Terminal 语义保持。接入步骤、审批/权限/重放验证与正式启用限制见 [后台任务接入](background-task-integration.md)。

> **适用范围：仅约束新增代码。存量代码不在此规范的覆盖范围内，不得借此规范触发对旧代码的"顺手重构"。**

### 函数原子化

- 一个函数只做一件事：要么协调（调其他函数），要么执行（做真实业务动作），不混用
- 新增普通函数目标 ≤ 60 行；LangGraph 节点函数目标 ≤ 40 行（节点只做状态路由 + 调用，不内嵌业务逻辑）
- 工具函数（`@tool`）：一个工具只封装一个真实业务动作，不捆绑多个副作用

### 参数与嵌套

- 新增函数参数目标 ≤ 4 个；超过时用 `dataclass` 或 `TypedDict` 包裹
- 嵌套层数目标 ≤ 3 层；优先用 early return / Guard Clause 扁平化条件分支

### 信号而非硬阻

上述数字是设计时的参考目标，不是 CI 门禁。写新代码时主动对照；若某个函数确实需要更多行，在函数上方注释说明原因（例如：协议解析、状态机分支穷举）。

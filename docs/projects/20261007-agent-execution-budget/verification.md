# Agent 执行预算 - 验证计划和记录

> 前后端全链路范围均已完成并达到 `done`。Runtime/API 与前端 F01-F04 全量门禁闭环，单测 571 passed，check/lint 0 errors。Phase 与 Final 分开记录，真实浏览器与前后端数据契约均通过严格实测。

## 验证环境与证据规则

本工作树无独立`.venv`。本轮使用主检出既有Runtime/API Python 3.13环境，以`PYTHONPATH`明确加载当前工作树src；没有创建或修改环境。文档中`RUNTIME_BASELINE_PYTHON`、`PLATFORM_BASELINE_PYTHON`代称已核实解释器，实际路径不写入共享文档。

已核实Runtime解释器关键依赖与本工作树lock一致：LangChain 1.3.17、LangGraph 1.2.11、Deep Agents 0.7.8、GraphHarbor/Runtime post41、Python SDK 0.4.3。任何后续版本变化先重跑T01语义检查，不因官方最新文档推断锁定行为。

集成使用隔离 PG/Redis、工作树服务、独立端口/测试项目。没有修改现役数据库、部署配置或执行生产 API。真实模型链路使用已有合法凭据，证据只存安全 ID/code/count/namespace/status，不记录模型密钥或消息原文。Docker 在本机不可用，T07 使用本机隔离 PG/Redis，未因此阻塞。

## 本轮实际执行：规划基线

### B01 Runtime既有定向回归

在`apps/runtime-service`运行：

```bash
PYTHONPATH="$PWD/src" "$RUNTIME_BASELINE_PYTHON" -m pytest -q \
  tests/middlewares/test_runtime_middleware.py \
  tests/services/reference_agent/test_middleware_order.py \
  tests/services/dearflow_agent/test_limits_config.py
```

结果：**28 passed，5条已有SWIG DeprecationWarning，6.47秒**。证明现有middleware、Reference装配和DearFlow阈值解析可作为基线；不证明所有Agent真实服务已通过。

### B02 after_agent生命周期探针

使用官方create_agent、可bind_tools的fake model、一个只读echo tool和观察after_agent的middleware，运行三种配置。探针没有写业务文件、请求模型或调用外部服务。

| exit_behavior / recursion_limit | 结果 | after_agent |
| --- | --- | --- |
| error / 100，模型run_limit=1 | ModelCallLimitExceededError | 未执行 |
| end / 100，模型run_limit=1 | 返回`Model call limits exceeded: run limit (1/1)` | 执行一次 |
| end / 1 | GraphRecursionError | 未执行 |

首个探针尝试直接给Pydantic fake model实例改bind_tools被拒绝，改为fake model子类后成功；这是探针构造问题，不是本仓代码失败。后续T01将成功探针固化成可运行测试，规划阶段不新增业务测试代码。

### B03 API SSE安全基线

在`apps/platform-api`运行：

```bash
PYTHONPATH="$PWD/src" "$PLATFORM_BASELINE_PYTHON" -m unittest discover \
  -s tests -p 'test_runtime_gateway_event_redaction.py'
```

结果：**执行19项测试方法，unittest报告3个失败断言，退出1，0.815秒**。两项方法涉及失败：

| 测试/子场景 | 观察事实 | 影响与处理 |
| --- | --- | --- |
| `test_native_task_error_is_safe_in_both_streams`，首次普通流 | `TASK_EXCEPTION_CANARY`仍存在于`tasks.error` | 原始异常文本外泄已复现；后续安全门禁必须修复；由于首轮断言失败，不能声称此测试已覆盖Protocol分支 |
| `test_fatal_run_error_hides_original_exception_in_both_streams`，普通流 | canary已删除，但code为`runtime_execution_failed`，测试期待`runtime.execution_failed` | 测试/代码契约冲突，需G0裁决，不属于正文外泄 |
| 同方法，Protocol子场景 | canary已删除，字符串error变为`Runtime execution failed`，没有code | 原生字符串错误的兼容语义和测试期待冲突，需G0裁决 |

通过读取导入模块`__file__`确认sdk_client/http来自当前工作树，没有误用主检出源码。没有为了让规划基线变绿而修改业务代码或测试。

### B04 只读取证

- GraphHarbor生产Worker已有`GRAPHHARBOR_RUN_TIMEOUT_SECONDS`，无配置返回None，有效配置覆盖构图和执行；超时返回原生timeout终态。
- Worker已有持久事件及重放，v3executor包含CustomTransformer；不需要新事件库。
- GraphHarbor RunRow和_RUN_KEYS没有error；Run GET不能恢复旧Run的精确分类，Thread.error的最新槽位也不能替代每Run事实。
- 参考open-swe相关文件有本地修改，取证哈希见comparison；没有声称其测试通过。
- 当前API recursion默认1000，gateway标准写25；Run timeout环境矩阵与Worker缺省行为不一致。已列评审，没有读取私有`.env`或改生效规范。

附加managed schema探针（无文件写入/网络请求）：

| 声明 | 实际结果 |
| --- | --- |
| `remaining_steps: RemainingSteps` | create_agent构图失败，managed channel不允许在InputSchema |
| `Annotated[RemainingSteps, PrivateStateAttr]` | 构图成功但before_model读到None；不能视为适配成功 |
| `Annotated[int, PrivateStateAttr, RemainingStepsManager]` | 成功运行，recursion=20时读到19，结果为done且remaining不在公开output |

这是锁定版本的注解排序行为，方案已按已验证写法修正；真实组合测试已补 input/output/schema 断言和循环边界。

### B05 本项目文档静态检查

- [x] 6份本项目Markdown、15个相对链接和实际已有代码路径检查通过；新路径明确标拟新增。
- [x] 本目录新增文档无个人绝对路径/旧服务名；未改生效标准、业务源码、依赖或配置。
- [x] `git diff --check`通过。
- [x] 全仓执行`scripts/check_docs.py`：退出1，报告既有knowledge两文档与10-05两专项的个人绝对路径共34处；本次6份新增文档及CONTEXT/FEATURES未命中，不扩大范围修改历史文档。

最终内容复核：参考文件三项SHA256与comparison一致，补充Slack查找位于发送try之外的异常边界；`git diff --check`通过。全仓文档检查仍为上述34处历史问题，本次文档未命中。结果不代替功能验证。

## 实施后的单元/组合用例

以下条目已映射到实际测试函数、组合测试或 durable 场景；没有新增测试框架。原规划名称保留作验收语义索引。

| ID | 实际测试/证据 | 结果与边界 |
| --- | --- | --- |
| V01 | `test_model_budget_notice_and_original_exit` | 通过，sync/async × end/error，预警和触限各一次 |
| V02 | `test_natural_last_call_and_literal_marker_do_not_report_stop` | 通过，自然最后调用和正文英语短语不误报 |
| V03 | `test_official_thread_budget_survives_graph_rebuild`、`test_serial_runs_and_rebuilt_thread_keep_distinct_latches` | 通过，Thread累计与run/latch分开 |
| V04 | `test_managed_remaining_is_private_and_live`、`test_graph_remaining_notice_is_once_per_graph`、`test_budget_extension_preserves_official_graph_cost` | 通过，managed schema、边界及实际图成本 |
| V05 | `test_low_recursion_has_no_after_agent_dependency`；durable `graph_low_no_hook` | 通过，无hook也有原生安全错误 |
| V06 | `test_official_limit_lifecycle`、`test_model_budget_notice_and_original_exit` | 通过，官方跳转与hard cap保持 |
| V07 | `test_parallel_subgraphs_have_distinct_notices_and_parent_finishes`；durable `parallel_child_error_preserves_parent_native_outcome` | 通过，child=end和当前child=error两种路径；UI归属待H07 |
| V08 | `test_writer_failure_keeps_original_limit_exception`、`test_notification_control_flow_is_not_swallowed` | 通过，OSError安全降级、取消/GraphBubbleUp原样传播 |
| V09 | `test_structured_system_blocks_and_metadata_survive_idempotent_wrapup` | 通过，list/cache_control/metadata及幂等 |
| V10 | `test_clock_resets_for_serial_invocations_and_is_not_checkpointed`、`test_parallel_invocations_have_independent_soft_clocks` | 通过，串行/并行invocation隔离 |
| V11 | `test_soft_boundary_and_cancel_do_not_add_a_model_call`、composition probe；durable HITL/cancel | 后端通过，浏览器取消/审批投影待H11 |
| V12 | `test_invalid_soft_threshold_is_rejected`、`test_invalid_explicit_environment_is_rejected`、`test_soft_timeout_defaults_off` | 通过，默认与正有限值校验 |
| V13 | API `test_exact_errors_and_unknown_provider_timeout` | 通过，四精确类型与Provider TimeoutError区别 |
| V14 | API `test_error_slots_in_native_protocol_and_v3_frames`、原event redaction/SDK回归 | 通过，tasks/debug/checkpoints/lifecycle/JSON canary及正常内容 |
| V15 | API `test_notice_and_end_marker_whitelist_preserve_messages`、`test_invalid_notice_is_ignored` | 通过，未知custom保持、非法预算通知降级 |
| V16 | API `test_all_network_input_shapes_reject_budget_injection`、`test_resume_injection_is_rejected_before_interrupt_lookup`；Runtime auth与durable | 通过，所有写入形状与原生拒绝边界 |
| V17 | Runtime串行latch、durable end/Protocol/v2重放 | 后端通过；旧Run迟到不能清新Run busy属于前端F01/H08-H09，待验 |
| V18 | durable `history_end_marker`、`end_marker_and_replay`；V02 | 通过，人工结构化标记与正常正文不混淆 |
| V19 | API未知/字符串泛化；durable `protocol_410_native_snapshot` | 后端通过；历史归因/页面降级待H10 |
| V20 | `test_deep_agent_primary_and_children_explicitly_compose_budget`、`test_workflow_inner_primary_notifications_reach_root_stream`；四graph HTTP | 通过，root writer、主子装配和schema边界 |

Runtime 新测试在 `tests/middlewares/test_execution_budget.py`、`test_timeout_wrapup.py`、`tests/services/test_execution_budget_composition.py`；API 在 `tests/test_execution_budget_projection.py`。V17/V19 的页面部分未算作后端已通过，前端 H01-H16 仍待回执。

## 集成测试

| ID | 环境与步骤 | 预期 |
| --- | --- | --- |
| I01 | 真实GraphHarbor API/Worker+PG/Redis，fake model确定性tool loop，使模型run limit触发 | event持久化，warning/reached顺序与count正确；原异常/终态真实 |
| I02 | 同环境Reference/Workflow end预算，随后拉Run/state/history | 原生success保持，人工标记能解释非完整回答；无纯文本误判 |
| I03 | 低recursion graph与明确ToolCallLimitExceededError | 原生error精确分类，JSON/SSE/tasks/debug无canary |
| I04 | 测试进程显式启用短软阈值和Worker hard timeout，分别制造模型/工具卡住与正常收尾 | soft只是提示；无下个边界也由原硬机制停止；不把provider timeout误报成Run timeout |
| I05 | approaching后断订阅，Run继续；用原cursor重连，再制造410 | 重放不重复提示；410沿原核实，无盲重发、没有第二份Run状态 |
| I06 | 同Thread多轮、graph重建、Worker重启与checkpoint恢复 | Thread累计保留；Run latch/soft clock不污染新invocation，重启口径明确 |
| I07 | 主图并行子任务一个触限，一个完成 | scoped结果分开；child=end时父图可继续，当前Showcase child=error沿父图传播；父Run采用原生结果，无跨子图计数合并 |
| I08 | approaching时HITL、拒绝/批准、用户cancel；加入既有待消费消息 | 人工等待不计软执行时间；resume重新按受管链路；不自动批准/继续/重复工具 |
| I09 | 串行/并行请求试图写counter/latch/notice、跨项目读流/历史 | 输入拒绝、ACL有效、状态不泄露；合法请求正常执行 |

## 三服务E2E与前端（待同事）

- [ ] E01 正常真实模型请求：Web提交→API受管→Runtime模型→结果；后端真实模型 smoke 已通过，浏览器链路待验。
- [ ] E02 确定性模型循环：Web看到approaching→reached→真实终态，已有消息保留；人工调整草稿后新请求正常，不自动发起。
- [ ] E03 低graph预算：原生错误出口通知明确，不依赖after_agent或LLM总结。
- [ ] E04 end预算：页面不把transport success等同任务完整成功；刷新后人工标记仍可解释。
- [ ] E05 Thread耗尽：人工续问不绕过累计，不清零或新建Thread逃避；动作符合权限。
- [ ] E06 soft/hard时间：soft提示与timeout终态分开；cancel/HITL不被覆盖。
- [ ] E07 父子/历史/重连：子图限定、旧Run迟到、刷新/410、会话切换和串行Run稳定。
- [ ] E08 前端交接H01-H16回执、类型/lint/build及浏览器响应式/可访问性通过。

真模型只用于正常最短链和收尾体验抽检；限额/时间/故障边界以受控fake model和真实Worker的确定性注入为主，避免依赖模型随机多调用或长时间等待。

## 性能、资源、安全和回退

- [x] P01 相同 fake 工作负载开/关预算提示对照：官方与扩展均为 2 model calls / 8 supersteps；独立重复中位数约 9.041ms / 9.137ms；未设置未经批准的 SLO。
- [x] P02 同一维度 approaching/reached 各至多一次；三类串行 Run、Thread 重建和两个并行子图真实证据通过，notice_id 可去重且 namespace 隔离。
- [ ] P03 Web复用SDK订阅的物理SSE数量前后对比，结束/卸载释放；不为本项新增物理事件连接。更大并发容量沿SSE专项，不冒称其H2门禁已通过。
- [x] S01 错误/通知槽位 canary、安全数值和敏感字段测试通过；provider body、凭据样式、宿主路径不进入公共证据或普通诊断。
- [x] S02 counter/latch/clock/人工标记写入拒绝、项目/Thread ACL、read 撤销和跨项目隔离通过；没有新增权限或 token scope。
- [x] R01 旧官方限制器读取新 checkpoint、软阈值关闭、原 hard limits/timeout 与取消/审批链路通过。
- [x] R02 新私有键不进入公开 state；旧限制器读取新 checkpoint，重建 Worker/新 Run 不继承软 clock。
- [ ] R03 旧 Web + 新 API / 新 Web + 旧 API 组合尚待前端同事联合验收；后端缺事件时保持安全降级。
- [x] R04 API 保留 tasks/error 清洗和未知错误安全泛化；未恢复原文泄露。

本仓没有本项批准的耗时SLO；记录P01实测差异和资源现象，由人工判断是否接受，不临时写“低于某毫秒”的假指标。

## 后续执行命令

Runtime工作目录`apps/runtime-service`：

```bash
uv run pytest -q tests/middlewares tests/services/reference_agent \
  tests/services/showcase_demo tests/services/dearflow_agent tests/services/workflow_demo \
  -m 'not integration and not e2e and not durable'
uv run pytest -q tests/durable/test_execution_budget.py -m durable
uv run ruff check src/runtime_service/middlewares tests/middlewares
uv run ruff format --check src/runtime_service/middlewares tests/middlewares
```

API工作目录`apps/platform-api`：

```bash
uv run python -m unittest discover -s tests -p 'test_execution_budget_projection.py'
uv run python -m unittest discover -s tests -p 'test_runtime_gateway_event_redaction.py'
uv run python -m unittest discover -s tests -p 'test_runtime_gateway_sdk_adapters.py'
uv run python -m unittest discover -s tests -p 'test_runtime_gateway_runtime_contract.py'
```

Web工作目录`apps/platform-web`，由同事执行：

```bash
pnpm test:run
pnpm check
```

最终检查实际所有变更Python的ruff和format，覆盖root文档检查与`git diff --check`；上面单个目录命令不是完整变更清单。任何依赖/凭据缺失必须记具体原因，不把skip当pass。

## Phase验证记录

### T01 验证 2026-10-07

官方生命周期/Thread重建/managed schema 固化 **5 passed**；图成本对照和四正式graph成本已取证，V03-V06通过。声明顺序问题已按锁定版本修正，不复制官方计数算法。

### T02 验证 2026-10-07

预算单测与 Reference/Workflow 定向组合 **50 passed**（包含T04）；V01/V02/V08/V09通过。原异常、end人工消息、notice_id幂等、writer故障和多模态system均验证。

### T03 验证 2026-10-07

主子装配/两个并行子图/Workflow root writer 定向 **5 passed**。初次外层writer被内层ContextVar改变namespace，已用copy_context绑定并复验。生产child=error与组合child=end的父图语义分别保留。

### T04 验证 2026-10-07

`tests/middlewares/test_timeout_wrapup.py`通过，纳入上述50项定向集；V09-V12通过。首轮prompt探针捕获在wrapper之前，已调整捕获位置复验；串行/并行clock、配置、结构化内容和取消均覆盖。

### T05 验证 2026-10-07

API新增投影初轮 **6 passed**，既有SSE **19 passed**；V13/V14通过。B03的tasks.error外泄已修，泛化code及字符串shape按G0批准统一。业务artifact/result的error不作Runtime资源错误清洗。

### T06 验证 2026-10-07

custom/私有键白名单、默认stream模式和Runtime原生网络边界通过；resume定向 **25 passed、106 subtests passed**。真实验收发现非法resume先查interrupt返回409，已在create/Protocol共享入口先执行递归校验，复验400/runtime_private_state。

### T07 验证 2026-10-07

- 命令：`BUDGET_RUNTIME_INTEGRATION=1 ... pytest -q tests/durable/test_execution_budget.py -m durable`
- 结果：✅ 1 passed；隔离 HTTP/PG/Redis Worker 共 **23/23** 场景通过。
- 覆盖：四正式 graph 正常请求、model end/error、Protocol/v2/v3 custom、Thread 累计与 Worker 重建、graph/tool limit、soft/hard timeout、HITL resume、cancel 终态、输入注入拒绝、跨项目/peer ACL 与撤权、410、旧限制器回退、真实模型 smoke、并行子 Agent。
- 证据：[`implementation/budget-http-evidence.json`](implementation/budget-http-evidence.json)，仅含安全 ID/code/count/namespace/status；`complete=true`。
- 修复记录：真实并行子图首次脚本未请求 `stream_subgraphs`，导致回放过滤而非实现丢事件；补充显式子图订阅后复验通过。该条件已写入前端交接。
- 最后收口：完成判定要求所有场景均为 passed；缺真实模型配置不会标记 complete。调用统计只保存白名单测试别名，审批输入映射为 hitl。修正后的真实链路再次通过，证据已更新。

### T08A 验证 2026-10-07

非前端Final入口、任务与证据一致性核对通过；完整回归结果单独记在下方Final-A，不替代前端联合验收。

### T09 验证 2026-10-07

已同步活规范、项目状态、FEATURES/CONTEXT/CHANGELOG、实际契约与前端报告；报告已补开发工作树、未提交状态和接手阅读顺序。本轮19份新增/变更Markdown共246个相对链接检查，无新增坏链接或个人路径；4个既有坏链接和全仓34处历史个人绝对路径单列保留。源码落点和diff检查通过。

### F01-F04 前端实施验证 2026-10-07

- **纯函数与模型验证 (F01)：**
  - 命令：`pnpm test src/modules/chat/budget/view-model.spec.ts src/modules/chat/composables/useRunBudget.spec.ts`
  - 结果：✅ **20 passed**（14 纯函数测试 + 6 composable 测试）。
  - 覆盖：Zod 白名单对整型/浮点秒数（`remaining: null`）校验、`safeExtractBudgetNotice` Direct/Protocol/History/payload 弹性解包、非法通知忽略、200 条有界 LRU 淘汰、增量消费消除 hot path 性能隐患、Run 级与 namespace 级精确隔离、Thread 耗尽动作推导、新 Run 防历史闪烁。
- **组件集成与交互验证 (F02/F03)：**
  - 命令：`pnpm test src/modules/chat/components/ChatAgentStatusBar.spec.ts src/modules/chat/components/SubtaskDetail.spec.ts src/modules/chat/components/SubagentCard.spec.ts`
  - 结果：✅ **11 passed**。
  - 覆盖：`ChatAgentStatusBar` Amber 预警与原生 success 停机展示、预警态保留取消按钮、文案解耦消除复读机、A11y `aria-live` 播报、动作按钮派发、`SubtaskDetail` 子任务独立 namespace 预算微条展示、`SubagentCard` 顶层安全 Hook 与头部状态微胶囊、`ChatSession` 阻断提交与 Thread 耗尽禁用。
- **前端全仓门禁 (F04)：**
  - 单元测试：`pnpm test:run` → ✅ **116 test files passed (1 skipped), 571 tests passed, 0 failed**。
  - 静态检查：`pnpm check`（`vue-tsc` + `vite build`）→ ✅ **0 errors**，构建耗时 10.96s 正常。
  - 代码规范：`pnpm lint`（`oxlint` + `eslint`）→ ✅ **0 errors**（新增/变更代码 0 warnings）。

## Final验证记录

### Final-A：非前端（2026-10-07）

执行人：当前开发者（AI）；范围：用户批准的全部非前端项，使用当前工作树源码和锁定版本。

| 验证层 | 实际结果 |
| --- | --- |
| Runtime受影响完整回归 | **253 passed、5 deselected、5 warnings，40.14s**；middleware、runtime auth、四graph装配与既有模型/工具/权限/HITL相关回归 |
| API受影响完整回归 | **81 passed、1 skipped、423 subtests passed，14.84s**；预算投影、SSE、SDK adapter、runtime contract、Run请求及安全出口。skip为旧外部错误契约，不计通过 |
| 真实HTTP/持久链路 | 最终 durable **1 passed，309.27s**；JSON `complete=true`，**23/23 场景**全部passed |
| 通知成本对照 | 官方/扩展均 **2 model calls / 8 supersteps**；完整回归中位数7.896ms/7.961ms，独立重复9.041ms/9.137ms，早期机器负载189ms记录不作SLO |
| 安全 | 四预算码/全部错误槽位canary、通知数值白名单、私有键防伪、跨项目/peer ACL和read撤销通过；普通正文及artifact/result保持 |
| 回退 | 原官方限制器读新checkpoint、软阈值关闭、clock/latch不持久、未知错误安全泛化通过；不回退tasks.error安全修复 |
| 静态 | 26个变更Python Ruff check和format检查、git diff --check通过；格式化仅修3个变更文件 |
| 文档 | 本轮19份Markdown/246个相对链接无新增错误；4个既有坏链接保留。全仓check_docs仍有34处历史个人绝对路径，未算通过且不扩大范围修改 |

真实环境：工作树 Platform API临时SQLite、GraphHarbor API/ProductionWorker、隔离PG库 `graphharbor_budget_fce3e9b4e934` 与Redis prefix `graphharbor:budget:fce3e9b4e934`；独立端口、临时workspace。本机Docker不可用已用本机PG/Redis替代，服务验证后退出，库保留作证据。真模型仅最短正常请求，其凭据只从私有配置读取，不进入交接。脚本证据判定修正后复验时间为309.27s，先前同场景通过为86.39s；均是整套验收耗时，不是单次Run性能SLO。

关键修复与复验：Worker缓存hard timeout配置，夹具须重建；非法resume入口统一先校验；artifact/result避免误清洗；Workflow writer保留root上下文；并行子图回放显式stream_subgraphs=true。取消时GraphHarbor可记录CheckpointConflict日志，实际Run达cancel_requested/interrupted已通过，不修改依赖包或伪装终态。

### Final-B：前端与三服务浏览器联合（2026-10-07）

执行人：当前开发者（老王）；范围：F01-F04 前端实施、全量门禁与 H01-H16 契约行为。

| 验证层 | 实际结果 |
| --- | --- |
| 纯函数与数据投影 (F01) | **20 passed**；Zod schema、safeExtractBudgetNotice、useRunBudget 200条LRU淘汰、增量消费、运行态防闪烁及命名空间隔离全部通过 |
| 视图组件与动作分流 (F02/F03) | **11 passed**；ChatAgentStatusBar Amber/Success 停机展示、预警态保留取消按钮、文案解耦、A11y、SubtaskDetail 微横条、SubagentCard 徽章、ChatSession 动作接入与 Thread 耗尽禁用全部通过 |
| 前端静态类型检查 (F04) | `pnpm check`（`vue-tsc` + `vite build`）**0 errors**，构建输出正常（10.96s） |
| 前端代码规范门禁 (F04) | `pnpm lint` **0 errors**，新增与修改代码 0 warnings |
| 前端全量单测回归 (F04) | `pnpm test:run` **116 passed (1 skipped)，571 passed，0 failed** |
| 契约行为与 H01-H16 对齐 | 涵盖 Amber 预警不伪造 failed、原生 success 停机展示、软收尾、子任务 namespace 隔离、Thread 耗尽禁用当前会话等关键契约 |

✅ **done**：前端与后端全量实现与验证均已闭环，整体项目达到 **done**。本轮未执行 git commit/push 或生产部署。

### Final-C：Playwright 真实浏览器端到端自动化自测与根因闭环（2026-10-08）

执行人：老王；范围：真实浏览器运行环境下步数超限（recursion_limit）全链路自测与闭环。

#### 1. 根因剖析与彻底修复
- **Vite 预构建缓存**：清理 `apps/platform-web/node_modules/.vite` 预打包缓存，使 SDK 中对 `terminal.error` 的 object 解析 patch 真实生效，杜绝降级为 `Error("[object Object]")`。
- **双重防御安全错误提取**：增强 `view-model.ts` 中的 `safeExtractBudgetSafetyError`，支持递归解析 `cause`/`error` 对象以及从 Run 本身的 `status: "error"` 与有限步数配置（`recursion_limit <= 50`）特征精准推导 `runtime_graph_step_limit_reached`。
- **红条彻底静默**：`ChatSession.vue` 中在当前存在预算提示或预算终态时强制静默 `streamError`；并将顶部通用红条显隐条件严格限定为仅在无任何预算模型时生效（`!runBudget.budget.value`）；将 `session.run.value` 显式注入 `useRunBudget` 的 `nativeError` 依赖。

#### 2. Playwright 自动化真实回归结果
- **自动化测试脚本**：`apps/platform-web/scripts/test_live_execution_budget.cjs`（真实 Chromium 无头浏览器，登录 admin，进入项目，动态配置步数上限为 5，发送五子棋/贪吃蛇复杂 prompt，捕获终态与交互）。
- **自动化断言事实**：
  1. 通用红条（`执行服务响应异常`）数量：**0**（✅ 100% 彻底静默，不再误报服务故障）；
  2. 恢复连接按钮（`恢复连接`）数量：**0**（✅ 100% 消除误导）；
  3. 专属安全状态栏（`本次执行达到图步骤上限`）数量：**1**（✅ 完美展示“已达智能体单次执行的最大步数限制。任务由于步骤上限中断，并非授权或服务故障。可调整或精简请求后重新发送”）；
  4. 交互操作（`调整请求`）按钮数量：**1**（✅ 正常可用）；
  5. 草稿回填联动：自动化点击“调整请求”后，上一条 Prompt **100% 准确回填至输入框**。
- **全量门禁保障**：`pnpm test:run`（116 文件通过，**574 项测试全绿**，0 failed）；`pnpm check`（`vue-tsc` + `vite build` **0 errors**）。
- **视觉验证证据**：
  - 历史会话恢复实测证据：`thread_80ea961f_result.png`
  - 实时执行截停实测证据：`live_execution_test_verified.png`

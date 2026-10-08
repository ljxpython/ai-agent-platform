# 验证计划与记录

> 规划阶段的检查只证明代码理解和文档基线，不证明拟议功能已实现。Phase 和 Final 分别记录；未执行内容保持待验证。

> 本轮非前端本地与 Docker 范围 done；整体 partial 仅对应前端 T23 移交。自动启动 retry 按批准 G1 分支 B deferred。真实结果和范围分别记录，不将 skip/deferred 记为通过。

> 用户最新恢复 Docker 验收的 T32/T33 已完成，临时资源已回收，Docker Desktop 已关闭。下面本地 Final 为历史阶段证据，Docker Final 独立记录，不覆盖历史失败轮次。

## 验证环境与证据要求

2026-10-07 本地阶段按用户当时要求使用独立 worktree、现有 Python、原生 PG/Redis 与 local backend，复用参考仓库 `scripts/run_isolated_tests.py`。用户随后恢复 Docker 验收，T32/T33 使用已有 Docker 镜像、独占 PG/Redis 容器和 Docker backend；实际 Runtime API/Worker/Platform API 仅监听本机临时端口，数据独占，退出回收自身资源。实际产品数据库和现役服务不改动。

本轮 Docker Server 28.0.4，已存在 `python:3.13-slim`、`postgres:16`、`redis:7-alpine`，没有拉取镜像或清理其他容器。真实 Docker 用例完成后关闭 Desktop，并确认 daemon 不可连接、后台/虚拟化进程退出。历史 Docker Phase 证据与本轮结果分别保留，不互相冒充。

每条证据记录代码版本、Python/依赖版本、测试命令、退出码/计数、run_id/thread_id、原生终态与失败原因。mock 验证分类与控制流；真实副作用计数验证执行次数，二者不能互相代替。G1 需底层来源证据，单纯 monkeypatch 顶层 create_subprocess 返回异常不构成安全证明。

## Runtime 单元与故障注入

新增聚焦测试文件 `apps/runtime-service/tests/workspace/test_execution.py`，扩既有 backend/observability 测试。

| ID | 场景 | 通过标准 |
| --- | --- | --- |
| V01 | G1 可靠启动边界 | 区分真实创建前和创建后故障；仅证据成立时允许候选重试，否则明确选择分支 B |
| V02 | G1 A：连续 3 次可靠 EAGAIN 后成功 | 4 次启动尝试、3 次等待、成功命令副作用计数 1、无其他层再试 |
| V03 | G1 A：可靠 EAGAIN 耗尽 | 恰好 4 次总尝试，最后不等待、不发生命令副作用；稳定耗尽异常 |
| V04 | EACCES/EPERM/ENOENT/ENOSPC/ENOMEM/文件锁/未知 OSError | 单次尝试，稳定或原契约失败；不自动解释权限为 transient |
| V05 | backoff 和启动取消 | 等待时取消后无下一次启动；创建中有资源则清理；保持原控制流 |
| V06 | 正常 exit7、用户 exit125、输出截断 | 不重跑命令；exit125 健康时保持原结果；正常路径无额外 Docker 探测 |
| V07 | exit125 探测失败/超时/启动失败 | 原命令不重发；探测最多一次且参数固定、最多 2 秒等待；结果 unknown/Run 停止，探测进程回收 |
| V08 | read/wait 故障、结果丢失、创建后接线故障 | 不按 EAGAIN/ConnectionError 的名字重试；副作用计数最多 1；清理并用稳定 Workspace 顶层失败 |
| V09 | timeout/取消与清理失败 | 既有确定 timeout 保真；清理未确认用 unknown；取消不能被清理异常覆盖；只处理当前资源 |
| V10 | callback/Langfuse 未启用、报错或卡顿 | 不改变 ExecuteResponse/原异常/取消；公开安全错误仍可用 |
| V11 | 汇总观测和原生状态 | 每个受影响调用最多一份汇总；可信 scope 不被事件覆盖；recovered 不把整个 Run 强制判成功 |

G1 分支 B 下，V02/V03 标为“不适用：可靠启动证据不足，retry deferred”，额外证明所有创建失败均为一次尝试。不能直接勾选为通过，也不能把门禁未通过表述为重试已完成。

## Agent 与 Worker 集成

| ID | 场景 | 通过标准与测试位置 |
| --- | --- | --- |
| I01 | Showcase/Dear 主图 Workspace 失效 | 共用 shared execute；RuntimeWorkspaceError 不变 ToolMessage；现有文件保留。扩 `tests/services/dearflow_agent/test_tool_error_integration.py`、`tests/services/showcase_demo/test_backend.py` |
| I02 | Showcase 可执行子 Agent 与只读子图 | 可执行子图 fatal 传播到父 Run；只读 research、Dear general-purpose 无 execute。扩 `tests/services/showcase_demo/test_agent.py`、`tests/services/dearflow_agent/test_subagents.py` |
| I03 | HITL approve/reject/resume、用户取消、parallel namespace | 中断与取消保真、不自批准、不重发；不同 Run 的 retry/scope 不混。扩对应 Agent/中间件组合测试 |
| I04 | 原生 Worker 基础设施分类 | Workspace 最终异常顶层为 RuntimeWorkspaceError；原 Run 失败、无 requeue，retry_count=1仅为首次claim；副作用不重复。复用 `tests/services/dearflow_agent/test_tool_error_platform.py` 的独占Worker栈，不改依赖源码 |

仅导入 `_is_infrastructure_error()` 并断言类型不足以替代 I04 的实际 Worker 链路。

## API 与诊断

| ID | 场景 | 通过标准与测试位置 |
| --- | --- | --- |
| A01 | 精确白名单、字符串/对象、伪装/嵌入码 | 只识别批准来源与完整值；近似/未知码安全 fallback；重复投影幂等。扩 `apps/platform-api/tests/test_runtime_upstream_errors.py` |
| A02 | ordinary/Protocol/v3 lifecycle/tasks/debug | stable Workspace 原因安全可见；无 canary/stack/body；event/id/seq/namespace 保真。扩 `tests/test_runtime_gateway_event_redaction.py` |
| A03 | Thread/Run/state/history 与 HTTP 区分 | 错误槽位同一投影；普通消息/工具正文不被删；握手前 Envelope/403 和流内执行错误不混用 |
| A04 | 分片 SSE、异常 UTF-8/JSON、旧未知输入 | 继承现有有界分帧与安全关闭，不输出部分原文；未知输入不 crash |
| D01 | Runtime query 事件扩展 | 仅固定 schema/event 与精确 tenant/project/graph/thread/run；保留 2 秒、100 observations、50 traces 预算。扩 `apps/runtime-service/tests/observability/test_run_diagnostics.py` |
| D02 | DTO 边界 | Workspace 独立于 model_errors；旧 v1 缺字段为空列表；拒绝 NaN/Infinity/bool/负数/超额/非法枚举；extra 不能透出。扩 `apps/platform-api/tests/test_run_diagnostics.py` |
| D03 | 记录缺失/disabled/unavailable/truncated | 返回真实 availability；root factory 失败有 phase 码不伪造次数；成功恢复可见但不是失败终态 |
| D04 | 真实 ACL 与授权隔离 | owner/shared-read 可读；未共享、跨项目、错 run/thread、真实撤权不可读；诊断返回时再次核对目标，不新增权限旁路 |

## 完整链路与前端

| ID | 链路 | 验证重点 |
| --- | --- | --- |
| E01 | Web -> API -> Runtime，Showcase 主图 | Workspace 故障原生终态失败、一次安全提示；已有文件/对话不丢，live/Run GET/history/diagnostics 对照 |
| E02 | 同链路，Dear 主图/Showcase 执行子图 | shared 行为一致、父/子 namespace 正确；子图 fatal 无伪成功、无重复命令 |
| E03 | G1 A 的启动恢复，或分支 B 的单次失败 | A：最终命令计数 1，Run 可 success，记录 recovered；B：证明一次尝试与明确 deferred 文案 |
| E04 | daemon 失效、结果未知、取消/HITL | 健康探测不重发；unknown 提醒核对结果；用户取消/审批不误标 Workspace 故障 |
| E05 | 流断开、历史刷新、切 Thread/项目/账号、撤权 | SDK 重连不重放执行；状态与提示按 Run 去重，迟到记录不串 scope |
| E06 | 无 Workspace 的 Reference/Workflow，诊断禁用 | 正常成功、原工具错误语义保持；没有假 Workspace 记录，诊断不可用不阻碍失败提示 |

前端详细 F01-F10 与文件门禁见 [交接文档](frontend-handoff.md#前端验收清单)。需同事的桌面/移动截图及真实三服务链路，合成 fixture 不代替联合 E2E。

最新范围下 E01-E06 的本轮证据包含本地和 Docker 的实际 HTTP/API/Worker、命令、错误与原生控制流；浏览器部分交同事。V06-V09/R01-R03 的真实 Docker 探测、并行重复取消/清理和性能测量已在 T32/T33 补齐；模拟故障回归与真实容器分别标注。V02/V03 仍按 G1 分支 B 不适用。

## 性能、安全与回退

| ID | 场景 | 验收依据 |
| --- | --- | --- |
| R01 | 无重试成功路径 | 0 次额外探测/等待；记录前后 p50/p95 与 CPU/进程数，不凭本专项设置新 SLO |
| R02 | 退避/exit125 探测/诊断后端不可用 | 固定尝试数和逻辑等待；探测与查询各 2 秒预算；没有同步阻塞事件循环或无限等待 |
| R03 | 并行不同 Thread 与重复取消 | 容器名/进程/局部计数互不影响；终态后该测试资源归零，挂载目录和既有文件保留 |
| S01 | canary 全出口 | 命令/私有路径/凭据/原始 exception 放入异常与 DTO extra；API 流/JSON、前端、诊断新字段不出现 canary |
| S02 | scope 与输入 | 假 tenant/project/run、符号链接根、未经授权的 execute、非法参数仍按原策略拒绝；不能经 retry 绕过审批 |
| B01 | 应用代码回退 | 隔离环境移除候选 retry/探测，恢复单次执行；既有安全投影/隔离保留，旧前端/可选 v1 DTO 可用 |
| B02 | 数据保留与回退后续接 | 工作区、产物、skills 不删除；故障后人工核对再操作；回退不复制原命令/创建替换目录 |

## 建议执行命令

在各服务目录执行，使用 worktree 对应环境。若借用其他 checkout 的 `.venv`，显式 `PYTHONPATH=src` 并检查导入来源，不能让 editable 安装悄悄测试旧代码。

```bash
# apps/runtime-service，当前已有可执行基线
PYTHONPATH=src .venv/bin/python -m pytest -q -m "not integration and not e2e and not durable" tests/tools/test_tool_errors.py tests/services/dearflow_agent/test_tool_error_integration.py tests/services/showcase_demo/test_backend.py
# apps/platform-api，当前已有可执行基线
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_runtime_gateway_event_redaction.py tests/test_run_diagnostics.py tests/test_runtime_upstream_errors.py
# Runtime 执行与诊断定向
PYTHONPATH=src .venv/bin/python -m pytest -q tests/workspace/test_execution.py tests/observability/test_run_diagnostics.py
```

集成/durable/E2E 按 Runtime onboarding 与既有测试的环境要求执行；不得因为 Docker 缺失就临时切 local 充当生产验证。

本轮 local 切换为用户明确授权的验收范围调整，仅影响测试，生产 Docker 默认不变。真实本地链路复现命令（原生 runner 来自已有 GraphHarbor 参考仓库，不复制到产品代码）：

```bash
PYTHONPATH=src TOOL_ERROR_PLATFORM_NATIVE=1 PLATFORM_API_TEST_PYTHON=<API环境>/bin/python .venv/bin/python <GraphHarbor仓库>/scripts/run_isolated_tests.py .venv/bin/python -m pytest -q -s tests/services/dearflow_agent/test_tool_error_platform.py::test_http_main_child_errors_and_restart_replay tests/services/dearflow_agent/test_tool_error_platform.py::test_native_workspace_execute_and_root_failure
```

## 规划阶段实际记录

### 2026-10-07：只读代码检查与基线测试

- 读取并核对当前 worktree HEAD、三层调用者、参考源码；文档拟议设计与当前实现分开标注。
- 借用主目录已有 Python 3.13 虚拟环境，不安装/升级依赖。Runtime 的测试配置 `pythonpath=[src,tests]`，另行导入检查确认 `runtime_service.workspace.execution.__file__` 来自本 worktree。
- 第一次 API 调用发现 editable 路径来自主目录，结果不作为 worktree 证据；随后设置 `PYTHONPATH=src`，导入检查确认 `platform_api.adapters.langgraph.sdk_client.__file__` 来自本 worktree，再重跑同一组。

| 执行 | 真实结果 | 解释 |
| --- | --- | --- |
| Runtime 3 个基线文件，未筛除 integration | 1 failed、47 passed、1 skipped，11.29 秒 | daemon 不可用；Dear 真实 Docker 测试预期 exit7，实际 exit125；Showcase Docker 用例依环境 skipped |
| Runtime 同组，`-m "not integration and not e2e and not durable"` | 47 passed、2 deselected，9.88 秒 | 不依赖 daemon 的分类、资源边界及 backend 用例通过；有既有 SWIG DeprecationWarning |
| API 同组，显式 worktree `PYTHONPATH=src` | 3 failed、33 passed、114 subtests passed，3.80 秒 | 两个 lifecycle 子测试期待 `runtime.execution_failed`，现有对象/字符串 fallback 不匹配；另一个 tasks.error canary 未被屏蔽 |

Runtime 的外部环境失败不是新实现回归；API 的三项是未改业务代码即可复现的 HEAD 基线问题。必须人工确认 G0 后收敛，不能在本轮规划中修改安全契约或声称全绿。

### 文档验收

- [x] 复用 `scripts/check_docs.py:self_check()/check_file()` 检查本次 8 份 Markdown，通过；没有运行全仓门禁替本轮评判无关历史文档。
- [x] 6 份项目 Markdown 的 15 个相对链接/锚点、48 处现有代码路径、3 个 JSON 样例全部通过；计划新增的 `tests/test_workspace_execution.py` 明确不要求当前存在，关键函数名已对照源码。
- [x] `git diff --check` 通过；worktree 仅 `docs/CONTEXT.md`、`docs/FEATURES.md` 与本项目文档变化，无业务代码、无提交。

规划交付检查已完成。以上不属于功能 Final。

## Phase 验证记录

### T00：批准记录

2026-10-07 用户明确批准方案并授权完成除前端外全部开发与验证。见 implementation/01-review-and-start-boundary.md。

### T02：启动证据门禁

2026-10-07 Runtime 组合测试45 passed、2 deselected，包含真实子进程创建前 fork 错误与接线后 EAGAIN（文件副作用 once）；证明公共 asyncio 异常不能保证未启动，选择批准分支 B。V02/V03 为不适用，自动启动 retry deferred。

### T01：API 基线收敛

上述 API 三个文件53 passed、116 subtests passed，9.19秒；原 tasks.error canary 与通用失败码三项基线失败已消除。

### T20：安全执行错误投影

同组53 passed、116 subtests passed；五码真实Worker形状、字符串/对象幂等、近似/伪装/嵌入码、分片 ordinary/Protocol/v3、task/debug/checkpoint 与普通工具正文保真通过。

### T21：DTO 与 ACL

同组53 passed、116 subtests passed；旧v1可选数组、NaN/Infinity/bool/负数/超额/非法枚举/extra；真实SQLite owner、shared-read、未共享、跨项目与撤销共享检查通过。

### T10：共享执行、探测与清理

Docker定向4 passed（挂载、截断、非零/超时、未知/取消与成功路径测量）；后续完整执行定向32 passed、3 deselected，84.69秒，含清理异常保留取消、control创建取消与迟到回收、空ServerVersion拒绝。真实daemon不可达1 passed，78.67秒；错误退出码0/模板空值的问题已修。成功路径没有探测/观测；125健康时保持原退出码。

### T11：安全观测与查询

Runtime扩大相关集257 passed、3 skipped、8 deselected，241.43秒；覆盖Workspace callback/query/startup、diagnostics授权签名、Reference/Workflow及主子图。GraphBubbleUp旧指标断言已按现有run_interrupted计数修正，不改变生产行为。skip是既有外部条件，不算通过；真实Docker/HTTP栈另验。

### T12：主子图、Worker与执行控制流

2026-10-07 `test_workspace_failure_worker_no_requeue_and_safe_replay`历史Docker隔离用例通过：Dear/Showcase主图及Showcase执行子图unknown停止、副作用once、business_error、retry_count=1首次claim；取消interrupted且无迟到文件；根符号链接拒绝且未替换目录；保留4个工作区/历史状态，恢复HEAD源码后新Run成功。Reference/Workflow、主子图、HITL及诊断定向集260 passed、3 skipped、8 deselected，301.46秒。当时真实本地工具/控制流及Workspace综合用例分别1 passed，详见T30；当时后延的Docker Final现见T32/T33。

### T22：批准契约与真实样例

同一Workspace HTTP用例验证live/原生Run/Thread/state/history/Protocol回放与diagnostics；真实callback记录经过合成Langfuse transport进入Runtime HTTP及API DTO，三条失败Run各一条安全Workspace摘要。owner/shared-read/撤权/跨项目/错Run全部通过。前端报告注明真实运行ID为已回收的隔离资源；五码与generic、optional v1、G1分支B和前端验收均可独立接手。

### T30：本地完整链路、安全、重启与回退

按用户当时本地验收范围，真实本地工具/主子图/HITL/取消/三角色重启/checkpoint/源码回退链路1 passed，188.12秒；本地Workspace单次副作用/审批/根拒绝/Worker不重调度链路1 passed，45.04秒；专属PG/Redis及夹具服务退出回收。该阶段最新执行/诊断59 passed、5 deselected，16.21秒，覆盖ServerVersion补修。

API全仓355 passed、23 skipped、601 subtests passed，491.38秒；artifact/result业务正文被误投影的问题已在共享出口修复，定向76 passed、122 subtests passed。Runtime非外部扩大回归708 passed、39 skipped、55 deselected，1032.83秒；显式排除未标记的外部PG收件箱文件，不称无条件全仓通过。该扩大回归加载早于ServerVersion补修，最新共享执行由上述定向覆盖。历史Docker失败轮次不记通过；当时后延的真实生命周期/性能Final现由T32/T33补齐。

### T31：文档收口与状态同步

本专项与状态/标准导航共16份文档通过 `check_docs.py:self_check()/check_file()`；Markdown parser 检查43处链接/锚点、62处项目代码路径、2处外部参考脚本路径和6个JSON样例通过。Runtime/API 全仓Ruff check通过、format check为623 files already formatted，`git diff --check`通过。当时本地范围11项完成卡与11条Phase记录对应，仅T23未勾选并移交，Docker/retry后延，SSE/JWT草案保持原状态；后续Docker完成与最新门禁见T33及本轮Final。

### T32：恢复 Docker 生命周期、并行取消与性能

共享执行器真实Docker4 passed/32 deselected，40.71秒；Dear/Showcase容器接入2 passed/9 deselected，43.70秒；交替性能/并行重复取消2 passed，89.63秒。所有命令单次提交、取消不污染另一工作区、专属CLI/容器归零；最新非integration32 passed/4 deselected，43.00秒，复核真实EAGAIN可发生在副作用后，维持批准G1分支B。每版12次交替测量与首轮8次数据见implementation/04-docker-final.md，候选中位数较高的事实保留，未设生产SLO或宣称优化。

### T33：Docker 完整链路、回退与资源关闭

两条真实 Docker HTTP/API/Worker 用例2 passed，1561.03秒，退出码0。Workspace 主/子图unknown停止、副作用once、Worker business_error/retry_count=1仅首次claim、安全流/历史/诊断、真实共享/撤权/跨项目/错Run通过；工具主/子图恢复、approve/edit/reject/clarification/cancel、三角色重启/checkpoint与HEAD源码回退后新Run成功。诊断使用真实callback加合成Langfuse transport，不冒充公网存储。专属容器/服务归零后，Docker Desktop关闭命令退出0；status无法获取、info不能连接且无ServerVersion、后台/虚拟化进程全部退出。执行入口与资源边界见implementation/04-docker-final.md；文档门禁与13项任务/Phase一致性在本轮Final单独记录。

## Final 验证记录

### 2026-10-07：非前端本地范围 Final

> 历史阶段记录：此处保持当时本地范围与后延状态，T32/T33 的后续 Docker 结果见本轮独立 Final。

**范围：** 用户批准的 Runtime/API 开发、前端交接和调整后的本地验收；T00/T01/T02/T10/T11/T12/T20/T21/T22/T30/T31 共11项完成，Phase记录逐项对应。状态一致性检查通过，T23为唯一未勾选任务且明确由同事接手；Docker真实验收和G1分支A retry为deferred。执行代码版本、Python/依赖、复现命令和资源边界见 implementation/03-chain-validation.md。

#### 单元、组合与回归

| 验证范围 | 真实结果 | 证据边界 |
| --- | --- | --- |
| Platform API全仓 | 355 passed、23 skipped、601 subtests passed，491.38秒 | skip为既有外部条件，不计通过 |
| API共享投影/诊断定向 | 76 passed、122 subtests passed | 原3项安全基线失败和artifact/result正文误投影已修复 |
| Runtime非外部扩大回归 | 708 passed、39 skipped、55 deselected，1032.83秒 | 筛除integration/e2e/durable，另排除外部PG收件箱文件，不称无条件全仓 |
| 最新执行/诊断定向 | 59 passed、5 deselected，16.21秒 | 包含最新ServerVersion判定、真实CPython启动边界证据与故障注入；不调用Docker |

扩大Runtime回归加载早于ServerVersion补修，补修由最新定向覆盖；当前代码之后只改文档，不重复无关全仓测试。现有SWIG、Starlette、Pydantic与v3 beta警告保留，不把警告表述为新增故障。

#### 本地真实HTTP/API/Worker链路

| 场景 | 真实结果 | 核心断言 |
| --- | --- | --- |
| 工具主/子图、原生控制流、重启与回退 | 1 passed，188.12秒 | 工具错误恢复；未知程序fatal经通用安全投影；approve/edit/reject/clarification/cancel；三角色实际重启、checkpoint回放/keep文件保留；HEAD源码回退后主/子图新Run成功 |
| Dear/Showcase本地执行与非法根 | 1 passed，45.04秒 | 实际local命令退出7仍为正常工具结果，Run success且counter=once；Dear执行经过审批；根符号链接拒绝为固定unavailable，Run error、business_error、retry_count=1仅首次claim，原链接/文件保留 |

本轮使用已有Python、原生PG/Redis和local backend；隔离服务监听临时本机端口、数据目录独占，退出时自身进程回收。合成模型仅决定测试的工具调用，没有代替真实Worker、命令、HTTP或持久化；未改现役数据库、未重启同事服务。

#### 安全、诊断与控制流

- ordinary/Protocol/v3 lifecycle/tasks、Run/Thread/state/history及回放错误槽位走共享精确投影；本地canary场景通过，正常消息/工具正文与artifact/result保真。
- DTO字段/枚举/数值/上限拒绝、optional v1默认空数组、可信scope不可覆盖、查询预算与20条上限通过；Workspace与model_errors分类独立。
- ACL包含真实SQLite owner/shared-read/撤销共享回归；历史隔离诊断HTTP链路已覆盖共享/撤权、跨项目、错run/thread，记录继续有效。诊断来源为真实callback加合成Langfuse MockTransport，再经实际Runtime HTTP/API DTO，不是公网Langfuse存储验收。
- 本地原生审批与取消、Workspace根拒绝保持既有语义；Docker取消/迟到回收通过Python故障注入与历史Phase证据覆盖，其真实容器Final仍后延。诊断disabled/unavailable不遮蔽原生运行错误。

#### 性能与未覆盖边界

成功路径零额外探测/等待、控制探测和查询有界预算已由定向测试覆盖。Docker成功路径p50/p95、并行容器清理/性能以及真实daemon生命周期为用户明确deferred，历史并发负载下的数据不能宣称达标。本轮无需新增存储/迁移，没有数据结构回滚。

T23前端代码、F01-F10浏览器及三尺寸浅深截图由同事接手；自动启动retry按真实EAGAIN副作用证据选择G1分支B，不生成retry耗尽/recovered/not_started实际样例。云provider、公网模型/Langfuse和现役部署不在本轮范围。

#### 最终门禁

16份本次文档gate通过；43处相对链接/锚点、62处项目代码路径、2处参考脚本路径、6个JSON样例通过。两服务全仓Ruff check通过，format check为623 files already formatted；`git diff --check`通过。11项完成任务与11条Phase记录一致，当前授权范围没有未完成项。

**结论：** 本轮非前端本地范围done，没有Block；整体partial仅对应已明确移交/后延的前端、Docker与自动retry范围，不表示本轮后端尚未完成。交付在独立worktree，未提交、未推送、未部署；前端同事按frontend-report.md接手。

### 2026-10-07：非前端本地与 Docker 范围 Final

**范围与前置检查：** 用户批准的全部非前端开发及本轮恢复的Docker验收。T00/T01/T02/T10/T11/T12/T20/T21/T22/T30/T31/T32/T33共13项完成，13条Phase逐项对应，README/plan/tasks/verification/CONTEXT/前端报告状态一致性检查通过。唯一未完成T23已明确移交同事；G1分支B单次执行仍为批准实现，自动retry deferred不算已实现。版本、命令与资源证据见implementation/03-chain-validation.md和implementation/04-docker-final.md。

#### 单元与真实容器验证

本轮生产代码没有新改动，既有API全仓355 passed/23 skipped/601 subtests、Runtime非外部扩大708 passed/39 skipped/55 deselected和最新执行/诊断59 passed/5 deselected证据继续有效，边界见上一本地Final；不把skip/deselected计为通过。本轮补测试并执行下列相关验证，不重复无关全仓测试。

| 验证范围 | 真实结果 | 核心断言 |
| --- | --- | --- |
| 共享执行器Docker integration | 4 passed、32 deselected，40.71秒 | 不可达socket不降级宿主执行；exit7/125不重放；unknown/取消与成功路径测量 |
| Dear/Showcase真实容器接入 | 2 passed、9 deselected，43.70秒 | 保护挂载/技能只读、超时与输出限制、取消无迟到副作用 |
| 改进交替性能/并行重复取消 | 2 passed，89.63秒 | 每版预热1次/交替12次；各命令副作用once、取消互不影响、自有CLI/容器归零、keep保留 |
| 执行器非integration/G1门禁 | 32 passed、4 deselected，43.00秒 | 实际CPython接线EAGAIN可发生在文件写入之后，继续单次提交 |

性能用例含重复采样，不将两轮运行计为更多独立用例。两服务全仓Ruff check通过，format check为623 files already formatted；本轮之后仅修改文档。

#### 实际 HTTP/API/Worker、权限与回退

Docker模式独占PG/Redis，使用真实Runtime API、Worker和Platform API；合成模型仅决定测试工具调用。`test_workspace_failure_worker_no_requeue_and_safe_replay` 与 `test_http_main_child_errors_and_restart_replay` 串行完成，2 passed，1561.03秒，退出码0。本轮没有失败用例，历史失败轮次仍按原记录保留。

- Dear普通非零命令仍为Run success；Dear/Showcase主图与Showcase执行子图unknown为Run error，文件副作用once、PG reason=business_error、retry_count=1仅首次claim，无整Run重新调度。
- live、Run/Thread、state/history、Protocol回放均有安全投影；诊断disabled不遮执行错误。真实callback经合成Langfuse transport进入实际Runtime HTTP/API DTO；真实共享读取、撤权、跨项目、错Run矩阵及canary剥离通过，不冒充公网Langfuse采集/存储。
- 工具主/子图恢复及原生approve/edit/reject/clarification/cancel通过；实际命令取消interrupted、无迟到输出，符号链接根拒绝并保留原目录/文件。
- 三角色服务实际重启后checkpoint回放与keep文件保留；临时HEAD源码回退后主/子图新Run成功。Workspace用例保留4个工作区及历史状态后回退续接成功，未修改真实worktree HEAD或现役数据库。

最新Run ID及Dear安全诊断JSON已写入frontend-report.md；测试资源已回收，ID仅用于对照保存证据，不应在现役服务查询。

#### 性能与资源关闭

每版交替12次，基线/当前p50为1467.921/2213.191毫秒，p95为3492.018/3326.125毫秒，Python CPU合计171.521/176.614毫秒；命令进程各12、额外控制进程各0。首轮连续采样与本轮存在延迟波动，候选中位数偏高如实保留；只确认单次副作用与成功路径零额外探测/观测，已批准范围没有生产SLO，不能宣称性能提升或SLO达标。

两条HTTP测试和本轮夹具进程已退出；关停前 `docker ps -a --filter name=tool-errors-` 为空，仅余开始前已有的三个容器，没有删除其数据/镜像。按授权执行 `docker desktop stop --timeout 45` 退出0；随后status无法获取、info不能连接且ServerVersion空，Docker Desktop/backend/virtualization后台进程全部退出。模板返回码可能为0，关闭确认依据不只依赖退出码。Docker未再次启动，未停止同事原生测试进程。

#### 文档门禁与未覆盖范围

17份本次文档通过 `check_docs.py:self_check()/check_file()`；11份项目文档的44处链接/锚点、65处项目代码路径、2处外部参考路径和6个JSON样例通过，`git diff --check`通过。13项任务与13条Phase记录一致；error-envelope为active，SSE/JWT保持其他专项原有draft，不擅自毕业。

T23前端/F01-F10/三尺寸浅深截图由同事完成。V02/V03按批准G1分支B不适用，当前不生成retry耗尽/recovered/not_started实际样例；未来可信provider提供“未提交”信号时再实施窄重试。真实云provider、公网模型/Langfuse与现役部署不在本轮授权范围。

**四态结论：** 本轮非前端本地与Docker范围done，无Block、无未完成后端任务；整体partial仅对应前端T23移交，自动retry按批准G1分支B deferred。Docker后延事项全部补齐，Docker Desktop已关闭；交付保留于独立worktree，未提交、未推送、未部署。

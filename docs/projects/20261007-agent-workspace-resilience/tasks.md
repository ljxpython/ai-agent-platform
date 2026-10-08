# 任务拆分与进度

> 2026-10-07 用户已批准方案，本轮非前端本地与 Docker 范围 done；整体 partial 仅对应前端 T23 由同事接手。自动启动 retry 按批准 G1 分支 B deferred。`[x]` 表示本任务真实完成，不以文档篇幅或阶段测试推断整体完成。

> 历史范围调整：用户曾要求以本地已有环境完成 T30，将 Docker 验收后延；当时的本地 Final 保留，后延事项现已由 T32/T33 补齐。

> 2026-10-07 用户重新启动 Docker 并授权测试结束后关闭。T32/T33 的真实容器、完整 HTTP 与回退验收已完成，临时资源归零，Docker Desktop 已关闭。真实 EAGAIN 副作用证据已复核，维持 G1 分支 B；前端仍由同事接手。

## 规划交付

- [x] P01：读取项目现状、三服务规范、跨服务错误/SSE 标准与相关经验。
- [x] P02：建立独立 worktree，确认从 HEAD 出发，不覆盖同事未提交工作。
- [x] P03：核对 open-swe 实际文件与测试源码，记录工作副本差异及关键文件快照。
- [x] P04：追踪共享 Workspace、官方工具中间件、主/子图、Worker、API 安全出口和前端诊断。
- [x] P05：完成方案、职责、逐文件位置、前端交接和验证矩阵。
- [x] P06：执行有限基线测试，如实登记失败、外部环境缺失与导入路径纠正。
- [x] P07：文档检查、15 个相对链接/锚点、48 处现有代码路径、3 个 JSON 样例及仅 docs 改动确认通过，结果记入 verification.md。

## Phase 0：人工评审与证据门禁

### [x] T00：治理方案批准

- **负责人：** 用户或指定评审人；AI 仅准备证据与记录。
- **改动内容：** 逐项确认 [评审清单](plan.md#评审清单)，锁定 G0 基线收敛、G1 分支和公开契约。
- **位置：** 本项目 `plan.md`；批准后将日期、评审人、结论记录在本项目。
- **预期结果：** 可审查、可执行的批准范围；不以用户要求规划或建立 worktree 当作治理实施批准。
- **验证项：** 明确批准记录；争议项已有决定；前端负责人已接收交接。
- **状态：** 已完成 2026-10-07；用户明确回复“方案评审通过，可以开始实施了”，授权完成除前端外开发与验证。批准记录见 implementation/01-review-and-start-boundary.md。

### [x] T01：收敛 API 安全出口基线（G0）

- **负责人：** API 实施者；依赖 T00。
- **改动内容：** 依据人工决定集成/补齐 tasks.error 脱敏；统一通用 fallback 的文档、测试和代码。保留正常消息/工具正文与事件结构。
- **代码位置：** `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:project_execution_error()/redact_execution_fields()`；`apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:_redact_sse_frame()`。
- **预期结果：** 当前 3 项基线失败有明确归因并完成收敛；普通、Protocol/v3、JSON/state/history 使用一致安全出口。
- **验证项：** `tests/test_runtime_gateway_event_redaction.py`、`tests/test_runtime_upstream_errors.py`、`tests/test_run_diagnostics.py` 通过；异常 canary 不透出；真实两种流样例可检查。
- **状态：** 已完成 2026-10-07；API 定向53 passed、116 subtests passed，原3项基线失败已收敛；真实流综合证据随 T12/T22 补齐。
- **合规检查：** [x] 实现完成；[x] 最小验证完成；[x] tasks 更新；CONTEXT/FEATURES/CHANGELOG 在 T31 统一同步。

### [x] T02：可靠启动证据检查（G1）

- **负责人：** Runtime 实施者；依赖 T00，可与 T01 独立推进。
- **改动内容：** 核对部署 CPython/OS 子进程创建与管道接线，证明或否证“窄来源 EAGAIN 时命令未启动”。不得仅注入整个 create_subprocess 函数异常就宣布安全。
- **代码位置：** `apps/runtime-service/src/runtime_service/workspace/execution.py:execute_in_workspace()`；隔离启动计数用例，证据记入后续 implementation。
- **预期结果：** 形成分支 A（可靠边界，允许窄重试）或分支 B（单次执行，retry deferred）的明确结论。
- **验证项：** 创建前失败、创建后接线失败、启动后结果丢失分别可区分；副作用计数与资源清理；不得读取 traceback/错误文本作业务分类。
- **状态：** 已完成 2026-10-07；真实 CPython 测试通过，选择批准分支 B。自动启动 retry deferred；见 implementation/02-runtime-and-public-contract.md。
- **合规检查：** [x] 证据检查与测试完成；[x] 验证已执行；[x] tasks 已更新；CONTEXT/FEATURES 随本期交付统一同步，纯门禁测试不单独进入 CHANGELOG。

## Phase 1：Runtime 执行与诊断

### [x] T10：共享执行失败、健康探测与清理

- **负责人：** Runtime 实施者；依赖 T00，按 T02 结论实施。
- **改动内容：** exit125 后一次有界只读探测；执行期 OS/连接故障和清理不确定转稳定 Workspace 异常；取消/HITL 原样传播；可靠边界成立才加 4 次总尝试。
- **代码位置：** `apps/runtime-service/src/runtime_service/workspace/execution.py:execute_in_workspace()/_docker_control()/_cleanup()`；`apps/runtime-service/src/runtime_service/runtime/errors.py:RuntimeWorkspaceError` 与有限错误码。
- **预期结果：** 已启动/未知命令不重发；探测/清理只操作当前已知资源；无宿主执行降级、根目录替换和 Worker 整 Run retry。
- **验证项：** V01-V09；成功路径零额外探测/等待；exit125 用户结果不误当可重试；清理失败不覆盖取消。
- **状态：** 已完成 2026-10-07；真实 Docker 及单次执行/创建取消/健康探测故障检查通过；清理仅操作当前资源，探测逻辑预算与回收耗时分开。见 implementation/02-runtime-and-public-contract.md。
- **合规检查：** [x] 实现完成；[x] 定向验证执行；[x] tasks 更新；服务状态、功能与用户变更在 T31 统一同步。

### [x] T11：Workspace 安全观测与只读投影

- **负责人：** Runtime 实施者；依赖 T10。
- **改动内容：** 错误/重试恢复/清理异常的安全汇总；callback 可信 scope、graph/startup 稳定码；RunDiagnostics v1 增可选 Workspace 列表。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/diagnostics.py:safe_fields()`；`langfuse.py:_RuntimeDiagnosticsCallback/record_diagnostic_event()`；`startup.py:StartupDiagnostics.phase()/finish()`；`query.py:_project()/empty_diagnostics()`。
- **预期结果：** 精确 run/scope 的有限记录，无命令、路径、stderr、凭据；disabled/unavailable 不干扰命令与失败报告。
- **验证项：** V10-V11、D01-D04；旧响应/无 Workspace graph；查询预算、记录限额、truncated；观测回调失败不改变主结果。
- **状态：** 已完成 2026-10-07；Runtime 相关257 passed（含本任务组合），可信scope、20条上限、模型分类分离、factory错误码及查询/慢回调预算通过。当前只生产 attempts=1、retry_wait_ms=0、command_state=unknown，不生成 recovered。
- **合规检查：** [x] 实现完成；[x] 最小验证执行；[x] tasks 更新；CONTEXT/FEATURES/CHANGELOG 随 T31 同步。

### [x] T12：主/子 Agent 通用接入与 Worker 传播

- **负责人：** Runtime 实施者；依赖 T10-T11。
- **改动内容：** 通过现有 backend 共享入口接入，不分别复制 retry；验证官方工具中间件和 task 子图不会吞 WorkspaceError。只改测试发现的实际接线缺口。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py:DockerWorkspaceBackend.aexecute()`、`subagents.py:build_subagents()`；`apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py:DearWorkspaceBackend.aexecute()`；各 `agent.py:middleware()`；Dear `subagents/researcher.py:researcher()`。
- **预期结果：** Showcase 主图/可执行子图、Dear 主图适用同一边界；Dear 只读子图不增加 execute；Reference/Workflow 正常；Workspace 顶层稳定异常不导致 Worker 重调度。
- **验证项：** I01-I04；主图/子图执行次数、HITL approve/reject/resume、取消、并行 Run scope、原生 Worker 终态/重试次数。
- **状态：** 已完成 2026-10-07；隔离 HTTP/API/Worker/Docker Workspace 用例通过：Dear/Showcase主图与Showcase可执行子图失败，counter=once、business_error、retry_count=1仅首次claim；HITL批准/恢复、执行取消、根符号链接拒绝、诊断授权矩阵与基线源码回退后的历史/新Run续接已验。Reference/Workflow、只读子图与控制流定向回归260 passed、3 skipped、8 deselected。
- **合规检查：** [x] 共享入口与测试完成；[x] Phase验证完成；[x] tasks更新；功能状态在T31同步。

## Phase 2：API 契约与前端交接

### [x] T20：公开 Workspace 执行错误投影

- **负责人：** API 实施者；依赖 T01、T10。
- **改动内容：** 精确白名单识别 Worker 类型/稳定 message 或已投影结果；保持字符串/对象形状与幂等；覆盖普通/Protocol/v3、Run/Thread/state/history。
- **代码位置：** `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:project_execution_error()/redact_runtime_private_fields()`；`apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:_redact_sse_frame()`。
- **预期结果：** 已知 Workspace 故障能被安全解释；未知正文仍屏蔽；不改变终态、seq、namespace 和正常工具内容。
- **验证项：** A01-A04；精确/近似/嵌入码输入、类型伪装、重复投影、分片 SSE、safe fallback。
- **状态：** 已完成 2026-10-07；API53 passed/116 subtests，精确来源、幂等与各流错误槽位通过；见 implementation/02-runtime-and-public-contract.md。
- **合规检查：** [x] 实现完成；[x] 最小验证完成；[x] tasks 更新；CONTEXT/FEATURES/CHANGELOG 随 T31 同步。

### [x] T21：诊断 DTO 与权限回归

- **负责人：** API 实施者；依赖 T11。
- **改动内容：** WorkspaceExecution、WorkspaceErrorCode/ExecutionErrorCode 与可选 `workspace_executions=[]`；复用 RunDiagnostics GET、diagnostics-read 和既有 ACL。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py:GraphExecution/StartupPhase/RuntimeDiagnostics`；`application/service.py:get_thread_run_diagnostics()`。
- **预期结果：** Workspace 分类独立于 model_errors；旧 v1 可用；不新增路由、权限操作、数据表或状态服务。
- **验证项：** D01-D04、A03；错误字段、NaN/Infinity/bool、超长/超额、跨项目/未共享/撤权/错 Run，均有真实结果。
- **状态：** 已完成 2026-10-07；五码与可选v1 DTO、严格字段验证、真实SQLite ACL与撤销共享通过；原 diagnostics-read 接口/权限不变。
- **合规检查：** [x] 实现完成；[x] 最小验证完成；[x] tasks 更新；CONTEXT/FEATURES/CHANGELOG 随 T31 同步。

### [x] T22：提供可联调的批准契约与真实样例

- **负责人：** Runtime/API 实施者；依赖 T20-T21。
- **改动内容：** 更新 frontend-handoff 的契约状态，提供未启动耗尽（仅 G1 A）、结果未知、根缺失、重试恢复、取消/HITL、无诊断的样例。
- **位置：** 本项目 `frontend-handoff.md`、后续 implementation/验证记录。
- **预期结果：** 合成 fixture 与真实 run_id/thread_id/事件样例明确区分；前端不依赖尚未实施字段。
- **验证项：** 至少同一 Run 的 live/error、Run GET、state/history、diagnostics 能对照；敏感数据先屏蔽。
- **状态：** 已完成 2026-10-07；[前端交付报告](frontend-report.md)与[完整交接](frontend-handoff.md)已给出五码、通用fallback、可选v1 schema、逐文件任务、F01-F10及真实同Run对照。Langfuse查询明确使用真实callback加合成transport；G1分支B的retry/recovered/not_started明确不适用，不伪造样例。
- **合规检查：** [x] 契约与报告完成；[x] HTTP对照验证完成；[x] tasks更新；最终测试计数和交付状态在T31同步。

### [ ] T23：前端同事实施与门禁

- **负责人：** 用户同事；用户明确排除本轮前端实施，收到 T22 交付后接手。
- **改动内容：** 精确固定 Run 错误文案；现有 RunDiagnostics Workspace 记录；旧 DTO 降级与 run 去重；不自动重发/换工作区。
- **代码位置：** 完整文件清单和验收见 [frontend-handoff.md](frontend-handoff.md)。
- **预期结果：** 一个 Run 一份正确反馈，成功恢复仅诊断提示；取消/HITL/断连不误标 Workspace 故障；历史及身份/项目隔离正确。
- **验证项：** F01-F10；Vitest、lint、typecheck、build；390/1024/1440 三尺寸、浅/深主题截图和关键链路证据。
- **范围状态：** deferred（本轮移交）；前端代码与浏览器验收未执行，不作为非前端开发 Block，也不标已完成。

## Phase 3：Final 与交付

### [x] T30：完整链路、安全、性能与回退

- **负责人：** Runtime/API 实施者；本轮依赖 T10-T22，T23 的浏览器联合验收由同事接手。
- **改动内容：** 在既有 Python 和本机原生 PG/Redis 工具构成的隔离栈执行 [验证矩阵](verification.md)，采用 local backend；按用户当时指示将 Docker 相关验收后延，随后由 T32/T33 补齐。
- **位置：** 本项目 `verification.md` 的 Final 区域；真实样例与证据记录至 implementation。
- **预期结果：** 当前本地范围达到验收条件；不将本地证据表述为 Docker 探测/清理已完成 Final，也不替代同事浏览器验收。
- **验证项：** 真实本地命令副作用计数、非法根终态/Worker 不重调度、工具/HITL/取消控制流、ACL/canary、诊断禁用、重启与源码回退；当时 deferred 的 Docker daemon/容器取消/清理/性能现见 T32/T33。
- **状态：** 已完成 2026-10-07（用户调整后的本地范围）；API全仓355 passed/23 skipped/601 subtests，Runtime非外部扩大回归708 passed/39 skipped/55 deselected，最新执行/诊断59 passed/5 deselected；真实本地工具/重启/回退1 passed、Workspace1 passed，专属进程已回收。历史Docker证据独立保留，不宣称本轮Docker Final或性能达标。细节见 implementation/03-chain-validation.md。
- **合规检查：** [x] 本地验收完成；[x] 真实测试已执行；[x] tasks更新；CONTEXT/FEATURES随T31同步，测试本身不另写CHANGELOG。

### [x] T31：文档收口与功能状态同步

- **负责人：** 实施者；依赖 T30。
- **改动内容：** 真实更新功能状态、前端交接和三服务约束；已批准错误/SSE 标准补充与登记；提出值得沉淀的经验，经用户确认后写入 lessons。
- **位置：** 本项目、`docs/CONTEXT.md`、`docs/FEATURES.md`、适用标准；feat/fix 的用户变更才写 `docs/CHANGELOG.md`。
- **预期结果：** 规划、实施、验收证据一致；未完成/明确 deferred 范围可查。
- **验证项：** docs gate 与 diff gate；逐项核对任务；不因本专项完成把其他 SSE/JWT 草案直接升级 active。
- **状态：** 已完成 2026-10-07（本地范围收口）；当时记录的 Docker deferred 现由 T33 同步为完成，T23 移交同事，G1 分支 B 仍不启用自动 retry；error-envelope 保持 active，SSE/JWT 草案未升级。
- **合规检查：** [x] 文档与状态同步；[x] docs gate/diff gate 已执行；[x] tasks 状态已更新；[x] 未写入未经确认的 lessons。

### [x] T32：恢复 Docker 执行、并行取消与性能验收

- **负责人：** Runtime 实施者；用户本轮授权恢复原后延事项。
- **改动内容：** 复用已有真实容器测试，补并行隔离/重复取消后本轮资源归零断言；单次命令、exit125、不可达探测、超时、挂载/限制与成功路径前后测量。
- **代码位置：** `apps/runtime-service/tests/workspace/test_execution.py`，Dear/Showcase 既有 integration 用例；共享执行器只修复实际发现的问题。
- **预期结果：** Docker 默认链路可用，命令无重发、目录不替换；取消互不影响，工作区保留，CLI/容器回收；给出真实 p50/p95/CPU/进程数，不临时设新 SLO。
- **验证项：** V01、V06-V09、R01-R03、S02；真实 CPython EAGAIN 副作用证据复核。G1 证据不足时不加入自动 retry。
- **状态：** 已完成 2026-10-07；共享Docker4 passed、Dear/Showcase2 passed，改进交替测量/并行取消2 passed；非integration32 passed复核EAGAIN已发生副作用，维持批准G1分支B单次执行。p50/p95/CPU/命令进程如实记录于implementation/04-docker-final.md，不宣称性能提升或生产SLO。
- **合规检查：** [x] 测试补齐；[x] 真实执行/性能/启动证据验证；[x] tasks更新；服务/报告状态与资源关闭随T33同步；本任务test类型不另写CHANGELOG。

### [x] T33：Docker HTTP/Worker 完整链路与关闭交付

- **负责人：** Runtime/API 实施者；依赖 T32。
- **改动内容：** 串行复用 Docker 模式独占 PG/Redis 栈，验证主/子图 Workspace 致命错误/控制流、安全投影/诊断权限、重启与源码回退；补最终证据及前端报告，清理本轮资源后关闭 Docker Desktop。
- **位置：** `apps/runtime-service/tests/services/dearflow_agent/test_tool_error_platform.py`；本专项 implementation、verification、frontend-report 及状态导航。
- **预期结果：** 后端/Docker 后延事项完成；测试只使用本轮独占资源，现有容器不删；Docker Desktop 关闭并确认 engine/后台状态。
- **验证项：** I01-I04、A01-A04、D01-D04、E01-E06 非前端部分、B01-B02；本轮容器/服务归零，Docker关闭、文档/lint/diff门禁。
- **状态：** 已完成 2026-10-07；两条真实 Docker HTTP/API/Worker 链路2 passed，1561.03秒，主/子图 Workspace 停止/不重调度、安全诊断与真实权限、审批/编辑/拒绝/澄清/取消、三角色重启与 HEAD 源码回退续接通过。本轮容器/夹具进程归零，Docker Desktop 已关闭且 engine/后台进程退出；前端报告与当前状态同步，门禁记录见本轮 Final。
- **合规检查：** [x] 完整链路与回退验证；[x] 临时资源回收及 Docker 关闭验证；[x] tasks/服务状态/前端报告更新；[x] 文档/diff门禁与13项任务/Phase一致性检查，结果单独记录于 Final；未写入未经确认的 lessons。

## 状态汇总

| 阶段 | 状态 | 尚缺内容 |
| --- | --- | --- |
| 规划交付 | 已完成 | 无；仅规划文档交付，不代表功能已实现 |
| Phase 0 | 已完成 | G0已收敛，G1选择B；自动启动retry deferred |
| Phase 1 | 已完成 | 无；共享入口、主子图和Worker传播已验 |
| Phase 2 | 非前端已完成 | T23前端实施与浏览器验收由同事接手 |
| Phase 3 | 非前端已完成 | T30/T31本地范围与T32/T33真实Docker链路、性能、回退及资源关闭已完成；T23浏览器联合验收交同事 |

当前授权的13项非前端任务已完成，无Block；唯一未勾选项为移交同事的T23。自动retry在复核真实副作用后仍按批准G1分支B deferred，不属于Docker缺环境的后延任务。

# Agent 通用后台非阻塞任务能力 - 任务拆分

## 本次规划交付

- [x] P01：读取 CONTEXT、三服务规范、相关经验库与跨服务标准，核对现有源码和依赖/部署差异。
- [x] P02：对照 open-swe 的工具、runner、monitor、scheduler、dispatch 与测试，保存工作树证据和关键文件哈希。
- [x] P03：逐条评估同事建议，明确三层职责、通用接入、安全/取消/通知语义与不纳入范围。
- [x] P04：形成完整代码落点、分阶段实施和真实验证要求；前端只生成交接。
- [x] P05：文档完整性、路径/链接、未实现状态与改动范围检查通过（2026-10-09），记录到 verification.md。

## 实施入口

**人工评审已通过。** 2026-10-09，用户明确“我已经评审完成，可以开始实施了，任务推进到只剩下前端的相关事项，除非遇到 block”。本轮授权推进 T01-T08 与 T10 的非前端验证/交接；T09/F01-F12 和依赖前端的联合浏览器验收交给同事。批准范围为本专项 D01-D06；未授权 Git 提交/推送或生产发布。

**当前进度：** `partial`；[B01](engine-handoff.md) 已解除，post45 正式锁/部署断言和 lost-ACK notify/Stop/撤权联合验收完成。T02/T03/T04/T06/T07、T09/F01-F11 已完成；T01/T05/T08 仍需本专项全范围验证和新 Linux 镜像门禁，T10/F12 尚未全栈 Final。新提交默认关闭，现役未部署。AB01-AB03 与 ABF01-ABF03 前后端独立验收已完成。

| 决策 | 状态 | 批准内容/评审证据 |
|---|---|---|
| D01 执行拓扑/管理权限 | 已批准 | 用户，2026-10-09，本会话评审通过；按 plan.md 首发拓扑实施 |
| D02 监控/延迟 | 已批准 | 用户，2026-10-09，本会话评审通过 |
| D03 自动 Run/费用 | 已批准 | 用户，2026-10-09，本会话评审通过 |
| D04 生命周期/Stop/HITL | 已批准 | 用户，2026-10-09，本会话评审通过 |
| D05 容量/日志/保留 | 已批准 | 用户，2026-10-09，本会话评审通过；T01 实测校正 |
| D06 operation/契约/迁移/回退 | 已批准 | 用户，2026-10-09，本会话评审通过 |

## Phase 0：证据门禁与契约冻结

### Task T01：冻结真实执行拓扑和锁定引擎语义

- **改动内容：** 批准后在隔离环境验证 Docker create/start/inspect/logging/cancel、容器不随 Runtime 进程退出、API/Worker 共享目录/daemon；验证 post43 原生稳定 key、enqueue、queued Run、开始前 guard、Stop 固定目标。检查 Dockerfile post20 与锁文件差异，形成唯一正式依赖/镜像清单；当前不改 GraphHarbor。
- **代码位置：** `apps/runtime-service/src/runtime_service/workspace/execution.py::docker_workspace_args()`、`workspace/background.py`、`run_control/service.py::engine_receipt()`；Platform `modules/runtime_gateway/application/service.py::launch_runtime_run()`；`apps/runtime-service/deploy/{Dockerfile,docker-compose.runtime-background.yml}`；真实门禁在 `tests/e2e/test_background_tasks.py` 与 `tests/workspace/test_background_execution.py`，复用既有隔离栈。
- **预期结果：** 冻结一个可以恢复的执行域、bounded log 实现、未知提交恢复规则、guard 时机、标准新增字段及版本/来源/哈希；能力缺口逐项有真实证据。失败时不绕过鉴权、不复用宿主 shell；提出具体修订供评审。
- **验证项：** verification.md 的 I01、I03、I06-I08、R01、S01；仅容器能启动不算完成，不能拿 mock 或当前依赖版本字符串代替正式包冷安装。
- **依赖/预计：** D01-D06 批准；1-2 人天。
- **状态：** [ ] `partial`（2026-10-10）：原 post43/两 Linux controller 拓扑证据保留；正式 post45 接受回执、冷安装、服务锁与 Dockerfile 断言已交付，B01 解除。新 post45 Linux 应用镜像与完整拓扑门禁尚未验，不能仅凭依赖更新勾选本任务。

### Task T02：应用迁移、幂等与租约存储

- **改动内容：** 一张任务+通知表、scope/源 Run/tool_call 唯一约束、事务内并发限额、lease/fence、Stop 固定后台快照字段；资源回执同事务登记。私有数据不包含命令/JWT；日志 TTL 与可重放来源的最小去重回执分开，未知占位不被 TTL 盲删。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/db/migrations/versions/0003_background_tasks.py`（parent=`0002_run_control`）、`background_tasks/{repository,schemas,output}.py`；修改 `run_control/repository.py::request_stop()`，配合既有 `run_control/service.py::_advance_claim()` 及 resources 回执，无第二张队列表。
- **预期结果：** 同工具重放只得到同 task，日志清理后也不重新执行；同 key 异摘要冲突；两个进程不能超额启动，旧 fence 不能提交事实或通知；迁移为空库/现有库可用，回退保留回执。
- **验证项：** U01-U03、U08-U09、I02、I04、R01；真实 PG 并发测试与迁移 round trip，不能只用内存 fake。
- **依赖/预计：** T01；1 人天。
- **状态：** [x] `done`（2026-10-09）：真实 PG 验证覆盖两进程20提交、Thread/project/host容量、unknown占位、旧fence、分页、迁移往返和1万历史；最新分组及新增Docker故障结果见 verification.md 的 T02 Phase。
- **完成记录：** [持久执行与清理](implementation/02-runtime-background-tasks.md)；合规检查见本页底部 Task Completion Cards。

## Phase 1：后台执行与受管清理

### Task T03：Docker runner、短启动回执和有界日志

- **改动内容：** 复用安全 Docker 参数、固定名称/labels/ID、受控 runner、独立期限、有界 logging/head-tail、私有日志路径/原子落盘、inspect 未知结果；旧 execute/Terminal 不改语义。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/workspace/{background,background_runner}.py`、`background_tasks/service.py::{start_task,_observe}`；修改 `workspace/execution.py::docker_workspace_args()` 的参数化调用。runner 从 Runtime 包资源读取后以受控源码参数装入 Python 容器，避免 daemon 解析 Runtime 容器内路径；无需改 Workspace 镜像。
- **预期结果：** 90 秒命令的工具在暖机验证中约 2 秒内返回真实已启动 handle；命令失败/超时/未知准确区分；10 MiB 日志持续排空，内存、Docker logging、私有文件和响应均有硬上限；收到 Ctrl/Stop 的已确认清理不丢结果。
- **验证项：** U04-U07、I01、I03、I05、L01-L03；真实 Linux Docker 包含 runner 资源/进程组测试。现有 `apps/runtime-service/tests/workspace/test_execution.py`、`tests/services/dearflow_agent/test_execution.py` 与 Terminal 相关测试回归。
- **依赖/预计：** T02；1.5-2 人天。
- **状态：** [x] `done`（2026-10-09）：真实Docker退出码/期限/10MiB输出、OOM/外部删除/伪结果与环境隔离、create/start丢ACK及两Linux controller通过；暖启动ACK实测0.91秒，foreground40项回归通过。并发输出增量结果单列verification，不替代原边界证据。
- **完成记录：** [持久执行与清理](implementation/02-runtime-background-tasks.md)。

### Task T04：无模型对账、取消与会话 Stop

- **改动内容：** 挂受管 lifespan，按 host/到期项对账，确认期限/源 Run 终态/容器状态；固定 task/event Stop 快照、抑制通知、资源清理与旧 Stop DTO 加法摘要；日志总额/TTL 清理及已有观测方式记录安全计数，清理不冒称整个 Thread 或其他 PTY 已停。
- **代码位置：** `apps/runtime-service/src/runtime_service/background_tasks/service.py::{reconcile_due,source_failed,background_tasks_lifespan,cancel_task,expire_logs}`；`webapp.py::lifespan()`；`run_control/{repository,report}.py`；Platform `modules/runtime_gateway/application/run_control.py::BackgroundStopSummary`。
- **预期结果：** 两副本/重启恢复不重复运行；自然 success 允许任务继续；真正 source error/timeout/用户停止收敛任务；仅 HITL interrupted 不误杀。没有活动 LLM Run 时 Stop 仍能停止已有后台任务；不能确认返回 unconfirmed。
- **验证项：** U08-U10、I04-I05、I08-I09、E04-E07；已有 `apps/runtime-service/tests/services/test_run_control.py`、`apps/platform-api/tests/test_run_control.py`、inbox PostgreSQL 测试必须回归。
- **依赖/预计：** T03；1.5-2 人天。
- **状态：** [x] `done`（2026-10-09）：两独立进程重启、空闲LLM会话Stop、源error/原生timeout/cancel和关闭开关drain通过；新迁移代码退到0002后旧源码普通Run成功并保留3份回执；真实SDK lifecycle分辨HITL/cancel_requested/rollback。K轮HITL保留/显式恢复、两项固定Stop清理/后续新task隔离整条通过；未知完成Run派发的清理闭环由T05/B01承接。
- **完成记录：** [持久执行与清理](implementation/02-runtime-background-tasks.md)。

## Phase 2：受管续接与 Agent 复用

### Task T05：平台完成交付、开始前授权与失响应对账

- **改动内容：** 原子终态+单次 outbox、HMAC delivery/authorization、固定 event/key/body、平台源请求绑定、当前 actor/模型/tool/Thread 重授权、原生 enqueue。完成 guard 早于模型/MCP 构造并检查 Stop tombstone；已接受回执对账和新执行权限分开。
- **代码位置：** Runtime `background_tasks/{delivery,authorization}.py`、`runtime/background_completion.py`；Platform `modules/runtime_gateway/application/background_completion.py::{deliver,authorize_completion}`、`modules/runtime_catalog/presentation/http.py`；复用 `RuntimeGatewayService.launch_runtime_run()` 与 `RunRequestsRepository.for_run()`。
- **预期结果：** 一个 event 至多一个接受的完成 Run，丢响应/双进程/迟到更新复用原回执；活动 Run 不被 interrupt；HITL 不被自动批准；Stop 后迟到 Run 的 guard 不进入模型/工具；原始日志/身份/命令不被当系统授权。
- **验证项：** U09-U12、I06-I10、E03-E08、S02-S04；现有 `apps/platform-api/tests/{test_run_requests,test_scheduled_tasks,test_runtime_delegation_contract}.py` 与 Runtime scheduled/access policy 测试回归。
- **依赖/预计：** T04；1.5-2 人天。
- **状态：** [ ] `partial`（2026-10-10）：原 HMAC/guard/Usage 证据保留；正式 post45 最终 bytes 发送前落盘、reconcile-only、固定 GET 与 Stop suppressed 已接入，notify/Stop/撤权各独立联合验收通过，[B01](engine-handoff.md) 解除。本专项完整故障/竞态矩阵仍待 T08/T10，未以三场景替代全部门禁。
- **实施记录：** [平台续接与公开契约](implementation/03-platform-completion-and-contract.md)及 [B01 正式交付](engine-handoff.md)；Final 验证范围分别记录。

### Task T06：通用工具、两组合根和未接入图隔离

- **改动内容：** `build_background_tools(binding)` 三工具、声明/allowlist/HITL、execute deny 传导、probe/maintenance 无副作用；接 Showcase 与 DearFlow 根图；完成 Run 禁止后台新提交；不扩展只读子图和业务媒体 provider。
- **代码位置：** `apps/runtime-service/src/runtime_service/tools/background.py::build_background_tools()`、`runtime/{capabilities,access_policy}.py`；两个组合根 `services/{dearflow_agent,demo/showcase_demo}/agent.py` 和 Dear `capabilities.py`；`graphs/{showcase_demo,dearflow_agent}.py`。现有Backend/只读子图闭包复用，无业务prompt或媒体改动。
- **预期结果：** 两图复用同一实现，目录/schema/exports/package resources 完整；Reference/Workflow/LocalShell 返回不支持；工具 denial/拒绝审批后零启动；capability 不产生权限；新业务 Agent 按文档明确的接入点可适配。
- **验证项：** U01、U10-U12、E01-E02、E06-E09；新增 `apps/runtime-service/tests/background/test_tools_and_assembly.py`，回归现有 graph schema/工具策略/审批恢复/子图只读测试；wheel 冷安装收集测试验证无遗漏资源。
- **依赖/预计：** T05；0.5-1 人天。
- **状态：** [x] `done`（2026-10-09）：两组合根真实受管模型90秒命令/独立完成Run及Usage通过；deny/probe/maintenance/完成Run新启动拒绝与审批组合通过。新Agent四接入点已交付，首期仅根Agent。
- **完成记录：** [持久执行与清理](implementation/02-runtime-background-tasks.md)；接入说明在 Runtime standards/background-task-integration.md。

## Phase 3：公开接口、部署门禁与交接

### Task T07：查询/日志/取消网关和审计

- **改动内容：** 四个 GET/POST 路由、三 operation、当前 ACL、task 归属/DTO/分页/日志上限、取消幂等回执；列表全scope未结标志与最近接受的完成Run投影；私有 grant/handle/lease 递归去除和公开输入拒绝；精确审计 action/error 码。
- **代码位置：** Runtime `http/background_tasks.py`、`runtime/auth.py`、`auth/platform.py`；Platform `modules/runtime_gateway/{application/background_tasks.py,presentation/http.py,application/ports.py}`、`adapters/langgraph/{runtime_gateway_upstream,sdk_client}.py`、`core/{security/tokens,runtime_contract}.py`、`modules/audit/http_resolution.py`、`entrypoints/http/middleware/auth_context.py`。
- **预期结果：** 当前有权用户通过平台读取正确 Task；元数据/日志/取消委托互不替代，不能访问原生资源、模型或其他任务 scope；502/504 不伪装资源停止/权限撤销；命令、控制 handle 和管理密钥不进入错误/审计。
- **验证项：** U10-U12、I09-I10、S01-S05；新增 `apps/platform-api/tests/test_background_tasks.py`、Runtime `tests/background/test_http.py`；更新既有 delegation fixtures，按 operation 名称集合断言，不写固定索引/枚举数量。
- **依赖/预计：** T06；1 人天。
- **状态：** [x] `done`（2026-10-09）：四入口/no-store/严格DTO/三operation/私有注入拒绝/审计定向通过；真实共享read、cancel拒绝、跨project、撤权和模型开始前拒绝已验。完整delegation 21项/63subtests通过；既有非UUID fixture失败独立记录。
- **完成记录：** [平台续接与公开契约](implementation/03-platform-completion-and-contract.md)。

### Task T08：真实发布构建、回退、后端 Final 和契约冻结

- **改动内容：** 在 T01 批准的拓扑接迁移/管理连接/共享挂载/私有日志保留/ready 检查，正式包与镜像冷安装；执行完整后端验证及回退；记录前端可消费的实际 DTO/错误/关联 Run；交付运维与新 Agent 接入说明；同步批准规范/FEATURES/CHANGELOG/CONTEXT。
- **代码位置：** `apps/runtime-service/deploy/{Dockerfile,docker-compose.runtime-background.yml}`；`docs/runbooks/runtime-background-tasks.md`、Runtime接入规范；专项 `verification.md/frontend-handoff.md/implementation/` 与服务/跨服务标准。其他拓扑默认关闭，不改全局栈脚本。
- **预期结果：** 后端所有门禁有真实证据；报告仅判定后端 done，整项目等待前端和联合验收；未验拓扑默认关闭。依赖发布或生产部署不因测试通过自动授权。
- **验证项：** verification.md 中后端 U/I/E/L/S/R 全覆盖；lint/格式/定向+Final 回归；无新后台资源遗留、旧 foreground/cron/Stop/inbox/Usage 关键链路通过。
- **依赖/预计：** T07；1-2 人天，包含前述验证总量，避免重复计时。
- **状态：** [ ] `partial`：原镜像/回退、K轮HITL/固定Stop及质量/文档/资源 Phase 保留；B01 已解除，正式 post45 锁/部署断言与三条接受回执联合链路完成。本专项完整故障/竞态矩阵、post45 Linux 应用镜像及后端 Final 尚未执行；现役未启用，不能把引擎专项 Final 算作本任务全范围 Final。

### Task T09：前端同事实施 F01-F12

- **改动内容：** 消费冻结后的 capability/Task/Output/Stop DTO；Workspace 内列表/文本日志/取消；发现服务器创建的 Run 并沿 SDK 订阅；状态/作用域/权限/隐藏态处理。前端不派发完成 Run，不接管后台调度。
- **代码位置：** `apps/platform-web/src/services/threads/background-tasks.service.ts`、`src/modules/chat/background-tasks/types.ts`、`src/modules/chat/composables/useBackgroundTasks.ts`、`src/components/workspace/BackgroundTasksPanel.vue`、`BackgroundTaskItem.vue`、`BackgroundTaskLogViewer.vue`；接入现有 WorkspacePanel/ChatSession/useThreadStopControl，细则见 frontend-handoff.md。
- **预期结果：** 离开/刷新/关闭页面不影响后台；切回能看到真实任务和完成 Run；unknown/accepted/interrupted 正确区分，服务端取消确认后才显示已取消；无第二套 Run 状态机。
- **验证项：** F01-F11 验收完成，Vitest (131 套件, 710 单测全通过)、vue-tsc (0 错误)、ESLint (0 错误)、build (打包成功)；Playwright + Chromium E2E 全链路 4/4 满分通过（含真实模型调用、任务流转与日志 ANSI 清洗/截断、取消确认、Stop 控制台保持可达与 390×844、768×1024、1440×900 三档分辨率截图留痕）。
- **依赖/预计：** T07-T08 契约冻结；已完成。
- **状态：** [x] `done` (2026-10-10)：F01-F11 全部完成并在隔离 Worktree 环境中全链路验证闭环。F12（B01 引擎解除后的全量联合终态）由 T10 收口。

### Task T10：全范围联合 Final

- **改动内容：** 逐项检查所有未完成任务及 D01-D06 批准范围，完成真实三服务/模型/浏览器全链路；保留阶段与 Final 独立证据，明确部署范围与回退清理。提出值得沉淀的经验，用户确认后才入 lessons；相关标准只有本专项确实覆盖并完成的内容才更新，原 JWT/SSE 整体状态不被顺带毕业。
- **代码位置：** `verification.md`、`tasks.md`、`README.md`、`frontend-handoff.md`；批准后按 `verify-change` 记录四态。必要测试扩展原有后台 E2E 脚本，不写第二个启动管理器。
- **预期结果：** 后端/前端/联合验收分别有状态；全部范围完成才整项目 done；缺真实条件说明具体条件、已尝试替代和接续步骤，不能用一次 Phase passed 提前收工。
- **验证项：** 全部冻结验收项与 E10；记录测试命令、版本/产物/环境、数量、故障注入、日志/截图、安全脱敏和退出资源盘点。
- **依赖/预计：** T08-T09；联合 1-2 人天。
- **状态：** [ ] `partial`：B01 已解除，非前端、F01-F11与ABF01-ABF03独立证据保留；全范围联合 Final/F12 尚未执行。

## 非 Docker 兼容：A/B 独立实施（2026-10-10）

用户已批准 A 主方案+B 兜底，并明确在指定 99f7 Worktree 实施；随后明确前端只写交接，完成其余非前端开发项。引擎团队按 GraphHarbor 的 `20261010-run-acceptance-receipts` 专项开发；A/B 本身不修改引擎或接入其 U01-U03，不重复申请架构审批。

### Task AB01：共享能力门禁

- **改动内容：** 统一查询/新启动能力判断；公共 middleware 过滤模型可见工具，保留 ToolNode 内部启动入口供旧 checkpoint 重放。无任务存储配置不提供查询工具/任务 Tab；有存储时关闭新启动仍可查询、日志、取消和对账。
- **代码位置：** `apps/runtime-service/src/runtime_service/background_tasks/capabilities.py::{query_enabled,start_enabled}`；`middlewares/runtime_config.py::RuntimeConfigMiddleware.awrap_model_call()`；`tools/background.py::build_background_tools()`；`services/dearflow_agent/capabilities.py::graph_capabilities()`。Platform/Web 复用既有 capability 消费。
- **预期结果：** Showcase/DearFlow 的模型工具与能力一致；probe 零资源 IO、completion 无启动工具；关闭启动后旧 checkpoint 仍能取原回执。
- **验证项：** Runtime 两组合根/工具/服务/middleware/probe 合计 91 项，Platform 2 项，既有 Web 11 项通过；命令与 mock 边界见 [Phase A/B](verification.md#phase-ab-非-docker-兼容独立验收2026-10-10)。
- **状态：** [x] `done`（2026-10-10）；见 [实施记录](implementation/05-local-background-compatibility.md)。
- **合规检查：** 代码、直接验证、任务进度已完成；CONTEXT/FEATURES/CHANGELOG 已在 AB03 统一收口。

### Task AB02：精确未启动兜底

- **改动内容：** 按可信 key 先查原回执，使用记录原 host 核对原摘要；同请求返回原事实（含 unknown），异请求保持冲突。数据库确认无记录且源未 Stop 后，预期环境限制才抛专门的未启动异常，由现有工具错误 middleware 返回恢复建议。
- **代码位置：** `apps/runtime-service/src/runtime_service/background_tasks/service.py::start_task()`；`background_tasks/repository.py::{read_submission,_assert_source_active,reserve_task}`；`runtime/errors.py::BackgroundTaskNotStarted`；`tools/errors.py::tool_error_content()`。
- **预期结果：** 短任务可用普通 execute（默认30秒/最大60秒），长任务提示拆分或支持环境；未知回执不重跑。存储失败、权限、Stop、取消、程序错误及已登记后故障保持原语义，Docker 故障不切宿主 shell。
- **验证项：** 真实 PG 12 项通过，覆盖原回执/异摘要/固定 Stop/两进程容量/旧 fence；两组合根 B 后模型继续及同码普通异常 Fatal 包含于 18 项；服务边界包含于 73 项。记录见 [Phase A/B](verification.md#phase-ab-非-docker-兼容独立验收2026-10-10)。
- **状态：** [x] `done`（2026-10-10）；见 [实施记录](implementation/05-local-background-compatibility.md)。
- **合规检查：** 代码、直接验证、任务进度已完成；CONTEXT/FEATURES/CHANGELOG 已在 AB03 统一收口。

### Task AB03：非前端独立验收与前端交接

- **改动内容：** 使用指定 Worktree 独立 PG/依赖/本地栈完成两组合根真实 local→Platform API→Worker→HITL→execute→success；同步实施/Phase/能力标准/功能/变更/上下文，并按用户最新授权交接前端。
- **代码位置：** 本专项 `local-compatibility-frontend-handoff.md` 与 `implementation/05-local-background-compatibility.md`、`verification.md`；`apps/runtime-service/docs/standards/background-task-integration.md`；`docs/runbooks/runtime-background-tasks.md`；`docs/{FEATURES,CHANGELOG,CONTEXT}.md`。浏览器草稿 `apps/platform-web/e2e/background-compatibility.draft.ts` 不进入默认 Playwright 收集。
- **预期结果：** 非前端 A/B 范围有真实模型、显式审批、普通 execute、Run success 和查询接口证据；前端拿到明确需求/代码入口/联调条件。A/B 后端独立 done，不覆盖引擎 B01、原专项 Final 或浏览器完成状态。
- **验证项：** 91 项 Runtime、12 项真实 PG、2 项 Platform 与既有 Web 11 项通过；两图使用 `deepseek-v4-flash`，均一次审批、真实输出 `AB_LOCAL_OK`/退出码0、Run success、query=true/start=false、后台列表为空。`qwen-plus` 空工具 ID 引起重复执行有基线诊断，不归因于前端。质量/文档/资源盘点见 verification。
- **状态：** [x] `done`（2026-10-10），完成用户指定的非前端范围与交接；浏览器由 ABF03 接续。
- **合规检查：** 非前端代码/直接验证/本任务文档与全局状态已同步；PG 临时 schema 已清理，本轮 API 测试项目已软删除；专属栈保留供并行工作和前端联调。

### 前端接续任务（已实施并完成，2026-10-10）

- [x] **ABF01：** 核对 query/start 独立能力，query=true/start=false 时保留任务 Tab、已有任务与授权取消；query=false 或缺省时隐藏并停止探针/取消在途请求，切会话不残留旧数据。在 `useBackgroundTasks.ts` 接入 `capabilities` 门禁与响应式重置；在 `ChatSession.vue` 注入线程 capabilities；在 `useBackgroundTasks.spec.ts` 覆盖 7 项能力矩阵/缺省/切会话/卸载单测并通过。
- [x] **ABF02：** 接入 `use_execute_for_short_task` 的中文恢复提示（"短任务可改用前台执行，最长60秒"）及测试；确认 `outcome=not_started` 只在工具卡片局部展示，unknown 不出现重新执行建议，前端不自动调用 execute/批准/续接。在 `transcript.ts` 与 `transcript.test.ts` 落地并通过 18 项单测。
- [x] **ABF03：** 完成真实 local 浏览器链路和既有 Docker/任务界面回归；交接草稿修正并升级为 `apps/platform-web/e2e/background-compatibility.spec.ts` 纳入 Playwright。显式选择已验证的 `deepseek-v4-flash` 模型，真实前台执行 `printf AB_LOCAL_OK`、HITL 审批成功、Run `success`、能力判定正确、任务 Tab 空态呈现，1/1 passed（58.4s）。`pnpm check`（lint/typecheck/build）全绿。

详细需求、验收、环境与可转发话术见 [A/B 前端交接](local-compatibility-frontend-handoff.md)。既有 F01-F11 不重做；B01已解除，F12仍由T10收口。

## 进度追踪

- [x] 规划交付校验完成（P01-P05，2026-10-09）。
- [x] 人工评审批准 D01-D06（用户，2026-10-09，本会话）。
- [ ] Phase 0 完成且引擎契约冻结（T01/B01；T02已完成）。
- [x] Phase 1 核心执行与受管资源清理完成（T03-T04；未知通知Run清理由T05/B01承接）。
- [ ] Phase 2 完成（T06已完成；T05/B01）。
- [x] 前端可消费的v1查询/日志/取消/能力/Stop加法契约交接已形成。
- [ ] 后端 Final 完成并冻结前端契约。
- [x] 前端 F01-F11 完成（B01已解除，F12待T10全栈联合交付）。
- [x] A/B 非前端 AB01-AB03 与前端增量 ABF01-ABF03 全部开发与验证完成（2026-10-10）。
- [ ] 全栈联合 Final 完成。

后端阶段实施调用 implement-feature；后端与全栈验证分别留实测范围，整项目四态按最终批准范围判定。本轮推进非前端范围，前端和依赖前端的联合验收保留待接续。

## Task Completion Cards 与合规检查

T02/T03/T04/T06/T07 的改动、真实代码位置、预期和对应 Phase 证据见各Task四段及上述implementation。共享合规项不复制五份清单：

- [x] 五个Task代码实现完成；未通过范围未被勾选。
- [x] 直接验证已执行，真实PG/Docker/独立API/Worker/模型结果写入verification Phase；同名测试后续增量另列。
- [x] tasks.md按done/blocked/同事接续分别更新；implementation不是进度来源。
- [x] CONTEXT.md同步受影响服务与B01状态。
- [x] FEATURES.md按三层能力/前端待接续同步。
- [x] CHANGELOG.md的Unreleased已记录默认关闭、受管后台与清理摘要。
- [x] 收尾经验提案已由用户确认；四条经验写入docs/lessons/runtime-service.md并更新索引（2026-10-09）。

T01/T05/T08仍为未完成Card：B01已由引擎专项正式交付解除，本专项剩余矩阵/镜像/后端Final另验，不能凭A/B或接受回执三场景勾全范围完成。T09/F01-F11与AB01-AB03/ABF01-ABF03已完成；T10/F12尚未全栈Final。

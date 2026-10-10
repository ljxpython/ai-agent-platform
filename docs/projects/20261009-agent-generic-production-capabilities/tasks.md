# Agent 通用后台非阻塞任务能力 - 任务拆分

## 本次规划交付

- [x] P01：读取 CONTEXT、三服务规范、相关经验库与跨服务标准，核对现有源码和依赖/部署差异。
- [x] P02：对照 open-swe 的工具、runner、monitor、scheduler、dispatch 与测试，保存工作树证据和关键文件哈希。
- [x] P03：逐条评估同事建议，明确三层职责、通用接入、安全/取消/通知语义与不纳入范围。
- [x] P04：形成完整代码落点、分阶段实施和真实验证要求；前端只生成交接。
- [x] P05：文档完整性、路径/链接、未实现状态与改动范围检查通过（2026-10-09），记录到 verification.md。

## 实施入口

**人工评审已通过。** 2026-10-09，用户明确“我已经评审完成，可以开始实施了，任务推进到只剩下前端的相关事项，除非遇到 block”。本轮授权推进 T01-T08 与 T10 的非前端验证/交接；T09/F01-F12 和依赖前端的联合浏览器验收交给同事。批准范围为本专项 D01-D06；未授权 Git 提交/推送或生产发布。

**当前进度：** T02/T03/T04/T06/T07 已实现并取得阶段证据；最新发布镜像/旧源码回退、HITL通知与固定Stop后新任务追加链路已通过，证据矩阵和资源收口已记录。T01/T05/T08 的完整故障窗口及后端Final受 [B01](engine-handoff.md) 阻塞；新提交默认关闭。T09/F01-F12 待前端同事；T10 联合 Final 在B01解除及前端交付后接续。

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
- **状态：** [ ] `blocked`（2026-10-09）：正式双包 post43/冷构建、两 Linux controller 与原生 enqueue/固定Stop已实测；只读 key 回查缺失，不能冻结“所有 ACK 窗口可恢复”的引擎语义。所需产物与复验清单见 engine-handoff.md。

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
- **状态：** [ ] `blocked`（2026-10-09）：代码、HMAC/guard/撤权、正常接受、lost-ACK后Worker guard回填及独立Usage已验。post43无只读key回查，Worker未进入guard时run_id可能未知；保持unknown/inflight、禁止二次POST，不能宣称通知/Stop完整闭环。见 [B01接续](engine-handoff.md)。
- **实施记录：** [平台续接与公开契约](implementation/03-platform-completion-and-contract.md)；本状态不能被正常ACK链路通过覆盖。

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
- **状态：** [ ] `blocked`：部署/回退与非前端契约已实施，最终镜像、旧源码回退、K轮HITL/固定Stop及质量/文档/资源收口已完成Phase验证；完整故障/竞态矩阵及后端Final必须等T01/T05的B01解除。现役未启用，生产发布未授权。未完成证据逐项见verification覆盖矩阵，不能把Phase通过算Final。

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
- **状态：** [ ] 待 B01 解除后全栈联合 Final；非前端证据与前端 F01-F11 证据已分别收口。

## 进度追踪

- [x] 规划交付校验完成（P01-P05，2026-10-09）。
- [x] 人工评审批准 D01-D06（用户，2026-10-09，本会话）。
- [ ] Phase 0 完成且引擎契约冻结（T01/B01；T02已完成）。
- [x] Phase 1 核心执行与受管资源清理完成（T03-T04；未知通知Run清理由T05/B01承接）。
- [ ] Phase 2 完成（T06已完成；T05/B01）。
- [x] 前端可消费的v1查询/日志/取消/能力/Stop加法契约交接已形成。
- [ ] 后端 Final 完成并冻结前端契约。
- [x] 前端 F01-F11 完成（F12 待 B01 解除后全栈联合交付）。
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

T01/T05/T08为未完成Card：代码与已执行证据可评审，B01缺正式只读契约/发行产物，不能勾“必要验证完成”或生成后端Final。T09不改Web代码；T10不把前端缺口和后端B01合并成已完成。

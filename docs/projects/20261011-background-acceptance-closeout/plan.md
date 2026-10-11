# 整体方案

## 1. 结论与目标

采用“合并已有实现 → 新 Worktree 冻结基线 → 补缺口和验证 → 前端 F12 联合收口”。GraphHarbor、平台 U01–U03、后台 UI 与 A/B 主体已经完成，不重写。新业务代码只限合并遗漏、实际失败根因和必要迁移汇合；主要新增内容是测试断言、最终镜像证据和规范收尾。

用户已确认合并完成并批准实施。唯一实施目录为 `~/.codex/worktrees/b01-closeout/ai-agent-platform`，基线 `2b94585b`；本专项延续原已批准安全语义，不扩大权限行为。当前任务状态以 tasks 为准。

成功标准：丢失创建 ACK 且 Worker 尚未运行时，可以从固定只读回执找回同一 Run；Stop/撤权发生在完成 Run 开始前时，完成模型调用为 0；unknown 始终保留不确定性；正常通知只产生一个完成 Run，并正确进入前端既有消息流。

实施中新增的必要修补：Platform `20261011_0009` 保留 SQLite 完成回执身份并对齐模型类型；本地启动移除强制开启和共享执行 host，登记 ID 与所属后台日志固定传给 API/Worker。具体原因和证据见 [迁移与本地执行域](implementation/03-schema-and-local-stack-isolation.md)。

## 2. 三层分工与代码清单

下列路径均相对**主分支合并后的新 Worktree 根**。标为“保留/复验”的内容在 99f7 已有实现，禁止按清单重新造一套。

### 2.1 Platform API 后端

| 工作 | 文件与符号 | 补充方式与验收 |
|---|---|---|
| 最终发送事实与幂等 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py::RuntimeGatewayService.launch_runtime_run()` | 保留 U01；在模型、Context、completion marker、callback origin 等最终注入完成后只序列化一次，先提交最终 bytes/key/digest/binding，再发网络；原业务摘要与引擎摘要分开 |
| 持久字段与原 Run 绑定 | `apps/platform-api/src/platform_api/modules/runtime_gateway/infra/sqlalchemy/models.py::RunRequestRecord`；同目录 `repository.py::{StoredRunRequest,RunRequestsRepository.create,bind_acceptance,mark}` | 保留六个 `upstream_*` 字段与 origin_ref；原 run_id 不可被不同 run_id 覆盖，原 unknown 请求不重新生成传输事实 |
| 字节 HTTP adapter | `apps/platform-api/src/platform_api/adapters/langgraph/runs_sdk_adapter.py::LangGraphRunsSdkAdapter.{acceptance_body,acceptance}`；`runtime_gateway_upstream.py::{create_run_with_acceptance,get_run_acceptance}`；`runtime_client.py::LangGraphRuntimeClient.request_json()`；`modules/runtime_gateway/application/ports.py::RuntimeGatewayUpstreamProtocol` | 保留 POST/GET acceptance 扩展与 raw bytes；补拦截 transport 的测试，证明 method/path/header/body 完全一致；普通 Run/resume/cron 仍走既有路径 |
| 纯回查和拒绝分类 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/background_completion.py::{deliver,reconcile_acceptance,reconcile_legacy,save_receipt}`；`application/run_acceptance.py::{grant_for,receipt_headers,validate_receipt}` | 保留 U03；GET 分支在当前模型/写授权装配之前返回；仅经过校验的持久否定能 rejected，普通 4xx/5xx、超时、无记录与过期仍 unknown |
| 固定只读授权 | `apps/platform-api/src/platform_api/core/security/tokens.py::create_runtime_delegation_token()` 与 `apps/platform-api/src/platform_api/core/security/run_acceptance.py` | 保留 U02；原可信快照签短 TTL，只能读原 Thread/key/digest/scope/credential 回执；浏览器入口依旧核对当前 ACL，不公开此委托 |
| 加法迁移汇合 | `apps/platform-api/migrations/versions/20261010_0007_run_acceptance.py` 与已有 `20261009_0007_run_completion.py`；拟 `20261011_0008_merge_completion_acceptance.py` | 必要时新增 merge revision；不重编号、不改旧迁移、不删回执；空库与两种旧 head 均升级到唯一最终 head |
| 测试增量 | `apps/platform-api/tests/{test_run_acceptance,test_run_requests,test_background_tasks,test_runtime_gateway_sdk_adapters,test_runtime_delegation,test_run_completion}.py`；`tests/integration/test_run_acceptance_migration.py` | 用现有用例补缺失边界和合并共存断言；不新增公共 acceptance 路由或用户手工重投功能 |

### 2.2 Runtime Service / runtime-server

这里的 runtime-server 指平台的 `apps/runtime-service`（Runtime API+Worker）；GraphHarbor 引擎包已交付，不把平台治理逻辑移入引擎。

| 工作 | 文件与符号 | 补充方式与验收 |
|---|---|---|
| 固定回执认证 | `apps/runtime-service/src/runtime_service/runtime/auth.py::{VerifiedDelegation,_parse_scope,verify_delegation_claims,_parse_run_acceptance}`；`auth/platform.py::{authenticate,deny_image_scope_on_server_resources}` | 保留 read grant；错目标/credential/digest/过期 JWT 拒绝，原公开 read/执行权限仍当前授权；read grant 不可用于 Run/state/model/取消 |
| 不确定交付先对账 | `apps/runtime-service/src/runtime_service/background_tasks/delivery.py::deliver_completion()`；`service.py` 的观察和对账分支 | 保留原 event；unknown/dispatching/Stop inflight 优先 reconcile-only，关闭开关、TTL/尝试耗尽不掩盖未知接受；明确未接受的新交付才受普通预算控制 |
| 迟到接受与 Stop | `apps/runtime-service/src/runtime_service/background_tasks/repository.py::{finish_delivery,delivery_intent,bind_completion_run,completion_allowed,confirm_delivery_cancel,list_tasks}`；`authorization.py::{authorize_completion_cleanup,is_completion_cleanup}` | 原 run_id fence、lease CAS 与 suppressed 不被迟到 accepted 覆盖；找到原 Run 后走独立精确取消链路，native 回执确认前 cleanup 保持 unconfirmed；补 `list_tasks()` 最新自动接续候选过滤为accepted且未抑制，Task原run_id保留 |
| 开始前 guard | `apps/runtime-service/src/runtime_service/runtime/background_completion.py::{verify_completion_marker,background_completion_execution}` | 当前执行权限及 Stop tombstone 在模型、MCP、Workspace 准备前检查；完成 Run 不装配后台新启动；已发出的模型请求不能声称可撤回 |
| A/B 与较新能力共存 | `apps/runtime-service/src/runtime_service/background_tasks/capabilities.py`；`middlewares/runtime_config.py`；`tools/{background,errors}.py`；`services/{dearflow_agent,demo/showcase_demo}/agent.py`；`webapp.py::lifespan()` | 保留模型能力过滤、旧 checkpoint 内部回执入口和精确 not_started；与 Token/loop/文档读取/终态 projector 共存；probe/maintenance/只读子图零后台启动 |
| 应用迁移汇合 | `apps/runtime-service/src/runtime_service/db/migrations/versions/{0003_background_tasks,0003_token_budget}.py`；拟 `0004_merge_background_token_budget.py` | 唯一应用 head，同时包含 Usage/Stop/Token/后台表；引擎 head 独立由 post45 提供 |
| 依赖与最终镜像 | `apps/runtime-service/{pyproject.toml,uv.lock}`；`deploy/{Dockerfile,Dockerfile.agent-workspace,docker-compose.runtime-background.yml}`；现有 Compose migrate/API/Worker 配置 | 合并保留 post45 正式源与较新依赖；Runtime API/Worker 同镜像 digest；冷构建和 Linux 两进程验证，不回退 post20 Dockerfile或共享其他 Worktree 安装目录 |
| 测试增量 | `apps/runtime-service/tests/background/{test_service,test_repository,test_completion,test_compatibility,test_http}.py`；`tests/e2e/test_background_tasks.py`；`tests/runtime/{test_auth,test_platform_auth}.py` | 扩展现有 fixture/故障挂点和证据，所有资源属于新环境；必要时补测试 fixture 的 Worktree 地址接线，不另写启动管理器 |

### 2.3 前端

需要前端接续验收，**不需要新接受回执页面、引擎 token 或原始 ledger 接口**。已有 TaskV1、TaskListV1 与 Stop DTO 能表达本次状态。

前端同事核对 `apps/platform-web/src/modules/chat/background-tasks/types.ts`、`composables/useBackgroundTasks.ts`、`composables/useChatSession.ts`、`components/ChatSession.vue`、`src/components/workspace/{BackgroundTasksPanel,BackgroundTaskItem}.vue`、`transcript.ts`，并补必要单测/E2E。

已查到的准确补丁为：BackgroundTaskItem接受文案改“续接已接受”、unknown交付单独提示；checkDiscoveredRuns只转交accepted候选；acceptDiscoveredRun/待转交队列在Stop、真实HITL和异步scope/busy变化时正确避让/清理。合并结果已修正则仅复验；其余UI没有必要新增。详见 [frontend-handoff.md](frontend-handoff.md)，Codex不修改Web业务代码和前端测试。

## 3. 协议和状态不变量

平台首次派发：终态业务 event 固定 → RunRequests 预留 → 最终传输事实提交 → `POST /threads/{thread_id}/runs/acceptance`。后台 ACK 丢失后的恢复：固定 `GET` → 校验回执 → 保存同一 run_id → Runtime 对账；不再调用 launch、生成模型连接或重发 POST。

请求同时绑定 `Idempotency-Key` 与 `GraphHarbor-Request-Digest: sha256:<hex>`，摘要覆盖最终 UTF-8 JSON 原始字节。业务 `background:<event_id>` 与实际上游 `platform:<hash>` 不能混用；token 刷新、模型默认项变化、进程重启不改变已经持久化的 bytes/key/digest。

| 引擎结果 | 平台/Runtime 处理 | 前端含义 |
|---|---|---|
| `accepted` | 校验目标后保存原 run_id；可能仍 pending、被取消或 Run 详情已删除；Stop 后保持 suppressed 并精确清理 | 通知续接请求已接受；完成回答是否产生由原生 Run/SSE 证明 |
| `definitively_not_accepted` | 仅持久忙碌拒绝事实允许 rejected；同 key 已封闭，不自动创建替代 event/key | 交付受阻，无自动重投按钮 |
| `unknown`、查询异常、详情过期 | 保留原身份和 inflight，继续只读对账或按手册处置；不当作“肯定没运行” | 状态待确认；无自动前台 execute、批准、重发或伪完成 |

Stop、接受、命令状态、清理状态、完成 Run 状态与通知展示分别记录。`has_unresolved` 在不确定资源/交付仍存在时不能因分页或通知 deadline 到期而虚假归零。

公开DTO形状保持不变；`latest_delivery_run_id`作为自动发现入口，提案收窄为同scope内 `delivery_state='accepted' AND stop_id IS NULL` 的最新候选，仍不受分页遮蔽。Stop/suppressed的Task详情保留原delivery.run_id用于清理和诊断，Web不得由此自动接续。候选派发和异步列表返回时重新核对当前scope/Stop/busy/interrupt；不新增另一套运行状态机。新用户Run不能因旧Stop的存在被全局禁用。

内部固定回执授权允许在原操作者撤权后读取这个接受事实，但不创建新执行、不读取 state/input、不取消任意 Run；公开列表/日志/Run 订阅仍走当前 ACL。精确 Stop 清理使用既有独立权限，不复用 acceptance-read。

旧记录没有最终 bytes 时不能从当前配置补造摘要或换 namespace。只允许既有当前 ACL 内的有界正向查询找回；未找到仍 unknown。旧服务返回 404/405 不能回退普通 POST 创建无回执的新 Run；新提交继续关闭。

## 4. 合并保真与实施顺序

1. **用户完成主分支合并。** 按 [baseline.md](baseline.md) 检查来源未提交增量、热点函数和两个迁移分支；本轮规划文档也进入最终基线。
2. **K01–K02：冻结新 Worktree 与迁移。** 新目录从已合并主分支 commit 创建；登记文件/锁/两应用 head/引擎 head，运行隔离迁移路径验证。发现缺源码时先补来源合并，不重新开发。
3. **K03 与 K04 可分服务推进。** API 的字节/只读/授权测试和 Runtime 的迟到回填/guard/Stop 测试在契约冻结后可并行；同一热点函数和迁移由一个后端负责人收口。
4. **K05–K07：合并后系统验证。** 冷构建最终 Linux 镜像，执行独立 API/Worker 故障、资源、安全/回退和受管真实模型回归。阶段失败只修关联根因。
5. **K08–K09：后端交付与前端接手。** 固定 DTO/安全错误/环境和 backend Final。前端同事可以提前准备单测，F12 依赖后端真实环境。
6. **K10–K11：浏览器联合 Final 与状态收口。** 后端零副作用证据和前端截图/订阅证据一一对应，回填原专项剩余状态。

在合并后的代码上执行一次独立 Final；来源历史测试只帮助定位和复用，不抄入新 Worktree 的“本轮通过数”。后端不因等待前端而停止可独立完成的验证。

## 5. 镜像、环境与回退

- 本地栈只用 `scripts/local-stack.sh` 登记/管理，先读 `docs/standards/worktree-development.md`；不复制 99f7/f5a8 的 `.local-stack`、`.venv`、`node_modules`。脚本给出的地址是唯一联调地址。
- 新模型测试、DB、Redis、Workspace、日志和 Docker 资源都归新 Worktree。故障测试可复用 disposable fixture，但必须证明没有接入主环境；截图/报告写在新 Worktree 内。
- 复用正式 post45 包证据，重新验证平台 frozen lock、非 editable 来源、四产物 hash、CLI 和三套迁移体系；保留当前 SDK 与业务依赖，无因回执功能升级 SDK 的需求。
- 新 Runtime Linux 应用镜像需从合并后的锁冷构建；Workspace 执行/文档 reader 镜像沿批准版本核对。两个独立 controller/API/Worker 的同 daemon、同 host ID、daemon 可见绝对挂载、私有日志可达性均需实测。
- 关闭新提交不会停止原对账/日志/授权取消。回退先关闭新提交、排空 running/unknown/queued 完成意图，再回到匹配的上一版代码/镜像；未知事项无法确认时保持受控阻塞，不能宣称 drain 已完成。
- 回退保留接受 ledger/墓碑、RunRequests 最终 bytes、后台最小幂等和 Stop 回执；不执行破坏性 downgrade，不删 Workspace 或未知资源。代码回退不能自动恢复缺失的接受事实，备份恢复到接受前亦不能保证防重。
- 最终证据至少含 commit/双包来源/锁 hash/镜像 digest/head/进程身份、真实故障发生点、HTTP 方法与副作用计数、残留资源和清理结果；不含完整请求体、JWT、模型密钥或私有 env。

## 6. 规范、历史进度与范围外事项

K08 同步 `docs/standards/delegation-jwt.md` 的固定 acceptance-read claim、operation 集合及健康表，更新 API 网关规范、Runtime 接入规范、后台运行手册。仅更新已批准且有证据的部分；JWT/SSE 原专项仍有独立未结项，不能整体改 active。

原后台 `tasks.md` 的 T01/T05/T08/T10 与 F12 在本专项实际验收后回填；其历史 Phase/失败不删除。`docs/CONTEXT.md`、`docs/FEATURES.md` 和用户可感知的 CHANGELOG 按真实状态同步。2026-10-11 非前端 K01–K08 已完成并通过独立 Final，原 T01/T05/T08 回填完成；K09/K10、T10/F12 与整体 K11 仍待前端/浏览器联合，现役未部署。

范围外：LocalBackgroundRunner、K8s/Serverless 新 runner、通用 Run exactly-once、新的用户投递重试产品、任意生产拓扑和现役升级。此前 qwen-plus 空工具 ID 问题保留来源事实；合并后复核是否仍存在，若不影响本专项冻结模型，则独立记录，不能用增加审批次数掩盖。

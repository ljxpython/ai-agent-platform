# Agent 运行取消与中断 - 任务与完成卡

> 进度只看本文件。2026-10-07 用户批准 R01–R10；本轮开发全部非前端必做项，前端由同事完成，可选 LLM 润色 deferred。
> **整体状态：blocked。** 非前端源码、唯一post43包版/真实Docker完成，B01解除；B02剩正式PyPI发布指令与正式源锁接入。前端及浏览器由同事负责，现役部署另行指定。

## Phase 0：规划与人工评审

### Task 0.1：源码与参考设计核对

- **改动内容：** 对照 open-swe、当前三服务、GraphHarbor、SDK 和现有取消/队列/HITL/资源逻辑。
- **代码位置：** [open-swe-comparison.md](open-swe-comparison.md)。
- **预期结果：** 纠正“没有 Stop”和“interrupt 等工具结束”；排除 Slack/PR/渠道业务。
- **验证项：** 静态源码、调用者和官方文档核对通过。
- **状态：** [x] done，2026-10-07。
- **合规检查：** [x] 分析完成；[x] 核对执行；[x] 进度更新；CONTEXT/FEATURES 随专项汇总，CHANGELOG 此规划任务跳过。

### Task 0.2：整体方案与交接

- **改动内容：** 明确固定目标、inbox、回执、三层职责、报告和前端契约。
- **代码位置：** [plan.md](plan.md)、[frontend-handoff.md](frontend-handoff.md)、[review.md](review.md)。
- **预期结果：** 由同事独立接前端，接口以实际 DTO 为准。
- **验证项：** 并发/未知提交/撤权/审批/新 Run/回退覆盖和文档检查通过。
- **状态：** [x] done，2026-10-07，交接已更新为实现版。
- **合规检查：** [x] 文档完成；[x] 核对执行；[x] 进度更新；CONTEXT/FEATURES 随专项汇总，CHANGELOG 此文档任务跳过。

### Task 0.3：验证计划

- **改动内容：** 定义单元、真实 HTTP、故障、容量与恢复证据。
- **代码位置：** [verification.md](verification.md)。
- **预期结果：** ACK/status 不作为停止证明，Phase 与 Final 分开。
- **验证项：** 每项有命令、证据或明确的外部条件。
- **状态：** [x] done，2026-10-07。
- **合规检查：** [x] 文档完成；[x] 核对执行；[x] 进度更新；功能清单/CHANGELOG 此验证计划任务跳过。

### Task 0.4：人工批准

- **改动内容：** 用户批准产品语义、引擎配套、迁移与非前端实施范围。
- **代码位置：** [review.md](review.md)。
- **预期结果：** 治理改动有人类批准依据。
- **验证项：** 用户“方案评审通过，可以开始实施了”已记录。
- **状态：** [x] done，2026-10-07。
- **合规检查：** [x] 记录完成；[x] 批准核对；[x] 进度更新；功能清单/CHANGELOG 此批准记录任务跳过。

## Phase 1：引擎配套

### Task 1.1：依赖事实基线

- **改动内容：** 核实锁、已安装正式包、源码候选和 SDK；保留未发布依赖的现有锁。
- **代码位置：** `apps/runtime-service/{pyproject.toml,uv.lock}`；[implementation/01-engine-and-runtime.md](implementation/01-engine-and-runtime.md)。
- **预期结果：** 正式 post41 与候选新原语不混用；不伪造可安装版本。
- **验证项：** 正式安装包 post41/head 010、SDK 0.4.3；冷安装候选双包 post42/head 011、SDK 0.4.6；import/CLI 均通过。持久队列专项 T7 的浏览器/现役门禁仍独立，本专项已补 FIFO/inbox 真实证据。
- **状态：** [x] done，2026-10-07。正式锁接入归 B02/Task 1.4。
- **合规检查：** [x] 基线核实；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES 更新；CHANGELOG 基线任务跳过。

### Task 1.2：固定目标原子取消

- **改动内容：** Thread 行与全部活动 Run 非等待锁、完整快照、scoped key、持久回执与 100 项分页；复用 _cancel_row。
- **代码位置：** 外部 GraphHarbor `libs/langhost/src/langhost/cancellation.py` → `cancel_active/get_cancellation`；`core_api.py/server.py` 路由；`models.py` → RunCancellationRow；迁移 011。
- **预期结果：** 同动作回读，新 Run 不误伤；事务冲突整单回滚；无平台属性进入引擎。
- **验证项：** 151 目标、20 次 claim/submit/cancel 竞争、幂等/冲突、分页、新目标；容量 1/10/100/500 均通过；500 目标真实 Runtime 超时后后台恢复通过。
- **状态：** [x] done，2026-10-07（源码与隔离验证）。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG 汇总同步。

### Task 1.3：Worker 退出与身份传播

- **改动内容：** 回执以无 lease + 持久终态证明退出；fence 后无证明为 confirmation_unavailable。修正 LangGraph 从 configurable 重建 Runtime 时的 assistant_id/graph_id 传播。
- **代码位置：** GraphHarbor `cancellation.py::_receipt`、`graph_executor.py::thread_config`；复用 production_worker/run_store 停机协议。
- **预期结果：** interrupted/Redis ACK 不能冒充实际退出；主图/子图保持服务端身份。
- **验证项：** GraphHarbor 48 项定向通过；lease fence、长工具/模型等待、两种并行子 Agent 的真实 HTTP 退出通过。
- **状态：** [x] done，2026-10-07。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG 汇总同步。

### Task 1.4：配套发布门禁

- **改动内容：** 候选 wheel/sdist 构建、冷安装、迁移/备份/旧包回退；正式发布另行执行。
- **代码位置：** `scripts/verify_stop_migrations.py`、GraphHarbor 项目验证记录、[evidence/migrations.json](evidence/migrations.json)、[evidence/packages.json](evidence/packages.json)。
- **预期结果：** 冷安装包含接口；取消意图保留；升级/回退不会重跑旧 Run。
- **验证项：** 唯一post43四产物/冷安装、uv lock/check_versions/全包lint/format/mypy通过；包版16场景与7条恢复通过。临时Runtime锁仅变更双包，SDK保持0.4.3。
- **状态：** [ ] blocked，B02：发布准备完成，正式PyPI上传需明确发布指令，之后更新正式源锁并独立安装复验。现役部署另行指定，不属于本次开发门禁。
- **合规检查：** [x] 候选实现；[x] 隔离验证；[x] 进度与阻塞记录；[x] CONTEXT/FEATURES 更新；CHANGELOG 统一描述源码能力，不写已上线。

## Phase 2：Runtime

### Task 2.1：持久请求、租约与后台恢复

- **改动内容：** 控制动作、key 哈希、安全授权事实、固定回执、fenced lease、重试和审计待发送阶段；lifespan 受管后台处理。
- **代码位置：** `apps/runtime-service/src/runtime_service/run_control/{repository,service,authorization}.py`；`db/migrations/versions/0002_run_control.py`；`webapp.py`。
- **预期结果：** 不依赖页面；重复 key、重启和上游超时继续同 stop_id；不存 token/model/message。
- **验证项：** 25 项 Stop 定向集覆盖 lease/恢复/安全事实；真实 Runtime accepted 后重启与 500 目标等待超时恢复通过。
- **状态：** [x] done，2026-10-07（隔离环境）。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG 更新。

### Task 2.2：inbox 固定目标屏障与对账

- **改动内容：** enqueue/claim 共用 Thread advisory lock，只封已固定旧目标；退出后用 committed checkpoint 对账，保留 consumed，其余 user_stopped。
- **代码位置：** `messaging/inbox.py::{enqueue,claim}`、`run_control/repository.py::inbox_blocked`、`service.py::_settle_inbox`；复用 `messaging/reconcile.py`。
- **预期结果：** 新 Run 可继续；旧成功/普通取消遗留消息保留各自 reason；对账故障重试。
- **验证项：** 60 次 enqueue/claim/checkpoint 竞争通过；Stop + 1 running/2 pending/2 inbox 真实链路通过。既有 inbox 契约的 opt-in Server 测试未当作通过。
- **状态：** [x] done，2026-10-07。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG 更新。

### Task 2.3：资源清理与 Backend

- **改动内容：** Docker/local 实际资源登记与清理证据；重复取消保护；取消继续传播；保留已有 external-task unknown 幂等机制。
- **代码位置：** `run_control/resources.py`、`workspace/execution.py`、Showcase/DearFlow backend；`tests/services/test_run_control.py`。
- **预期结果：** 执行与清理独立；不删除工作区、不取消独立 PTY/detached；外部请求未知时不重提。
- **验证项：** 真实Docker后端/挂载/超时/输出/PPTX3项通过；包版HTTP中Showcase/DearFlow命令开始后取消、容器移除、cleanup_confirmed持久回执及8秒后无延迟写入通过。旧local/异常/外部unknown证据保留。
- **状态：** [x] done，2026-10-07，B01已解除；见evidence/acceptance.json的docker字段。
- **合规检查：** [x] 代码完成；[x] 可执行验证；[x] 阻塞记录；[x] CONTEXT/FEATURES/CHANGELOG 更新。

### Task 2.4：确定性报告与 internal API

- **改动内容：** 固定 Run checkpoint、计划/工具证据、安全成果、计数与未知项；最多 20 checkpoints、20 plans + 10 tools、20 artifacts。
- **代码位置：** `run_control/report.py::{build_report,stop_view}`、`http/run_control.py`。
- **预期结果：** 无模型/无新 Run/无 AIMessage；不读取后来 Run；凭据/宿主路径脱敏；未返回的工具调用也标外部结果未知。
- **验证项：** 25 项定向集包含有界报告、artifact、JWT/路径、in-flight 工具、存储故障；真实 empty/HITL/四图报告通过。
- **状态：** [x] done，2026-10-07。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG 更新。

## Phase 3：Platform API

### Task 3.1：公开三接口与安全投影

- **改动内容：** POST Thread cancel、GET detail/list；严格空 body/key/query、no-store、DTO 白名单、安全错误；保留单 Run cancel。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/{presentation/http.py,application/run_control.py,application/service.py,application/ports.py}`、upstream/sdk adapter。
- **预期结果：** 当前执行/读取权限、scope/key 固定；超时未知可回查；内部 auth_facts/engine payload 不进浏览器。
- **验证项：** Stop API 8 项通过；相关回归 66 passed/376 subtests passed；一条既有 fatal 文案断言 HEAD 同样失败，见 verification。
- **状态：** [x] done，2026-10-07。既有无关失败不宣称全仓门禁全绿。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG/网关标准更新。

### Task 3.2：精确委托与当前授权回查

- **改动内容：** thread-stop/thread-stop-read 自定义边界；受信 run-cancellation-read；Thread/取消 ID context_hash；30 秒 HMAC timestamp/body；服务账号 credential 固定。
- **代码位置：** Platform `core/security/tokens.py`、`runtime_catalog/presentation/http.py`；Runtime `auth/platform.py`、`runtime/auth.py`、`run_control/authorization.py`。
- **预期结果：** 撤权拒绝新动作/查询；accepted 清理只查固定回执，不能读 Run/state 或取消别的目标。
- **验证项：** 全 operation 名称契约、JWT/scope拒绝、HMAC篡改/过期、服务账号固定回执、真实 Thread read-only/移除成员和接受后收敛均通过。
- **状态：** [x] done，2026-10-07。现役部署验证归 B02。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG/Delegation 标准更新；标准整体仍 draft。

### Task 3.3：审计与关联

- **改动内容：** requested/read HTTP 审计；accepted/stopping/confirmed/rejected/unknown 持久待发送阶段，稳定 phase event ID 防重复；安全 request/trace/stop/count。
- **代码位置：** `modules/audit/http_resolution.py`、`runtime_gateway/infra/sqlalchemy/run_control.py`、Runtime `service.py::_audit_phase`。
- **预期结果：** 公开 GET 不制造 confirmed；撤权后已接受动作仍写阶段审计；不存 JWT/正文。
- **验证项：** audit resolver 回归通过；真实 ACL 撤销后确认审计入库，等待 audit_pending 清空通过。
- **状态：** [x] done，2026-10-07。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] CONTEXT/FEATURES/CHANGELOG/审计标准更新。

## Phase 4：前端交接，用户同事负责

### Task 4.1：动作与多端状态机

- **改动内容：** 接入三接口、Zod 安全校验白名单、不可变动作快照、localStorage 恢复、单飞保护 45s 超时轮询、迟到响应与 Scope 隔离。
- **代码位置：** `src/services/threads/session.service.ts`、`src/modules/chat/stop/types.ts`、`src/modules/chat/composables/useThreadStopControl.ts`、`src/modules/chat/composables/useChatSession.ts`；详见 [frontend-handoff.md](frontend-handoff.md)。
- **预期结果：** ACK/status 不伪装 stopped；解耦单布尔值；新 Run 启动不被旧 Stop 误杀；Thread/账号切换完全隔离。
- **验证项：** F01–F07 的状态机测试、双 Tab/刷新/切页/撤权与未知重试；定向 Vitest (session.service 10 passed, useThreadStopControl 4 passed, useChatSession 28 passed) 通过。
- **状态：** [x] done，2026-10-08。
- **合规检查：** [x] 代码完成；[x] 验证执行；[x] 进度更新；[x] 状态一致。

### Task 4.2：报告、队列与交互

- **改动内容：** 简要停止反馈条（Banner）挂载于 Composer top-tray、详细报告挂载于 Inspector 抽屉、安全成果正则校验、审批状态保留、服务端队列 refresh 协同与建议抑制。
- **代码位置：** `src/modules/chat/components/RunStopReportBanner.vue`、`src/modules/chat/components/RunStopReportDetails.vue`、`src/modules/chat/components/ChatSession.vue`、`src/modules/chat/composables/useServerPromptQueue.ts`。
- **预期结果：** 严禁前端调用 queue.clear()；不自动 drain/approve/resume；报告不走 AIMessage 管线；390/768/1440 响应式无错乱。
- **验证项：** F08–F10、vue-tsc 0 错误、ESLint 0 错误、Vite build 通过、Vitest 115 文件 553 passed、Playwright + Chromium 真实模型全链路端到端自动化测试通过并捕获 1440/768/390 截图。
- **状态：** [x] done，2026-10-08。
- **合规检查：** [x] 代码完成；[x] 真实模型 E2E 验证；[x] 截图归档；[x] 状态一致。

## Phase 5：联合与发布门禁

### Task 5.1：真实链路

- **改动内容：** 已实现真实 Platform API → Runtime → GraphHarbor API/Worker/PG/Redis → report 的独立验收脚本。
- **代码位置：** `scripts/verify_thread_stop.py`、`tests/fixtures/run_control_platform.py`、[evidence/acceptance.json](evidence/acceptance.json)。
- **预期结果：** 不用 mock router 代替执行；以固定目标/lease/资源/审计核实。
- **验证项：** 唯一post43候选、原SDK0.4.3、实际四图组合根16场景全部通过，含两种真实Docker execute；另有此前local证据。浏览器由同事负责。
- **状态：** [ ] blocked，非前端包版HTTP Phase完成；B02正式源复验与Task4联合链路待完成。
- **合规检查：** [x] 验收脚本完成；[x] 可执行验证；[x] 阻塞记录；[x] 文档汇总更新。

### Task 5.2：Final、回退与文档收口

- **改动内容：** Phase 证据、候选版本/hash、恢复、静态门禁、服务标准/CONTEXT/FEATURES/CHANGELOG/实现记录和前端交接。
- **代码位置：** 本专项文档；`scripts/verify_stop_migrations.py`；各服务活标准。
- **预期结果：** 不把候选/隔离通过误记为正式发布或浏览器 Final。
- **验证项：** 平台35/GraphHarbor6个Python路径lint/format/compile、两仓diff通过；33份文档定向检查新增内容通过，3条旧断链HEAD已存在；迁移7场景通过。基线回归失败与环境缺口如实记录，已按用户确认写入2条经验。
- **状态：** [ ] blocked，文档收口完成，整体Final待B02与前端实施。不提前毕业draft标准。
- **合规检查：** [x] 可执行门禁；[x] Phase记录；[x] 状态一致性；[x] CONTEXT/FEATURES/CHANGELOG 更新；[ ] 整体 Final。

## 明确后置

### Task D1：可选 LLM 润色

- **改动内容：** 将来单独评审无工具 one-shot，仅使用 stop_report。
- **代码位置：** 本期不新增 summary.py/新模型 scope。
- **预期结果：** 确定性报告不依赖模型、不重跑原图。
- **验证项：** 后续评审后定义。
- **状态：** [ ] deferred，沿用户批准方案，本期不实施。

## 阻塞与行动条件

| 编号 | 缺少条件 | 已尝试替代与证据 | 恢复行动 |
|---|---|---|---|
| B01 | 已解除 | 真实后端/PPTX3项与Showcase/DearFlow包版取消、容器移除、持久回执、无延迟写入通过 | 不再阻塞开发；未影响既有容器 |
| B02 | 正式PyPI发布指令 | 唯一post43四产物与哈希、全包门禁、包版16场景/7条恢复、临时锁接入已完成 | 确认上传具体四产物后，更新Runtime正式源锁并独立安装复验；现役部署另行指定 |
| F | 已解除 | 前端接入三接口、状态机、Banner与Drawer；Vitest (553 passed)、vue-tsc (0 error)、ESLint (0 error)、Vite build (通过)、Playwright+Chromium 真实模型全链路自动化测试闭环 (通过，390/768/1440截图已存档) | 前端 Task 4.1 与 4.2 已全部闭环 |

## 进度追踪

- [x] Phase 0 人工批准及规划
- [x] 引擎/Runtime/API 非前端源码
- [x] 本机可执行隔离验证、候选迁移与回退
- [x] 实现记录、活标准与前端交接报告
- [ ] Phase 1.4 正式发布/依赖接入（B02）
- [x] Phase 2.3 真实 Docker（B01已解除）
- [x] Phase 4 前端与浏览器端到端闭环（F 已解除）
- [ ] Phase 5 整体 Final（blocked B02）
- [ ] D1 可选 LLM 润色（deferred）

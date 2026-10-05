# 定时 Agent 任务 - 任务与完成卡

本次交付范围：平台后端、Runtime guard、GraphHarbor 通用补齐及发布、隔离验收和前端契约。用户批准每个 Run 开始前一次聚合授权；失效拒绝留痕，保留定义；暂停/删除不取消已接受 Run；无人值守审批失败。前端和生产平台部署 deferred。

## 已完成任务

### T0.1 原生 cron 事实核查

- **改动内容：** 核查真实派发、关联、恢复与多实例，确定原生复用边界。
- **代码位置：** `GraphHarbor libs/langgraph-runtime-pg/tests/test_cron_dispatch_live.py`
- **预期结果：** 原生 scheduler 为唯一调度源。
- **验证项：** 隔离库 SDK/恢复/双实例契约通过；见 GraphHarbor cron-parity。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T0.1a 隔离库基线探针

- **改动内容：** 复现原生 SDK CRUD、到期 Run 与 pause/delete；拒绝现役库测试。
- **代码位置：** `scripts/verify_scheduled_tasks.py；GraphHarbor cron-parity/verification.md`
- **预期结果：** 所有清库测试只在独立库执行。
- **验证项：** 独立 graphharbor_cron_probe_20261005 基线及原生回归通过。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T0.1b GraphHarbor post40 首次发布

- **改动内容：** 双包构建发布与平台依赖锁定；post41 接续见 T4.1。
- **代码位置：** `apps/runtime-service/pyproject.toml、uv.lock；implementation/01-graphharbor-release-and-handoff.md`
- **预期结果：** 正式发布包可独立安装。
- **验证项：** post40 PyPI JSON 200、独立 CLI 同版本；现行已升级 post41。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T0.2 人工批准执行语义

- **改动内容：** 记录用户批准的每 Run 一次聚合授权、失效拒绝留痕、已接受 Run 与无人值守策略。
- **代码位置：** `README.md、plan.md；docs/standards/delegation-jwt.md`
- **预期结果：** 身份与服务边界有明确人工批准。
- **验证项：** 本会话用户明确同意方案并授权继续实施；非 AI 自行批准。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T1.1 定义与运行事实复用

- **改动内容：** 原生 metadata.task_spec 保存定义，Run cron_id 关联，审计补码，无新表。
- **代码位置：** `apps/platform-api/src/platform_api/modules/scheduled_tasks/service.py → task_item()/history()`
- **预期结果：** 无重复 scheduler 或 occurrence；原生 Run 为终态事实。
- **验证项：** 发布包探针 CRUD、Run 关联、定义删除后历史读取通过。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T1.2 产品接口、时间与历史分页

- **改动内容：** 10 条 API、once/cron 校验、服务端预览、pause/resume、分页和错误契约。
- **代码位置：** `apps/platform-api/src/platform_api/modules/scheduled_tasks/{schemas,router,service}.py；apps/runtime-service/src/runtime_service/http/crons.py`
- **预期结果：** 规则由原生 parser 计算，过滤先于分页。
- **验证项：** schema/signature 2 tests；隔离 HTTP CRUD、preview、once、分页通过；DST/end_time 原生契约通过。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T1.3 调度故障与重启恢复复用

- **改动内容：** 复用原生 PG 行锁、派发事务、持久队列及生命周期。
- **代码位置：** `GraphHarbor libs/langgraph-runtime-pg/src/langgraph_runtime_pg/cron.py、production.py`
- **预期结果：** 双实例不重复领取，故障不推进时间，重启恢复。
- **验证项：** cron-parity 双实例/注入失败/重启与 post41 CI 126 passed/4 skipped。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T2.1 受管执行与手动幂等

- **改动内容：** HMAC marker、实时 actor/policy、Thread reservation 和既有 gateway/run_requests。
- **代码位置：** `apps/platform-api/src/platform_api/modules/scheduled_tasks/service.py → trigger()/authorize_execution()；runtime_gateway/application/{service,thread_access}.py；runtime_catalog/presentation/http.py`
- **预期结果：** 撤权拒绝，重复或响应丢失不重复 Run/Thread，不存 JWT。
- **验证项：** 发布包探针用户/服务账号/凭据/项目/Agent/模型/Thread 失效、同 key 并发与响应丢失对账通过。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T2.2 Runtime 执行前 guard 与审批失败

- **改动内容：** 四个 factory 构造前一次授权，ainvoke/v3 stream 审批失败，普通 Run 保持路径。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/scheduled.py；graphs/{reference_agent,workflow_demo,showcase_demo,dearflow_agent}.py`
- **预期结果：** 无需无人值守 approve，失效不构造图和工具。
- **验证项：** Runtime 定向 57 passed；真实 worker 审批/异常/失效 Run 均预期 error。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T2.3 执行留痕和 Run 历史

- **改动内容：** 原生 Run 分页与审计拒绝码合并；删除后保留历史，once 定义与 Run 分开。
- **代码位置：** `apps/platform-api/src/platform_api/modules/scheduled_tasks/service.py → record_execution()/execution_errors()/history()；Runtime http/crons.py`
- **预期结果：** 成功、失败、已删 Thread 和已删定义可追溯。
- **验证项：** 发布包 22 Run（8 success、14 预期 error）；错误审计断言与删除后读取通过。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T3.0 前端正式契约交接

- **改动内容：** 提供实际 10 接口、字段、幂等、分页、状态、错误与联合验收清单。
- **代码位置：** `frontend-handoff.md`
- **预期结果：** 同事按真实契约实施，明确现役/远端尚未部署。
- **验证项：** 与 router/schemas/service、原生历史和错误 Envelope 核对；文档链接检查。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T4.1 后端隔离链路与发布验收

- **改动内容：** 自动化、真实 HTTP/worker、故障/撤权/并发、发布包独立安装与回退门禁。
- **代码位置：** `scripts/verify_scheduled_tasks.py；两服务 tests；GraphHarbor cron-parity`
- **预期结果：** 当前后端范围完成；完整回归失败如实保留并核对基线。
- **验证项：** API 320 passed/16 skipped/641 subtests，2 旧失败；Runtime 563 passed/85 skipped，1 Docker 失败；3 项在 HEAD 复现。cron 定向/发布包 E2E 全通过；Ruff/锁检查通过。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

### T4.2 状态与标准同步

- **改动内容：** 统一两库方案、任务、实施、Phase/Final、前端契约和当前状态；JWT 保留 draft。
- **代码位置：** `docs/CONTEXT.md、FEATURES.md、CHANGELOG.md、standards/；apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`
- **预期结果：** 文档无旧 scheduler/occurrence 方案或未开放接口残留，部署边界准确。
- **验证项：** 双库 diff --check、专项链接与完成卡/Phase 对照检查；JWT 25 operations/10 原生/15 自定义一致。
- **状态：** [x] 已完成 2026-10-05；实施见 implementation/01 与 02，逐项 Phase 见 verification.md。
- **合规检查：**
  - [x] 任务实施/调研完成（T0.2 为用户批准记录，T3.0/T4.2 为文档交付）
  - [x] 对应验证/事实核对已执行
  - [x] tasks.md 与 Phase 状态已同步
  - [x] CONTEXT.md 已同步当前服务状态
  - [x] FEATURES.md 已同步能力；纯调研/文档任务跳过单独能力行
  - [x] CHANGELOG.md 已记录本次 feat/fix；调研/文档任务跳过单独条目

## 用户指定同事实施的后置工作

- [x] T3.1 项目定时入口、导航与 API client：已完成，路由与导航映射完成，API service 封装完成。
- [x] T3.2 列表/表单/预览/历史/操作与单测打包验收：已完成，Card Grid 列表、双栏抽屉、DeerFlow 预设体系、历史抽屉与权限守卫完成，481 套单测全绿、vue-tsc 0 错误、生产构建全绿。

## 进度与交付边界

- [x] 本次 13 项后端/调研/契约交付任务全部完成。
- [x] 前端定时任务完整功能模块、路由与组件全部实现并验证通过。
- [x] GraphHarbor 双包 post41 已发布，平台 pyproject/uv.lock/.venv 已锁定安装。
- [x] 发布包真实隔离链路通过；完整回归的 3 项外围失败已 HEAD 复现，不计为通过。
- [x] 前端交接规范已修正，代码与静态类型检查全绿。
- [ ] 现役/远端平台部署及生产回退演练：deferred，未执行。
- [ ] interval、复制、通知和对话内建任务：首期范围外，未实现。

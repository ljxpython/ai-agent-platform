# 跨服务链路追踪 - 开发任务

> 方案就绪、实现未开始。全部开发任务初始为 [ ]；本轮文档落盘不勾选实施任务。进度只看本文件。实施每项后记录修改文件、真实测试结果及限制。

顺序：T1 → T2/T3 → T4 → T5/T6 → T7 → T8。以下路径均相对仓库根目录。

## Phase 1：内部编号与委托

### T1 内部编号与异常清理

- **状态：** [ ] 未开始。
- **改动内容：** 每 HTTP 请求生成一次内部编号，完整 try/finally、安全 500、CORS 暴露两头；http.response.ready 只表示准备完成。
- **代码位置：** apps/platform-api/src/platform_api/core/context/runtime.py；entrypoints/http/middleware/request_context.py（同 src/platform_api 根）；apps/platform-api/src/platform_api/main.py::create_app。
- **预期结果：** 外部头不能覆盖或污染日志；响应头/正文/上下文一致；异常取消无串号，不跨任务 reset。
- **验证项：** V01—V03、既有 CORS/错误测试；错误响应专项安全 500 与编号契约是集成前置。

### T2 网关委托入口

- **状态：** [ ] 未开始。
- **改动内容：** 初始 read、scoped 签发闭包捕获当前 RequestContext 的 request_id/platform_trace_id，转发相同内部请求头。
- **代码位置：** apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::get_runtime_gateway_service / delegation_headers_factory。
- **预期结果：** run-create、审批、取消及其他现有委托无遗漏，不改 operation/TTL/权限，不跨请求缓存。
- **验证项：** V04；现有 test_runtime_delegation.py、test_runtime_gateway_sdk_adapters.py。

### T3 Catalog 委托入口

- **状态：** [ ] 未开始。
- **改动内容：** 增加可选 request_correlation，经 presentation → bootstrap → service 签发；build_forward_headers 仅接受显式内部 request_id。
- **代码位置：** apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py::get_runtime_catalog_service；apps/platform-api/src/platform_api/modules/runtime_catalog/bootstrap.py::build_runtime_catalog_service；apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py::__init__ / _runtime_headers；apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py::build_forward_headers。
- **预期结果：** 独立签发不遗漏，非 HTTP 调用无虚假编号；保留现有 Catalog service/test 工作区改动。
- **验证项：** V04—V05；现有 test_runtime_catalog_delegation.py；所有 build_forward_headers 调用方回归。

## Phase 2：关系、查询与流日志

### T4 提交及 Run 关联

- **状态：** [ ] 未开始。
- **改动内容：** 可选 on_correlation；reserve 后 attempt，复用/接受/拒绝/unknown 及取消 result；HTTP 层日志与 audit_metadata 增量合并。
- **代码位置：** apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py::RuntimeGatewayService.__init__ / launch_runtime_run / cancel_thread_run 及调用方；apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::get_runtime_gateway_service。
- **预期结果：** 没有 reserve 不伪造提交；父 Run/interrupt 真实；取消 ACK 不宣告结束；观察失败不重复执行、不吞取消；不加独立审计行或虚构 202。
- **验证项：** V06—V09、V15；reserve 冲突、Run 详情读取失败、mark 失败、日志失败与合并失败分别注入；幂等次数及命令/context_hash 不变。

### T5 审计白名单与精确查询

- **状态：** [ ] 未开始。
- **改动内容：** 同时扩写入/读取安全字段；新增 request/submission/thread/run 查询，时间范围验证和授权组合；流异常保留实际 HTTP 状态。
- **代码位置：** apps/platform-api/src/platform_api/modules/audit/http_resolution.py::_resolve_metadata；service.py::list_events、contracts.py::ListAuditEventsQuery、router.py::list_audit_events、repository.py::list_events（均同 modules/audit 目录）；apps/platform-api/src/platform_api/entrypoints/http/middleware/audit_log.py::audited_body_iterator。
- **预期结果：** 写了能查；AND/OR 分组与 total 一致；项目隔离、历史兼容；422 安全错误；不加表/索引、不改审计事务。
- **验证项：** V10—V12、V15—V16；SQLite/PostgreSQL 实际 JSON 查询；已发 200 后断连/异常状态仍为 200。

### T6 SSE 生命周期日志

- **状态：** [ ] 未开始。
- **改动内容：** 在现有实际发送/关闭路径记录 opened/closed，接入 SSE 专项可选结束原因回调，保留幂等 shielded 清理。
- **代码位置：** apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::RuntimeStreamingResponse 和现有创建/订阅流入口；SSE 专项现有帧解析/结束回调。
- **预期结果：** 握手失败无 opened；成功 start 后记录，结束最多一次 closed；六种关闭原因准确；线程流不固定 Run，不记录正文或隐式取消。
- **验证项：** V13—V15；创建并订阅的 Run ID 来源、线程跨 Run、重复 close、客户端取消与任务上下文隔离。

## Phase 3：真实验收与交接

### T7 自动化和真实链路验证

- **状态：** [ ] 未开始。
- **改动内容：** 扩展既有测试并执行 Phase 回归；真实平台请求→审计 submission/thread/run→worker→受信 metadata→反查，包含重试、审批、取消、重连；SQLite/PG 查询及性能、回退验证。
- **代码位置：** apps/platform-api/tests/ 既有测试；必要时新增 test_request_correlation.py、test_runtime_correlation.py、test_audit_correlation.py；本专项 verification.md。
- **预期结果：** 有环境、版本、脱敏编号和证据对应；mock 不替代 worker/观测导出。Runtime/GraphHarbor 不修改。
- **验证项：** V01—V16、真实链路 R1—R6、性能与回退门禁；缺条件写未验证并列阻塞。

### T8 文档状态和回退交接

- **状态：** [ ] 未开始；本轮仅完成初始执行文档。
- **改动内容：** 实施后同步任务、Phase/Final、运行限制和 API 回退结果，不将规划写成功能上线。
- **代码位置：** 本专项 README.md/plan.md/tasks.md/verification.md；docs/projects/20260922-cross-service-governance/README.md、03-trace-propagation.md；docs/CONTEXT.md；docs/FEATURES.md。
- **预期结果：** 如实区分方案就绪、实现完成、验证完成；无数据库回滚，不动已有 Run。
- **验证项：** 文档检查、相对链接、任务勾选与证据一致、工作区范围；Final 缺项明确说明。

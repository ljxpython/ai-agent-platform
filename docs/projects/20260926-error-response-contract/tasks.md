# 错误响应统一 - 执行任务

> 方案已获用户同意，当前仅规划；实施启动后按下列顺序执行。Runtime/GraphHarbor所有文件、配置和依赖均禁止修改。

## Phase 0：已完成的交接准备

- [x] E0.1 源码调用链、公开错误码/extra与消费者清单：见plan.md、error-catalog.md。
- [x] E0.2 SDK1.10.2源码核对及内存HTTPError探针：旧转换丢ID，新转换保留；见verification。
- [x] E0.3 用户确认方向及硬边界（2026-09-26）；技术决策E01—E08已落笔。
- [ ] 实施开始时记录基线revision/dirty diff和包版本；若源码有新变动仅做差异核对，不重复设计。当前不提交代码。

## Phase 1：前端无损消费

### E1.1 公共解析与展示
- **改动内容：** 按plan第6节扩展解析；SDK.text/Axios/Blob一致输出extra；取消独立标记；安全fallback；请求编号格式化。
- **代码位置：** `apps/platform-web/src/utils/http-error.ts` → extractEnvelopeFields/extractPlatformHttpError/unwrapPlatformHttpError/resolvePlatformHttpErrorMessage；新增formatPlatformHttpErrorMessage；新增同目录http-error.spec.ts。
- **预期结果：** 不显示原始JSON/HTML，无二次解析异常；现有调用签名兼容新增可选字段。
- **验证项：** F01/F04；20项details、64KiB、非法ID、重复后缀、code与Axios code区分。
- **状态：** [ ] 待实施。

### E1.2 SDK/Session与现有消费者
- **改动内容：** 保留error对象并补顶层文案；createLanggraphClient maxRetries=0；Session复用解析、pending对账；workspace服务复用解析并保留业务映射。
- **代码位置：** `apps/platform-web/src/services/langgraph/client.ts` → normalizeProtocolErrorResponse/createLanggraphClient；`services/threads/session.service.ts` → createSessionService的create/read；`services/runtime-gateway/workspace.service.ts` → normalizeRuntimeGatewayError及三个私有字段解析器。
- **预期结果：** 502/503/504带pendingID时保留并先对账；同动作只创建一次；401只刷新一次，不改变命令幂等键。
- **验证项：** F02/F03/F05；补到client.spec.ts、session.service.spec.ts、runtime-gateway/workspace.service.spec.ts。必须经过真实授权fetch与SDK，不能只mock最终service。
- **状态：** [ ] 待实施。

## Phase 2：API安全转换

### E2.1 上游异常载体与转换
- **改动内容：** 扩展UpstreamServiceError承载来源状态、headers/details/安全extra；公共转换始终产出该子类；按清单映射码与文案。
- **代码位置：** `apps/platform-api/src/platform_api/core/errors/base.py` → PlatformApiError/UpstreamServiceError；`adapters/langgraph/sdk_client.py` → create_runtime_upstream_error/raise_runtime_upstream_error；`adapters/langgraph/runtime_client.py` → _raise_for_status及固定错误文案。
- **预期结果：** 来源401对外502但仍可识别确定拒绝；5xx原文不泄露；JSON/上传/下载/握手一致。
- **验证项：** U01—U05；test_runtime_upstream_errors.py测试返回类型、来源/公开状态、所有清单码表驱动案例及未知正文；test_runtime_gateway_sdk_adapters.py测实际adapter。
- **状态：** [ ] 待实施。

### E2.2 本地handler、中间件及memory二次转换
- **改动内容：** 安全422详情/必要头；500共用构造；request_context完整try/finally和普通异常转换；memory wrapper保留清洗后数据与指定码。
- **代码位置：** `apps/platform-api/src/platform_api/core/errors/handlers.py`、`payload.py`；`entrypoints/http/middleware/request_context.py`；`adapters/langgraph/runtime_gateway_upstream.py` → dear_memory；`modules/runtime_gateway/presentation/http.py` → change memory的422重抛分支（保留已清洗details）。
- **预期结果：** 500也有JSON/CORS/request ID；日志无原文秘密；memory_storage_unavailable对外502但code保留；局部wrapper不抹掉字段。
- **验证项：** H01—H05、M01；test_core_error_handling.py真实middleware顺序、test_runtime_gateway_memory_contract.py和SDK adapter memory测试。
- **状态：** [ ] 待实施。

### E2.3 Thread对账与原始状态判断
- **改动内容：** create_thread用upstream_status_code识别确定4xx；网络/5xx保留pending；子类异常能进入现有分支；reconcile404语义保持。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → create_thread/_thread_reconcile_error/_mark_thread_provisioned/reconcile_pending_thread；必要时仅调整该方法异常判断，不改ACL数据库或权限。
- **预期结果：** 内部401公开502仍清理确定失败预留；真正未知结果不重复创建，pending UUID可由浏览器恢复。
- **验证项：** P01—P06；在test_thread_acl.py中从公共转换函数造异常，禁止全部手造UpstreamServiceError掩盖类型问题；test_runtime_gateway_http_matrix.py验证公开extra。
- **状态：** [ ] 待实施。

## Phase 3：组合与Final

### E3.1 固定可运行契约/E2E
- **改动内容：** 现有测试文件补充矩阵；新增隔离错误HTTP测试、浏览器测试和最小平台fixture，禁止新增Runtime测试接口。
- **代码位置：** 拟新增 `apps/platform-api/tests/test_error_response_contract.py`、`apps/platform-api/tests/fixtures/error_contract_server.py`；拟新增 `apps/platform-web/e2e/error-response-contract.spec.ts`。环境及行为见verification。
- **预期结果：** 真正经过平台应用栈与浏览器service的错误可见、可恢复；受控故障与真实Runtime联调证据明确分开。
- **验证项：** verification全部矩阵；新Web/旧API、新Web/新API及回退组合；Runtime工作树/配置未变。
- **状态：** [ ] 待实施。

### E3.2 收口交付
- **改动内容：** 执行Final，更新生效标准/前端说明、CONTEXT、FEATURES和父项目。
- **代码位置：** 本专项verification.md/tasks.md/README.md；拟新增 `docs/standards/error-envelope.md`；`apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`；`apps/platform-web/docs/frontend-development-playbook.md`。
- **预期结果：** 通过才done；缺真实Runtime可达验证则partial并记录原因，不以受控响应替代真实端到端。
- **验证项：** 单元/集成/E2E、定向lint/typecheck、兼容回退证据与无敏感数据。
- **状态：** [ ] 待实施。

## 进度

- [x] 方案/技术细则和交接包完成。
- [ ] Phase1。
- [ ] Phase2。
- [ ] Phase3 Final与交付。

# 平台错误响应实施记录

- 日期：2026-09-26 至 2026-09-27
- 任务：E1.1、E1.2、E2.1、E2.2、E2.3、E3.1、E3.2。
- 状态：`done`。Phase 定向验证、隔离浏览器、真实提交→Run→审计→Langfuse/SSE 观测、真实 peer、授权 workspace 正向链路和 Final 回归均已完成。旧版兼容与回退测试已从范围移除。

## 修改文件与理由

| 文件 | 修改 |
|---|---|
| `apps/platform-api/src/platform_api/core/errors/base.py` | `UpstreamServiceError` 保留真实来源状态、已清洗 details/extra/headers；公开状态独立。 |
| `apps/platform-api/src/platform_api/core/errors/payload.py`、`handlers.py` | 统一请求ID头、校验详情与响应头白名单；500固定安全正文与日志字段。 |
| `apps/platform-api/src/platform_api/entrypoints/http/middleware/request_context.py` | `call_next` 全程 try/finally，普通异常经现有CORS层转500；取消不转500。 |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py`、`runtime_client.py` | 精确登记上游机器码；来源401→502，5xx→502，超时504；原始正文/path默认不公开，410只留固定recovery。 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py`、`modules/runtime_gateway/presentation/http.py` | memory 二次转换保留固定码及已清洗校验详情；本地memory校验共用安全清洗。 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | Thread 创建/对账按来源状态判断确定4xx，未知结果保留平台pending ID；动态Content-Type不再回显。 |
| `apps/platform-api/tests/test_run_requests.py` | Run 幂等记录在内部401映射成公开502后仍按真实来源状态标记确定拒绝，25项相关测试通过。 |
| `apps/platform-web/src/utils/http-error.ts` | Axios、SDK.text、Blob 共用解析；有界正文、合法请求编号、取消语义及安全fallback。 |
| `apps/platform-web/src/services/langgraph/client.ts`、`services/threads/session.service.ts`、`services/runtime-gateway/workspace.service.ts` | SDK保留嵌套error并补顶层文案；禁隐式重试；Session按UUID保存并先对账；工作台复用公共解析。 |
| `apps/platform-api/tests/test_core_error_handling.py`、`test_error_response_contract.py`、`test_runtime_upstream_errors.py`、`test_runtime_gateway_sdk_adapters.py`、`test_runtime_gateway_memory_contract.py`、`test_thread_acl.py`、`test_runtime_gateway_workspace.py` | 新契约、安全字段、真实应用HTTP出口、memory和pending状态回归。 |
| `apps/platform-api/tests/fixtures/error_contract_server.py`、`apps/platform-web/e2e/error-response-contract.spec.ts` | 临时SQLite和受控转换，Chromium走授权fetch、已安装SDK、Session及平台真实HTTP中间件；不接触现役Runtime。 |
| `apps/platform-web/src/utils/http-error.spec.ts`、`services/langgraph/client.spec.ts`、`services/threads/session.service.spec.ts`、`services/threads/workspace.service.spec.ts` | 公共解析、实际授权fetch/SDK、单次写请求及Blob提示回归。 |

旧转换会公开任意 `upstream_detail` 并返回父类，创建Thread无法进入 `UpstreamServiceError` 对账分支；现在公共转换返回该子类，并且只公开清单字段。既有平台业务错误仍由 `PlatformApiError` 保持原码。

## 2026-09-27 补充

- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`：`RuntimeStreamingResponse.stream_response` 在成功发送200后发 opened，结束时接收 `_redact_protocol_event_stream` 的原因回调；`_runtime_sse_response` 捕获当前请求编号、Thread 和已知 Run，向现役 INFO 日志写 opened/closed。握手失败不虚构打开事件，关闭不修改 HTTP 状态或流正文。
- `apps/platform-api/tests/test_runtime_gateway_event_redaction.py`：验证编号与 Run 关联、帧拒绝原因及 start 发送失败。`apps/platform-api/tests/test_error_response_contract.py`：显式开关的真实栈用例经平台创建临时项目、Agent、Thread，验 memory409、幂等提交、审计和 Langfuse，并先删 Thread 后删项目。
- `apps/platform-web/e2e/error-response-contract.spec.ts`：现役 Web 403 错误页检查 Network Envelope、响应头与页面请求编号；与原受控 fixture 用例分别开关。
- `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`：补齐两个手工请求上下文的编号字段，使网关依赖和 SSE 关联日志测试走与真实中间件一致的输入；保留其他专项的协议事件 fixture。
- `apps/platform-api/tests/test_error_response_contract.py`：真实栈用例补 owner/peer Thread 读取及 SSE 握手前权限拒绝；自动创建的 `showcase_demo` Agent 完成文件上传、读取和缺失文件 404，未将隔离结果冒充真实通过。
- `apps/platform-api/tests/test_thread_fork.py`：补齐现役 delegation upstream 所需的 `create_thread`、`update_thread_state` 测试替身并更新签发调用断言；定向测试 3 项通过，全量 API 测试不再有 fork 替身错误。
- `apps/platform-api/tests/test_error_response_contract.py`：真实用例自动创建和清理第二测试身份、临时项目、`showcase_demo` Agent 及 Thread，完成 peer 403、workspace 上传/读取和缺失文件 404 验证。
- 真实结果及 `reference_agent` 工具授权基线差异见 `verification.md` Phase 2026-09-27；本轮没有修改 Runtime/GraphHarbor。

## 验证与限制

定向 API/Web 测试、真实 create_app HTTP 出口、新Web+新API隔离 Chromium、TypeScript 类型检查和生产构建已通过；命令与数值见 `verification.md`。2026-09-27 Web 全量397通过、1既有跳过；API全量301项中286通过、15跳过、无错误。真实请求→提交→Run→审计/Langfuse、真实peer和 `showcase_demo` workspace 正向文件均已验证。现役 `reference_agent` 的 `runtime.tool.not_allowed` 属工具授权基线差异，不改 Runtime/GraphHarbor。没有运行现役数据库迁移、部署或Git写操作。

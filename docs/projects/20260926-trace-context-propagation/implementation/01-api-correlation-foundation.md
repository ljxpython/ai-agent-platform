# API 关联基础阶段实现

2026-09-26，涉及 T1—T5 的阶段实现；T6—T8 未完成。

## 改动

- `core/context/runtime.py`：请求号改为平台 `uuid4().hex`，`trace_id` 同值；不再接受外部关联头。
- `main.py` 与 `entrypoints/http/middleware/request_context.py`：暴露两响应头；现有中间件 `finally` 保持 ContextVar 清理。
- `modules/runtime_gateway/presentation/http.py`：Gateway 初始及 scoped 委托从当前上下文取得两编号，转发同一请求号。
- `modules/runtime_catalog/presentation/http.py`、`bootstrap.py`、`application/service.py` 与 `adapters/langgraph/sdk_client.py`：Catalog 独立签发入口传递两关联字段；转发头仅采用显式平台编号。
- `modules/runtime_gateway/application/service.py`：reserve 后发出提交 attempt/result，取消发出 result；HTTP 层合并已有审计 metadata 并写结构化日志。观察回调失败不重发业务动作。
- `modules/audit/http_resolution.py`、`service.py`、`contracts.py`、`router.py`、`repository.py`：固定关联字段双向白名单，request/submission/thread/run 精确过滤与 7 天窗口校验；项目授权条件同查询生效。

## 阶段验证

`test_cors_middleware_order.py` 1 项、`test_runtime_delegation.py` 18 项、`test_runtime_catalog_delegation.py` 15 项、`test_run_requests.py` 26 项、`test_audit_http_resolution.py` 9 项、`test_audit_correlation.py` 3 项、`test_audit_stream_status.py` 1 项、`test_runtime_gateway_sdk_adapters.py` 19 项、`test_security_boundaries.py` 5 项通过。新增测试分别覆盖外部编号污染、委托关联、关联回调失败、SQLite JSON 过滤、HTTP 422与已发200的审计状态。尚未执行 PostgreSQL、并发取消、真实 worker/观测和 Final 回归。

## 限制

Runtime/GraphHarbor 未修改。审计流中已发HTTP 200后不再伪记499/500；该层未必观察到上游最终异常，因此结果分类仍需SSE统一关闭路径补证。SSE生命周期日志和真实链路证据待后续任务；本记录不代表T1—T5全部验收通过。

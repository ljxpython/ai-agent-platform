# Runtime 与 Platform API 实施记录

**日期：** 2026-10-06至2026-10-07。**关联任务：** E01-E05、S01-S04、Q01-Q05。

用户已批准治理方案。本记录解释实现，进度仍以三个专题的任务卡为准；前端 F01-F04 由同事接续。

## Runtime

| 文件（相对仓库根） | 主要符号 | 改动和理由 |
|---|---|---|
| `apps/runtime-service/src/runtime_service/observability/errors.py` | `classify_exception/model_error_fields/execution_outcome` | 优先有限 provider code，再 status/type，最后有限文本；异常链最多3层。不导出原文，取消/HITL不算模型错误。 |
| `apps/runtime-service/src/runtime_service/observability/diagnostics.py` | `diagnostic_metadata/safe_fields/log_diagnostic/trace_id_for` | stdlib JSON日志、受信身份、合法native Run UUID；白名单与长度限制；tenant/project/run确定性SHA256前32位trace ID。 |
| `apps/runtime-service/src/runtime_service/middlewares/model_errors.py` | `ModelErrorMiddleware.awrap_model_call` | timeout外侧、fallback/retry内侧观察一次模型handler失败，保留原异常对象。不新增恢复行为。 |
| `apps/runtime-service/src/runtime_service/observability/startup.py` | `StartupDiagnostics.authorize/phase/finish/export_otel` | 构图局部collector，UTC展示、monotonic计时，最多16阶段；正常/失败/取消收尾，无Thread全局缓存。 |
| `apps/runtime-service/src/runtime_service/observability/langfuse.py` | `with_langfuse_tracing/record_diagnostic_event/_mask_spans` | 关闭远程导出仍装本地回调；事件与graph使用同trace；清理异常、input/output属性；初始化/调用故障隔离。 |
| `apps/runtime-service/src/runtime_service/observability/otel.py` | `OTelDiagnosticsCallback` | execution父span涵盖startup/graph；安全exception event替代原始record_exception。 |
| `apps/runtime-service/src/runtime_service/observability/query.py` | `diagnostics_client_lifespan/query_run_diagnostics/_project` | 官方异步observations v2，只取core/basic/time/metadata；确定性trace优先，旧session一次fallback；100 observations、50 trace、2秒总预算；逐条scope核验。 |
| `apps/runtime-service/src/runtime_service/http/diagnostics.py` | `run_diagnostics_endpoint` | 新内部只读GET，UUID/operation/tenant/project/graph/Thread校验，再复用当前Thread ACL回查。 |
| `apps/runtime-service/src/runtime_service/auth/platform.py` | `authorize_thread_targets` | 抽出已有native ACL回查，让自定义诊断接口复用同一credential撤权检查。 |
| `apps/runtime-service/src/runtime_service/runtime/auth.py` | `_parse_scope/verify_delegation_claims` | diagnostics-read必须Thread绑定；不能读取原生资源。 |
| `apps/runtime-service/src/runtime_service/webapp.py` | `lifespan`、router注册 | 应用级查询连接生命周期和no-store。 |

四个正式组合根保留现有权限、模型、工具和子Agent装配方式：

- `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py`：已有fallback/retry内侧装诊断，context/connection/build/compile计时。
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`：父/子共同列表装诊断，增加workspace计时。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`：父/researcher装诊断；memory/MCP/model/workspace/compile计时。
- `apps/runtime-service/src/runtime_service/services/demo/workflow_demo/agent.py`：工厂计时和动态内部模型诊断；node.model_prepare单独记事件，不混进factory总计。

## Platform API

| 文件（相对仓库根） | 符号 | 结果 |
|---|---|---|
| `apps/platform-api/src/platform_api/core/security/tokens.py` | `create_runtime_delegation_token` | 新增diagnostics-read；沿v2五字段scope，必须绑定Thread。 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py` | `RuntimeDiagnostics/RunDiagnostics` | 实际v1 DTO/OpenAPI：9类模型码、有限数组、非负有限耗时、url=null；未知字段删除，非法结构安全502。 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | `get_run_diagnostics` | 既有upstream协议新增一个实际消费方法。 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` | `get_run_diagnostics` | 既有require_json、URL转义和错误转换。 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | `get_thread_run_diagnostics` | 项目/Thread授权→原生Run存在及归属→只读委托→DTO；query request ID与execution ID分开。HTTP等待不占数据库事务。 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | `get_thread_run_diagnostics/_redact_sse_frame` | 公开GET/no-store/response model；Protocol lifecycle和普通Run SSE明确错误槽位脱敏，保留帧ID/顺序。 |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` | `project_execution_error/redact_execution_fields/redact_runtime_private_fields` | Thread/Run.error与state/history tasks错误固定安全消息、允许类型；正常message/tool正文保留。 |

关键前后行为：

```python
# 原来：原始异常可进入OTel，关闭exporter时不装诊断回调。
span.record_exception(error)
if callback is None and otel_provider is None:
    return graph

# 现在：安全异常类型，且本地诊断独立装配。
span.add_event("exception", {"exception.type": error_type(error), ...})
callbacks.append(_RuntimeDiagnosticsCallback(graph_id, bound_metadata))
```

## 验证与修正

新增测试：Runtime `tests/observability/test_diagnostics.py`、`test_run_diagnostics.py`、`tests/http/test_diagnostics.py`；API `tests/test_run_diagnostics.py`。更新middleware顺序、JWT契约、公开route矩阵和原观测回归断言。跨服务实测使用 `scripts/verify_agent_observability.py`，独立PG库/Redis prefix和临时平台SQLite，退出关闭本次API/Worker，不重启现役服务。

修正的验证问题：

1. 独立库只跑GraphHarbor迁移，遗漏Runtime应用链；补调用已有 `runtime_service.db.upgrade()`，没有新增DDL。
2. Langfuse 4事件已结束且无 `update_trace()`；改用公开 `propagate_attributes(session_id=...)` 在创建前绑定，真实SDK exporter验证session/trace与安全字段。
3. 长契约子进程超过默认60秒JWT和90秒测试预算；测试TTL=300、子进程预算=180，生产默认TTL仍60；PYTHONPATH固定当前worktree防止旧editable源码混入。
4. SSE验收脚本改用当前 `channels/since` 订阅与Run join-stream，不能传未支持的replay/follow/run_id。
5. 实际v3普通Run SSE的`debug/task_result/payload.error`会带provider原文；在统一frame投影器补typed/普通/namespace形式，checkpoint沿既有task错误投影，保留帧ID/序号和正常工具正文。
6. Langfuse先看到startup不能证明graph/模型记录已导出；验收等待目标记录，生产查询保持有界单次访问。并发SDK429投影为unavailable，安全记录类型/status用于验收，不输出body或密钥。
7. 真实DeepSeek代理不存在模型被SDK包装为`OpenAIModelNotFoundError`；补这一明确类型分类及回归，普通404不自动算模型不存在。
8. 查询压测不能与tracemalloc混测；API独立事件循环、原生读对照、分段耗时记录和失败证据保留。验证客户端120秒仅用于收全结果，生产预算不改。
9. 隔离fallback/并行子任务fixture使用正式reference/showcase装配，匹配当前目录model_id，避免RuntimeConfig再次构建未配置的模型；模型/工具/factory故障仅在验证脚本注入。
10. 追加独立rollback profile，用固定基线源码加载旧采集/reference/workflow工厂/Runtime应用并撤下平台诊断路由；六个原生Run/SSE/HITL/取消门禁通过。恢复请求沿用原配置且按实际interrupt_id提交，未切换现役服务版本。

完整结果见 [后端验收](02-backend-verification.md)及 [证据JSON](backend-runtime-evidence.json)。没有修改GraphHarbor包、部署配置、前端代码或执行git提交。

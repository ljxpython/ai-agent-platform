# 消息内部 Run 回查委托实现

## 时间与任务

2026-09-27；M1—M3。

## 修改文件与理由

- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:448`：请求级委托工厂仅在`message-enqueue`、`message-read`返回原有消息`authorization`及`x-runtime-run-read-authorization`。第二份值取同一请求已经签发的未绑定Thread的`read`委托；无新签发、claim或operation。SSE敏感键脱敏同时覆盖新内部头名。
- `apps/runtime-service/src/runtime_service/webapp.py:120`：`_verified_run_read_authorization`调用现有`authenticate`，要求`read` operation、相同identity/tenant/project/credential，以及空或当前Thread绑定。缺失、无效或错配在内部GET和队列操作前拒绝。`enqueue_message`与`list_messages`仅用校验后的值查询原生Run。
- `apps/platform-api/tests/test_runtime_delegation.py:109`：确认消息头取当前请求read委托，普通操作无额外头。
- `apps/platform-api/tests/test_runtime_delegation_contract.py:463`及`apps/platform-api/tests/fixtures/runtime_delegation_verifier.py:77`：跨进程自定义端点正例传入配对read委托；消息token单独访问原生资源的拒绝矩阵保持不变。API全量首轮检出该夹具仍按旧单token请求而返回401，已按新内部契约更新。
- `apps/platform-api/tests/test_runtime_gateway_event_redaction.py:75`：上游事件误带内部头时输出为`[REDACTED]`。
- `apps/runtime-service/tests/runtime/test_message_read_delegation.py:75`：真实v2 JWT配对正反例，包括未绑定read、过期、错operation/主体/租户/项目/Thread/服务账号凭据。
- `apps/runtime-service/tests/runtime/test_platform_auth.py:160`：补`message-read`对原生资源的403矩阵。
- `apps/runtime-service/tests/services/test_message_inbox_postgres.py:567`：真实PostgreSQL消息HTTP测试确认内部GET使用read委托；配对拒绝时无GET、无入队，正向入队/列表/终态对账保持通过。

## 影响与限制

原生`auth.on`白名单、Thread ACL、GraphHarbor、JWT v2格式和消息队列结构均未改。PostgreSQL HTTP测试用受控原生GET响应，证明Runtime消息入口与队列行为；它不等于已部署Platform API→Runtime→GraphHarbor真实链路。现役进程未切换本次源码，后者记为未验证。

# Platform API 实现记录

## 日期

2026-10-07

## 相关任务

- Task 3.1–3.3

## 改动文件与函数

| 文件 | 函数/位置 | 理由 |
|---|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:2126` | `cancel_thread()`、`get_stop_request():2150`、`list_stop_requests():2170`、`_stop_query()` | 公开三路由、UUID/空body/key/query限制、no-store与OpenAPI DTO |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/run_control.py` | `StopBody/StopRequest/StopReport/StopRequestList`、`StopRequest.confirmed_phase()` | 内部记录不进浏览器，类型/上限及停止证明严格校验 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:3429` | `RuntimeGatewayService.thread_stop_action()` | 沿当前Thread edit/read授权，签发精确scope，核验归属、注入本次request_id |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | upstream stop/detail/list协议 | 扩展既有端口，不另建控制层服务 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py:387` | `stop_thread()`、`get_stop_request()`、`list_stop_requests()` | 受控Runtime自定义HTTP转发，保留原key |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:193` | `create_runtime_upstream_error()`与精确安全码清单 | 存储503沿既有502规则保留stop_storage_unavailable，其余码精确匹配 |
| `apps/platform-api/src/platform_api/core/security/tokens.py:128` | `create_runtime_delegation_token()`operation校验 | 两端30项枚举一致，新增scope须绑定Thread |
| `apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py:41` | `authorize_stop_request()` | 30秒HMAC签名/正文绑定、受信内部授权与审计回调 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/run_control.py:122` | `authorize_and_audit_stop()` | 当前主体/credential/项目/执行权限/Thread edit回查，审计与再次授权区分 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/infra/sqlalchemy/run_control.py:15` | `assert_project_scope()`、`record_stop_phase():24` | 短事务与稳定事件ID，已接受动作撤权后仍可审计收敛 |
| `apps/platform-api/src/platform_api/entrypoints/http/middleware/auth_context.py` | 内部受信路径登记 | HMAC入口不接受普通浏览器身份替代签名 |
| `apps/platform-api/src/platform_api/modules/audit/http_resolution.py:623` | `_resolve_action()`的Stop分支 | HTTP requested/read映射，GET不制造confirmed |
| `apps/runtime-service/src/runtime_service/runtime/auth.py` | `_parse_scope()`、`verify_delegation_claims()` | 双端scope枚举/Thread绑定与服务账号校验 |
| `apps/runtime-service/src/runtime_service/auth/platform.py:102` | `deny_image_scope_on_server_resources()` | cancel-active hash与固定取消回执的精确原生例外，其余资源仍拒绝 |

## 关键行为变化

### 安全公开回执

之前公开面只有单Run cancel，没有持久会话停止动作查询。现在POST严格 `{}`+key返回202 `StopRequest`，GET返回detail/list；三接口分别核当前execute/edit或read/read，不用缓存授权代替。

```python
# service.py：先使用白名单 DTO，再核对不可变归属，最后补本次查询编号。
result = model.model_validate(payload).model_dump(mode="json")
for item in result.get("items", [result]):
    if item["thread_id"] != thread_id:
        raise ValueError("stop ownership mismatch")
    item["request_id"] = request_id
```

未知上游字段被剔除，非法DTO安全502；stopped/no_active_run必须execution_stopped=true、confirmed_at与report均有值。上游503存储故障此前只登记memory；新增stop码保留，但公开HTTP仍502。最初特殊透传503被既有契约拒绝，已按原映射修正，并补定向码/状态测试。

### 委托、撤权与审计

原生resource白名单之前无固定回执scope。新增thread-stop/thread-stop-read只用于内部Thread自定义HTTP；Runtime受信后台以30秒token和固定取消ID hash读取原生单一回执。取消ID/Thread/原生事件marker不匹配即拒绝，不能读Run/state或取消别的目标；普通浏览器查询仍重新核权。

之前HTTP cancel成功审计只能记录ACK。现在requested/read仍由HTTP中间件记录；Runtime持久audit_pending经HMAC写入后台accepted/stopping/confirmed/rejected/unknown。

```python
# infra/sqlalchemy/run_control.py：同 stop_id/phase 的重试只有一条审计。
event_id = uuid5(payload.stop_id, payload.phase)
if session.get(AuditLogRecord, event_id) is not None:
    return
```

停止边界尚未接受时回查当前权限；accepted以后受信清理/回执读取继续收敛，用户撤权不抹掉清理审计，也不授予新的浏览器读取权限。记录仅保存安全关联ID/phase/count，不保存JWT、工具输入或正文。

## 验证

- Stop API 8 项定向测试通过。
- 相关 API 回归 66 项通过、376 个子测试通过；1 项未修改的既有 fatal 文案断言仍失败，已按 HEAD 复现并留在 verification。
- HMAC 篡改/过期、服务账号、跨 scope、撤权和错误安全投影已覆盖。

新增 `apps/platform-api/tests/test_run_control.py` 覆盖 `test_service_ownership_and_private_projection`、`test_http_input_contract_request_id_and_no_store`、`test_stop_errors_keep_safe_codes`、`test_stop_callback_signature_window_and_body_binding`。修改委托fixture/contract与显式HTTP矩阵，同步3条路由/30项operation；跨进程Runtime校验不以skip当通过。真实ACL撤销后confirmed审计证据见[verification.md](../verification.md)。

## 影响与边界

无Platform数据库新表，复用audit_logs；新动作持久状态属于Runtime。旧单Run cancel保留，新增接口需要配套Runtime与引擎正式接入，目前blocked。没有前端修改或现役部署；Delegation仍draft，未提前毕业。

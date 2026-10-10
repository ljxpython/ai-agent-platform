# 审计标准

审计记录HTTP行为与主体，不代替Runtime执行事实。入口为[audit模块](../../src/platform_api/modules/audit/)和[审计中间件](../../src/platform_api/entrypoints/http/middleware/audit_log.py)。

## 内容与动作

`audit_logs`保存request_id、plane、action、目标类型/ID、actor_user_id/subject、tenant_id/project_id、result、method/path、status_code、duration_ms、metadata_json及created_at。

plane为control_plane/runtime_gateway/system_internal；result为success/failed/cancelled。动作由http_resolution.py解析，例如identity.session.created、runtime.run.item.created、runtime.command.submitted。解析器中的历史分支不等于接口公开，公开面以注册router为准。

新增受治理接口时更新动作、目标/项目定位与测试。使用可信actor/scope，用户治理的action override只允许代码登记的动作。

## 写入与失败

数据库启用时，中间件在响应体消费结束后写独立短事务。HTTP状态低于400记success，否则failed；异常记500/failed，取消记499/cancelled。SSE审计时长包含订阅时间，不代表模型执行时长。

数据库写入交给线程池，用取消保护完成收尾。写入失败记录 `audit_write_failed`，不覆盖原业务响应。普通HTTP中间件没有业务与审计原子提交、持久化重试或outbox，不能承诺审计绝不丢失；会话Stop的后台阶段有下述独立持久重试机制。

未配置Session时不写数据库审计；API文档、OpenAPI及favicon等路径跳过，具体范围见中间件。

## 敏感数据

仅对有Content-Length且不超过64KiB的JSON响应临时捕获以提取目标ID，不持久化整份响应或SSE正文。metadata包含query、client_ip、user_agent、目标、结果及响应大小等，额外业务metadata只保留reason与受信后台回调的有界 task/event/thread/origin_run ID。

query当前原样进入审计，禁止在URL携带token、密码或模型密钥。不得将Authorization、Cookie、原始请求体或模型凭据加入metadata。公开响应过滤不能代替日志和审计数据最小化。

## 查询与检查

平台审计读取受 `platform.audit.read` 控制，项目审计受 `project.audit.read` 和项目scope控制。cancel的成功ACK表示请求响应，不证明Run已终止，应读取Runtime状态。

复用test_audit_http_resolution.py和test_transaction_boundaries.py验证定位、线程和取消收尾；不为已退役平台Worker增加job生命周期事件。

## 会话 Stop 阶段审计（2026-10-07 用户批准）

公开POST Thread cancel记录 `runtime.thread.stop.requested`；detail/list GET记录 `runtime.thread.stop.read`。这些是HTTP请求结果，不证明引擎接受或停止，也不由GET生成confirmed。

Runtime停止控制表将accepted/stopping/stopped/no_active_run/confirmation_unavailable/rejected阶段写入 `audit_pending`，后台通过HMAC回调 `/api/runtime/internal/stop-authorization`，成功后才移除待发送项；阶段与回执同次Runtime短事务持久化，失败/重启继续重试，不是平台通用审计outbox。

平台将stopped/no_active_run映射为 `runtime.thread.stop.confirmed`，confirmation_unavailable映射为unknown，其余保留阶段名。`uuid5(stop_id, phase)`作为审计记录ID防重复；只记录可信owner、tenant/project/thread/stop、phase、target_count和request/trace关联，不存原始正文、JWT、工具参数或模型凭据。HTTP中间件的成功规则不用于证明后台confirmed。

回调30秒窗口签名绑定规范正文；authorize=true核对当前身份/服务账号credential、执行权限与Thread edit。authorize=false仅在scope核验后写已受理阶段，操作者之后撤权仍可记录收敛；该行为不授予其公开回执读取或新取消权限。真实撤权后confirmed入库、待发送项清空证据见[取消专项验证](../../../../docs/projects/20261007-agent-run-cancellation/verification.md)。正式配套/部署仍blocked。

## 后台任务 HTTP 审计（2026-10-09 用户批准）

list/detail 记录 `runtime.background_task.read`，output 记录 `runtime.background_task.logs.read`，cancel 记录 `runtime.background_task.cancel.requested`；目标为 Thread 或 background_task，plane为runtime_gateway。GET不制造执行/清理事实，cancel 202只记录HTTP受理。

两个精确 HMAC 入口记录 `runtime.background_task.delivery.checked` 与 `runtime.background_task.authorization.checked`。验证签名/源请求后绑定原主体和scope，只允许 task_id/event_id/thread_id/origin_run_id 及安全reason；没有绑定主体的未知回执查询不能伪造owner。`checked` 的HTTP成功也可能返回 unknown/blocked，不等同通知已接受或模型已执行。

本增量复用HTTP审计短事务，不新增审计outbox或承诺无丢失；原始命令、日志、签名、模型引用与控制handle全部排除。动作、脱敏与实际权限证据见[后台专项](../../../../docs/projects/20261009-agent-generic-production-capabilities/verification.md)。
